"""
Incremental Newegg scraper for the Newegg -> PriceYak pipeline.

Mirror of scrape_amazon_incremental.py. Reads newegg_urls.txt (search/category
pages and/or individual product pages), scrapes each via Crawlbase, extracts
Newegg item numbers, and queues them (with price) for batch_uploader_newegg.py
which lists them on PriceYak with source="newegg".

Newegg identifiers: the canonical product id is the "Item #" that appears in the
URL path as /p/<ITEM> (e.g. .../p/N82E16814932608) and on the page as "Item#".
That bare item number is what PriceYak's create_batch wants in product_ids,
exactly like an ASIN for Amazon.

Usage:
    python scrape_newegg_incremental.py [--min-price 80] [--max-urls 500]
"""

import json
import time
import random
import sys
import os
import re
from crawlbase import CrawlingAPI
import hashlib
from bs4 import BeautifulSoup
from scrape_newegg_batch import batch_manager

# Make stdout/stderr tolerate Unicode glyphs on the Windows cp1252 console.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configuration
TOKEN_FILE = "crawlbase_creds.txt"
URL_FILE = "newegg_urls.txt"
OUTPUT_DIR = os.path.join("..", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "listme_newegg.txt")
SUCCESS_FILE = os.path.join(OUTPUT_DIR, "normalizedneweggurls.txt")
FAILED_FILE = os.path.join(OUTPUT_DIR, "failedneweggurls.txt")
NEWEGG_DIR = os.path.join(OUTPUT_DIR, "newegg")
CACHE_DIR = os.path.join(NEWEGG_DIR, "cache")

delay_between_requests = 1
CACHE_EXPIRATION = 12 * 3600  # 12 hours

# A Newegg item number in the URL path: /p/<ITEM>. Exclude /p/pl (the product
# LIST / search results page). Item numbers look like N82E16814932608 (1st-party),
# 9SIA... (marketplace), or hyphenated global codes like 2WC-000D-000R6.
ITEM_IN_PATH = re.compile(r"/p/(?!pl(?:[/?]|$))([A-Za-z0-9][A-Za-z0-9\-]{3,})", re.I)
ITEM_IN_QUERY = re.compile(r"[?&]Item=([A-Za-z0-9\-]+)", re.I)


def load_api_token(filename: str) -> str:
    try:
        with open(filename, "r") as f:
            token = f.readline().strip()
        if not token:
            print(f"Error: {filename} is empty or token not found.")
            sys.exit(1)
        return token
    except Exception as e:
        print(f"Error reading token from {filename}: {e}")
        sys.exit(1)


def load_urls_from_file(filename: str) -> list:
    try:
        with open(filename, "r") as f:
            urls = [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
        if not urls:
            print(f"Error: No URLs found in {filename}.")
            sys.exit(1)
        return urls
    except Exception as e:
        print(f"Error reading URLs from {filename}: {e}")
        sys.exit(1)


def sanitize_filename(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def get_cache_filepath(url: str) -> str:
    return os.path.join(CACHE_DIR, sanitize_filename(url) + ".json")


def load_cached_response(url: str):
    path = get_cache_filepath(url)
    if not os.path.exists(path):
        print("CACHE MISS")
        return None
    try:
        with open(path, "r") as f:
            cached = json.load(f)
        if time.time() - cached.get("timestamp", 0) < CACHE_EXPIRATION:
            print("CACHE HIT")
            return {
                "status_code": cached.get("status_code"),
                "body": cached.get("body", "").encode("utf-8"),
            }
    except Exception as e:
        print(f"Error loading cache for {url}: {e}")
    print("CACHE MISS")
    return None


def save_cached_response(url: str, res: dict) -> None:
    path = get_cache_filepath(url)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = res.get("body", b"")
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError:
            body_str = body.decode("utf-8", errors="ignore")
        cached = {
            "url": url,
            "status_code": res.get("status_code"),
            "body": body_str,
            "timestamp": time.time(),
        }
        with open(path, "w") as f:
            json.dump(cached, f)
    except Exception as e:
        print(f"Error saving cache for {url}: {e}")


def extract_newegg_item(url: str):
    """Pull the Newegg item number out of a product URL, or None."""
    m = ITEM_IN_QUERY.search(url or "")
    if m:
        return m.group(1).upper()
    m = ITEM_IN_PATH.search(url or "")
    if m:
        return m.group(1).upper()
    return None


def normalize_newegg_url(url: str) -> str:
    item = extract_newegg_item(url)
    return f"https://www.newegg.com/p/{item}" if item else url


def is_product_page(url: str) -> bool:
    return bool(extract_newegg_item(url))


def scrape_newegg_with_crawlbase(url: str, api_token: str):
    cached = load_cached_response(url)
    if cached:
        return cached

    api = CrawlingAPI({"token": api_token})
    try:
        response = api.get(url, {
            "ajax_wait": "true",
            "page_wait": "3000",
            "country": "US",
        })
        if response["status_code"] == 200:
            save_cached_response(url, response)
            return response
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def _price_to_float(text):
    """Parse a price like '$59.99' / '1,299.00' -> float, or None."""
    m = re.search(r"(\d[\d,]*\.?\d*)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_price_current(li):
    """Newegg renders price as <li class=price-current><strong>1,299</strong>
    <sup>.99</sup></li>. Combine the dollars + cents into a float, or None."""
    if not li:
        return None
    strong = li.find("strong")
    sup = li.find("sup")
    if strong:
        dollars = strong.get_text(strip=True).replace(",", "")
        cents = (sup.get_text(strip=True).lstrip(".") if sup else "") or "00"
        try:
            return float(f"{dollars}.{cents}")
        except ValueError:
            pass
    return _price_to_float(li.get_text())


def extract_items_from_browse_page(html: str) -> list:
    """All Newegg item numbers linked from a search/category page."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        item = extract_newegg_item(a.get("href", ""))
        if item and item not in seen:
            seen.add(item)
            items.append(item)
    return items


def extract_item_prices_from_browse_page(html: str) -> dict:
    """Map item number -> price for cards on a search/category page. Items whose
    price can't be read are absent (callers treat absent as 'let through')."""
    soup = BeautifulSoup(html, "html.parser")
    prices = {}
    for cell in soup.select("div.item-cell, div.item-container"):
        a = cell.select_one("a.item-title") or cell.find("a", href=True)
        if not a:
            continue
        item = extract_newegg_item(a.get("href", ""))
        if not item or item in prices:
            continue
        p = _parse_price_current(cell.select_one("li.price-current"))
        if p is not None:
            prices[item] = p
    return prices


def extract_newegg_details(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    item = extract_newegg_item(url)

    title_el = soup.select_one("h1.product-title") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "N/A"

    price_el = soup.select_one("li.price-current") or soup.select_one(".product-price li.price-current")
    price_val = _parse_price_current(price_el)
    price = f"{price_val:.2f}" if price_val is not None else "N/A"

    img_el = soup.select_one("img.product-view-img-original") or soup.find("img")
    image_url = img_el.get("src") if img_el else "N/A"

    return {
        "newegg_item": item,
        "title": title,
        "price": price,
        "image_url": image_url,
        "url": normalize_newegg_url(url),
    }


def price_in_range(price, min_price, max_price) -> bool:
    """True if price clears the floor and is under the ceiling. A price of None
    (couldn't be read) is let through, matching the rest of the pipeline."""
    if price is None:
        return True
    if min_price > 0 and price < min_price:
        return False
    if max_price > 0 and price > max_price:
        return False
    return True


def save_to_listme_incremental(item: str):
    with open(OUTPUT_FILE, "a") as f:
        f.write(item + "\n")


def save_items_batch(items: list):
    with open(OUTPUT_FILE, "a") as f:
        for item in items:
            f.write(item + "\n")


def main():
    min_price = 0
    max_price = 0  # 0 = no ceiling
    max_urls = 0  # 0 = scrape the whole list
    for i, arg in enumerate(sys.argv):
        if arg == "--min-price" and i + 1 < len(sys.argv):
            min_price = float(sys.argv[i + 1])
        if arg == "--max-price" and i + 1 < len(sys.argv):
            max_price = float(sys.argv[i + 1])
        if arg == "--max-urls" and i + 1 < len(sys.argv):
            max_urls = int(sys.argv[i + 1])

    print("Starting incremental Newegg scraper with batch processing...")
    if min_price > 0:
        print(f"Minimum price filter: ${min_price:.0f}")
    if max_price > 0:
        print(f"Maximum price filter: ${max_price:.0f}")

    batch_manager.cleanup_files()

    api_token = load_api_token(TOKEN_FILE)
    urls = load_urls_from_file(URL_FILE)
    random.shuffle(urls)

    if max_urls > 0 and len(urls) > max_urls:
        total = len(urls)
        urls = urls[:max_urls]
        print(f"Sampling {max_urls} of {total} URLs this run (random subset)")
    else:
        print(f"Randomized scraping order for {len(urls)} URLs")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(NEWEGG_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    open(OUTPUT_FILE, "w").close()

    successful_urls = []
    failed_urls = []
    total_items_extracted = 0

    print(f"Processing {len(urls)} URLs...")

    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}] Processing: {url}")

        response = scrape_newegg_with_crawlbase(url, api_token)

        if response and response["status_code"] == 200:
            html = response["body"].decode("utf-8")

            if is_product_page(url):
                details = extract_newegg_details(html, url)

                if details.get("newegg_item"):
                    if (min_price > 0 or max_price > 0) and details.get("price") and details["price"] != "N/A":
                        try:
                            p = float(details["price"])
                            if not price_in_range(p, min_price, max_price):
                                bounds = f"${min_price:.0f}-{max_price:.0f}" if max_price > 0 else f">=${min_price:.0f}"
                                print(f"✗ Skipped (${p:.2f} outside {bounds}): {details['title'][:50]}...")
                                continue
                        except ValueError:
                            pass  # can't parse price, let it through

                    with open(os.path.join(NEWEGG_DIR, f"{details['newegg_item']}.json"), "w") as f:
                        json.dump(details, f, indent=2)

                    batch_manager.add_scraped_item(details["url"], details)
                    save_to_listme_incremental(details["newegg_item"])

                    successful_urls.append(normalize_newegg_url(url))
                    total_items_extracted += 1
                    print(f"✓ Product page scraped: {details['title'][:50]}...")
                    print(f"  Item: {details['newegg_item']}, Price: ${details.get('price', 'N/A')}")
            else:
                items = extract_items_from_browse_page(html)

                # Scrape-time price gate: Newegg search/deal/best-seller pages
                # carry opaque N= facet ids we can't build generically, so enforce
                # the floor AND ceiling here from each card's listed price. Items
                # whose price can't be read are let through (parity with the
                # product-page gate).
                if items and (min_price > 0 or max_price > 0):
                    card_prices = extract_item_prices_from_browse_page(html)
                    before = len(items)
                    items = [it for it in items
                             if price_in_range(card_prices.get(it), min_price, max_price)]
                    skipped = before - len(items)
                    if skipped:
                        bounds = f"${min_price:.0f}-{max_price:.0f}" if max_price > 0 else f"below ${min_price:.0f}"
                        print(f"  Price gate: skipped {skipped}/{before} card(s) outside {bounds}")

                if items:
                    print(f"✓ Browse page: Found {len(items)} products")
                    print(f"  Items: {', '.join(items[:5])}{'...' if len(items) > 5 else ''}")
                    save_items_batch(items)
                    for it in items:
                        product_data = {
                            "newegg_item": it,
                            "url": f"https://www.newegg.com/p/{it}",
                            "source": "browse_page",
                        }
                        batch_manager.add_scraped_item(product_data["url"], product_data)
                    successful_urls.append(url)
                    total_items_extracted += len(items)
                else:
                    print("✗ Browse page: No products found")
                    failed_urls.append(url)
        else:
            failed_urls.append(url)
            print("✗ Failed to scrape")

        if idx < len(urls):
            time.sleep(delay_between_requests)

    with open(SUCCESS_FILE, "w") as f:
        for url in successful_urls:
            f.write(url + "\n")
    with open(FAILED_FILE, "w") as f:
        for url in failed_urls:
            f.write(url + "\n")

    status = batch_manager.get_status()
    print("\n" + "=" * 50)
    print("SCRAPING COMPLETE")
    print(f"Successfully processed: {len(successful_urls)} URLs")
    print(f"Failed: {len(failed_urls)} URLs")
    print(f"Total items extracted: {total_items_extracted}")
    print(f"Items ready for upload: {status['items_pending'] if status else 0}")
    print("=" * 50)


if __name__ == "__main__":
    main()
