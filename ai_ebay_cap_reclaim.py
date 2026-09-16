"""
Cap reclaim -- free eBay dollar-limit headroom by ending high-value SLOW-MOVERS.

The store is bound by eBay's ~$484,882 TOTAL LISTED VALUE limit, not item count
(see the dollar-limit analysis). Every listing consumes price x qty of that cap.
High-priced items that don't sell are dead weight: the $300+ band held ~26% of
the cap for ~5% of sales, and margins are flat across price bands -- so expensive
inventory earns no premium. This ends the worst offenders so the freed cap can be
redeployed into cheaper, faster-selling items (MAX_PRICE steers new scraping there).

"MODERATE" policy (union of):
  A) price >= $150, 0 lifetime orders, age > 60d
  B) price >= $300, 0 lifetime orders, age > 30d
  C) price >= $200, 0 lifetime orders, age > 45d, < 25 views, 0 watchers

Ending = PriceYak bulk_delist (same as the OOS / blacklist sweeps). NOT
blacklisted -- these are legit products, just poor cap ROI; the MAX_PRICE scrape
ceiling keeps the expensive ones from coming back. Writes a CSV, has --dry-run.

Usage:
    python ai_ebay_cap_reclaim.py --dry-run          # show what would be ended
    python ai_ebay_cap_reclaim.py                    # end + report + push
    python ai_ebay_cap_reclaim.py --max-end 500      # cap how many per run
"""

import os
import csv
import time
import argparse
import logging
from datetime import datetime

import requests
import config

try:
    from notify import send as notify_send
except Exception:
    def notify_send(title, message, priority="default", tags=None):
        return False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
BULK_DELIST_URL = "https://www.priceyak.com/v0/account/{}/listings/bulk_delist".format(config.PY_ACCOUNT_ID)


def py_login():
    return requests.post(
        "https://www.priceyak.com/v0/account/{}/api_login".format(config.PY_ACCOUNT_ID),
        json={"api_key": config.PY_API_KEY}, timeout=30,
    ).json()["token"]


def get_active_listings(token):
    h = {"Authorization": "Bearer " + token}
    items, off = [], 0
    while True:
        d = requests.get(
            "https://www.priceyak.com/v0/account/{}/listings".format(config.PY_ACCOUNT_ID),
            headers=h, params={"count": 200, "offset": off}, timeout=120,
        ).json().get("data", [])
        if not d:
            break
        items += d
        off += 200
        if off > 20000:
            break
    return items


def bulk_delist(token, itemids):
    h = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    return requests.post(BULK_DELIST_URL, headers=h, json={"itemids": itemids, "shred": False}, timeout=120)


def should_cull(it, now):
    price = (it.get("price") or 0) / 100.0
    qty = it.get("quantity") or 0
    if qty <= 0 or price <= 0:
        return None
    orders = it.get("order_count") or 0
    if orders > 0:
        return None  # it has sold -- keep proven earners
    age_d = (now - (it.get("created_time") or now)) / 86400.0
    views = it.get("view_count") or 0
    watchers = it.get("watch_count") or 0
    if price >= 150 and age_d > 60:
        return "A: >=$150, 0 sales, >60d"
    if price >= 300 and age_d > 30:
        return "B: >=$300, 0 sales, >30d"
    if price >= 200 and age_d > 45 and views < 25 and watchers == 0:
        return "C: >=$200, 0 sales, >45d, cold"
    return None


def main():
    ap = argparse.ArgumentParser(description="Reclaim eBay $-limit cap by ending high-value slow-movers")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-end", type=int, default=1000, help="Cap listings ended per run (default 1000)")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)

    token = py_login()
    items = get_active_listings(token)
    now = time.time()
    total_cap = sum(((it.get("price") or 0) / 100.0) * (it.get("quantity") or 0) for it in items)

    cull = []
    for it in items:
        reason = should_cull(it, now)
        if reason:
            price = (it.get("price") or 0) / 100.0
            cull.append((str(it.get("itemid")), price, reason, (it.get("title") or "")[:55]))
    cull.sort(key=lambda x: -x[1])  # end priciest first (most cap per delist)
    freed = sum(p for _, p, _, _ in cull)

    log.info(f"Active: {len(items)} listings, ${total_cap:,.0f} cap used. Cull candidates: "
             f"{len(cull)} (${freed:,.0f} freed = {100*freed/total_cap if total_cap else 0:.1f}% of cap).")

    to_end = cull[: args.max_end]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = os.path.join(DATA_DIR, "cap_reclaim_{}.csv".format(ts))
    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "price", "reason", "title"])
        for iid, p, reason, title in to_end:
            w.writerow([iid, "%.2f" % p, reason, title])
    log.info("Report -> %s", report)

    print("=" * 64)
    print("CAP RECLAIM  (cap used ${:,.0f} / limit ~$484,882)".format(total_cap))
    print("  cull candidates: {}  (${:,.0f} freed, {:.1f}% of cap)".format(
        len(cull), freed, 100 * freed / total_cap if total_cap else 0))
    print("  ending this run: {}".format(len(to_end)))
    for iid, p, reason, title in to_end[:12]:
        print("    ${:7.2f}  {}  [{}]  {}".format(p, iid, reason.split(":")[0], title))
    print("=" * 64)

    if args.dry_run:
        log.info(f"[DRY] Would end {len(to_end)} listing(s), freeing ${sum(p for _, p, _, _ in to_end):,.0f} of cap.")
        return

    if not to_end:
        log.info("Nothing to cull.")
        return

    itemids = [iid for iid, _, _, _ in to_end]
    r = bulk_delist(token, itemids)
    freed_now = sum(p for _, p, _, _ in to_end)
    log.info("bulk_delist %d listing(s) -> HTTP %s: %s", len(itemids), r.status_code, r.text[:200])

    if not args.no_push:
        notify_send(
            "eBay cap reclaim: freed ${:,.0f}".format(freed_now),
            "Ended {} high-value slow-movers, freeing ${:,.0f} of the $484,882 limit "
            "for cheaper/faster items.".format(len(itemids), freed_now),
            priority="default", tags="money_with_wings",
        )


if __name__ == "__main__":
    main()
