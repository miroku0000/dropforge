"""
eBay Delete Zero-View Listings (Playwright)
Goes to active listings, removes rows with views using JavaScript,
then selects all remaining (zero-view) listings and deletes them.
Deletes up to 200 listings per run.

Usage:
    python ai_ebay_delete_zero_view_listings.py
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

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
ACTIVE_LISTINGS_URL = "https://www.ebay.com/sh/lst/active"


def delete_zero_view_listings():
    """
    1. Go to active listings (200 per page)
    2. Run JS to remove rows that have views
    3. Select all remaining (zero-view) listings
    4. Click delete
    5. Confirm deletion
    """
    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900})

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to active listings
            log.info(f"Opening {ACTIVE_LISTINGS_URL}")
            page.goto(ACTIVE_LISTINGS_URL, wait_until="load", timeout=60000)

            # Check login
            if "signin" in page.url.lower():
                log.warning("Please log in to eBay in the browser window.")
                page.wait_for_url("**/sh/lst/**", timeout=120000)
                log.info("Login detected, continuing...")

            page.wait_for_timeout(5000)

            # Set items per page to 200 by navigating with the parameter
            log.info("Setting items per page to 200...")
            page.goto(ACTIVE_LISTINGS_URL + "?limit=200", wait_until="load", timeout=60000)
            page.wait_for_timeout(5000)

            # Screenshot before filtering
            ss1 = os.path.join(DOWNLOAD_DIR, f"zero_view_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss1, full_page=False)
            log.info(f"Before screenshot: {ss1}")

            # Count total rows before filtering
            total_before = page.evaluate("""
                document.querySelectorAll('tr[data-testid], table tbody tr').length
            """)
            log.info(f"Total listing rows before filtering: {total_before}")

            # 2. Run JavaScript to remove rows that have views (non-zero)
            log.info("Removing listings with views...")
            removed_count = page.evaluate("""
                (() => {
                    let removed = 0;
                    $($("tr > td > div .column-views > .fake-link"))
                        .filter(function(index) {
                            return $(this).text().split("Link")[0] != "0";
                        })
                        .parent().parent().parent().parent().remove();
                    // Count remaining rows
                    let remaining = $("tr > td > div .column-views > .fake-link").length;
                    return { removed: arguments[0] - remaining, remaining: remaining };
                })()
            """) if False else None  # Can't pass args this way

            # Simpler approach
            page.evaluate("""
                $($("tr > td > div .column-views > .fake-link"))
                    .filter(function(index) {
                        return $(this).text().split("Link")[0] != "0";
                    })
                    .parent().parent().parent().parent().remove();
            """)
            page.wait_for_timeout(1000)

            # Count remaining rows
            remaining = page.evaluate("""
                $("tr > td > div .column-views > .fake-link").length
            """)
            log.info(f"Remaining zero-view listings: {remaining}")

            if remaining == 0:
                log.info("No zero-view listings found. Nothing to delete.")
                return 0

            # Screenshot after filtering
            ss2 = os.path.join(DOWNLOAD_DIR, f"zero_view_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss2, full_page=False)
            log.info(f"Filtered screenshot: {ss2}")

            # 3. Select all remaining listings
            log.info("Selecting all zero-view listings...")
            select_all = page.locator("input[aria-label*='Select all']").first
            if not select_all.is_visible(timeout=3000):
                select_all = page.locator("th input[type='checkbox'], .shui-dt-checkall").first

            if not select_all.is_visible(timeout=3000):
                log.error("Could not find Select all checkbox")
                raise RuntimeError("Select all not found")

            select_all.evaluate("el => el.click()")
            page.wait_for_timeout(2000)
            log.info("Selected all zero-view listings")

            # 4. Click "Actions" dropdown, then "End listings"
            log.info("Clicking Actions dropdown...")
            actions_btn = page.locator("button:has-text('Actions')").first
            actions_btn.click()
            page.wait_for_timeout(1000)

            log.info("Clicking 'End listings'...")
            end_btn = page.locator("text='End listings'").first
            end_btn.click()
            page.wait_for_timeout(3000)
            log.info("Clicked 'End listings'")

            # 5. Confirm deletion in the confirmation dialog
            log.info("Confirming deletion...")
            ss4 = os.path.join(DOWNLOAD_DIR, f"zero_view_confirm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss4, full_page=False)
            log.info(f"Confirmation dialog screenshot: {ss4}")

            confirm_btn = page.locator("button.btn--primary:has-text('End listings')").first
            if confirm_btn.is_visible(timeout=5000):
                confirm_btn.click()
                log.info("Confirmed 'End listings'!")
                page.wait_for_timeout(10000)
            else:
                log.warning("No confirmation dialog found")

            # Final screenshot
            ss5 = os.path.join(DOWNLOAD_DIR, f"zero_view_done_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss5, full_page=False)
            log.info(f"Done screenshot: {ss5}")
            log.info(f"Deleted up to {remaining} zero-view listings")
            return remaining

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"zero_view_error_{ts}.png"))
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


if __name__ == "__main__":
    delete_zero_view_listings()
