"""
Discover rising-demand search terms via Google Trends and add them to
amazon_urls.txt. For each seed term, Google Trends returns "rising" and "top"
related queries -- rising queries are demand waves you may not be listing yet.

REQUIRES:  pip install pytrends
NOTE:      Google rate-limits Trends aggressively (HTTP 429), especially from
           datacenter IPs. The script backs off and skips on 429 rather than
           failing the whole run. If you get all-429, run it from a residential
           connection or space runs out.

Seeds come from args, --file, --stdin, or --from-urls N (random existing terms).

Usage:
    pip install pytrends
    python mine_google_trends.py "rock tumbler" "dash cam"
    python mine_google_trends.py --from-urls 15 --rising-only --min-price 50
    python mine_google_trends.py --file seeds.txt --print-only
"""

import os
import sys
import time
import random
import argparse
import logging

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE, keyword_of

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def _load_pytrends():
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.error("pytrends is not installed. Run:  pip install pytrends")
        sys.exit(2)
    return TrendReq(hl="en-US", tz=360, timeout=(10, 25))


def related_terms(pytrends, seed, rising_only, top_n, sleep):
    """Return related queries (rising first) for a seed, or [] on rate-limit/empty."""
    out = []
    try:
        pytrends.build_payload([seed], timeframe="today 3-m", geo="US")
        rq = pytrends.related_queries().get(seed) or {}
        for kind in (["rising"] if rising_only else ["rising", "top"]):
            df = rq.get(kind)
            if df is not None and not df.empty:
                out.extend(str(q) for q in df["query"].head(top_n).tolist())
    except Exception as e:
        log.warning(f"  trends failed for '{seed}': {e}")
    time.sleep(sleep)
    return out


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


def main():
    ap = argparse.ArgumentParser(description="Discover rising terms via Google Trends into amazon_urls.txt")
    ap.add_argument("seeds", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--from-urls", type=int, default=0, metavar="N",
                    help="Seed from N random existing keywords in the urls file")
    ap.add_argument("--rising-only", action="store_true", help="Only rising queries (newest demand)")
    ap.add_argument("--top-n", type=int, default=10, help="Max related queries per seed per kind")
    ap.add_argument("--sleep", type=float, default=2.0, help="Seconds between seeds (rate-limit politeness)")
    ap.add_argument("--min-price", type=float, default=0)
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    seeds = list(args.seeds)
    if args.file:
        seeds += _read_lines(args.file)
    if args.stdin:
        seeds += [ln.strip() for ln in sys.stdin if ln.strip() and not ln.strip().startswith("#")]
    if args.from_urls > 0 and os.path.exists(args.urls_file):
        kws = [k for k in (keyword_of(l.strip()) for l in open(args.urls_file, encoding="utf-8")) if k]
        if kws:
            seeds += random.sample(kws, min(args.from_urls, len(kws)))
    if not seeds:
        ap.error("No seeds. Pass terms as args, --file, --stdin, and/or --from-urls.")

    pytrends = _load_pytrends()
    log.info(f"Querying Google Trends for {len(seeds)} seed(s)...")

    found, seen = [], set()
    for seed in seeds:
        for t in related_terms(pytrends, seed.strip(), args.rising_only, args.top_n, args.sleep):
            low = t.lower().strip()
            if low and low not in seen:
                seen.add(low)
                found.append(t.strip())
        log.info(f"  '{seed}' -> {len(found)} cumulative term(s)")

    if not found:
        log.info("No related terms (likely rate-limited or no data).")
        return

    if args.print_only:
        for t in found:
            print(t)
        return

    added, skipped = add_search_terms(
        found,
        min_price=args.min_price if args.min_price > 0 else None,
        prime=not args.no_prime,
        high_rating=not args.no_high_rating,
        urls_file=args.urls_file,
    )
    print(f"Added {len(added)} new search term(s) to {args.urls_file} ({len(skipped)} already present).")
    for t in added[:40]:
        print(f"  + {t}")


if __name__ == "__main__":
    main()
