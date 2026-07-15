"""
One-time normalizer for amazon_urls.txt.

Rewrites every search URL through the canonical builder
(amazon_search_urls.build_amazon_search_url) so ALL of them enforce the same
filters in the single correctly-joined rh= form:
    * price floor  (p_36, default $60)
    * fast ship    (Prime / free-shipping-eligible)
    * 4 stars & up

It also:
    * DROPS un-keyworded seed URLs -- the i=bazaar category searches and
      /b/?node= browse pages -- which can't take a clean price floor (bazaar is
      Amazon's ultra-low-price index; browse nodes ignore search facets).
    * Fixes the multi-&rh= bug (Amazon honored only the last facet, so the price
      floor was silently ignored on those).
    * Dedupes by search keyword (keeps the first occurrence).

The original file is backed up to amazon_urls.txt.PRE-NORMALIZE before writing.

Usage:
    python normalize_amazon_urls.py              # dry-run: print what would change
    python normalize_amazon_urls.py --apply      # back up + rewrite the file
    python normalize_amazon_urls.py --apply --min-price 60
"""

import argparse
import os
import re

from amazon_search_urls import build_amazon_search_url, keyword_of

URLS_FILE = "amazon_urls.txt"
BACKUP = "amazon_urls.txt.PRE-NORMALIZE"


def raw_keyword(url):
    """Original-case search keyword (the k= value), or None for browse pages."""
    from urllib.parse import unquote_plus
    m = re.search(r"[?&]k=([^&]+)", url)
    return unquote_plus(m.group(1)).strip() if m else None


CURATED_RE = re.compile(r"/zgbs/|/gp/movers-and-shakers/|/gp/bestsellers|/gp/new-releases")


def classify(url):
    """('drop'|'search'|'keep', detail).
       search -> /s?k= keyword page, normalize filters
       keep   -> curated Best Sellers / Movers & Shakers / New Releases list page
                 (can't carry an rh= filter; price enforced downstream)
       drop   -> bazaar ultra-low-price index, or a bare browse node."""
    if "i=bazaar" in url:
        return "drop", "bazaar (ultra-low-price index)"
    kw = raw_keyword(url)
    if kw:
        return "search", kw
    if CURATED_RE.search(url):
        return "keep", "curated list page (bestsellers/movers/new-releases)"
    if "/b/?" in url or "/b?" in url or re.search(r"[?&]node=", url):
        return "drop", "browse-node page (no keyword)"
    return "drop", "no keyword / uncategorized"


def main():
    ap = argparse.ArgumentParser(description="Normalize amazon_urls.txt filters")
    ap.add_argument("--apply", action="store_true", help="Back up and rewrite the file (default: dry-run)")
    ap.add_argument("--min-price", type=int, default=60, help="Price floor in dollars (default 60)")
    args = ap.parse_args()

    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    out = []                       # final file contents, in original order
    n_search = n_curated = 0
    dropped, deduped = [], []
    seen_kw, seen_url = set(), set()
    drop_reasons = {}
    for url in lines:
        kind, detail = classify(url)
        if kind == "drop":
            dropped.append(url)
            drop_reasons[detail] = drop_reasons.get(detail, 0) + 1
            continue
        if kind == "search":
            key = detail.lower()
            if key in seen_kw:
                deduped.append(url)
                continue
            seen_kw.add(key)
            out.append(build_amazon_search_url(detail, min_price=args.min_price, prime=True, high_rating=True))
            n_search += 1
        else:                      # keep (curated) -- left exactly as-is
            if url in seen_url:
                deduped.append(url)
                continue
            seen_url.add(url)
            out.append(url)
            n_curated += 1

    print(f"Input URLs:                 {len(lines)}")
    print(f"  -> search, normalized:    {n_search}  (now enforce >= ${args.min_price} + fast-ship + 4-star, single rh=)")
    print(f"  -> curated, kept as-is:   {n_curated}  (bestsellers/movers/new-releases; price gated at scrape/list time)")
    print(f"  -> dropped:               {len(dropped)}")
    for r, c in sorted(drop_reasons.items(), key=lambda x: -x[1]):
        print(f"       {c:>4}  {r}")
    print(f"  -> deduped:               {len(deduped)}")
    print(f"  => final file:            {len(out)} URL(s)")
    print()
    print("Sample normalized search URLs:")
    for u in [x for x in out if "/s?k=" in x][:3]:
        print("  ", u)
    print("Sample kept curated URLs:")
    for u in [x for x in out if "/s?k=" not in x][:3]:
        print("  ", u)
    print("Sample dropped URLs:")
    for u in dropped[:3]:
        print("  ", u)
    kept = out

    if not args.apply:
        print(f"\nDRY-RUN. Re-run with --apply to back up to {BACKUP} and rewrite.")
        return

    with open(BACKUP, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")
    print(f"\nAPPLIED. Backed up {len(lines)} original line(s) to {BACKUP}; "
          f"wrote {len(kept)} normalized URL(s) to {URLS_FILE}.")


if __name__ == "__main__":
    main()
