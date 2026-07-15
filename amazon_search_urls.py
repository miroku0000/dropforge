"""
Helpers for adding Amazon *search* terms to amazon_urls.txt.

amazon_urls.txt is the input for scrape_amazon_incremental.py. The scraper treats
a search/browse URL as a source of ASINs, so adding a search term here means the
next scrape harvests products matching that term.

For sourcing good resale candidates the default filters are Prime/Next-Day +
4-stars-and-up, plus an optional minimum price (a margin floor). Dedup is by the
search keyword (the ?k= param), not the exact URL, so the same term with
different filters is never added twice.

Used by add_amazon_searches.py. (The existing generators
analyze_roi_and_generate_amazon_searches.py and ai_ebay_trending_to_amazon.py
build equivalent URLs inline; this module is the standalone path.)
"""

import os
import re
from urllib.parse import quote_plus, unquote_plus

AMAZON_URLS_FILE = "amazon_urls.txt"

# Amazon "rh" facet values
_RH_PRIME = "p_n_free_shipping_eligible%3A2944662011"   # Prime eligible / fast ship
_RH_4STAR = "p_72%3A2491149011"                          # 4 stars & up


def build_amazon_search_url(term, min_price=None, prime=True, high_rating=True):
    """Build an Amazon search URL for `term` with optional sourcing filters.

    Amazon expects a single rh= param with the facets comma-joined (%2C). The
    older inline builders emitted one rh= per facet, so only the last took
    effect; this joins them so price + Prime + rating all apply together.
    """
    url = f"https://www.amazon.com/s?k={quote_plus(term)}"
    facets = []
    if min_price and min_price > 0:
        facets.append(f"p_36%3A{int(min_price * 100)}-")   # price in cents, "min-"
    if prime:
        facets.append(_RH_PRIME)
    if high_rating:
        facets.append(_RH_4STAR)
    if facets:
        url += "&rh=" + "%2C".join(facets)
    url += "&i=aps"
    return url


def keyword_of(url):
    """Return the lowercased search keyword from an Amazon search URL, or None."""
    m = re.search(r"[?&]k=([^&]+)", url)
    return unquote_plus(m.group(1)).strip().lower() if m else None


def add_search_terms(terms, min_price=None, prime=True, high_rating=True,
                     urls_file=AMAZON_URLS_FILE):
    """Append search URLs for `terms` to urls_file, skipping terms whose keyword
    is already present. Returns (added_terms, skipped_terms)."""
    existing_urls = set()
    existing_keywords = set()
    if os.path.exists(urls_file):
        with open(urls_file, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if not u:
                    continue
                existing_urls.add(u)
                kw = keyword_of(u)
                if kw:
                    existing_keywords.add(kw)

    added, skipped, new_urls = [], [], []
    seen_this_run = set()
    for term in terms:
        term = (term or "").strip()
        if not term:
            continue
        key = term.lower()
        if key in existing_keywords or key in seen_this_run:
            skipped.append(term)
            continue
        url = build_amazon_search_url(term, min_price, prime, high_rating)
        if url in existing_urls:
            skipped.append(term)
            continue
        new_urls.append(url)
        seen_this_run.add(key)
        added.append(term)

    if new_urls:
        # Ensure we start on a fresh line (the file may not end in one).
        needs_nl = False
        if os.path.exists(urls_file) and os.path.getsize(urls_file) > 0:
            with open(urls_file, "rb") as f:
                f.seek(-1, os.SEEK_END)
                needs_nl = f.read(1) != b"\n"
        with open(urls_file, "a", encoding="utf-8") as f:
            if needs_nl:
                f.write("\n")
            for u in new_urls:
                f.write(u + "\n")

    return added, skipped
