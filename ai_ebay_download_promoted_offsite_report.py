"""
eBay Promoted Offsite Listing Report Download (Playwright)
Goes to the Promoted Offsite campaign, clicks Generate Report,
clicks Generate, then downloads the report when ready.

Uses a persistent Playwright profile so eBay login is remembered.

Usage:
    python ai_ebay_download_promoted_offsite_report.py
"""

import os
import sys
import logging
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

DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
CAMPAIGN_ID = "159005538019"


def download_promoted_offsite_report(campaign_id=CAMPAIGN_ID):
    """
    1. Go to campaign dashboard (listings tab)
    2. Click Generate Report
    3. Click Generate
    4. Wait for report, download it
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = launch_ebay_browser(p)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to campaign dashboard listings tab
            url = f"https://www.ebay.com/sh/ads/dashboard/campaign/{campaign_id}?tab=listings"
            log.info(f"Opening {url}")
            page.goto(url, wait_until="load", timeout=60000)

            # Check if redirected to login
            if "signin" in page.url.lower():
                log.warning("Not logged in. Please log in manually in the browser window.")
                log.warning("After logging in, re-run this script. Your session will be remembered.")
                page.wait_for_url("**/sh/ads/**", timeout=120000)
                log.info("Login detected, continuing...")

            # 2. Click "Generate Report"
            log.info("Looking for Generate Report button...")
            report_btn = page.get_by_role("button", name="Generate Report")
            if not report_btn.is_visible(timeout=5000):
                report_btn = page.locator("button:has-text('Generate Report'), button:has-text('Generate report')").first

            report_btn.scroll_into_view_if_needed()
            report_btn.click()
            log.info("Clicked Generate Report")
            page.wait_for_timeout(3000)

            # Screenshot the popup
            ss_popup = os.path.join(DOWNLOAD_DIR, f"po_popup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_popup, full_page=True)
            log.info(f"Popup screenshot: {ss_popup}")

            # 3. Click "Generate" button in the popup
            log.info("Clicking Generate in popup...")
            generate_btn = None

            dialog_btn = page.locator("div[role='dialog'] button:has-text('Generate')").first
            if dialog_btn.is_visible(timeout=3000):
                generate_btn = dialog_btn
            else:
                for btn_text in ["Generate", "Download", "Export", "Submit"]:
                    candidates = page.locator(f"button:has-text('{btn_text}')").all()
                    for btn in candidates:
                        text = btn.inner_text().strip()
                        if text == btn_text:
                            generate_btn = btn
                            break
                    if generate_btn:
                        break

            if not generate_btn:
                log.error("Could not find Generate button in popup")
                raise RuntimeError("No Generate button found -- check screenshot")

            generate_btn.click()
            log.info("Clicked Generate, waiting for report to be ready...")
            page.wait_for_timeout(5000)

            # Screenshot after clicking generate
            ss_after = os.path.join(DOWNLOAD_DIR, f"po_after_generate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_after, full_page=True)
            log.info(f"Post-generate screenshot: {ss_after}")

            # 4. Wait for Download button/link and download the file
            download_clicked = False
            for attempt in range(360):  # Try for up to 30 minutes
                for selector in [
                    "a:has-text('Download')",
                    "button:has-text('Download')",
                    "a[download]",
                    "a:has-text('download')",
                    "button:has-text('download')",
                    "a[href*='download']",
                    "a[href*='.csv']",
                    "a[href*='report']",
                ]:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=1000):
                        log.info(f"Found download element: {selector}")
                        try:
                            with page.expect_download(timeout=30000) as download_info:
                                loc.click()
                            download = download_info.value
                            now = datetime.now()
                            date_part = now.strftime("%m_%d_%Y, %H_%M")
                            today = now.strftime("%Y%m%d")
                            filename = f"Promoted offsite - {date_part}_Listing_{today}.csv"
                            save_path = os.path.join(DOWNLOAD_DIR, filename)
                            download.save_as(save_path)
                            log.info(f"Report saved: {save_path}")
                            download_clicked = True
                            return save_path
                        except Exception as dl_err:
                            log.warning(f"Download attempt failed with {selector}: {dl_err}")
                            continue

                log.info(f"Waiting for download link... (attempt {attempt + 1}/360)")
                page.wait_for_timeout(5000)

            if not download_clicked:
                ss_final = os.path.join(DOWNLOAD_DIR, f"po_no_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss_final, full_page=True)
                log.error(f"No download link found. Screenshot: {ss_final}")
                return None

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = os.path.join(DOWNLOAD_DIR, f"po_screenshot_error_{ts}.png")
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
    download_promoted_offsite_report()
