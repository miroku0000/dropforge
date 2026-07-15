import json
import time
import random
import sys
import os
import re
from crawlbase import CrawlingAPI
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
from scrape_amazon_batch import batch_manager

# Make stdout/stderr tolerate Unicode glyphs on the Windows cp1252 console.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configuration
TOKEN_FILE = "crawlbase_creds.txt"
URL_FILE = "amazon_urls.txt"
OUTPUT_DIR = os.path.join("..", "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "listme.txt")
SUCCESS_FILE = os.path.join(OUTPUT_DIR, "normalizedamazonurls.txt")
FAILED_FILE = os.path.join(OUTPUT_DIR, "failedamazonurls.txt")
AMAZON_DIR = os.path.join(OUTPUT_DIR, "amazon")
CACHE_DIR = os.path.join(AMAZON_DIR, "cache")
BLACKLIST_FILE = os.path.join("..", "data", "blacklist.txt")

delay_between_requests = 1
CACHE_EXPIRATION = 12 * 3600  # 12 hours

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

def clean_url(url: str) -> str:
    return url

def load_urls_from_file(filename: str) -> list[str]:
    try:
        with open(filename, "r") as f:
            urls = [clean_url(line.strip()) for line in f if line.strip()]
        if not urls:
            print(f"Error: No URLs found in {filename}.")
            sys.exit(1)
        return urls
    except Exception as e:
        print(f"Error reading URLs from {filename}: {e}")
        sys.exit(1)

def sanitize_filename(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()

def extract_rating_float(rating_string):
    try:
        return float(rating_string.split(" out")[0])
    except:
        return 0.0

def get_cache_filepath(url: str) -> str:
    filename = sanitize_filename(url) + ".json"
    return os.path.join(CACHE_DIR, filename)

def load_cached_response(url: str) -> dict | None:
    path = get_cache_filepath(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            cached = json.load(f)
        timestamp = cached.get("timestamp", 0)
        if time.time() - timestamp < CACHE_EXPIRATION:
            print("CACHE HIT")
            body_str = cached.get("body", "")
            return {
                "status_code": cached.get("status_code"),
                "body": body_str.encode("utf-8"),
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

def extract_amazon_asin(url):
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/exec/obidos/ASIN/([A-Z0-9]{10})",
        r"/o/ASIN/([A-Z0-9]{10})",
        r"/gp/aw/d/([A-Z0-9]{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def normalize_amazon_url(url: str) -> str:
    asin = extract_amazon_asin(url)
    if asin:
        return f"https://www.amazon.com/dp/{asin}"
    else:
        return url

def scrape_amazon_with_crawlbase(url: str, api_token: str) -> dict:
    cached = load_cached_response(url)
    if cached:
        return cached

    api = CrawlingAPI({"token": api_token})
    
    try:
        response = api.get(url, {
            "ajax_wait": "true",
            "page_wait": "3000",
        })
        
        if response["status_code"] == 200:
            save_cached_response(url, response)
            return response
        else:
            return None
            
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def extract_asins_from_browse_page(html: str) -> list[str]:
    """Extract all product ASINs from an Amazon browse/category page"""
    soup = BeautifulSoup(html, "html.parser")
    asins = set()
    
    # Method 1: Look for data-asin attributes
    elements_with_asin = soup.find_all(attrs={"data-asin": True})
    for element in elements_with_asin:
        asin = element.get("data-asin", "").strip()
        if asin and len(asin) == 10:
            asins.add(asin)
    
    # Method 2: Look for ASINs in product links
    links = soup.find_all("a", href=True)
    for link in links:
        href = link.get("href", "")
        asin = extract_amazon_asin(href)
        if asin:
            asins.add(asin)
    
    # Method 3: Look in s-result-item divs (search results)
    result_items = soup.find_all("div", {"class": re.compile("s-result-item")})
    for item in result_items:
        asin = item.get("data-asin", "").strip()
        if asin and len(asin) == 10:
            asins.add(asin)
    
    # Method 4: Look in sg-col-inner divs (newer layout)
    sg_items = soup.find_all("div", {"data-component-type": "s-search-result"})
    for item in sg_items:
        asin = item.get("data-asin", "").strip()
        if asin and len(asin) == 10:
            asins.add(asin)
    
    return list(asins)

def _price_to_float(text):
    """Parse a price like '$59.99' / '59' / '1,299.00' -> float, or None."""
    m = re.search(r"(\d[\d,]*\.?\d*)", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None

def extract_asin_prices_from_browse_page(html: str) -> dict:
    """Map ASIN -> price (float) for cards on a browse/category/bestseller page.
    Covers search-result cards (a-offscreen/a-price-whole) and the p13n grid used
    by Best Sellers / Movers & Shakers (p13n-sc-price). ASINs whose price can't be
    read are simply absent (callers treat absent as 'let through')."""
    soup = BeautifulSoup(html, "html.parser")
    prices = {}
    for card in soup.find_all(attrs={"data-asin": True}):
        asin = (card.get("data-asin") or "").strip()
        if len(asin) != 10 or asin in prices:
            continue
        el = (card.find("span", class_="a-offscreen")
              or card.find("span", class_="a-price-whole")
              or card.find("span", class_=re.compile("p13n-sc-price")))
        if el:
            p = _price_to_float(el.get_text())
            if p is not None:
                prices[asin] = p
    return prices

def is_product_page(url: str) -> bool:
    """Check if URL is likely a product page"""
    return bool(extract_amazon_asin(url))

def extract_amazon_details(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract product details as before
    asin = extract_amazon_asin(url)
    
    title_element = soup.find("span", id="productTitle")
    title = title_element.get_text(strip=True) if title_element else "N/A"
    
    price_element = soup.find("span", class_="a-price-whole") or soup.find("span", class_="a-price")
    if price_element:
        price_text = price_element.get_text(strip=True)
        price = re.sub(r"[^\d.]", "", price_text)
    else:
        price = "N/A"
    
    rating_element = soup.find("span", class_="a-icon-alt")
    if rating_element:
        rating_text = rating_element.get_text(strip=True)
        rating = extract_rating_float(rating_text)
    else:
        rating = 0.0
    
    review_count_element = soup.find("span", id="acrCustomerReviewText")
    if review_count_element:
        review_text = review_count_element.get_text(strip=True)
        review_count = re.sub(r"[^\d]", "", review_text)
    else:
        review_count = "0"
    
    image_element = soup.find("img", id="landingImage") or soup.find("img", class_="a-dynamic-image")
    image_url = image_element.get("src") if image_element else "N/A"
    
    return {
        "asin": asin,
        "title": title,
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "image_url": image_url,
        "url": normalize_amazon_url(url),
    }

def save_to_listme_incremental(product_id: str):
    """Append a single product ID to listme.txt immediately"""
    with open(OUTPUT_FILE, "a") as f:
        f.write(product_id + "\n")

def save_asins_batch(asins: list[str]):
    """Save multiple ASINs to listme.txt"""
    with open(OUTPUT_FILE, "a") as f:
        for asin in asins:
            f.write(asin + "\n")

def main():
    # Parse --min-price argument
    min_price = 0
    max_urls = 0  # 0 = scrape the whole list
    for i, arg in enumerate(sys.argv):
        if arg == '--min-price' and i + 1 < len(sys.argv):
            min_price = float(sys.argv[i + 1])
        if arg == '--max-urls' and i + 1 < len(sys.argv):
            max_urls = int(sys.argv[i + 1])

    print("Starting incremental Amazon scraper with batch processing...")
    if min_price > 0:
        print(f"Minimum price filter: ${min_price:.0f}")

    # Initialize batch manager
    batch_manager.cleanup_files()

    # Load configuration
    api_token = load_api_token(TOKEN_FILE)
    urls = load_urls_from_file(URL_FILE)
    
    # Randomize the order of URLs to scrape
    random.shuffle(urls)

    # Optionally scrape only a random subset this run. This lets amazon_urls.txt
    # grow unbounded (cheap to add search terms) while bounding scrape cost: each
    # run hits a different random slice, so the whole list is covered over time.
    if max_urls > 0 and len(urls) > max_urls:
        total = len(urls)
        urls = urls[:max_urls]
        print(f"Sampling {max_urls} of {total} URLs this run (random subset)")
    else:
        print(f"Randomized scraping order for {len(urls)} URLs")
    
    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(AMAZON_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    # Clear listme.txt at start
    open(OUTPUT_FILE, "w").close()
    
    # Track results
    successful_urls = []
    failed_urls = []
    all_products = []
    total_asins_extracted = 0
    
    print(f"Processing {len(urls)} URLs...")
    
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}] Processing: {url}")
        
        # Scrape the URL
        response = scrape_amazon_with_crawlbase(url, api_token)
        
        if response and response["status_code"] == 200:
            html = response["body"].decode("utf-8")
            
            # Check if this is a product page or browse page
            if is_product_page(url):
                # Handle as product page
                details = extract_amazon_details(html, url)
                
                if details.get("asin"):
                    # Check minimum price filter
                    if min_price > 0 and details.get("price") and details["price"] != "N/A":
                        try:
                            product_price = float(details["price"])
                            if product_price < min_price:
                                print(f"✗ Skipped (${product_price:.2f} < ${min_price:.0f} min): {details['title'][:50]}...")
                                continue
                        except ValueError:
                            pass  # Can't parse price, let it through

                    # Save to individual file
                    output_file = os.path.join(AMAZON_DIR, f"{details['asin']}.json")
                    with open(output_file, "w") as f:
                        json.dump(details, f, indent=2)

                    # Add to batch queue
                    batch_manager.add_scraped_item(details["url"], details)

                    # Immediately append to listme.txt
                    save_to_listme_incremental(details["asin"])

                    successful_urls.append(normalize_amazon_url(url))
                    all_products.append(details)

                    print(f"✓ Product page scraped: {details['title'][:50]}...")
                    print(f"  ASIN: {details['asin']}, Price: ${details.get('price', 'N/A')}")
                    total_asins_extracted += 1
            else:
                # Handle as browse/category page
                asins = extract_asins_from_browse_page(html)

                # Scrape-time price gate: curated pages (Best Sellers / Movers &
                # Shakers) can't carry an rh= price filter in the URL, so enforce
                # the floor here using each card's listed price. ASINs whose price
                # can't be read are let through (parity with the product-page gate).
                if asins and min_price > 0:
                    card_prices = extract_asin_prices_from_browse_page(html)
                    before = len(asins)
                    asins = [a for a in asins
                             if card_prices.get(a) is None or card_prices[a] >= min_price]
                    skipped = before - len(asins)
                    if skipped:
                        print(f"  Price gate: skipped {skipped}/{before} card(s) below ${min_price:.0f}")

                if asins:
                    print(f"✓ Browse page: Found {len(asins)} products")
                    print(f"  ASINs: {', '.join(asins[:5])}{'...' if len(asins) > 5 else ''}")
                    
                    # Save ASINs to listme.txt
                    save_asins_batch(asins)
                    
                    # Add each ASIN to batch queue
                    for asin in asins:
                        product_data = {
                            "asin": asin,
                            "url": f"https://www.amazon.com/dp/{asin}",
                            "source": "browse_page"
                        }
                        batch_manager.add_scraped_item(product_data["url"], product_data)
                    
                    successful_urls.append(url)
                    total_asins_extracted += len(asins)
                else:
                    print(f"✗ Browse page: No products found")
                    failed_urls.append(url)
        else:
            failed_urls.append(url)
            print(f"✗ Failed to scrape")
        
        # Add delay between requests
        if idx < len(urls):
            time.sleep(delay_between_requests)
    
    # Save summary files
    with open(SUCCESS_FILE, "w") as f:
        for url in successful_urls:
            f.write(url + "\n")
    
    with open(FAILED_FILE, "w") as f:
        for url in failed_urls:
            f.write(url + "\n")
    
    # Final status
    status = batch_manager.get_status()
    print("\n" + "="*50)
    print("SCRAPING COMPLETE")
    print(f"Successfully processed: {len(successful_urls)} URLs")
    print(f"Failed: {len(failed_urls)} URLs")
    print(f"Total ASINs extracted: {total_asins_extracted}")
    print(f"Items ready for upload: {status['items_pending'] if status else 0}")
    print("="*50)

if __name__ == "__main__":
    main()