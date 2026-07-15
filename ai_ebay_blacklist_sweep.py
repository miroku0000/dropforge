"""
Pre-emptive blacklist sweep -- get ahead of the eBay Issue Resolution Center.

Scans active PriceYak/eBay listings against the PriceYak blacklist and acts:
  - ASIN match  (listing's ASIN/seller_sku is on the blacklist) -> END
  - Brand match (listing's brand exactly matches a blacklisted brand) -> END
  - Keyword match (a blacklisted keyword appears as a whole word in the title)
        -> REPORT ONLY (keyword matching is false-positive prone)

Ending = PriceYak bulk_delist + add the ASIN to the blacklist so it can't relist.

Also SYNCS the blacklist's ASINs into data/blacklist.txt (the Amazon scrape
filter, which stores UPPERCASE ASINs) so blacklisted items aren't re-scraped.

Why a sweep when PriceYak already blocks blacklisted items at list time? Because
the blacklist grows over time (e.g. from the Issue Resolution Center flow), and
listings created BEFORE a brand/ASIN was blacklisted stay live until something
removes them -- this is that something. Runs daily from airotate.bat.

Usage: python ai_ebay_blacklist_sweep.py [--dry-run]
"""

import os
import re
import sys
import csv
import requests
from datetime import datetime

from priceyakblacklistadd import (
    ACCOUNT_ID,
    API_KEY,
    login,
    get_blacklist,
    post_blacklist,
)

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
SCRAPE_BLACKLIST_FILE = os.path.join("..", "data", "blacklist.txt")  # used by scrapers
BULK_DELIST_URL = (
    "https://www.priceyak.com/v0/account/{}/listings/bulk_delist".format(ACCOUNT_ID)
)
ASIN_RE = re.compile(r"^[A-Za-z0-9]{10}$")  # ASIN / 10-char ISBN form


def get_active_listings(token):
    h = {"Authorization": "Bearer " + token}
    items, off = [], 0
    while True:
        d = requests.get(
            "https://www.priceyak.com/v0/account/{}/listings?count=200&offset={}".format(
                ACCOUNT_ID, off
            ),
            headers=h,
            timeout=120,
        ).json().get("data", [])
        if not d:
            break
        items += d
        off += 200
        if off > 5000:
            break
    return items


def bulk_delist(token, itemids):
    h = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    r = requests.post(BULK_DELIST_URL, headers=h, json={"itemids": itemids, "shred": False})
    return r


def sync_asins_to_scrape_filter(asins, dry):
    """Merge blacklist ASINs (UPPERCASE) into data/blacklist.txt for the scrapers."""
    asin_up = sorted({a.upper() for a in asins if ASIN_RE.match(a)})
    existing = set()
    if os.path.exists(SCRAPE_BLACKLIST_FILE):
        with open(SCRAPE_BLACKLIST_FILE, "r") as f:
            existing = {ln.strip().upper() for ln in f if ln.strip()}
    new = [a for a in asin_up if a not in existing]
    print("Scrape filter: {} blacklist ASIN(s); {} new to add (file has {}).".format(
        len(asin_up), len(new), len(existing)))
    if new and not dry:
        merged = sorted(existing | set(asin_up))
        with open(SCRAPE_BLACKLIST_FILE, "w") as f:
            f.write("\n".join(merged) + "\n")
        print("  -> wrote {} ASIN(s) to {}".format(len(merged), SCRAPE_BLACKLIST_FILE))


def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(DATA_DIR, exist_ok=True)

    token = login(ACCOUNT_ID, API_KEY)
    bl = get_blacklist(token)
    brands = set(b.strip().lower() for b in bl["brand"] if b.strip())
    asins_bl = set(a.strip().lower() for a in bl["product_id"] if a.strip())
    kw_res = [
        (k.strip().lower(), re.compile(r"\b" + re.escape(k.strip().lower()) + r"\b"))
        for k in bl["keyword"]
        if k.strip()
    ]
    print("Blacklist: {} brands, {} keywords, {} ASINs".format(
        len(brands), len(kw_res), len(asins_bl)))

    listings = get_active_listings(token)
    print("Active listings scanned: {}".format(len(listings)))

    end = {}      # itemid -> (reason, asin, title)
    keyword = {}  # itemid -> (kw, title)
    for it in listings:
        iid = str(it.get("itemid"))
        brand = (it.get("brand") or "").strip().lower()
        asin = (
            ((it.get("product") or {}).get("product_id") or it.get("seller_sku") or "")
            .strip().lower()
        )
        title = (it.get("title") or "")
        tl = title.lower()
        if asin and asin in asins_bl:
            end[iid] = ("asin:" + asin, asin, title)
        elif brand and brand in brands:
            end[iid] = ("brand:" + brand, asin, title)
        else:
            for k, rx in kw_res:
                if rx.search(tl):
                    keyword[iid] = (k, title)
                    break

    print("\n--- RESULTS ---")
    print("END (ASIN/brand match): {}".format(len(end)))
    for iid, (reason, asin, title) in end.items():
        print("  END  {}  [{}]  {}".format(iid, reason, title[:50]))
    print("REPORT (keyword match, not ended): {}".format(len(keyword)))
    for iid, (k, title) in keyword.items():
        print("  KW?  {}  [{}]  {}".format(iid, k, title[:50]))

    # CSV report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = os.path.join(DATA_DIR, "blacklist_sweep_{}.csv".format(ts))
    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["action", "ebay_item_id", "reason", "asin", "title"])
        for iid, (reason, asin, title) in end.items():
            w.writerow(["END", iid, reason, asin, title])
        for iid, (k, title) in keyword.items():
            w.writerow(["REPORT_KEYWORD", iid, "keyword:" + k, "", title])
    print("\nReport -> {}".format(report))

    # Keep the scrape filter in sync regardless.
    sync_asins_to_scrape_filter(asins_bl, dry)

    if not end:
        print("\nNothing to end. Done.")
        return

    if dry:
        print("\n[DRY RUN] Would end {} listing(s) and blacklist their ASINs.".format(len(end)))
        return

    # 1) Delist
    itemids = list(end.keys())
    r = bulk_delist(token, itemids)
    print("\nbulk_delist status {}: {}".format(r.status_code, r.text[:200]))

    # 2) Add their ASINs to the blacklist so they can't relist (dedupe case-insensitively).
    end_asins = {a for (_, a, _) in end.values() if a}
    if end_asins:
        doc = get_blacklist(token)
        have = set(x.lower() for x in doc["product_id"])
        add = [a for a in end_asins if a not in have]
        if add:
            doc["product_id"] = doc["product_id"] + add
            pr = post_blacklist(token, doc)
            print("blacklist add {} ASIN(s) -> status {}".format(len(add), pr.status_code))

    print("\nEnded {} listing(s).".format(len(end)))


if __name__ == "__main__":
    main()
