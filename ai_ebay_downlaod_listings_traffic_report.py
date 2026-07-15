"""
eBay Listings Traffic Report Download (Playwright)
Goes to the Seller Hub traffic page and clicks the download button
for the active listings traffic report.

Uses a persistent Playwright profile so eBay login is remembered.

Usage:
    python ai_ebay_downlaod_listings_traffic_report.py
"""

import os
import time
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser, _is_bot_blocked, _wait_for_captcha

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')


def download_listings_traffic_report():
    """
    1. Go to Seller Hub traffic page
    2. Click the download active listings traffic report button
    3. Wait for download to complete
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = launch_ebay_browser(p)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to traffic page
            url = "https://www.ebay.com/sh/performance/traffic"
            log.info(f"Opening {url}")
            page.goto(url, wait_until="load", timeout=60000)

            # Handle bot detection / CAPTCHA
            if _is_bot_blocked(page):
                log.warning("Bot detection on traffic page, waiting for CAPTCHA...")
                _wait_for_captcha(page)
                # Retry navigation after CAPTCHA
                page.goto(url, wait_until="load", timeout=60000)
                time.sleep(3)

            # Check if redirected to login
            if "signin" in page.url.lower():
                log.warning("Not logged in. Please log in manually in the browser window.")
                log.warning("After logging in, re-run this script. Your session will be remembered.")
                page.wait_for_url("**/sh/**", timeout=120000)
                log.info("Login detected, continuing...")

            # Wait for page to fully render
            time.sleep(5)

            # 2. Click the download button
            log.info("Looking for download active listings traffic report button...")

            download_btn = page.locator('[aria-label="Download active listings traffic report"]').first
            if not download_btn.is_visible(timeout=10000):
                # Fallback selectors
                download_btn = page.locator('button[aria-label*="Download"][aria-label*="traffic"], button[aria-label*="download"][aria-label*="traffic"]').first

            if not download_btn.is_visible(timeout=5000):
                ss = os.path.join(DOWNLOAD_DIR, f"traffic_no_btn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss, full_page=True)
                log.error(f"Could not find download button. Screenshot: {ss}")
                raise RuntimeError("Download button not found")

            download_btn.scroll_into_view_if_needed()

            # 3. Click and wait for download
            log.info("Clicking download button...")
            with page.expect_download(timeout=1800000) as download_info:  # 30 min timeout
                download_btn.click()

            download = download_info.value
            log.info(f"Download started: {download.suggested_filename}")

            # Save with the original eBay filename
            save_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
            download.save_as(save_path)
            log.info(f"Report saved: {save_path}")
            return save_path

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = os.path.join(DOWNLOAD_DIR, f"traffic_error_{ts}.png")
            try:
                page.screenshot(path=ss_path)
                log.info(f"Screenshot saved: {ss_path}")
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


if __name__ == "__main__":
    download_listings_traffic_report()
