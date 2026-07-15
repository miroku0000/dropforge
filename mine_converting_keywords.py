"""
Mine the eBay Top Converters keyword report for real buyer search phrases that
drive demand on YOUR listings, and add them to amazon_urls.txt as Amazon
searches. This is the highest-signal term source: every keyword here is a phrase
a real buyer typed that led to impressions/clicks/sales on your store.

Input: the latest "Top Converters*Keyword*.csv" in ~/Downloads (downloaded by
ai_ebay_download_top_converters_keyword_report.py). Relevant columns:
    Seller Keyword, Impressions, Clicks, Sold quantity, Sales

A keyword qualifies if it clears ANY of the demand thresholds (it sold, OR got
real clicks, OR got real impressions). Single-word generic keywords (e.g. "hood")
are dropped unless they actually sold, since they make poor Amazon searches.

Usage:
    python mine_converting_keywords.py
    python mine_converting_keywords.py --min-impressions 30 --max 100 --min-price 50
    python mine_converting_keywords.py --print-only        # list terms, no write
"""

import os
import csv
import glob
import argparse
import logging

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")


def find_keyword_report():
    patterns = [
        os.path.join(DOWNLOADS_DIR, "Top Converters*Keyword*.csv"),
        os.path.join(DOWNLOADS_DIR, "*Keyword*.csv"),
    ]
    for pat in patterns:
        files = glob.glob(pat)
        if files:
            return max(files, key=os.path.getmtime)
    return None


def _to_int(s):
    try:
        return int(float(str(s).replace(",", "").replace("$", "").replace("%", "").strip() or 0))
    except ValueError:
        return 0


def _find_header_row(path):
    """The report has a banner line before the real header; find the header row."""
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        for i, line in enumerate(f):
            if "Seller Keyword" in line:
                return i
    return 0


def load_keywords(path, min_impr, min_clicks, min_sold, min_words, all_mode=False):
    skip = _find_header_row(path)
    rows = []
    with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for _ in range(skip):
            next(f, None)
        reader = csv.DictReader(f)
        for row in reader:
            kw = (row.get("Seller Keyword") or "").strip()
            if not kw:
                continue
            impr = _to_int(row.get("Impressions"))
            clicks = _to_int(row.get("Clicks"))
            sold = _to_int(row.get("Sold quantity"))
            words = len(kw.split())
            # Demand gate: sold, OR enough clicks, OR enough impressions.
            # --all keeps every keyword (use the curated list as expander seeds).
            qualifies = all_mode or sold >= min_sold or clicks >= min_clicks or impr >= min_impr
            if not qualifies:
                continue
            # Drop single-word generics unless they actually sold.
            if words < min_words and sold < 1:
                continue
            rows.append({"kw": kw, "impr": impr, "clicks": clicks, "sold": sold})
    # De-dupe by keyword keeping the strongest signal; rank by sold, clicks, impr.
    best = {}
    for r in rows:
        k = r["kw"].lower()
        if k not in best or (r["sold"], r["clicks"], r["impr"]) > (best[k]["sold"], best[k]["clicks"], best[k]["impr"]):
            best[k] = r
    ranked = sorted(best.values(), key=lambda r: (r["sold"], r["clicks"], r["impr"]), reverse=True)
    return ranked


def main():
    ap = argparse.ArgumentParser(description="Mine converting eBay keywords into amazon_urls.txt")
    ap.add_argument("--file", help="Keyword report CSV (default: latest in ~/Downloads)")
    ap.add_argument("--min-impressions", type=int, default=20)
    ap.add_argument("--min-clicks", type=int, default=2)
    ap.add_argument("--min-sold", type=int, default=1)
    ap.add_argument("--min-words", type=int, default=2, help="Drop shorter keywords unless they sold (default 2)")
    ap.add_argument("--max", type=int, default=150, help="Add at most this many (highest-demand first)")
    ap.add_argument("--min-price", type=float, default=0)
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--all", action="store_true",
                    help="Ignore demand thresholds; use every keyword (good as expander seeds)")
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    path = args.file or find_keyword_report()
    if not path or not os.path.exists(path):
        log.error("No Top Converters keyword report found in ~/Downloads.")
        return
    log.info(f"Reading keyword report: {path}")

    ranked = load_keywords(path, args.min_impressions, args.min_clicks,
                           args.min_sold, args.min_words, all_mode=args.all)
    if args.all:
        log.info(f"{len(ranked)} keyword(s) (all, thresholds ignored).")
    else:
        log.info(f"{len(ranked)} keyword(s) clear the demand thresholds.")
        if not ranked:
            log.info("Tip: this report has no impression/click/sale data yet. "
                     "Use --all to feed the curated keywords into the expander instead.")
    if not ranked:
        return

    chosen = ranked[: args.max]
    terms = [r["kw"] for r in chosen]

    for r in chosen[:20]:
        log.info(f"  {r['sold']:>2} sold  {r['clicks']:>4} clk  {r['impr']:>6} impr  | {r['kw']}")
    if len(chosen) > 20:
        log.info(f"  ... and {len(chosen) - 20} more.")

    if args.print_only:
        for t in terms:
            print(t)
        return

    added, skipped = add_search_terms(
        terms,
        min_price=args.min_price if args.min_price > 0 else None,
        prime=not args.no_prime,
        high_rating=not args.no_high_rating,
        urls_file=args.urls_file,
    )
    print(f"Added {len(added)} new search term(s) to {args.urls_file} ({len(skipped)} already present).")
    for t in added[:40]:
        print(f"  + {t}")
    if len(added) > 40:
        print(f"  ... and {len(added) - 40} more.")


if __name__ == "__main__":
    main()
