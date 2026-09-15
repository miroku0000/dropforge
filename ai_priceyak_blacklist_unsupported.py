"""
Blacklist the ASINs behind "item_not_supported" order failures.

When PriceYak fails an order with failure_reason == "item_not_supported",
Amazon will NEVER fulfill that product through the managed account -- retrying
is useless and the listing will keep taking orders it can't fill. This script
closes that loop:

  1. Scan recent PriceYak orders for state=="failure" & "item_not_supported".
  2. Add each item's Amazon ASIN to the PriceYak listing blacklist (so it can't
     relist) -- reusing priceyakblacklistadd's login/get/post helpers.
  3. Sync those ASINs into data/blacklist.txt (UPPERCASE) so the Amazon scrapers
     stop re-scraping them.
  4. End the live eBay listing (PriceYak bulk_delist) so it stops selling now,
     unless --no-delist.

Blacklisting is idempotent (case-insensitive de-dupe -- PriceYak lowercases
product_ids server-side). Safe to run repeatedly / daily from airotate.

Usage:
    python ai_priceyak_blacklist_unsupported.py                 # blacklist + delist + push
    python ai_priceyak_blacklist_unsupported.py --dry-run       # show, change nothing
    python ai_priceyak_blacklist_unsupported.py --scan 1000     # scan more history
    python ai_priceyak_blacklist_unsupported.py --no-delist     # blacklist only, leave listing live
    python ai_priceyak_blacklist_unsupported.py --no-push       # no ntfy/Telegram alert
"""

import os
import re
import sys
import argparse
import logging

import requests

from priceyakblacklistadd import (
    ACCOUNT_ID,
    API_KEY,
    login,
    get_blacklist,
    post_blacklist,
)
from notify import send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

TARGET_REASON = "item_not_supported"
SCRAPE_BLACKLIST_FILE = os.path.join("..", "data", "blacklist.txt")  # scrapers' filter (UPPERCASE ASINs)
BULK_DELIST_URL = "https://www.priceyak.com/v0/account/{}/listings/bulk_delist".format(ACCOUNT_ID)
ASIN_RE = re.compile(r"^[A-Za-z0-9]{10}$")


def fetch_recent_orders(token, scan):
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    orders, offset = [], 0
    while offset < scan:
        r = requests.get(
            "https://www.priceyak.com/v0/account/{}/orders".format(ACCOUNT_ID),
            headers=headers, params={"count": 100, "offset": offset}, timeout=60,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        orders.extend(data)
        offset += len(data)
        if not data:
            break
    return orders[:scan]


def _asin_and_itemid(order):
    """Pull the Amazon ASIN and eBay item id out of a PriceYak order's first item."""
    items = order.get("items") or []
    if not items:
        return None, None
    it = items[0]
    lst = it.get("listing") or {}
    prod = lst.get("product") or {}
    asin = (it.get("product_id") or lst.get("seller_sku") or prod.get("product_id") or "").strip()
    itemid = lst.get("itemid")
    return (asin or None), (str(itemid) if itemid else None)


def bulk_delist(token, itemids):
    h = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    return requests.post(BULK_DELIST_URL, headers=h, json={"itemids": itemids, "shred": False}, timeout=120)


def sync_asins_to_scrape_filter(asins, dry):
    """Merge blacklist ASINs (UPPERCASE) into data/blacklist.txt for the scrapers."""
    asin_up = sorted({a.upper() for a in asins if ASIN_RE.match(a)})
    existing = set()
    if os.path.exists(SCRAPE_BLACKLIST_FILE):
        with open(SCRAPE_BLACKLIST_FILE, "r", encoding="utf-8") as f:
            existing = {ln.strip().upper() for ln in f if ln.strip()}
    new = [a for a in asin_up if a not in existing]
    log.info("Scrape filter: %d new ASIN(s) to add (file has %d).", len(new), len(existing))
    if new and not dry:
        merged = sorted(existing | set(asin_up))
        with open(SCRAPE_BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(merged) + "\n")
        log.info("  -> wrote %d ASIN(s) to %s", len(merged), SCRAPE_BLACKLIST_FILE)
    return new


def main():
    ap = argparse.ArgumentParser(description="Blacklist ASINs from item_not_supported order failures")
    ap.add_argument("--scan", type=int, default=500, help="Recent orders to scan (default 500)")
    ap.add_argument("--no-delist", action="store_true", help="Blacklist only; leave the eBay listing live")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without doing it")
    ap.add_argument("--no-push", action="store_true", help="Suppress the ntfy/Telegram alert")
    args = ap.parse_args()

    token = login(ACCOUNT_ID, API_KEY)
    orders = fetch_recent_orders(token, args.scan)
    log.info("Scanned %d recent order(s).", len(orders))

    # Collect the offending orders, de-duped by ASIN.
    hits = {}  # asin(lower) -> {"asin", "itemid", "buyer", "ebay_order"}
    for o in orders:
        if o.get("state") != "failure" or o.get("failure_reason") != TARGET_REASON:
            continue
        asin, itemid = _asin_and_itemid(o)
        if not asin:
            log.warning("Order %s is item_not_supported but has no ASIN; skipping.", o.get("id"))
            continue
        key = asin.lower()
        rec = hits.setdefault(key, {"asin": asin, "itemid": itemid,
                                    "buyer": o.get("buyer_username", ""),
                                    "ebay_order": o.get("destination_order_id", "")})
        if itemid and not rec.get("itemid"):
            rec["itemid"] = itemid

    if not hits:
        log.info("No %s failures in the last %d orders. Nothing to do.", TARGET_REASON, len(orders))
        return

    print("=" * 64)
    print("ITEM_NOT_SUPPORTED -> BLACKLIST  (scanned {})".format(len(orders)))
    for rec in hits.values():
        print("  {}  itemid={}  buyer={}  ebay_order={}".format(
            rec["asin"], rec.get("itemid"), rec["buyer"], rec["ebay_order"]))
    print("=" * 64)

    # 1) Add ASINs to the PriceYak blacklist (case-insensitive de-dupe).
    doc = get_blacklist(token)
    have = set(x.lower() for x in doc["product_id"])
    to_add = [rec["asin"] for k, rec in hits.items() if k not in have]
    if not to_add:
        log.info("All %d ASIN(s) already blacklisted.", len(hits))
    elif args.dry_run:
        log.info("[DRY] Would blacklist %d new ASIN(s): %s", len(to_add), ", ".join(to_add))
    else:
        doc["product_id"] = doc["product_id"] + to_add
        pr = post_blacklist(token, doc)
        if pr.ok:
            log.info("Blacklisted %d new ASIN(s); product_id count now %d.",
                     len(to_add), len(doc["product_id"]))
        else:
            log.error("Blacklist POST failed (%s): %s", pr.status_code, pr.text[:200])
            sys.exit(1)

    # 2) Keep the scrape filter in sync.
    sync_asins_to_scrape_filter([rec["asin"] for rec in hits.values()], args.dry_run)

    # 3) End the live listings so they stop selling now.
    itemids = sorted({rec["itemid"] for rec in hits.values() if rec.get("itemid")})
    if itemids and not args.no_delist:
        if args.dry_run:
            log.info("[DRY] Would bulk_delist %d listing(s): %s", len(itemids), ", ".join(itemids))
        else:
            r = bulk_delist(token, itemids)
            log.info("bulk_delist %d listing(s) -> HTTP %s: %s", len(itemids), r.status_code, r.text[:200])

    # 4) Push an alert.
    if args.no_push or args.dry_run:
        return
    lines = ["Blacklisted {} ASIN(s) from '{}' order failures:".format(len(hits), TARGET_REASON)]
    for rec in hits.values():
        lines.append("  {} (itemid {}, order {})".format(rec["asin"], rec.get("itemid"), rec["ebay_order"]))
    if itemids and not args.no_delist:
        lines.append("Ended {} live listing(s).".format(len(itemids)))
    send("PriceYak: blacklisted unsupported items", "\n".join(lines), priority="default", tags="no_entry")


if __name__ == "__main__":
    main()
