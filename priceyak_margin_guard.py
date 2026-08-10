"""
Profitability guard for PriceYak margins.

Runs daily (airotate Step 13b, just before send_offers). Measures the REALIZED
net profit of recent sales -- using amount_paid, which already reflects any
accepted 5%-off offer -- and if sales are actually losing money, automatically
raises the slow-mover margin floor (pricer.sales_ranges) for the configured
sources, then notifies. This is the safety net for the margin settings managed
by priceyak_margins.py: if the floor is too low and discounted sales go
underwater, this ratchets it back up.

Per sale:  net = amount_paid - amazon_cost - actual_ebay_fees
  * amazon_cost      : cost_of(order)              (from pnl_month)
  * actual_ebay_fees : destination_fees (cents)    (real fees PriceYak recorded)
Refunded orders and $0-revenue reshipments are skipped (not price problems).

Trigger (money is being lost):
  * >= MIN_LOSS_SALES individual sales with net < 0 in the window, OR
  * total net over the window < 0
On trigger, raise sales_ranges[0].margin_percent by STEP_POINTS for each source
in SOURCES, capped at MAX_MARGIN_PCT, at most once per COOLDOWN_DAYS.

Usage:
    python priceyak_margin_guard.py                 # report only (dry-run)
    python priceyak_margin_guard.py --apply         # raise floor if losing money
    python priceyak_margin_guard.py --days 21 --apply
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timedelta

from pnl_month import py_login, fetch_orders_until, cost_of
from priceyak_margins import get_account, put_pricer, backup_pricer, BACKUP_DIR
import notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("margin_guard.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

STATE_FILE = "margin_guard_state.json"

# --- tunables -------------------------------------------------------------
WINDOW_DAYS = 14          # look-back for realized sales
SOURCES = ["amazon", "walmart"]   # pricer sources whose floor we ratchet
MIN_LOSS_SALES = 2        # this many money-losing sales triggers a raise
STEP_POINTS = 3.0         # raise the floor by this many percentage points
MAX_MARGIN_PCT = 30.0     # never push the floor above this
COOLDOWN_DAYS = 3         # don't raise more than once per this many days
# --------------------------------------------------------------------------


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def realized_sales(token, days):
    """Realized net profit per sale over the last `days`."""
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    orders = fetch_orders_until(token, start_ts)
    rows = []
    for o in orders:
        if (o.get("created_time") or 0) < start_ts or o.get("cancelled"):
            continue
        revenue = (o.get("amount_paid") or 0) / 100.0
        cost, src, _note = cost_of(o)
        if src == "refunded" or revenue <= 0:   # reversed sale / reshipment
            continue
        if src == "none":                        # unknown cost -> can't judge
            continue
        fees = o.get("destination_fees")
        fees = fees / 100.0 if fees else revenue * 0.13
        net = revenue - cost - fees
        rows.append({"id": o.get("id"), "revenue": revenue, "cost": cost,
                     "fees": fees, "net": net, "ts": o.get("created_time")})
    return rows


def raise_floors(token, points):
    """Raise sales_ranges[0].margin_percent by `points` for each SOURCE, capped."""
    pricer = get_account(token)["pricer"]
    backup_pricer(pricer)
    changed = []
    for name in SOURCES:
        cfg = pricer.get(name)
        if not isinstance(cfg, dict):
            continue
        sr = cfg.get("sales_ranges") or [{}]
        old = float(sr[0].get("margin_percent", 0)) * 100
        new = min(old + points, MAX_MARGIN_PCT)
        if new > old:
            sr[0]["margin_percent"] = round(new / 100.0, 4)
            cfg["sales_ranges"] = sr
            cfg["enable_sales_ranges"] = True
            changed.append((name, old, new))
    if changed:
        put_pricer(token, pricer)
    return changed


def main():
    ap = argparse.ArgumentParser(description="PriceYak profitability guard")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    ap.add_argument("--apply", action="store_true", help="Raise the floor if losing money (default: report only)")
    ap.add_argument("--notify-ok", action="store_true", help="Also push a notification when everything is healthy")
    args = ap.parse_args()

    try:
        token = py_login()
        rows = realized_sales(token, args.days)
    except Exception as e:
        log.error(f"Guard could not read PriceYak: {e}")
        notify.send("Margin guard FAILED", f"Could not read PriceYak sales: {e}", priority="high", tags="warning")
        sys.exit(1)

    n = len(rows)
    total_net = sum(r["net"] for r in rows)
    total_rev = sum(r["revenue"] for r in rows)
    losses = [r for r in rows if r["net"] < 0]
    margin_pct = (total_net / total_rev * 100) if total_rev else 0.0

    log.info(f"window {args.days}d: {n} sales, net ${total_net:.2f} on ${total_rev:.2f} "
             f"({margin_pct:.1f}%), {len(losses)} loss sales")
    for r in losses:
        log.info(f"  LOSS {r['id']}: rev ${r['revenue']:.2f} - cost ${r['cost']:.2f} "
                 f"- fees ${r['fees']:.2f} = ${r['net']:.2f}")

    losing_money = len(losses) >= MIN_LOSS_SALES or total_net < 0
    summary = (f"{n} sales / {args.days}d: net ${total_net:.2f} ({margin_pct:.1f}%), "
               f"{len(losses)} at a loss")

    if not losing_money:
        log.info("Healthy -- no action.")
        if args.notify_ok:
            notify.send("Margin guard OK", summary, tags="white_check_mark")
        return

    # We're losing money. Decide whether to raise (cooldown-gated).
    state = load_state()
    last = state.get("last_raise")
    in_cooldown = False
    if last:
        try:
            in_cooldown = datetime.now() - datetime.fromisoformat(last) < timedelta(days=COOLDOWN_DAYS)
        except Exception:
            in_cooldown = False

    if not args.apply:
        notify.send("Margin guard: LOSSES (report-only)",
                    summary + "\nRun with --apply to raise the floor.", priority="high", tags="warning")
        log.info("Losing money but --apply not set; no change.")
        return

    if in_cooldown:
        notify.send("Margin guard: still losing money",
                    summary + f"\nAlready raised within {COOLDOWN_DAYS}d; not raising again yet.",
                    priority="high", tags="warning")
        log.info("In cooldown; not raising again.")
        return

    changed = raise_floors(token, STEP_POINTS)
    if changed:
        detail = "; ".join(f"{name} {old:.0f}%->{new:.0f}%" for name, old, new in changed)
        state["last_raise"] = datetime.now().isoformat()
        state["last_summary"] = summary
        save_state(state)
        log.info(f"Raised floors: {detail}")
        notify.send("Margin guard RAISED prices",
                    summary + f"\nRaised slow-mover floor: {detail}", priority="high", tags="chart_with_upwards_trend")
    else:
        notify.send("Margin guard: at cap",
                    summary + f"\nFloor already at {MAX_MARGIN_PCT:.0f}% cap; not raising. Review pricing.",
                    priority="high", tags="warning")
        log.info("Floors already at cap; no change.")


if __name__ == "__main__":
    main()
