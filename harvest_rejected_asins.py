"""
Harvest PERMANENTLY-rejected ASINs from PriceYak listing-request history into
data/rejected_asins.txt, so listing_prefilter stops re-submitting them next cycle.

PriceYak GET /v0/account/{id}/requests -> each attempt has state, failure_reason,
product.product_id. We record only reasons that will NEVER succeed on retry:

    veromatic, veromatic_aplus   (VeRO-protected brand)
    banned_brand, banned_keyword, banned_product_id   (PriceYak blacklist hits)
    max_source_price             (Amazon price above our ceiling)

Deliberately NOT harvested:
  - no_offers, product_unavailable, timeout, pdata_*  -> transient / restockable;
    these can succeed later, so we don't want to skip them forever.
  - duplicate_req / duplicate_listing -> handled LIVE by listing_prefilter's
    active-listing dedup (an ended listing should become submittable again, so a
    stale persisted "duplicate" would be wrong).

Merge is idempotent (UPPERCASE, de-duped, sorted). Reuses the request-fetch shape
from ai_priceyak_listing_failures.

Usage:
    python harvest_rejected_asins.py                 # scan history, merge, write
    python harvest_rejected_asins.py --scan 5000     # page deeper for a backfill
    python harvest_rejected_asins.py --hours 168     # only the last N hours
    python harvest_rejected_asins.py --dry-run
"""

import os
import sys
import time
import argparse
import logging
from collections import Counter

import requests

from ai_relist_proven_sellers import priceyak_login, PRICEYAK_ACCOUNT_ID
from listing_prefilter import REJECTED_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

PERMANENT = {"veromatic", "veromatic_aplus", "banned_brand", "banned_keyword",
             "banned_product_id", "max_source_price"}


def fetch_requests(token, hours, scan_cap):
    """Page only FAILED requests (server-side state=failure), so a large backlog
    of pending 'created' rows doesn't bury the failures we care about."""
    h = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    cutoff = (time.time() - hours * 3600) if hours else 0
    out, off = [], 0
    while off < scan_cap:
        d = requests.get(
            "https://www.priceyak.com/v0/account/{}/requests".format(PRICEYAK_ACCOUNT_ID),
            headers=h, params={"count": 100, "offset": off, "state": "failure"}, timeout=90,
        ).json().get("data", [])
        if not d:
            break
        out.extend(d)
        off += len(d)
        if hours and min((r.get("created_time") or 9e18) for r in d) < cutoff:
            break
    if hours:
        out = [r for r in out if (r.get("created_time") or 0) >= cutoff]
    return out


def asin_of(r):
    return (r.get("product") or {}).get("product_id") or r.get("destination_product_id")


def main():
    ap = argparse.ArgumentParser(description="Harvest permanently-rejected ASINs into rejected_asins.txt")
    ap.add_argument("--scan", type=int, default=3000, help="Max request rows to page through (default 3000)")
    ap.add_argument("--hours", type=float, default=0, help="Only consider attempts newer than N hours (0 = all scanned)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be added without writing")
    args = ap.parse_args()

    token = priceyak_login()
    reqs = fetch_requests(token, args.hours, args.scan)
    log.info("Scanned %d request row(s).", len(reqs))

    reasons = Counter()
    found = set()
    for r in reqs:
        reason = r.get("failure_reason")
        if r.get("state") == "success" or reason not in PERMANENT:
            continue
        a = asin_of(r)
        if a:
            found.add(a.strip().upper())
            reasons[reason] += 1

    log.info("Permanent-reject reasons seen: %s", dict(reasons))
    log.info("Distinct permanently-rejected ASIN(s) in scan: %d", len(found))

    existing = set()
    if os.path.exists(REJECTED_FILE):
        with open(REJECTED_FILE, "r", encoding="utf-8") as f:
            existing = {ln.strip().upper() for ln in f if ln.strip()}
    new = sorted(found - existing)
    log.info("rejected_asins.txt has %d; %d new to add.", len(existing), len(new))

    if not new:
        log.info("Nothing new to add.")
        return
    if args.dry_run:
        log.info("[DRY] Would add %d ASIN(s), e.g. %s", len(new), ", ".join(new[:10]))
        return

    merged = sorted(existing | found)
    os.makedirs(os.path.dirname(REJECTED_FILE), exist_ok=True)
    with open(REJECTED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(merged) + "\n")
    log.info("Wrote %d ASIN(s) to %s (+%d new).", len(merged), REJECTED_FILE, len(new))


if __name__ == "__main__":
    main()
