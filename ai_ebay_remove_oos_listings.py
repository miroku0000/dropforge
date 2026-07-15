"""
Remove eBay listings that have been out of stock for too long, via PriceYak.

Background
----------
These listings are dropshipped from Amazon through PriceYak. When the Amazon
source goes out of stock, PriceYak sets the eBay quantity to 0 but leaves the
listing up (it keeps re-listing on the 30-day GTC cycle), hoping the source
restocks. Items that have been dead for weeks just drag on store metrics and
count against listing limits, so we end them.

Signal (from PriceYak GET /v0/account/{id}/listings)
----------------------------------------------------
    quantity        == 0        -> currently out of stock
    oos_time        (unix ts)   -> when it went out of stock
    force_oos_until (unix ts)   -> a temporary manual OOS hold (respect it)
    active          == True     -> still a live listing
    itemid                      -> eBay item id
    product.product_id          -> Amazon ASIN (for the report)

days_out_of_stock = (now - oos_time) / 86400. We delist anything OOS >= --days.

We do NOT blacklist these ASINs -- out of stock is not a policy violation and
the source may restock later. We only end the currently-dead eBay listing.
(Contrast with the Issue Resolution / blacklist sweep flows, which DO blacklist.)

Removal reuses the same PriceYak `listings/bulk_delist` endpoint that
priceyakbulkdelete.py uses.

Usage
-----
    python ai_ebay_remove_oos_listings.py [--days 14] [--max 200] [--dry-run]

    --days N     End listings out of stock for >= N days (default 14).
    --max  N     Safety cap: end at most N listings this run, longest-OOS
                 first (default 200). Extra qualifiers are logged, not ended.
    --dry-run    Report what would be ended; make no changes.
"""

import os
import csv
import sys
import time
import argparse
import logging
from datetime import datetime

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# Same store / credentials as priceyakbulkdelete.py
import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")

PAGE_SIZE = 200
DELIST_CHUNK = 200


def py_login():
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
        json={"api_key": PY_API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def fetch_active_listings(token):
    """Page through every ACTIVE PriceYak listing (include_inactive=false)."""
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    rows = []
    offset = 0
    while True:
        url = (
            f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings"
            f"?count={PAGE_SIZE}&offset={offset}"
            f"&include_inactive=false&accurate_count=true"
        )
        r = requests.get(url, headers=headers, timeout=120)
        r.raise_for_status()
        body = r.json()
        data = body.get("data", [])
        rows.extend(data)
        offset += len(data)
        total = body.get("total_count", 0)
        if not data or offset >= total:
            break
    log.info(f"Fetched {len(rows)} active listing(s) from PriceYak.")
    return rows


def bulk_delist(token, itemids):
    """End eBay listings via PriceYak bulk_delist (same endpoint as priceyakbulkdelete.py)."""
    url = f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings/bulk_delist"
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.priceyak.com",
        "Authorization": "Bearer " + token,
    }
    ok = 0
    for i in range(0, len(itemids), DELIST_CHUNK):
        chunk = itemids[i : i + DELIST_CHUNK]
        r = requests.post(url, headers=headers, json={"itemids": chunk, "shred": False}, timeout=120)
        log.info(f"  bulk_delist {len(chunk)} item(s) -> HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            ok += len(chunk)
    return ok


def select_oos(rows, days, now):
    """Return [(listing, days_oos)] for listings OOS >= `days`, longest first."""
    out = []
    for x in rows:
        if not x.get("active"):
            continue
        if x.get("quantity", 0) != 0:
            continue  # in stock
        oos = x.get("oos_time")
        if not oos:
            continue  # OOS but no timestamp yet -> can't age it, skip (conservative)
        fou = x.get("force_oos_until")
        if fou and fou > now:
            continue  # temporary manual hold -> leave it
        d = (now - oos) / 86400.0
        if d >= days:
            out.append((x, d))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def write_report(selected, ts):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"oos_removed_{ts}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ebay_item_id", "amazon_asin", "days_out_of_stock", "oos_date", "title"])
        for x, d in selected:
            asin = (x.get("product") or {}).get("product_id") or x.get("seller_sku") or ""
            oos_date = datetime.fromtimestamp(x["oos_time"]).strftime("%Y-%m-%d")
            w.writerow([x.get("itemid", ""), asin, f"{d:.1f}", oos_date, x.get("title", "")])
    return path


def main():
    ap = argparse.ArgumentParser(description="End eBay listings out of stock for too long (via PriceYak).")
    ap.add_argument("--days", type=int, default=14, help="End listings OOS for >= this many days (default 14).")
    ap.add_argument("--max", type=int, default=200, help="End at most this many listings this run (default 200).")
    ap.add_argument("--dry-run", action="store_true", help="Report only; make no changes.")
    args = ap.parse_args()

    now = time.time()
    token = py_login()
    rows = fetch_active_listings(token)

    oos_now = [x for x in rows if x.get("quantity", 0) == 0]
    selected = select_oos(rows, args.days, now)
    log.info(
        f"{len(oos_now)} listing(s) currently out of stock; "
        f"{len(selected)} have been OOS for >= {args.days} day(s)."
    )

    if not selected:
        log.info("Nothing to remove. Exiting.")
        return

    # Safety cap: longest-OOS first; log anything we hold back.
    capped = selected[: args.max]
    if len(selected) > args.max:
        log.warning(
            f"{len(selected)} listings qualify but --max={args.max}; ending the "
            f"{args.max} longest-OOS this run, leaving {len(selected) - args.max} for next run."
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = write_report(capped, ts)
    log.info(f"Wrote report -> {report}")

    for x, d in capped[:15]:
        asin = (x.get("product") or {}).get("product_id") or x.get("seller_sku") or "?"
        log.info(f"  {x.get('itemid',''):<14} {int(d):>4}d  {asin:<12} {x.get('title','')[:45]}")
    if len(capped) > 15:
        log.info(f"  ... and {len(capped) - 15} more (see report).")

    itemids = [x.get("itemid") for x, _ in capped if x.get("itemid")]

    if args.dry_run:
        log.info(f"[DRY RUN] Would end {len(itemids)} listing(s). No changes made.")
        return

    log.info(f"Ending {len(itemids)} out-of-stock listing(s) via PriceYak bulk_delist...")
    ended = bulk_delist(token, itemids)
    log.info(f"Done. Requested {len(itemids)}, bulk_delist accepted {ended}.")


if __name__ == "__main__":
    main()
