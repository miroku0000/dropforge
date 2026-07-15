"""
Shared Playwright browser launcher with anti-detection for eBay.

All eBay automation scripts should use `launch_ebay_browser()` from this module
instead of calling `p.chromium.launch_persistent_context()` directly.

Strategy: Launch real Chrome as a normal subprocess with --remote-debugging-port,
then connect via CDP. Includes a warm-up step that navigates to ebay.com first
and waits for any CAPTCHA/bot detection to be solved before handing off to the
calling script. Once the session is warm, subsequent scripts reuse the same
Chrome process.
"""

import os
import subprocess
import time
import logging

log = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
CDP_PORT = 19222

# How long to wait for the user to solve a CAPTCHA (seconds)
CAPTCHA_TIMEOUT = 300


def _find_chrome():
    """Find the Chrome executable on Windows."""
    candidates = [
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _try_connect(playwright, port, timeout=3000):
    """Try to connect to Chrome via CDP. Returns Browser or None."""
    try:
        browser = playwright.chromium.connect_over_cdp(
            f"http://localhost:{port}",
            timeout=timeout,
        )
        return browser
    except Exception:
        return None


def _is_bot_blocked(page):
    """Check if the page is showing eBay's bot detection / CAPTCHA page."""
    try:
        url = page.url.lower()
        if "captcha" in url or "blocked" in url:
            return True
        text = page.locator("body").inner_text(timeout=3000)
        if "pardon our interruption" in text.lower():
            return True
        if "unusual traffic" in text.lower():
            return True
    except Exception:
        pass
    return False


def _wait_for_captcha(page, timeout_s=CAPTCHA_TIMEOUT):
    """
    If the page shows a bot detection / CAPTCHA page, wait for the user
    to solve it manually. Returns True if resolved, False if timed out.
    """
    if not _is_bot_blocked(page):
        return True

    log.warning("=" * 60)
    log.warning("CAPTCHA / BOT DETECTION detected!")
    log.warning("Please solve the CAPTCHA in the Chrome window.")
    log.warning(f"Waiting up to {timeout_s}s...")
    log.warning("=" * 60)

    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(2)
        if not _is_bot_blocked(page):
            log.info("CAPTCHA solved! Continuing...")
            return True

    log.error("CAPTCHA was not solved in time.")
    return False


def needs_signin(page):
    """
    True if `page` is an eBay sign-in / password / re-auth page.

    eBay sign-in is two-step (username, then password). The password step can
    stay on a URL that a simple "signin in url" check misses, or appear as a
    re-auth form on an otherwise-normal eBay page. So check the URL *and* the
    page content -- a visible password field is the most reliable signal.

    Shared by every script that drives the eBay web UI via launch_ebay_browser.
    """
    try:
        url = (page.url or "").lower()
        if "signin" in url or "login.ebay" in url or "/signin/" in url:
            return True
    except Exception:
        pass
    try:
        pw = page.query_selector('input[type="password"]')
        if pw and pw.is_visible():
            return True
    except Exception:
        pass
    try:
        text = page.locator("body").inner_text(timeout=3000).lower()
        for marker in (
            "enter your password",
            "confirm your password",
            "keep me signed in",
            "having trouble signing in",
        ):
            if marker in text:
                return True
    except Exception:
        pass
    return False


def _ebay_login_creds():
    """eBay (ebay_user, ebay_pass) from credentials.txt, or (None, None)."""
    creds = {}
    path = "credentials.txt"
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip().lower()] = v.strip()
    return creds.get("ebay_user"), creds.get("ebay_pass")


def auto_login(page):
    """Fill the eBay sign-in form from credentials.txt (username step ->
    continue -> password step -> sign in). Returns True if creds were submitted.
    eBay may still show a CAPTCHA / 2FA that needs a human -- the caller's wait
    loop handles that. Selectors: #userid, #signin-continue-btn, #pass, #sgnBt."""
    user, pw = _ebay_login_creds()
    if not user or not pw:
        log.info("auto_login: no ebay_user/ebay_pass in credentials.txt; manual sign-in.")
        return False
    submitted = False
    try:
        uid = page.query_selector("#userid")
        if uid and uid.is_visible():
            uid.fill(user)
            btn = page.query_selector("#signin-continue-btn")
            if btn:
                btn.click()
            page.wait_for_timeout(2500)
        pwf = page.query_selector("#pass") or page.query_selector('input[type="password"]')
        if pwf and pwf.is_visible():
            pwf.fill(pw)
            sb = page.query_selector("#sgnBt")
            (sb.click() if sb else page.keyboard.press("Enter"))
            submitted = True
            page.wait_for_timeout(3500)
    except Exception as e:
        log.warning(f"auto_login could not complete the form: {e}")
    return submitted


def wait_for_signin(page, success_url_glob=None, timeout_s=300):
    """
    Get past an eBay sign-in: auto-fill credentials from credentials.txt, then
    wait until we're no longer on a sign-in page (in case a CAPTCHA/2FA needs a
    human). Returns True once signed in.

    success_url_glob: optional glob (e.g. "**/sh/**") to wait for as a positive
    confirmation; if given and matched it returns immediately.
    """
    log.warning("=" * 60)
    log.warning("SIGN-IN REQUIRED -- attempting auto-login from credentials.txt...")
    log.warning("(If a CAPTCHA / 2FA appears, complete it in Chrome.)")
    log.warning(f"Waiting up to {timeout_s // 60} min...")
    log.warning("=" * 60)

    if auto_login(page):
        log.info("Submitted eBay credentials; letting the redirect settle...")
        try:
            page.wait_for_load_state("load", timeout=20000)
        except Exception:
            pass

    def _settle():
        # Let any post-login redirect finish so the caller's next goto isn't
        # "interrupted by another navigation".
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        time.sleep(2)

    if success_url_glob:
        try:
            page.wait_for_url(success_url_glob, timeout=timeout_s * 1000)
            log.info("Sign-in completed (reached target page). Continuing...")
            _settle()
            return True
        except Exception:
            pass  # fall through to content-based polling

    start = time.time()
    while time.time() - start < timeout_s:
        time.sleep(2)
        if not needs_signin(page):
            log.info("Sign-in completed. Continuing...")
            _settle()
            return True
    log.error("Sign-in was not completed in time.")
    return False


def _warm_up_session(context):
    """
    Navigate to eBay Seller Hub to warm up the session.
    Handles CAPTCHA/bot detection and login prompts.
    Uses Seller Hub (not the homepage) because Seller Hub has stricter
    bot detection -- solving the CAPTCHA here clears it for all subsequent
    Seller Hub navigations in this session.
    """
    # Find or create a real page (not chrome:// internal)
    page = None
    for p in context.pages:
        if not p.url.startswith("chrome://"):
            page = p
            break
    if page is None:
        page = context.new_page()

    # If we're already on a Seller Hub page and not blocked, skip warm-up
    if "/sh/" in page.url and "ebay.com" in page.url and not _is_bot_blocked(page):
        log.info("Session already warm (on Seller Hub page)")
        return

    log.info("Warming up session: navigating to eBay Seller Hub...")
    try:
        page.goto("https://www.ebay.com/sh/ovw", wait_until="load", timeout=60000)
    except Exception:
        pass  # Timeout is OK, we'll check the page state

    time.sleep(3)  # Let the page settle

    # Handle CAPTCHA if present
    if _is_bot_blocked(page):
        resolved = _wait_for_captcha(page)
        if not resolved:
            log.error("Could not get past eBay bot detection.")
            return

    # Handle login if redirected. Detect by URL *and* page content so the
    # password step (which can stay on a non-obvious URL) is not missed.
    if needs_signin(page):
        wait_for_signin(page, success_url_glob="**/sh/**")

    # Check for CAPTCHA again after login
    if _is_bot_blocked(page):
        _wait_for_captcha(page)

    time.sleep(2)  # Brief pause after warm-up
    log.info("Session warm-up complete")


class _CDPContextWrapper:
    """
    Wraps a CDP browser context so that close() is safe for sequential scripts.

    When connected via CDP, the default context can't be closed (Playwright raises).
    Instead, close() disconnects from Chrome.
    Chrome stays running with the profile/session intact for the next script.
    """

    def __init__(self, context, browser):
        self._context = context
        self._browser = browser

    @property
    def pages(self):
        """Return only real browsing pages, not internal chrome:// pages."""
        return [p for p in self._context.pages if not p.url.startswith("chrome://")]

    def close(self):
        """Disconnect from Chrome. Chrome stays running with session intact."""
        try:
            self._browser.close()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._context, name)


def launch_ebay_browser(playwright, profile_dir=None, viewport=None,
                        accept_downloads=True, headless=False):
    """
    Launch a real Chrome browser and connect via CDP for eBay automation.

    Includes a warm-up step: navigates to ebay.com first, handles any
    CAPTCHA/bot detection, and waits for login if needed. After warm-up,
    subsequent navigations in the same session are trusted.

    Sequential scripts (like in airotate.bat) share the same Chrome process,
    so warm-up and login only happen once.

    Args:
        playwright: The Playwright instance from sync_playwright()
        profile_dir: Path to persistent profile directory (default: .playwright_profile)
        viewport: Dict with width/height (default: {"width": 1280, "height": 900})
        accept_downloads: Whether to accept downloads (default: True)
        headless: Run headless (default: False, ignored for CDP)

    Returns:
        A context-like object with the same API as BrowserContext.
    """
    if profile_dir is None:
        profile_dir = os.path.abspath(PROFILE_DIR)
    else:
        profile_dir = os.path.abspath(profile_dir)
    if viewport is None:
        viewport = {"width": 1280, "height": 900}

    port = CDP_PORT

    # 1. Try connecting to an already-running Chrome on our debug port
    log.info(f"Trying to connect to Chrome on port {port}...")
    browser = _try_connect(playwright, port)
    freshly_launched = False

    if browser:
        log.info("Connected to existing Chrome instance")
    else:
        # 2. Launch Chrome with remote debugging
        chrome_path = _find_chrome()
        if not chrome_path:
            log.warning("Chrome not found, falling back to Playwright-managed browser")
            return _fallback_launch(playwright, profile_dir, viewport,
                                    accept_downloads, headless)

        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            f"--window-size={viewport['width']},{viewport['height']}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-component-update",
        ]
        log.info(f"Launching Chrome: {chrome_path}")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        freshly_launched = True

        # Wait for Chrome to start accepting connections
        for attempt in range(15):
            time.sleep(1)
            browser = _try_connect(playwright, port)
            if browser:
                log.info(f"Connected to Chrome after {attempt + 1}s")
                break

        if not browser:
            log.warning("Could not connect to Chrome via CDP, falling back")
            return _fallback_launch(playwright, profile_dir, viewport,
                                    accept_downloads, headless)

    # 3. Get the default browser context (has the profile cookies/session)
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context(viewport=viewport)

    # 4. Wait for Chrome to fully initialize if freshly launched
    if freshly_launched:
        time.sleep(3)

    # 5. Warm up the session: visit ebay.com, handle CAPTCHA/login
    _warm_up_session(context)

    log.info("Chrome ready via CDP")
    return _CDPContextWrapper(context, browser)


# Stealth args for fallback mode
_STEALTH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-features=AutomationControlled',
    '--disable-infobars',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-component-update',
]

# Stealth JS for fallback mode
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
delete window.__playwright;
delete window.__pw_manual;
if (!window.chrome) { window.chrome = { runtime: {} }; }
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""


def _fallback_launch(playwright, profile_dir, viewport, accept_downloads, headless):
    """Fallback: use Playwright-managed Chrome (less stealthy but works without CDP)."""
    log.info("Using fallback: Playwright-managed Chrome (channel='chrome')")
    try:
        context = playwright.chromium.launch_persistent_context(
            profile_dir,
            channel='chrome',
            headless=headless,
            accept_downloads=accept_downloads,
            viewport=viewport,
            args=_STEALTH_ARGS,
        )
    except Exception as e:
        log.warning(f"Chrome channel failed ({e}), using bundled Chromium")
        context = playwright.chromium.launch_persistent_context(
            profile_dir,
            headless=headless,
            accept_downloads=accept_downloads,
            viewport=viewport,
            args=_STEALTH_ARGS,
        )

    context.add_init_script(_STEALTH_JS)
    for page in context.pages:
        try:
            page.evaluate(_STEALTH_JS)
        except Exception:
            pass

    return context
