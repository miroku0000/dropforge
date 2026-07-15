"""
eBay Terapeak Product Research -> Amazon search terms.

Drives the existing logged-in eBay session (playwright_browser.launch_ebay_browser,
same as the other ai_ebay_* scripts) to open Terapeak Product Research for each
seed keyword, reads the titles of the listings that actually SOLD on eBay, reduces
them to product-type phrases (reusing mine_winner_titles.title_to_phrases), and
adds the most common ones to amazon_urls.txt.

Why Terapeak: unlike your own sales data, this is "what's selling across all of
eBay" for a seed -- real marketplace demand, with the exact product wording buyers
respond to.

Seeds: args, --file, --stdin, or --from-urls N (random existing terms).

Usage:
    python ai_ebay_terapeak_terms.py --probe "rock tumbler"      # inspect page, save HTML
    python ai_ebay_terapeak_terms.py "rock tumbler" "dash cam"
    python ai_ebay_terapeak_terms.py --from-urls 10 --min-price 50
"""

import os
import sys
import time
import random
import argparse
import logging
from collections import Counter
from urllib.parse import quote_plus
from datetime import datetime

from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser, needs_signin, wait_for_signin, _is_bot_blocked, _wait_for_captcha

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE, keyword_of
from mine_winner_titles import title_to_phrases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")


def research_url(keyword, day_range=90):
    return (
        "https://www.ebay.com/sh/research?marketplace=EBAY-US"
        f"&keywords={quote_plus(keyword)}&dayRange={day_range}&tabName=SUMMARY&offset=0&limit=50"
    )


TITLE_SEL = "a.research-table-row__link-row-anchor"


def _ensure_ready(page, url):
    page.goto(url, wait_until="load", timeout=60000)
    if _is_bot_blocked(page):
        _wait_for_captcha(page)
        page.goto(url, wait_until="load", timeout=60000)
    if needs_signin(page):
        wait_for_signin(page, success_url_glob="**/sh/research**")
        page.goto(url, wait_until="load", timeout=60000)


def _wait_for_results(page, timeout_s=35):
    """The research table loads async (spinners). Wait for the title rows to
    appear and the count to stabilize, so we don't read a half-rendered / stale
    table."""
    try:
        page.wait_for_selector(TITLE_SEL, timeout=timeout_s * 1000)
    except Exception:
        log.warning("  results table did not appear")
        return
    last, stable = -1, 0
    for _ in range(timeout_s):
        n = len(page.query_selector_all(TITLE_SEL))
        stable = stable + 1 if n == last else 0
        last = n
        if n >= 5 and stable >= 3:
            break
        page.wait_for_timeout(1000)
    log.info(f"  results stabilized at {last} row(s)")


def probe(page, keyword):
    """Dump page structure to find the listing-title selector."""
    url = research_url(keyword)
    log.info(f"PROBE navigating: {url}")
    _ensure_ready(page, url)
    _wait_for_results(page)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(DOWNLOAD_DIR, f"terapeak_probe_{ts}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page.content())
    png = os.path.join(DOWNLOAD_DIR, f"terapeak_probe_{ts}.png")
    try:
        page.screenshot(path=png, full_page=True)
    except Exception:
        pass
    log.info(f"Saved HTML -> {html_path}")
    log.info(f"Saved PNG  -> {png}")
    log.info(f"Final URL: {page.url}")
    # Try a bunch of candidate selectors and report counts + samples.
    candidates = [
        "a.research-table-row__link-row-anchor",
        "a[href*='/itm/']",
        ".research-table-row__title",
        "[class*='research-table-row'] a",
        "[class*='item-title']",
        "td[class*='title'] a",
        "a[class*='title']",
        ".grid-row a",
        "table tbody tr",
    ]
    for sel in candidates:
        try:
            els = page.query_selector_all(sel)
        except Exception:
            continue
        if not els:
            continue
        samples = []
        for e in els[:4]:
            try:
                t = (e.inner_text() or "").strip().replace("\n", " ")
                if t:
                    samples.append(t[:60])
            except Exception:
                pass
        log.info(f"  [{len(els):>4}] {sel}  ::  {samples}")


def scrape_titles(page, keyword, day_range, limit):
    """Return sold/research listing titles for a keyword from Terapeak."""
    url = research_url(keyword, day_range)
    _ensure_ready(page, url)
    _wait_for_results(page)
    titles = []
    for e in page.query_selector_all(TITLE_SEL)[:limit]:
        try:
            t = " ".join((e.inner_text() or "").split())
            if len(t) > 12 and " " in t:
                titles.append(t)
        except Exception:
            continue
    return titles


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


def collect_seeds(args):
    seeds = list(args.seeds)
    if args.file:
        seeds += _read_lines(args.file)
    if args.stdin:
        seeds += [ln.strip() for ln in sys.stdin if ln.strip() and not ln.strip().startswith("#")]
    if args.from_urls > 0 and os.path.exists(args.urls_file):
        kws = [k for k in (keyword_of(l.strip()) for l in open(args.urls_file, encoding="utf-8")) if k]
        if kws:
            seeds += random.sample(kws, min(args.from_urls, len(kws)))
    return seeds


def main():
    ap = argparse.ArgumentParser(description="Terapeak Product Research -> Amazon search terms")
    ap.add_argument("seeds", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--from-urls", type=int, default=0, metavar="N")
    ap.add_argument("--day-range", type=int, default=90)
    ap.add_argument("--limit", type=int, default=50, help="Listings to read per seed")
    ap.add_argument("--max", type=int, default=60, help="Max phrases to add")
    ap.add_argument("--min-count", type=int, default=2, help="Phrase must appear in >= N listings")
    ap.add_argument("--min-price", type=float, default=0)
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--probe", action="store_true", help="Inspect the page structure (dev) and exit")
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    seeds = collect_seeds(args)
    if not seeds and not args.probe:
        ap.error("No seeds. Pass terms as args, --file, --stdin, and/or --from-urls.")
    if args.probe and not seeds:
        seeds = ["rock tumbler"]

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 950}, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            if args.probe:
                probe(page, seeds[0])
                return

            phrase_counts = Counter()
            for seed in seeds:
                try:
                    titles = scrape_titles(page, seed.strip(), args.day_range, args.limit)
                    for t in titles:
                        for phrase in set(title_to_phrases(t)):
                            phrase_counts[phrase] += 1
                    log.info(f"  '{seed}' -> {len(titles)} sold listing(s)")
                except Exception as e:
                    log.warning(f"  '{seed}' failed: {e}")
                page.wait_for_timeout(1500)

            phrases = [p_ for p_, c in phrase_counts.most_common() if c >= args.min_count][: args.max]
            log.info(f"{len(phrases)} phrase(s) over min-count {args.min_count}.")
            for p_ in phrases[:25]:
                log.info(f"  {phrase_counts[p_]:>3}x  {p_}")

            if args.print_only:
                for p_ in phrases:
                    print(p_)
                return
            if not phrases:
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
        finally:
            context.close()
            log.info("Disconnected from Chrome (left running).")


if __name__ == "__main__":
    main()
