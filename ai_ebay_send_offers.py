"""
eBay Send Offers to Buyers (Playwright)
Sends offers on all eligible listings for 5% off with an extra 5% coupon.

Flow:
1. Go to active listings filtered by SIO-eligible
2. Select all listings
3. Click "Offer to buyers"
4. Enter 5% discount
5. Check "Send coupon" and select "Extra 5%"
6. Click Send

Uses a persistent Playwright profile so eBay login is remembered.

Usage:
    python ai_ebay_send_offers.py            # 5% off (default)
    python ai_ebay_send_offers.py 10         # 10% off
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
SIO_URL = "https://www.ebay.com/sh/lst/active?pill_status=sioEligible&action=search"


def send_offers(percent_off=5):
    """
    Send offers to buyers on all eligible listings.
    """
    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900})

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to SIO-eligible listings
            log.info(f"Opening SIO-eligible listings page...")
            page.goto(SIO_URL, wait_until="load", timeout=60000)

            # Check login
            if "signin" in page.url.lower():
                log.warning("Please log in to eBay in the browser window.")
                page.wait_for_url("**/sh/lst/**", timeout=120000)
                log.info("Login detected, continuing...")

            page.wait_for_timeout(5000)

            # Screenshot
            ss = os.path.join(DOWNLOAD_DIR, f"sio_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss, full_page=True)
            log.info(f"Page screenshot: {ss}")

            # 2. Select all listings - click the "select all" checkbox
            log.info("Selecting all eligible listings...")
            select_all = None
            for selector in [
                "input[data-testid='shui-dt-checkall']",
                "input.shui-dt-checkall",
                "[data-testid='shui-dt-checkall']",
                "input[aria-label*='Select all']",
                "th input[type='checkbox']",
            ]:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=2000):
                    select_all = loc
                    log.info(f"Found select all: {selector}")
                    break

            if not select_all:
                # Fallback: find by searching all checkboxes in table header
                checkboxes = page.locator("thead input[type='checkbox'], .shui-dt-checkall").all()
                if checkboxes:
                    select_all = checkboxes[0]
                    log.info("Found select all via fallback")

            if not select_all:
                log.error("Could not find 'Select all' checkbox")
                raise RuntimeError("Select all checkbox not found")

            select_all.evaluate("el => el.click()")
            page.wait_for_timeout(2000)
            log.info("Selected all listings")

            # 3. Click "Offer to buyers" button
            log.info("Looking for 'Offer to buyers' button...")
            offer_btn = None
            for selector in [
                "button:has-text('Offer to buyers')",
                "button:has-text('Offer to Buyers')",
                "button[data-testid='offerToBuyers']",
                "#offerToBuyers",
                "button:has-text('Send offer')",
                "button:has-text('Send Offer')",
            ]:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=2000):
                    offer_btn = loc
                    log.info(f"Found offer button: {selector}")
                    break

            if not offer_btn:
                # Try finding by partial text
                buttons = page.locator("button").all()
                for btn in buttons:
                    text = btn.inner_text().lower()
                    if "offer" in text and "buyer" in text:
                        offer_btn = btn
                        log.info(f"Found offer button by text: {btn.inner_text()}")
                        break

            if not offer_btn:
                log.error("Could not find 'Offer to buyers' button")
                ss2 = os.path.join(DOWNLOAD_DIR, f"sio_no_offer_btn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss2, full_page=True)
                raise RuntimeError("Offer to buyers button not found")

            offer_btn.evaluate("el => el.click()")
            page.wait_for_timeout(3000)
            log.info("Clicked 'Offer to buyers'")

            # Screenshot the offer dialog
            ss3 = os.path.join(DOWNLOAD_DIR, f"sio_dialog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss3, full_page=True)
            log.info(f"Offer dialog screenshot: {ss3}")

            # 4. Enter the discount percentage
            log.info(f"Setting discount to {percent_off}%...")
            offer_input = None
            for selector in [
                "input[name='offerAmount']",
                "input.textbox__control[name='offerAmount']",
                "[data-testid='offerAmount']",
                "input[aria-label*='offer']",
                "input[aria-label*='Offer']",
                "input[aria-label*='discount']",
                "input[aria-label*='percentage']",
            ]:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=2000):
                    offer_input = loc
                    log.info(f"Found offer input: {selector}")
                    break

            if not offer_input:
                # Fallback: find any visible text input in a dialog
                dialog_inputs = page.locator("div[role='dialog'] input[type='text'], .lightbox-dialog input[type='text']").all()
                for inp in dialog_inputs:
                    if inp.is_visible():
                        offer_input = inp
                        log.info("Found offer input via dialog fallback")
                        break

            if not offer_input:
                log.error("Could not find offer amount input")
                raise RuntimeError("Offer amount input not found")

            offer_input.click(click_count=3)
            offer_input.fill(str(percent_off))
            page.wait_for_timeout(1000)
            log.info(f"Entered {percent_off}% discount")

            # 5. Check "Send coupon" checkbox and select "Extra 5%"
            log.info("Looking for 'Send coupon' option...")
            coupon_checkbox = None
            for selector in [
                "#checkbox__send-coupon",
                "input[id*='send-coupon']",
                "input[name*='coupon']",
                "label:has-text('coupon')",
                "span:has-text('coupon')",
            ]:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=2000):
                    coupon_checkbox = loc
                    log.info(f"Found coupon checkbox: {selector}")
                    break

            if coupon_checkbox:
                coupon_checkbox.evaluate("el => el.click()")
                page.wait_for_timeout(1000)
                log.info("Checked 'Send coupon'")

                # Select "Extra 5%" coupon option
                log.info("Selecting 'Extra 5%' coupon...")
                # Click the coupon value selector
                coupon_selector = page.locator(".se-field-card__content-value").first
                if coupon_selector.is_visible(timeout=2000):
                    coupon_selector.evaluate("el => el.click()")
                    page.wait_for_timeout(1000)

                # Click "Extra 5%" option
                extra5 = page.locator(f"text='Extra {percent_off}%'").first
                if not extra5.is_visible(timeout=2000):
                    extra5 = page.locator(f"span:has-text('Extra {percent_off}')").first
                if extra5.is_visible(timeout=2000):
                    extra5.evaluate("el => el.click()")
                    page.wait_for_timeout(1000)
                    log.info(f"Selected 'Extra {percent_off}%' coupon")
                else:
                    log.warning(f"Could not find 'Extra {percent_off}%' option")
            else:
                log.warning("Could not find coupon checkbox - sending without coupon")

            page.wait_for_timeout(1000)

            # Screenshot before sending
            ss4 = os.path.join(DOWNLOAD_DIR, f"sio_before_send_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss4, full_page=True)
            log.info(f"Pre-send screenshot: {ss4}")

            # 6. Click the "Send offers" submit button
            log.info("Clicking 'Send offers' button...")
            send_btn = page.locator("button[data-testid='submit-button']").first
            if not send_btn.is_visible(timeout=5000):
                log.error("Could not find submit button")
                raise RuntimeError("Send button not found")

            send_btn.click()
            log.info("Clicked Send offers!")

            # Wait for dialog to close
            page.wait_for_timeout(10000)

            # Screenshot after send
            ss5 = os.path.join(DOWNLOAD_DIR, f"sio_after_send_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss5, full_page=True)
            log.info(f"After-send screenshot: {ss5}")

            # Wait 30 seconds then take final verification screenshot
            log.info("Waiting 30 seconds before final verification...")
            page.wait_for_timeout(30000)

            # Reload the SIO-eligible page to verify
            page.goto(SIO_URL, wait_until="load", timeout=60000)
            page.wait_for_timeout(5000)

            ss6 = os.path.join(DOWNLOAD_DIR, f"sio_verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss6, full_page=True)
            log.info(f"Verification screenshot (reloaded page): {ss6}")
            log.info(f"Offers sent at {percent_off}% off on all eligible listings!")

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"sio_error_{ts}.png"))
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


if __name__ == "__main__":
    pct = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    send_offers(pct)
