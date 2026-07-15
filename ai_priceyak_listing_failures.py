"""
Monitor PriceYak listing-request failures, alert on infra-error spikes (a
PriceYak fetcher outage), and re-submit the TRANSIENT failures so they actually
list. The biggest growth lever isn't scraping more -- it's not losing the items
that fail for transient PriceYak-side reasons.

PriceYak GET /v0/account/{id}/requests -> each listing attempt has state,
failure_reason, errors, product. Reasons split into:
  TRANSIENT (retry):   pdata_offers_internal_error, timeout, pdata_details_product_unavailable,
                       pdata_*  (PriceYak fetcher / internal errors)
  PERMANENT (skip):    no_offers, max_source_price, duplicate_req, duplicate_listing,
                       banned_brand, banned_product_id, veromatic, veromatic_aplus

Usage:
    python ai_priceyak_listing_failures.py                 # report + alert
    python ai_priceyak_listing_failures.py --hours 24
    python ai_priceyak_listing_failures.py --retry --max 200   # resubmit transient ASINs
"""

import sys
import time
import argparse
import logging
from collections import Counter

import requests
from ai_relist_proven_sellers import priceyak_login, submit_to_priceyak, PRICEYAK_ACCOUNT_ID
from notify import send

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

TRANSIENT = {"pdata_offers_internal_error", "timeout", "pdata_details_product_unavailable",
             "pdata_details_invalid_variant", "internal_error"}
# everything else (no_offers, max_source_price, banned_*, veromatic*, duplicate_*) is permanent


def fetch_requests(token, hours, scan_cap=2000):
    h = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    cutoff = time.time() - hours * 3600
    out, off = [], 0
    while off < scan_cap:
        d = requests.get(f"https://www.priceyak.com/v0/account/{PRICEYAK_ACCOUNT_ID}/requests",
                         headers=h, params={"count": 100, "offset": off}, timeout=60).json().get("data", [])
        if not d:
            break
        out.extend(d)
        off += len(d)
        if min((r.get("created_time") or 9e18) for r in d) < cutoff:
            break
    return [r for r in out if (r.get("created_time") or 0) >= cutoff]


def asin_of(r):
    return (r.get("product") or {}).get("product_id") or r.get("destination_product_id")


def main():
    ap = argparse.ArgumentParser(description="PriceYak listing-failure monitor + retry")
    ap.add_argument("--hours", type=float, default=24, help="Look back this many hours (default 24)")
    ap.add_argument("--retry", action="store_true", help="Re-submit transient-failure ASINs")
    ap.add_argument("--max", type=int, default=200, help="Cap ASINs resubmitted per run (default 200)")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    token = priceyak_login()
    reqs = fetch_requests(token, args.hours)
    if not reqs:
        log.info("No listing requests in window.")
        return

    states = Counter(r.get("state") for r in reqs)
    fails = [r for r in reqs if r.get("state") != "success"]
    reasons = Counter(r.get("failure_reason") for r in fails if r.get("failure_reason"))
    n = len(reqs)
    fail_rate = round(100 * len(fails) / n)
    transient = [r for r in fails if r.get("failure_reason") in TRANSIENT]
    infra_rate = round(100 * len(transient) / n)

    print("=" * 64)
    print(f"PriceYak listing requests last {args.hours:.0f}h: {n}  ({fail_rate}% failed)")
    print(f"  states: {dict(states)}")
    print(f"  transient (retryable): {len(transient)} ({infra_rate}% of all)")
    for reason, cnt in reasons.most_common(12):
        tag = "RETRY" if reason in TRANSIENT else "skip"
        print(f"    {cnt:>4}  [{tag}] {reason}")
    print("=" * 64)

    # Retry transient failures -- but only when the fetcher is actually working
    # again (a recent success exists). During a full outage, retrying just re-fails.
    fetcher_healthy = states.get("success", 0) > 0
    retried = 0
    if args.retry and transient and not fetcher_healthy:
        log.info("Skipping retry: 0 recent successes -> fetcher still down (outage). Will retry once it recovers.")
    elif args.retry and transient:
        seen, asins = set(), []
        for r in transient:
            a = asin_of(r)
            if a and a not in seen:
                seen.add(a)
                asins.append(a)
        asins = asins[: args.max]
        if asins:
            resp = submit_to_priceyak(asins, token)
            retried = len(asins) if resp.status_code == 200 else 0
            log.info(f"resubmitted {len(asins)} ASIN(s) -> HTTP {resp.status_code}")

    if args.no_push:
        return
    # Alert when transient/infra failures are a big share -> likely a PriceYak outage.
    if infra_rate >= 25 or (args.retry and retried):
        lines = [f"{fail_rate}% of {n} listing attempts failed in {args.hours:.0f}h.",
                 f"{len(transient)} transient (PriceYak-side) -- retryable."]
        for reason, cnt in reasons.most_common(6):
            lines.append(f"  {cnt} {reason}")
        if args.retry:
            lines.append(f"Resubmitted {retried} transient ASIN(s).")
        title = "PriceYak: listing fetcher errors (likely outage)" if infra_rate >= 40 else "PriceYak: listing failures"
        send(title, "\n".join(lines), priority="high" if infra_rate >= 40 else "default", tags="warning")


if __name__ == "__main__":
    main()
