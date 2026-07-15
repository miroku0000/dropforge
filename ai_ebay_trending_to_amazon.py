"""
eBay Trending Keywords to Amazon Search URLs (Playwright)
Scrapes trending keywords from eBay Sourcing Insights page,
converts them to Amazon search URLs, and adds new ones to amazon_urls.txt.

Usage:
    python ai_ebay_trending_to_amazon.py
    python ai_ebay_trending_to_amazon.py --min-price 50
"""

import os
import sys
import logging
import argparse
from urllib.parse import quote_plus
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
SOURCING_URL = "https://www.ebay.com/sh/research/sourcing-insights/top-category?marketplace=EBAY-US"
AMAZON_URLS_FILE = "amazon_urls.txt"


def create_amazon_search_url(keyword, min_price=None):
    """Create an Amazon search URL from a keyword.

    Routes through the canonical builder so every generated URL enforces the
    same filters (price floor + fast-ship + 4-star) in one correctly-joined rh=.
    """
    from amazon_search_urls import build_amazon_search_url
    return build_amazon_search_url(keyword, min_price=min_price, prime=True, high_rating=True)


def scrape_trending_keywords():
    """Scrape trending keywords from eBay Sourcing Insights."""
    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900}, accept_downloads=False)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            log.info(f"Opening {SOURCING_URL}")
            page.goto(SOURCING_URL, wait_until="load", timeout=60000)

            # Check login
            if "signin" in page.url.lower():
                log.warning("Please log in to eBay in the browser window.")
                page.wait_for_url("**/sh/research/**", timeout=120000)
                log.info("Login detected, continuing...")

            page.wait_for_timeout(5000)

            # Screenshot
            ss = os.path.join(DOWNLOAD_DIR, f"trending_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss, full_page=True)
            log.info(f"Page screenshot: {ss}")

            # Extract trending category names from the cards
            keywords = set()

            # The category names are in .catres__category-card-title-link elements
            elements = page.locator(".catres__category-card-title-link").all()
            for el in elements:
                try:
                    text = el.inner_text().strip()
                    if text and len(text) > 2:
                        keywords.add(text)
                except Exception:
                    continue

            # Fallback: try broader selectors
            if not keywords:
                log.info("Primary selector found nothing, trying fallbacks...")
                for selector in [
                    ".catres__category-card-title-header a",
                    ".category-card a",
                    "[class*='category-card-title'] a",
                ]:
                    elements = page.locator(selector).all()
                    for el in elements:
                        try:
                            text = el.inner_text().strip()
                            if text and len(text) > 2 and len(text) < 100:
                                keywords.add(text)
                        except Exception:
                            continue

            # Remove blacklisted categories that don't work well for reselling
            blacklist = {
                'athletic shoes',
                'dvds & blu-ray discs',
                'vinyl records',
                'video games',
                'coats, jackets & vests',
                'hoodies & sweatshirts',
                't-shirts',
                'tops',
                "women's bags & handbags",
            }
            # Also filter out anything with clothing-related words
            clothing_words = {'shirt', 'pants', 'dress', 'skirt', 'jacket', 'coat',
                              'hoodie', 'sweatshirt', 'jeans', 'shorts', 'blouse',
                              'sweater', 'legging', 'sock', 'underwear', 'lingerie',
                              'swimwear', 'bikini', 'shoe', 'boot', 'sandal',
                              'sneaker', 'heel', 'slipper', 'clothing', 'apparel',
                              'activewear', 'athleisure', 'footwear', 'vest'}
            keywords = {k for k in keywords
                        if k.lower() not in blacklist
                        and not any(w in k.lower() for w in clothing_words)}

            # If still empty, dump HTML for debugging
            if not keywords:
                log.warning("No keywords found, saving page for debugging...")
                html_path = os.path.join(DOWNLOAD_DIR, f"trending_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                log.info(f"Page HTML saved: {html_path}")

            log.info(f"Found {len(keywords)} trending keywords")
            for kw in sorted(keywords):
                log.info(f"  - {kw}")

            return sorted(keywords)

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"trending_error_{ts}.png"))
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


def add_to_amazon_urls(keywords, min_price=None):
    """Convert keywords to Amazon URLs and add new ones to amazon_urls.txt."""
    # Load existing URLs
    existing_urls = set()
    if os.path.exists(AMAZON_URLS_FILE):
        with open(AMAZON_URLS_FILE, 'r', encoding='utf-8') as f:
            existing_urls = set(line.strip() for line in f if line.strip())
    log.info(f"Existing URLs in {AMAZON_URLS_FILE}: {len(existing_urls)}")

    # Also check by keyword to avoid duplicate searches with slightly different URL params
    existing_keywords = set()
    for url in existing_urls:
        if 'k=' in url:
            # Extract the keyword from the URL
            import re
            match = re.search(r'[?&]k=([^&]+)', url)
            if match:
                from urllib.parse import unquote_plus
                existing_keywords.add(unquote_plus(match.group(1)).lower())

    # Generate new URLs
    new_urls = []
    for keyword in keywords:
        if keyword.lower() in existing_keywords:
            log.info(f"  Already exists: {keyword}")
            continue

        url = create_amazon_search_url(keyword, min_price=min_price)
        if url not in existing_urls:
            new_urls.append(url)
            existing_urls.add(url)
            existing_keywords.add(keyword.lower())
            log.info(f"  New: {keyword} -> {url[:80]}...")

    # Append new URLs
    if new_urls:
        with open(AMAZON_URLS_FILE, 'a', encoding='utf-8') as f:
            for url in new_urls:
                f.write(url + '\n')
        log.info(f"Added {len(new_urls)} new URLs to {AMAZON_URLS_FILE}")
    else:
        log.info("No new URLs to add")

    log.info(f"Total URLs in {AMAZON_URLS_FILE}: {len(existing_urls)}")
    return new_urls


def main():
    parser = argparse.ArgumentParser(description="eBay Trending Keywords to Amazon Search URLs")
    parser.add_argument('--min-price', type=float, default=0, help='Minimum price filter for Amazon searches')
    args = parser.parse_args()

    # Scrape trending keywords
    keywords = scrape_trending_keywords()

    if not keywords:
        log.warning("No trending keywords found. Check the screenshots for debugging.")
        return

    # Add to amazon_urls.txt
    new_urls = add_to_amazon_urls(keywords, min_price=args.min_price if args.min_price > 0 else None)

    print(f"\nFound {len(keywords)} trending keywords, added {len(new_urls)} new Amazon search URLs")


if __name__ == "__main__":
    main()
