"""
Crawlbase monthly cost, derived from the Account API.

GET https://api.crawlbase.com/account?token=...&product=crawling-api returns
`currentMonth.totalSuccess` (request count) and `totalDue` ($ so far). We charge
each month at an average **cost per 1000 requests**:  cost = requests/1000 * rate.

The rate is NOT totalDue/totalSuccess of a single snapshot -- early in a month
that's inflated by fixed/rounding overhead (e.g. 3.80/842 = $4.51/1000). The true
marginal rate (~$2.76/1000) is the DELTA between two same-month snapshots:
    rate = (due_now - due_earlier) / (success_now - success_earlier) * 1000
because the fixed overhead cancels. We accumulate snapshots and aggregate; until
there's enough delta we use the seeded default (2.76).

API is rate-limited 1 req / 5 min -> response is cached. The API only exposes the
CURRENT month, so each run snapshots it; once a month rolls over its last count is
final. Historical months (no API data) use manual_cost.

crawlbase_costs.json:
    {"rate_per_1000": 2.76,
     "requests":  {"YYYY-MM": <latest success count>},
     "snapshots": {"YYYY-MM": {"first": [succ, due], "last": [succ, due]}},
     "manual_cost": {"YYYY-MM": <dollars>}}

    python crawlbase_cost.py     # record current month + print costs
"""

import os
import json
import time
import datetime

import requests
from zoneinfo import ZoneInfo

PAC = ZoneInfo("America/Los_Angeles")
CREDS_FILE = "crawlbase_creds.txt"
CACHE_FILE = ".crawlbase_account_cache.json"
COSTS_FILE = "crawlbase_costs.json"
PRODUCT = "crawling-api"
CACHE_TTL = 320            # > 5 min rate limit
DEFAULT_RATE = 2.76        # $/1000 requests (your known rate; refined from deltas)
MIN_DELTA_SUCCESS = 300    # need this much request delta to trust a marginal rate
RATE_BOUNDS = (1.0, 5.0)   # sanity clamp on any computed rate


def _token():
    with open(CREDS_FILE) as f:
        for line in f:
            if line.strip():
                return line.strip()
    raise RuntimeError("no token in " + CREDS_FILE)


def fetch_account(product=PRODUCT):
    """Account API response, cached to respect the 1-req/5-min limit."""
    if os.path.exists(CACHE_FILE):
        try:
            c = json.load(open(CACHE_FILE))
            if c.get("product") == product and time.time() - c.get("ts", 0) < CACHE_TTL:
                return c["data"]
        except Exception:
            pass
    r = requests.get("https://api.crawlbase.com/account",
                     params={"token": _token(), "product": product}, timeout=30)
    r.raise_for_status()
    d = r.json()
    json.dump({"ts": time.time(), "product": product, "data": d}, open(CACHE_FILE, "w"))
    return d


def load():
    d = json.load(open(COSTS_FILE)) if os.path.exists(COSTS_FILE) else {}
    d.setdefault("rate_per_1000", DEFAULT_RATE)
    d.setdefault("requests", {})
    d.setdefault("snapshots", {})
    d.setdefault("manual_cost", {})
    return d


def _marginal_rate(snapshots):
    """Aggregate marginal $/1000 across months with enough request delta."""
    num = den = 0.0
    for s in snapshots.values():
        f, l = s.get("first"), s.get("last")
        if f and l and (l[0] - f[0]) >= MIN_DELTA_SUCCESS:
            num += (l[1] - f[1])
            den += (l[0] - f[0])
    if den <= 0:
        return None
    r = num / den * 1000
    return r if RATE_BOUNDS[0] <= r <= RATE_BOUNDS[1] else None


def month_cost(data, month):
    """Cost for YYYY-MM: manual override if present, else requests/1000 * rate."""
    if month in data["manual_cost"]:
        return round(float(data["manual_cost"][month]), 2)
    req = data["requests"].get(month)
    rate = data.get("rate_per_1000") or DEFAULT_RATE
    return None if req is None else round(req / 1000.0 * rate, 2)


def record_current(product=PRODUCT):
    """Snapshot the current month + refine the marginal rate. Never raises."""
    data = load()
    try:
        cm = (fetch_account(product) or {}).get("currentMonth") or {}
        success = int(cm.get("totalSuccess") or 0)
        due = float(cm.get("totalDue") or 0)
        now = datetime.datetime.now(PAC)
        key = f"{now.year}-{now.month:02d}"
        data["requests"][key] = success
        snap = data["snapshots"].setdefault(key, {"first": [success, due]})
        snap["last"] = [success, due]
        refined = _marginal_rate(data["snapshots"])
        if refined:
            data["rate_per_1000"] = round(refined, 4)
        json.dump(data, open(COSTS_FILE, "w"), indent=2, sort_keys=True)
    except Exception as e:
        print(f"crawlbase_cost: could not record current month ({e})")
    return data


if __name__ == "__main__":
    data = record_current()
    print(f"rate per 1000 requests: ${data.get('rate_per_1000')}")
    print("monthly cost:")
    for m in sorted(set(data["requests"]) | set(data["manual_cost"])):
        print(f"  {m}: ${month_cost(data, m)}  (requests={data['requests'].get(m, '-')})")
