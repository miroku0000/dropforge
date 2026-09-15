"""
eBay Send Offers to Buyers (Playwright)
Sends offers on all SIO-eligible listings for 5% off.

Flow:
1. Go to active listings filtered by SIO-eligible
2. Select all listings (aborts cleanly if 0 eligible)
3. Click "Offer to buyers"
4. Enter 5% discount
5. Ensure "Send automated offer" is enabled (eBay retired the old
   "Send coupon / Extra 5%" control -- it no longer exists in the dialog)
6. Click Send

Uses a persistent Playwright profile so eBay login is remembered. Auto-logs in
from credentials.txt when eBay bounces to sign-in, and pushes a phone alert via
notify.py on failure / suspicious 0-eligible so this revenue step can't fail
silently.

Usage:
    python ai_ebay_send_offers.py            # 5% off (default)
    python ai_ebay_send_offers.py 10         # 10% off
"""

import os
import sys
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser, needs_signin, wait_for_signin

try:
    from notify import send as notify_send
except Exception:  # notify is optional; never let its absence break the run
    def notify_send(title, message, priority="default", tags=None):
        return False

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


def _safe_shot(page, name):
    """
    Take a debug screenshot without ever aborting the run. full_page=True on the
    long active-listings page can exceed 30s and kill the whole flow, so we use a
    viewport-only capture with a short timeout and swallow any failure.
    """
    ss = os.path.join(DOWNLOAD_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    try:
        page.screenshot(path=ss, full_page=False, timeout=10000)
        log.info(f"Screenshot: {ss}")
    except Exception as e:
        log.warning(f"Screenshot '{name}' skipped: {e}")


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

            # Check login. Use the shared auto-login helper (fills credentials
            # from credentials.txt) so this works unattended in airotate --
            # eBay often bounces the active-listings page to sign-in even when
            # the Seller Hub warm-up looked fine.
            if needs_signin(page):
                if not wait_for_signin(page, success_url_glob="**/sh/lst/**"):
                    raise RuntimeError("Could not sign in to eBay (auto-login failed)")
                # Sign-in redirected us away from the SIO page; go back.
                log.info("Re-opening SIO-eligible listings page after sign-in...")
                page.goto(SIO_URL, wait_until="load", timeout=60000)

            page.wait_for_timeout(5000)

            # Screenshot
            _safe_shot(page, "sio_page")

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

            # Count what actually got selected. A silent "0 selected" would sail
            # through the rest of the flow as a fake success and send no offers --
            # the exact critical failure we must not miss. If there are genuinely
            # 0 eligible listings, that's a clean no-op, not an error, so return
            # the count and let the caller decide how loudly to report it.
            try:
                selected_count = page.locator(
                    "tbody input[type='checkbox']:checked, "
                    "[data-testid='shui-dt-body'] input[type='checkbox']:checked"
                ).count()
            except Exception:
                selected_count = -1  # couldn't determine; don't fabricate a number
            log.info(f"Listings selected: {selected_count}")
            if selected_count == 0:
                log.warning("0 eligible listings selected -- nothing to offer.")
                return 0

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
                _safe_shot(page, "sio_no_offer_btn")
                raise RuntimeError("Offer to buyers button not found")

            offer_btn.evaluate("el => el.click()")
            page.wait_for_timeout(3000)
            log.info("Clicked 'Offer to buyers'")

            # Screenshot the offer dialog
            _safe_shot(page, "sio_dialog")

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

            # 5. Ensure "Send automated offer" is enabled.
            # eBay retired the old "Send coupon / Extra 5%" control -- the current
            # dialog has no coupon option at all (confirmed from the live dialog
            # 2026-07-21). The modern equivalent is "Send automated offer", which
            # keeps offering the discount to interested buyers for ~1 year. It is
            # checked by default; we verify it's ticked rather than blindly click
            # it (a blind click would toggle it OFF).
            log.info("Ensuring 'Send automated offer' is enabled...")
            try:
                auto_offer = page.locator(
                    "input[type='checkbox']:below(:text('Send automated offer')), "
                    "label:has-text('Send automated offer') input[type='checkbox']"
                ).first
                if auto_offer.count() and not auto_offer.is_checked():
                    # Click the associated label/text so the styled checkbox flips.
                    page.locator("text=Send automated offer").first.click()
                    page.wait_for_timeout(500)
                    log.info("Enabled 'Send automated offer'")
                else:
                    log.info("'Send automated offer' already enabled (default)")
            except Exception as e:
                # Non-fatal: the offer still sends at the discount even if we can't
                # confirm the automated-offer toggle.
                log.warning(f"Could not confirm 'Send automated offer' state: {e}")

            page.wait_for_timeout(1000)

            # Screenshot before sending
            _safe_shot(page, "sio_before_send")

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
            _safe_shot(page, "sio_after_send")

            # Wait 30 seconds then take final verification screenshot
            log.info("Waiting 30 seconds before final verification...")
            page.wait_for_timeout(30000)

            # Reload the SIO-eligible page to verify
            page.goto(SIO_URL, wait_until="load", timeout=60000)
            page.wait_for_timeout(5000)

            _safe_shot(page, "sio_verify")
            log.info(f"Offers sent at {percent_off}% off on all eligible listings!")
            return selected_count if selected_count > 0 else -1

        except Exception as e:
            log.error(f"Failed: {e}")
            _safe_shot(page, "sio_error")
            raise

        finally:
            context.close()
            log.info("Browser closed")


if __name__ == "__main__":
    pct = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    try:
        count = send_offers(pct)
        if count == 0:
            # Not a crash, but sending offers to nobody on a ~1300-listing store
            # is abnormal -- surface it so a broken selector can't hide as "0 eligible".
            notify_send(
                "eBay send-offers: 0 eligible",
                f"Send-offers ran but selected 0 listings (nothing sent at {pct}% off). "
                "Verify this is a real empty day and not a broken filter/selector.",
                priority="high",
                tags="warning",
            )
        else:
            shown = "all" if count < 0 else str(count)
            log.info(f"Done: offers sent at {pct}% off on {shown} eligible listings.")
            # Daily heartbeat: a positive "it worked" push so that silence itself
            # becomes a signal something is wrong.
            notify_send(
                "eBay offers sent ✅",
                f"Sent {pct}% off offers to {shown} eligible listings.",
                priority="default",
                tags="white_check_mark",
            )
    except Exception as e:
        # This step drives a lot of sales -- a failure must page us, not fail silently.
        notify_send(
            "eBay SEND-OFFERS FAILED",
            f"ai_ebay_send_offers.py crashed at {pct}% off: {e}\n"
            "No offers went out this run. Check screenshots in ~/Downloads (sio_error_*).",
            priority="urgent",
            tags="rotating_light",
        )
        raise
