"""
Mine rising-demand search terms from Amazon Movers & Shakers / Best Sellers.

Movers & Shakers = the biggest 24-hour sales-rank gainers per category -- an
early signal of demand waves. This scrapes those grid pages (via Crawlbase, the
same scraper the project already uses for Amazon), pulls the product titles,
reduces them to product-type phrases (reusing mine_winner_titles.title_to_phrases),
and adds the most common phrases to amazon_urls.txt.

Costs one Crawlbase call per page, so it samples a random subset of categories
per run by default (--max-pages).

Usage:
    python mine_amazon_movers.py
    python mine_amazon_movers.py --max-pages 6 --max 50 --min-price 50
    python mine_amazon_movers.py --print-only
"""

import random
import argparse
import logging
from collections import Counter

from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE
from mine_winner_titles import title_to_phrases

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

TOKEN_FILE = "crawlbase_creds.txt"

# Category slugs that match the store's niches. Both Movers & Shakers (rising)
# and Best Sellers (steady demand) use these slugs.
CATEGORY_SLUGS = [
    "automotive", "tools", "home-garden", "kitchen", "electronics",
    "sporting-goods", "office-products", "pet-supplies", "lawn-garden",
    "toys-and-games", "industrial", "baby-products", "arts-crafts",
    "musical-instruments", "appliances", "hpc",
]


def build_urls():
    urls = []
    for slug in CATEGORY_SLUGS:
        urls.append(f"https://www.amazon.com/gp/movers-and-shakers/{slug}")
        urls.append(f"https://www.amazon.com/gp/bestsellers/{slug}")
    return urls


def load_token():
    with open(TOKEN_FILE, "r") as f:
        return f.readline().strip()


def extract_titles(html):
    """Product titles on the grid live in the per-tile line-clamp span (preferred)
    and the product image alt text. The grid lazy-loads, so the page must be
    fetched with Crawlbase scroll=true (see main) or these will be empty."""
    soup = BeautifulSoup(html, "html.parser")
    titles = set()
    # Preferred: the title clamp span inside each faceout (class has a hash suffix).
    for sp in soup.select('div[class*="p13n-sc-css-line-clamp"], span[class*="p13n-sc-truncate"]'):
        t = " ".join(sp.get_text(" ", strip=True).split())
        if len(t) > 12 and " " in t:
            titles.add(t)
    # Fallback: product image alt text.
    for img in soup.find_all("img", alt=True):
        alt = " ".join((img.get("alt") or "").split())
        if len(alt) > 12 and " " in alt:
            titles.add(alt)
    return titles


def main():
    ap = argparse.ArgumentParser(description="Mine rising-demand terms from Amazon Movers & Shakers / Best Sellers")
    ap.add_argument("--max-pages", type=int, default=6, help="Random category pages to fetch this run (default 6)")
    ap.add_argument("--max", type=int, default=50, help="Add at most this many phrases (default 50)")
    ap.add_argument("--min-count", type=int, default=2, help="Phrase must appear in >= this many products (default 2)")
    ap.add_argument("--min-price", type=float, default=0)
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    api = CrawlingAPI({"token": load_token()})
    urls = build_urls()
    random.shuffle(urls)
    urls = urls[: args.max_pages]

    phrase_counts = Counter()
    pages_ok = 0
    for url in urls:
        try:
            resp = api.get(url, {"page_wait": "4000", "scroll": "true"})
            if resp["status_code"] != 200:
                log.warning(f"  {resp['status_code']} for {url}")
                continue
            html = resp["body"].decode("utf-8", errors="ignore")
            titles = extract_titles(html)
            for t in titles:
                for phrase in set(title_to_phrases(t)):
                    phrase_counts[phrase] += 1
            log.info(f"  {len(titles)} titles from {url.split('/')[-2]}/{url.split('/')[-1]}")
            pages_ok += 1
        except Exception as e:
            log.warning(f"  failed {url}: {e}")

    log.info(f"Fetched {pages_ok} page(s); {len(phrase_counts)} distinct phrase(s).")
    phrases = [p for p, c in phrase_counts.most_common() if c >= args.min_count][: args.max]
    if not phrases:
        log.info("No phrases met the min-count threshold.")
        return

    for p in phrases[:25]:
        log.info(f"  {phrase_counts[p]:>3}x  {p}")

    if args.print_only:
        for p in phrases:
            print(p)
        return

    added, skipped = add_search_terms(
        phrases,
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
