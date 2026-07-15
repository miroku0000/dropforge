"""
eBay Ads Report Automation (Playwright)
Connects to your running Chrome via CDP or launches a separate browser
with a persistent profile. Never kills your existing browser.

First run: you'll need to log in to eBay manually. After that, the
persistent profile remembers your session.

Usage:
    python ebay_ads_report_automation.py                          # 14-day report
    python ebay_ads_report_automation.py ebay_ads_report_7days    # 7-day
    python ebay_ads_report_automation.py ebay_ads_report_30days   # 30-day
"""

import time
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
CAMPAIGN_ID = "12402748019"


def generate_report(campaign_id=CAMPAIGN_ID, days_back=14):
    """
    Open campaign dashboard -> click Generate Report -> select date range -> Generate.
    Uses a persistent Playwright profile so eBay login is remembered.
    Returns the path to the downloaded file, or None.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with sync_playwright() as p:
        # Use persistent context -- keeps cookies/login between runs
        # This launches a SEPARATE Chromium, does NOT touch your Chrome
        context = launch_ebay_browser(p)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to campaign listings tab
            url = f"https://www.ebay.com/sh/ads/dashboard/campaign/{campaign_id}?tab=listings"
            log.info(f"Opening {url}")
            page.goto(url, wait_until="load", timeout=60000)

            # Check if we got redirected to login
            if "signin" in page.url.lower():
                log.warning("Not logged in to eBay. Please log in manually in the browser window.")
                log.warning("After logging in, re-run this task. Your session will be remembered.")
                page.wait_for_url("**/sh/ads/**", timeout=120000)  # Wait up to 2 min for manual login
                log.info("Login detected, continuing...")

            # 2. Click "Generate Report"
            log.info("Looking for Generate Report button...")
            report_btn = page.get_by_role("button", name="Generate Report")

            # Fallback: try other selectors
            if not report_btn.is_visible(timeout=5000):
                report_btn = page.locator("button:has-text('Generate Report'), button:has-text('Generate report')").first

            report_btn.scroll_into_view_if_needed()
            report_btn.click()
            log.info("Clicked Generate Report")
            page.wait_for_timeout(2000)

            # 3. Take screenshot of the popup so we can see what's there
            page.wait_for_timeout(2000)
            ss_popup = os.path.join(DOWNLOAD_DIR, f"popup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_popup, full_page=True)
            log.info(f"Popup screenshot saved: {ss_popup}")

            # Also dump the popup HTML to help debug
            html_dump = os.path.join(DOWNLOAD_DIR, f"popup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(html_dump, 'w', encoding='utf-8') as f:
                # Try to get dialog/overlay content
                dialogs = page.locator("div[role='dialog'], div[class*='modal'], div[class*='overlay'], div[class*='popup'], div[class*='drawer']").all()
                if dialogs:
                    for i, d in enumerate(dialogs):
                        f.write(f"<!-- Dialog {i} -->\n")
                        f.write(d.inner_html())
                        f.write("\n\n")
                else:
                    f.write(page.content())
            log.info(f"Popup HTML saved: {html_dump}")

            # 3b. Select date range in popup
            date_text = f"Past {days_back} days"
            log.info(f"Selecting '{date_text}'...")

            # Try multiple text variations
            date_variations = [
                f"Past {days_back} days",
                f"Past {days_back} Days",
                f"Last {days_back} days",
                f"Last {days_back} Days",
                f"{days_back} days",
                f"{days_back} Days",
            ]

            clicked_date = False
            for variant in date_variations:
                loc = page.locator(f"text='{variant}'").first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    log.info(f"Selected date range: '{variant}'")
                    clicked_date = True
                    break

            if not clicked_date:
                # Try any radio/checkbox/label/span containing the number of days
                fallbacks = page.locator(f"label:has-text('{days_back}'), span:has-text('{days_back}'), div:has-text('{days_back}')").all()
                for fb in fallbacks:
                    text = fb.inner_text().strip()
                    if str(days_back) in text and ("day" in text.lower() or "past" in text.lower() or "last" in text.lower()):
                        fb.click()
                        log.info(f"Selected date range via fallback: '{text}'")
                        clicked_date = True
                        break

            if not clicked_date:
                log.warning(f"Could not find '{date_text}' -- check screenshot at {ss_popup}")

            page.wait_for_timeout(1000)

            # 4. Click "Generate" in the popup
            log.info("Clicking Generate in popup...")

            # Look for Generate button inside a dialog, or a standalone Generate button
            # that is NOT the original "Generate Report" button
            generate_btn = None

            # Try dialog button first
            dialog_btn = page.locator("div[role='dialog'] button:has-text('Generate')").first
            if dialog_btn.is_visible(timeout=3000):
                generate_btn = dialog_btn
            else:
                # Fallback: find button whose text is exactly "Generate" or "Download"
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
                log.error("Could not find Generate/Download button in popup")
                raise RuntimeError("No Generate button found -- check screenshot")

            # Click Generate -- this may NOT trigger an immediate download.
            # eBay often generates the report server-side, then shows a
            # "Download" link/button once it's ready.
            generate_btn.click()
            log.info("Clicked Generate, waiting for report to be ready...")

            # Wait for the report to be generated and a Download button/link to appear
            page.wait_for_timeout(5000)

            # Take screenshot to see current state
            ss_after = os.path.join(DOWNLOAD_DIR, f"after_generate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss_after, full_page=True)
            log.info(f"Post-generate screenshot: {ss_after}")

            # Now look for a Download button/link that appears after generation
            download_clicked = False
            for attempt in range(360):  # Try for up to 30 minutes
                # Look for download link/button
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
                        # Set up download listener and click
                        try:
                            with page.expect_download(timeout=30000) as download_info:
                                loc.click()
                            download = download_info.value
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"automagical_Listing_ads_report_{days_back}d_{ts}.csv"
                            save_path = os.path.join(DOWNLOAD_DIR, filename)
                            download.save_as(save_path)
                            log.info(f"Report saved: {save_path}")
                            download_clicked = True
                            return save_path
                        except Exception as dl_err:
                            log.warning(f"Download attempt failed with {selector}: {dl_err}")
                            continue

                log.info(f"Waiting for download link... (attempt {attempt + 1}/12)")
                page.wait_for_timeout(5000)

            if not download_clicked:
                # Final screenshot
                ss_final = os.path.join(DOWNLOAD_DIR, f"no_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss_final, full_page=True)
                log.error(f"No download link found after waiting. Screenshot: {ss_final}")
                return None

        except Exception as e:
            log.error(f"Failed: {e}")
            # Take screenshot for debugging
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = os.path.join(DOWNLOAD_DIR, f"screenshot_error_{ts}.png")
            try:
                page.screenshot(path=ss_path)
                log.info(f"Screenshot saved: {ss_path}")
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


# ---------------------------------------------------------------------------
# Named tasks
# ---------------------------------------------------------------------------

TASKS = {
    "ebay_ads_report": {
        "name": "eBay Ads Report (14 days)",
        "description": "Generate eBay promoted listings report for the past 14 days",
        "run": lambda: generate_report(days_back=14),
    },
    "ebay_ads_report_7days": {
        "name": "eBay Ads Report (7 days)",
        "description": "Generate eBay promoted listings report for the past 7 days",
        "run": lambda: generate_report(days_back=7),
    },
    "ebay_ads_report_14days": {
        "name": "eBay Ads Report (14 days)",
        "description": "Generate eBay promoted listings report for the past 14 days",
        "run": lambda: generate_report(days_back=14),
    },
    "ebay_ads_report_30days": {
        "name": "eBay Ads Report (30 days)",
        "description": "Generate eBay promoted listings report for the past 30 days",
        "run": lambda: generate_report(days_back=30),
    },
}


def run_task(name):
    task = TASKS.get(name)
    if not task:
        print(f"Unknown task: {name}")
        print(f"Available: {', '.join(TASKS.keys())}")
        return None
    log.info(f"Running task: {task['name']}")
    return task["run"]()


if __name__ == "__main__":
    task_name = sys.argv[1] if len(sys.argv) > 1 else "ebay_ads_report"
    run_task(task_name)
