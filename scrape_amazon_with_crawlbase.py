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
        except:
            body_str = ""
        to_cache = {
            "timestamp": time.time(),
            "status_code": res.get("status_code"),
            "body": body_str,
        }
        with open(path, "w") as f:
            json.dump(to_cache, f)
    except Exception as e:
        print(f"Error saving cache for {url}: {e}")


def add_pg2_to_bestseller(urls):
    original_urls = list(urls)
    for url in original_urls:
        if "Best-Sellers" in url:
            urls.append(url + "?pg=2")
    return urls


def scrape_random_amazon_pages(
    num_pages: int, api_token: str, source_urls: list[str]
) -> tuple[list[str], list[str], list[str]]:
    all_asins = []
    successful_urls = []
    failed_urls = []
    api = CrawlingAPI({"token": api_token})

    os.makedirs(AMAZON_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(str(len(source_urls)))
    urls_to_scrape = random.sample(source_urls, min(num_pages, len(source_urls)))
    urls_to_scrape = add_pg2_to_bestseller(urls_to_scrape)

    for index, url in enumerate(urls_to_scrape):
        try:
            res = load_cached_response(url)
            if res is None:
                print("Cache Miss")
                url_lower = url.lower()
                if "best-sellers" in url_lower:
                    print(f"amazon-best-sellers: {url}")
                    res = api.get(url, {"scraper": "amazon-best-sellers"})
                elif any(
                    p in url_lower
                    for p in [
                        "/s?",
                        "/s/",
                        "search",
                        "s?k=",
                        "i=bazaar",
                    ]
                ):
                    print(f"amazon-serp: {url}")
                    res = api.get(url, {"scraper": "amazon-serp"})
                elif any(
                    p in url_lower
                    for p in [
                        "movers-and-shakers",
                        "lightning_deals",
                        "goldbox",
                        "deals",
                        "events",
                        "haul",
                        "fmc",
                        "node=",
                        "ishaul=1",
                    ]
                ):
                    print(f"generic: {url}")
                    res = api.get(url, {"render": "true", "device": "desktop"})
                elif "new-releas" in url:
                    print(f"amazon-new-releases: {url}")
                    res = api.get(url, {"scraper": "amazon-new-releases"})
                else:
                    print(f"unclassified: {url}")
                    res = api.get(url, {"render": "true", "device": "desktop"})
                save_cached_response(url, res)

            if res.get("status_code") != 200:
                print(f"Error scraping {url}, Status: {res.get('status_code')}")
                failed_urls.append(url)
                continue

            successful_urls.append(url)
            body_decoded = res["body"].decode("utf-8")

            if any(
                key in url.lower()
                for key in [
                    "lightning_deals",
                    "goldbox",
                    "movers-and-shakers",
                    "node=",
                    "ishaul=1",
                    "events",
                    "haul",
                    "fmc",
                    "deals",
                ]
            ):
                soup = BeautifulSoup(body_decoded, "html.parser")
                for tag in soup.select("[data-asin]"):
                    asin = tag.get("data-asin")
                    if asin and len(asin) == 10 and asin not in all_asins:
                        all_asins.append(asin)
                        print(f"Included {asin} from rendered page")
            else:
                data = json.loads(body_decoded)
                products = data.get("body", {}).get("products", [])
                for prod in products:
                    asin = prod.get("asin")
                    rating_str = prod.get("customerReview", "")
                    rating_val = extract_rating_float(rating_str)
                    if asin and rating_val >= 4.5 and asin not in all_asins:
                        all_asins.append(asin)
                        print(f"Included {asin} with rating {rating_val}")
        except Exception as e:
            print(f"Exception processing {url}: {e}")
            failed_urls.append(url)
        if delay_between_requests > 0 and index < len(urls_to_scrape) - 1:
            time.sleep(delay_between_requests)
    return all_asins, successful_urls, failed_urls


def load_blacklist(filename: str) -> set[str]:
    try:
        with open(filename, "r") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"Error reading blacklist from {filename}: {e}")
        return set()


if __name__ == "__main__":
    token = load_api_token(TOKEN_FILE)
    urls = load_urls_from_file(URL_FILE)
    number_to_scrape = len(urls) * 10 // 10
    print(f"number_to_srape={number_to_scrape}")
    final_asins, success_urls, fail_urls = scrape_random_amazon_pages(
        number_to_scrape, token, urls
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load blacklist and filter ASINs
    blacklist = load_blacklist(BLACKLIST_FILE)
    filtered_asins = [asin for asin in final_asins if asin not in blacklist]

    if filtered_asins:
        with open(OUTPUT_FILE, "w") as f:
            for asin in filtered_asins:
                f.write(asin + "\n")
        print(f"Saved {len(filtered_asins)} ASINs to {OUTPUT_FILE}")
    else:
        print("No ASINs collected (all filtered by blacklist or none found).")

    with open(SUCCESS_FILE, "w") as f:
        for url in success_urls:
            f.write(url + "\n")

    with open(FAILED_FILE, "w") as f:
        for url in fail_urls:
            f.write(url + "\n")

    print(f"Saved {len(success_urls)} successful and {len(fail_urls)} failed URLs.")
