"""
Count current active eBay listings.

Usage:
    python ai_ebay_count_current_listings.py
"""

import os
import re
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')


def count_listings():
    with sync_playwright() as p:
        context = launch_ebay_browser(p, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto("https://www.ebay.com/sh/lst/active", wait_until="load", timeout=60000)
            if "signin" in page.url.lower():
                page.wait_for_url("**/sh/lst/**", timeout=120000)
            page.wait_for_timeout(3000)

            # Look for "Manage active listings(2,533)" in page text
            body = page.locator("body").inner_text()
            match = re.search(r'active\s+listings\s*\(\s*([\d,]+)\s*\)', body, re.IGNORECASE)
            if match:
                print(match.group(1).replace(',', ''))
            else:
                # Fallback: try other patterns
                match = re.search(r'([\d,]+)\s+active', body, re.IGNORECASE)
                if match:
                    print(match.group(1).replace(',', ''))
                else:
                    print("0")
        finally:
            context.close()


if __name__ == "__main__":
    count_listings()
