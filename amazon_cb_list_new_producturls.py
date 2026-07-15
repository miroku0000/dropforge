import requests
from bs4 import BeautifulSoup

# Read Crawlbase token from file
with open("crawlbase_creds.txt", "r") as f:
    CRAWLBASE_TOKEN = f.read().strip()

CRAWLBASE_URL = "https://api.crawlbase.com"
START_URL = "https://www.amazon.com/gp/new-releases"


def crawl_url(target_url):
    params = {
        "token": CRAWLBASE_TOKEN,
        "url": target_url,
        "render": "false",  # Set to 'true' if JS rendering is needed
    }
    response = requests.get(CRAWLBASE_URL, params=params)
    response.raise_for_status()
    return response.text


def extract_category_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.select('a[href*="/gp/new-releases/"]'):
        href = a.get("href")
        if href and href.startswith("/gp/new-releases/"):
            full_url = "https://www.amazon.com" + href.split("?")[0]
            links.add(full_url)
    return links


def crawl_categories(start_url, visited=None):
    if visited is None:
        visited = set()
    if start_url in visited:
        return visited
    visited.add(start_url)
    try:
        html = crawl_url(start_url)
        links = extract_category_links(html)
        for link in links:
            if link not in visited:
                crawl_categories(link, visited)
    except Exception as e:
        print(f"Error crawling {start_url}: {e}")
    return visited


if __name__ == "__main__":
    all_category_urls = crawl_categories(START_URL)
    for url in sorted(all_category_urls):
        print(url)
