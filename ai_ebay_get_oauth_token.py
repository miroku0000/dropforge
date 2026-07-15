"""
eBay OAuth Token Generator (Playwright)
Opens the eBay Developer Portal OAuth page, clicks through the flow,
extracts the token, and saves it to credentials.txt.

Uses a persistent Playwright profile so developer portal login is remembered.

Usage:
    python ai_ebay_get_oauth_token.py
"""

import os
import re
import logging
from datetime import datetime, timedelta
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
DOWNLOAD_DIR = os.path.join(os.getcwd(), 'downloads')
DEVELOPER_PORTAL_URL = "https://developer.ebay.com/my/auth?env=production&index=0&auth_type=oauth"


def get_oauth_token():
    """
    1. Go to eBay Developer Portal OAuth page
    2. Click 'Sign in to Production' or similar button
    3. Complete eBay consent if needed
    4. Extract the token from the page
    5. Save to credentials.txt
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with sync_playwright() as p:
        context = launch_ebay_browser(p)

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. Navigate to developer portal OAuth page
            log.info(f"Opening {DEVELOPER_PORTAL_URL}")
            page.goto(DEVELOPER_PORTAL_URL, wait_until="load", timeout=60000)

            # Check if we need to log in to the developer portal
            if "signin" in page.url.lower() or "login" in page.url.lower():
                log.warning("Please log in to the eBay Developer Portal in the browser window.")
                page.wait_for_url("**/my/auth**", timeout=120000)
                log.info("Developer portal login detected, continuing...")
                page.wait_for_timeout(3000)

            # Screenshot the page
            ss = os.path.join(DOWNLOAD_DIR, f"oauth_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss, full_page=True)
            log.info(f"Page screenshot: {ss}")

            # 2. Look for the "Sign in to Production" or "Get a User Token" button
            log.info("Looking for Sign in / Get Token button...")

            sign_in_btn = None
            for selector in [
                "button:has-text('Sign in to Production')",
                "a:has-text('Sign in to Production')",
                "button:has-text('Get a Token')",
                "a:has-text('Get a Token')",
                "button:has-text('Get a User Token')",
                "a:has-text('Get a User Token')",
                "button:has-text('Sign In to Production')",
                "a:has-text('Sign In to Production')",
                "button:has-text('Generate Token')",
                "#oauth-user-token-btn",
                "[data-testid='sign-in-production']",
            ]:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=2000):
                    sign_in_btn = loc
                    log.info(f"Found button: {selector}")
                    break

            if not sign_in_btn:
                # Maybe the token is already displayed on the page
                token = _extract_token_from_page(page)
                if token:
                    log.info("Token already displayed on page!")
                    _save_token(token)
                    return token

                log.error("Could not find Sign in button or existing token")
                html_path = os.path.join(DOWNLOAD_DIR, f"oauth_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                log.info(f"Page HTML dumped: {html_path}")
                raise RuntimeError("No Sign in button found -- check screenshot and HTML dump")

            # Click the button -- this may open a popup or redirect
            log.info("Clicking Sign in / Get Token button...")
            popup = None
            try:
                with page.context.expect_page(timeout=10000) as popup_info:
                    sign_in_btn.click()
                popup = popup_info.value
                popup.wait_for_load_state("networkidle", timeout=30000)
                log.info(f"Popup opened: {popup.url}")

                # Handle eBay consent in popup
                if "signin" in popup.url.lower() or "authorize" in popup.url.lower():
                    log.warning("Please complete eBay sign-in/consent in the popup window.")

                # Look for Agree/Allow button in popup
                for agree_text in ["I agree", "Agree", "Allow", "Accept", "Confirm"]:
                    agree_btn = popup.locator(f"button:has-text('{agree_text}'), input[value='{agree_text}']").first
                    if agree_btn.is_visible(timeout=3000):
                        agree_btn.click()
                        log.info(f"Clicked '{agree_text}' in popup")
                        break

                # Wait for popup to close
                try:
                    popup.wait_for_event("close", timeout=120000)
                    log.info("Popup closed")
                except Exception:
                    log.info("Popup may still be open, continuing...")

            except Exception:
                # No popup -- button may have redirected the main page
                log.info("No popup detected, checking main page...")
                page.wait_for_timeout(5000)

                if "signin" in page.url.lower() or "authorize" in page.url.lower():
                    log.warning("Please complete eBay sign-in/consent in the browser.")
                    page.wait_for_url("**/my/auth**", timeout=120000)
                    log.info("Redirected back to developer portal")

            # 3. Wait for the token to appear on the page
            log.info("Waiting for token to appear on page...")
            page.wait_for_timeout(5000)

            token = None
            for attempt in range(24):  # Wait up to 2 minutes
                token = _extract_token_from_page(page)
                if token:
                    break
                log.info(f"Waiting for token... (attempt {attempt + 1}/24)")
                page.wait_for_timeout(5000)

            if not token:
                ss_final = os.path.join(DOWNLOAD_DIR, f"oauth_no_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss_final, full_page=True)
                html_path = os.path.join(DOWNLOAD_DIR, f"oauth_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                log.error(f"Token not found. Screenshot: {ss_final}, HTML: {html_path}")
                return None

            # 4. Save the token
            _save_token(token)
            log.info("OAuth token obtained and saved successfully!")
            return token

        except Exception as e:
            log.error(f"Failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"oauth_error_{ts}.png"))
            except Exception:
                pass
            raise

        finally:
            context.close()
            log.info("Browser closed")


def _extract_token_from_page(page):
    """Try to find and extract an OAuth token from the page content."""
    selectors = [
        "textarea",
        "code",
        "pre",
        "input[type='text'][readonly]",
        "input[readonly]",
        ".token-value",
        "[class*='token']",
        "[data-testid*='token']",
    ]

    for selector in selectors:
        elements = page.locator(selector).all()
        for el in elements:
            try:
                text = el.input_value() if selector.startswith("input") or selector == "textarea" else el.inner_text()
                if text and "v^1.1#" in text:
                    token = text.strip()
                    log.info(f"Found token in {selector}: {token[:60]}...")
                    return token
            except Exception:
                continue

    # Fallback: regex search the entire page
    try:
        body_text = page.locator("body").inner_text()
        match = re.search(r'(v\^1\.1#[A-Za-z0-9^#+=/.]+)', body_text)
        if match:
            token = match.group(1)
            log.info(f"Found token via regex: {token[:60]}...")
            return token
    except Exception:
        pass

    return None


def _save_token(token):
    """Save the token to credentials.txt."""
    creds_path = "credentials.txt"
    if not os.path.exists(creds_path):
        log.error(f"{creds_path} not found")
        return

    with open(creds_path, 'r') as f:
        lines = f.readlines()

    now = datetime.now()
    expiry = now + timedelta(hours=2)
    new_lines = []
    token_updated = False
    expiry_updated = False

    for line in lines:
        if line.startswith('token='):
            new_lines.append(f'token={token}\n')
            token_updated = True
        elif line.startswith('token_expiry='):
            new_lines.append(f'token_expiry={expiry.isoformat()}\n')
            expiry_updated = True
        elif line.startswith('# Token expires at:'):
            new_lines.append(f'# Token expires at: {expiry.strftime("%Y-%m-%d %H:%M:%S")}\n')
        else:
            new_lines.append(line)

    if not token_updated:
        new_lines.append(f'token={token}\n')
    if not expiry_updated:
        new_lines.append(f'token_expiry={expiry.isoformat()}\n')

    new_lines.append(f'\n# OAuth token obtained via developer portal {now.strftime("%Y-%m-%d %H:%M:%S")}\n')

    with open(creds_path, 'w') as f:
        f.writelines(new_lines)

    log.info(f"Token saved to {creds_path}")
    log.info(f"Expires at: {expiry.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    get_oauth_token()
