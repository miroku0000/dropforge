"""
Add Amazon search terms to amazon_urls.txt (the scrape input list).

Each term becomes an Amazon search URL with sourcing filters (Prime/Next-Day +
4-stars-and-up by default, plus optional --min-price). The next scrape harvests
products matching each term. Terms whose keyword is already in the file are
skipped, so it is safe to re-run.

Terms can come from positional args, a --file (one per line, # = comment), and/or
--stdin (one per line). Combine freely.

Examples:
    python add_amazon_searches.py "cordless drill" "garage storage rack"
    python add_amazon_searches.py --file my_terms.txt --min-price 50
    type my_terms.txt | python add_amazon_searches.py --stdin
    python add_amazon_searches.py --no-prime "vintage typewriter"
"""

import sys
import argparse

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE


def _read_terms_file(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(description="Add Amazon search terms to amazon_urls.txt")
    ap.add_argument("terms", nargs="*", help="Search terms (quote multi-word terms)")
    ap.add_argument("--file", help="Read terms from a file (one per line, # = comment)")
    ap.add_argument("--stdin", action="store_true", help="Read terms from stdin (one per line)")
    ap.add_argument("--min-price", type=float, default=0, help="Minimum price filter (margin floor)")
    ap.add_argument("--no-prime", action="store_true", help="Do not require Prime/Next-Day")
    ap.add_argument("--no-high-rating", action="store_true", help="Do not require 4+ stars")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE, help=f"Target file (default {AMAZON_URLS_FILE})")
    args = ap.parse_args()

    terms = list(args.terms)
    if args.file:
        terms += _read_terms_file(args.file)
    if args.stdin:
        terms += [ln.strip() for ln in sys.stdin if ln.strip() and not ln.strip().startswith("#")]

    if not terms:
        ap.error("No terms given. Pass terms as arguments, --file, and/or --stdin.")

    added, skipped = add_search_terms(
        terms,
        min_price=args.min_price if args.min_price > 0 else None,
        prime=not args.no_prime,
        high_rating=not args.no_high_rating,
        urls_file=args.urls_file,
    )

    print(f"Added {len(added)} new search term(s) to {args.urls_file}:")
    for t in added:
        print(f"  + {t}")
    if skipped:
        print(f"Skipped {len(skipped)} already-present term(s):")
        for t in skipped:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
