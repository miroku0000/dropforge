"""
Listing controller: check where we are vs. our store target and eBay's monthly
limit, then tune the listing knobs (listing_config.bat) for the next airotate run
-- and delete back under if we overshot. Push a digest via notify.py.

Run order:
  * airotate (morning) calls  `python check_limits.py --snapshot`  at the start
    to record the active-listing count, so we can measure net growth.
  * a scheduled task ~6h later runs  `python check_limits.py`  to assess and tune.

Knobs (listing_config.bat), consumed by airotate:
  MAX_URLS      scrape subset per run (main throttle on new listings)
  RELIST_MAX    proven sellers relisted per run
  MAX_LISTINGS  target store size (your cap; never exceed)
  DELETE_MAX    low performers culled per run

Constraint: never exceed MAX_LISTINGS; if over, delete down to it. Also throttle
if eBay's monthly headroom (items / $) runs low.
"""

import os
import re
import sys
import json
import subprocess
import argparse
import logging
from datetime import datetime

import requests
from refresh_transactions import PY_ACCOUNT_ID, PY_API_KEY
from notify import send

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

CONFIG = "listing_config.bat"
STATE = "listing_state.json"
KNOBS = ("PLAN_LIMIT", "MAX_LISTINGS", "MAX_URLS", "RELIST_MAX", "DELETE_MAX", "MIN_PRICE")
PLAN_BUFFER = 20   # keep the target this far under the PriceYak plan ceiling
URLS_MIN, URLS_MAX = 200, 3000
EBAY_QTY_FLOOR, EBAY_AMT_FLOOR = 800, 5000   # throttle below these monthly remainders


def parse_config():
    cfg = {}
    with open(CONFIG) as f:
        for line in f:
            m = re.match(r"\s*set\s+(\w+)=(.+?)\s*$", line, re.I)
            if m:
                try:
                    cfg[m.group(1).upper()] = int(m.group(2))
                except ValueError:
                    cfg[m.group(1).upper()] = m.group(2)
    return cfg


def write_config(cfg):
    lines = ["@echo off",
             "REM Tunable listing knobs -- auto-adjusted by check_limits.py based on headroom.",
             "REM Edit MAX_LISTINGS to set your target store size; the rest self-tune."]
    lines += [f"set {k}={cfg[k]}" for k in KNOBS]
    with open(CONFIG, "w") as f:
        f.write("\n".join(lines) + "\n")


def get_ebay_headroom(timeout=35):
    """eBay monthly headroom (items, $) via ebay_limits.py in a SUBPROCESS so a
    slow/hanging OAuth refresh can't block this controller. Returns (None, None)
    on failure -- eBay isn't the binding constraint (the PriceYak plan is)."""
    try:
        out = subprocess.run([sys.executable, "ebay_limits.py"],
                             capture_output=True, text=True, timeout=timeout)
        m = re.search(r"([\d]+) items, \$([\d,.]+)", out.stdout)
        if m:
            return int(m.group(1)), float(m.group(2).replace(",", ""))
        log.warning("eBay headroom unavailable (no parse): " + (out.stdout or out.stderr)[:80])
    except Exception as e:
        log.warning(f"eBay headroom unavailable ({str(e)[:50]})")
    return None, None


def active_count():
    tok = requests.post(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
                        json={"api_key": PY_API_KEY}, timeout=30).json()["token"]
    r = requests.get(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings"
                     "?count=1&include_inactive=false&accurate_count=true",
                     headers={"Authorization": "Bearer " + tok, "Accept": "*/*"}, timeout=60).json()
    return r.get("total_count", 0)


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=2)


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def main():
    ap = argparse.ArgumentParser(description="Listing limit controller")
    ap.add_argument("--snapshot", action="store_true", help="Record current active count (call at airotate start)")
    ap.add_argument("--dry-run", action="store_true", help="Compute + report, but don't write config or delete")
    args = ap.parse_args()

    active = active_count()
    state = load_state()
    now = datetime.now().isoformat(timespec="minutes")

    if args.snapshot:
        state["airotate"] = {"count": active, "time": now}
        save_state(state)
        log.info(f"snapshot: {active} active listings at {now}")
        return

    cfg = parse_config()
    qty_rem, amt_rem = get_ebay_headroom()
    target = cfg["MAX_LISTINGS"]
    gap = target - active
    am = state.get("airotate", {})
    net = (active - am["count"]) if am.get("count") is not None else None

    new = dict(cfg)
    actions = []

    if active > target:                                    # overshot -> delete back under
        over = active - target
        actions.append(f"OVER target by {over} -> deleting down to {target}")
        if not args.dry_run:
            subprocess.run([sys.executable, "ai_ebay_enforce_max_listings.py", str(target)])
        new["MAX_URLS"] = _clamp(cfg["MAX_URLS"] * 0.7, URLS_MIN, URLS_MAX)
    elif qty_rem is not None and (qty_rem < EBAY_QTY_FLOOR or amt_rem < EBAY_AMT_FLOOR):
        new["MAX_URLS"] = _clamp(cfg["MAX_URLS"] * 0.5, URLS_MIN, URLS_MAX)
        actions.append("eBay monthly headroom low -> throttling scrape")
    else:                                                  # under target -> scale to the gap
        if gap > 600:
            new["MAX_URLS"] = _clamp(cfg["MAX_URLS"] * 1.4, URLS_MIN, URLS_MAX)
            actions.append(f"gap {gap} large -> more scraping")
        elif gap < 150:
            new["MAX_URLS"] = _clamp(cfg["MAX_URLS"] * 0.7, URLS_MIN, URLS_MAX)
            actions.append(f"gap {gap} small -> easing scraping")
        # pinned at target with eBay room -> grow target, but never past the
        # PriceYak plan ceiling (PLAN_LIMIT - buffer).
        ceiling = cfg.get("PLAN_LIMIT", target) - PLAN_BUFFER
        if active >= target * 0.98 and (qty_rem is None or qty_rem > 2000) and target < ceiling:
            new["MAX_LISTINGS"] = min(target + 300, ceiling)
            actions.append(f"store pinned; raising target to {new['MAX_LISTINGS']} (plan ceiling {ceiling})")

    if not actions:
        actions.append("steady -- no change")

    state["check"] = {"count": active, "time": now, "net_since_airotate": net}
    if not args.dry_run:
        write_config(new)
        save_state(state)

    netstr = f"{net:+d}" if net is not None else "n/a"
    ebay_line = (f"eBay monthly headroom: {qty_rem} items, ${amt_rem:,.0f}"
                 if qty_rem is not None else "eBay monthly headroom: unavailable")
    lines = [
        f"active {active} / target {target} (gap {gap}); net since airotate {netstr}",
        ebay_line,
        "actions: " + "; ".join(actions),
        f"next-run knobs: MAX_URLS {cfg['MAX_URLS']}->{new['MAX_URLS']}, "
        f"target {cfg['MAX_LISTINGS']}->{new['MAX_LISTINGS']}",
    ]
    body = "\n".join(lines)
    print("=" * 60 + "\n" + body + "\n" + "=" * 60)
    prio = "high" if active > target else "default"
    if not args.dry_run:
        send("listing check", body, priority=prio, tags="bar_chart")


if __name__ == "__main__":
    main()
