"""
eBay Suggested Priority Campaign Listing Report Download (Playwright)
Goes to the Suggested Priority campaign, clicks Generate Report,
checks the Listing report checkbox, clicks Generate, then
downloads the report when ready.

Uses a persistent Playwright profile so eBay login is remembered.

Usage:
    python ai_ebay_download_suggested_priority_report.py
"""

import os
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
CAMPAIGN_ID = "160102992019"


def download_suggested_priority_report(campaign_id=CAMPAIGN_ID):
    """
    1. Go to campaign dashboard (listings tab)
    2. Click Generate Report
    3. Check the Listing report checkbox
    4. Click Generate
    5. Wait for report, download it
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
            ss_popup = os.path.join(DOWNLOAD_DIR, f"sp_popup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_popup, full_page=True)
            log.info(f"Popup screenshot: {ss_popup}")

            # 3. Check the "Listing report" checkbox
            log.info("Looking for Listing report checkbox...")
            listing_checked = False

            listing_selectors = [
                "text='Listing report'",
                "text='Listing Report'",
                "label:has-text('Listing report')",
                "label:has-text('Listing Report')",
                "span:has-text('Listing report')",
            ]

            for selector in listing_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=2000):
                        loc.click()
                        log.info(f"Clicked Listing report option: {selector}")
                        listing_checked = True
                        break
                except Exception:
                    continue

            if not listing_checked:
                # Try finding any checkbox near "Listing" text
                checkboxes = page.locator("input[type='checkbox']").all()
                for cb in checkboxes:
                    try:
                        parent = cb.locator("..")
                        text = parent.inner_text().lower()
                        if "listing" in text:
                            cb.check()
                            log.info(f"Checked listing checkbox via parent text: {text.strip()[:50]}")
                            listing_checked = True
                            break
                    except Exception:
                        continue

            if not listing_checked:
                log.warning("Could not find Listing report checkbox -- it may already be selected")

            page.wait_for_timeout(1000)

            # 4. Click "Generate" button in the popup
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
            ss_after = os.path.join(DOWNLOAD_DIR, f"sp_after_generate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_after, full_page=True)
            log.info(f"Post-generate screenshot: {ss_after}")

            # 5. Wait for Download button/link and download the file
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
                            today = datetime.now().strftime("%Y%m%d")
                            filename = f"Suggested Priority_Listing_{today}.csv"
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
                ss_final = os.path.join(DOWNLOAD_DIR, f"sp_no_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss_final, full_page=True)
                log.error(f"No download link found. Screenshot: {ss_final}")
                return None

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"sp_screenshot_error_{ts}.png"))
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


if __name__ == "__main__":
    download_suggested_priority_report()
