"""
eBay Top Converters Keyword Bid Updater (Playwright)
Reads bid recommendations from generate_bid_changes_csv.py output,
then updates each keyword bid through the eBay Seller Hub browser UI.

Uses a persistent Playwright profile so eBay login is remembered.

Usage:
    python ai_ebay_update_keyword_bids.py                           # Use latest bid_changes_detailed_*.csv
    python ai_ebay_update_keyword_bids.py bid_changes_detailed.csv  # Use specific file
"""

import os
import sys
import glob
import logging
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_bid_updates.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
CAMPAIGN_ID = "158950352019"
CAMPAIGN_URL = f"https://www.ebay.com/sh/ads/dashboard/campaign/{CAMPAIGN_ID}"


def find_latest_bid_changes():
    """Find the most recent bid_changes_detailed_*.csv file."""
    patterns = [
        os.path.join(os.getcwd(), 'bid_changes_detailed_*.csv'),
        os.path.join(DOWNLOAD_DIR, 'bid_changes_detailed_*.csv'),
    ]
    latest = None
    latest_time = 0
    for pattern in patterns:
        for f in glob.glob(pattern):
            mtime = os.path.getmtime(f)
            if mtime > latest_time:
                latest_time = mtime
                latest = f
    return latest


def load_bid_changes(filepath):
    """Load and validate bid changes CSV."""
    df = pd.read_csv(filepath)
    log.info(f"Loaded {len(df)} bid changes from {os.path.basename(filepath)}")

    # Filter to only rows that actually need changes
    changes = []
    for _, row in df.iterrows():
        new_bid = row['New Bid']
        if new_bid == 'PAUSE':
            changes.append({
                'keyword_id': str(int(row['Keyword ID'])),
                'keyword': row['Keyword'],
                'match_type': row['Match Type'],
                'current_bid': row['Current Bid'].replace('$', ''),
                'new_bid': '0.05',
                'action': row['Action'],
                'pause': True,
            })
        else:
            current = float(row['Current Bid'].replace('$', ''))
            new = float(new_bid.replace('$', ''))
            if abs(current - new) >= 0.01:  # Only if actually changing
                changes.append({
                    'keyword_id': str(int(row['Keyword ID'])),
                    'keyword': row['Keyword'],
                    'match_type': row['Match Type'],
                    'current_bid': f"{current:.2f}",
                    'new_bid': f"{new:.2f}",
                    'action': row['Action'],
                    'pause': False,
                })

    log.info(f"{len(changes)} keywords need bid updates (filtered unchanged)")
    return changes


def update_keyword_bids(changes, dry_run=False):
    """
    Navigate to the Top Converters campaign keywords tab and update each bid.
    """
    if not changes:
        log.info("No bid changes to apply")
        return

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900})

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Navigate to campaign keywords tab
            url = f"{CAMPAIGN_URL}?tab=keywords"
            log.info(f"Opening {url}")
            page.goto(url, wait_until="load", timeout=60000)

            # Check login
            if "signin" in page.url.lower():
                log.warning("Please log in to eBay in the browser window.")
                page.wait_for_url("**/sh/ads/**", timeout=120000)
                log.info("Login detected, continuing...")

            page.wait_for_timeout(3000)

            # Diagnostic: dump page structure before doing anything
            _dump_page_diagnostics(page)

            # Track results
            updated = 0
            failed = 0
            skipped = 0

            for i, change in enumerate(changes):
                keyword = change['keyword']
                new_bid = change['new_bid']
                action = change['action']
                should_pause = change['pause']

                log.info(f"[{i+1}/{len(changes)}] {keyword} ({change['match_type']}): "
                         f"${change['current_bid']} -> ${new_bid} ({action})")

                if dry_run:
                    log.info(f"  DRY RUN - skipping")
                    skipped += 1
                    continue

                try:
                    success = _update_single_keyword(page, change)
                    if success:
                        updated += 1
                        log.info(f"  Updated successfully")
                    else:
                        failed += 1
                        log.warning(f"  Failed to update")
                except Exception as e:
                    failed += 1
                    log.error(f"  Error: {e}")
                    # Screenshot on error
                    ss = os.path.join(DOWNLOAD_DIR, f"bid_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    try:
                        page.screenshot(path=ss)
                    except Exception:
                        pass

            # Summary
            log.info(f"\n{'='*60}")
            log.info(f"BID UPDATE SUMMARY")
            log.info(f"{'='*60}")
            log.info(f"Total keywords: {len(changes)}")
            log.info(f"Updated: {updated}")
            log.info(f"Failed: {failed}")
            log.info(f"Skipped: {skipped}")

            # Final screenshot
            ss = os.path.join(DOWNLOAD_DIR, f"bid_update_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss, full_page=True)
            log.info(f"Final screenshot: {ss}")

        except Exception as e:
            log.error(f"Failed: {e}")
            raise

        finally:
            context.close()
            log.info("Browser closed")


def _dump_page_diagnostics(page):
    """Dump detailed page info to help identify the right elements."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Screenshot
    ss = os.path.join(DOWNLOAD_DIR, f"keywords_page_{ts}.png")
    page.screenshot(path=ss, full_page=True)
    log.info(f"Page screenshot: {ss}")

    # Find ALL input fields on the page
    inputs = page.locator("input").all()
    log.info(f"\n--- ALL INPUT FIELDS ({len(inputs)}) ---")
    for i, inp in enumerate(inputs):
        try:
            attrs = {}
            for attr in ['type', 'placeholder', 'aria-label', 'name', 'id', 'class', 'value']:
                val = inp.get_attribute(attr)
                if val:
                    attrs[attr] = val[:80]
            visible = inp.is_visible()
            log.info(f"  Input {i}: visible={visible} attrs={attrs}")
        except Exception as e:
            log.info(f"  Input {i}: error reading - {e}")

    # Find ALL buttons
    buttons = page.locator("button").all()
    log.info(f"\n--- ALL BUTTONS ({len(buttons)}) ---")
    for i, btn in enumerate(buttons):
        try:
            text = btn.inner_text().strip()[:60]
            aria = btn.get_attribute('aria-label') or ''
            cls = (btn.get_attribute('class') or '')[:80]
            visible = btn.is_visible()
            if visible and (text or aria):
                log.info(f"  Button {i}: text='{text}' aria='{aria}' class='{cls}'")
        except Exception:
            pass

    # Find table structure
    tables = page.locator("table").all()
    log.info(f"\n--- TABLES ({len(tables)}) ---")
    for i, tbl in enumerate(tables):
        try:
            rows = tbl.locator("tr").count()
            headers = tbl.locator("th").all_inner_texts()
            log.info(f"  Table {i}: {rows} rows, headers={headers[:10]}")
        except Exception as e:
            log.info(f"  Table {i}: error - {e}")

    # Find elements with role='row' or role='grid'
    grids = page.locator("[role='grid'], [role='table']").all()
    log.info(f"\n--- GRID/TABLE ROLES ({len(grids)}) ---")
    for i, grid in enumerate(grids):
        try:
            rows = grid.locator("[role='row']").count()
            aria = grid.get_attribute('aria-label') or ''
            log.info(f"  Grid {i}: {rows} rows, aria='{aria}'")
        except Exception:
            pass

    # Find anything that looks like keyword rows (text containing $)
    log.info(f"\n--- SAMPLE ROWS WITH $ (first 5) ---")
    dollar_elements = page.locator("tr:has-text('$'), [role='row']:has-text('$')").all()
    for i, el in enumerate(dollar_elements[:5]):
        try:
            text = el.inner_text().strip().replace('\n', ' | ')[:200]
            log.info(f"  Row {i}: {text}")
        except Exception:
            pass

    # Dump full HTML of the main content area
    html_path = os.path.join(DOWNLOAD_DIR, f"keywords_page_{ts}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(page.content())
    log.info(f"Full page HTML: {html_path}")

    log.info("--- END DIAGNOSTICS ---\n")


def _clear_search(page):
    """Clear the keyword search field."""
    # Click Cancel Search button via JavaScript to avoid interception
    cancel_btn = page.locator("button[aria-label='Cancel Search']").first
    if cancel_btn.is_visible(timeout=1000):
        cancel_btn.evaluate("el => el.click()")
        page.wait_for_timeout(2000)
    else:
        # Fallback: clear the search box directly
        search_box = page.locator("input[aria-label='Search keywords']").first
        if search_box.is_visible(timeout=1000):
            search_box.evaluate("el => { el.focus(); el.value = ''; }")
            search_box.fill("")
            search_box.press("Enter")
            page.wait_for_timeout(2000)


def _update_single_keyword(page, change):
    """Update a single keyword's bid on the current page."""
    keyword = change['keyword']
    new_bid = change['new_bid']
    should_pause = change['pause']

    # Use the keyword search field (NOT the top eBay search bar)
    search_box = page.locator("input[aria-label='Search keywords']").first
    if not search_box.is_visible(timeout=5000):
        log.warning("Could not find keyword search box")
        return False

    # 1. Click the Start Search button first to expand/activate the search field
    start_btn = page.locator("button.start-search").first
    if start_btn.is_visible(timeout=2000):
        start_btn.evaluate("el => el.click()")
        page.wait_for_timeout(500)

    # 2. Now type the keyword into the search field
    search_box.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    search_box.evaluate("el => { el.focus(); el.value = ''; }")
    page.wait_for_timeout(200)
    search_box.fill(keyword)
    page.wait_for_timeout(500)
    search_box.press("Enter")

    # Wait for grid to re-render with filtered results
    page.wait_for_timeout(3000)

    # Find the matching row in the grid
    rows = page.locator("[role='row']").all()
    keyword_row = None
    for row in rows:
        try:
            text = row.inner_text().lower()
            if keyword.lower() in text and '$' in text:
                keyword_row = row
                break
        except Exception:
            continue

    if not keyword_row:
        log.warning(f"Could not find keyword '{keyword}' in search results")
        _clear_search(page)
        return False

    # Find the bid input (aria-label="Your bid") inside this row
    bid_input = keyword_row.locator("input[aria-label='Your bid']").first
    if not bid_input.is_visible(timeout=2000):
        log.warning(f"Could not find bid input for '{keyword}'")
        search_box.fill("")
        page.wait_for_timeout(1000)
        return False

    current_value = bid_input.input_value()
    log.info(f"  Current bid on page: ${current_value}, setting to: ${new_bid}")

    # Update the bid: click, select all, type new value, press Tab to confirm
    bid_input.click(click_count=3)  # Select all text
    page.wait_for_timeout(200)
    bid_input.fill(new_bid)
    page.wait_for_timeout(300)
    bid_input.press("Tab")  # Tab away to confirm the change
    page.wait_for_timeout(1000)

    # Handle pause -- toggle the switch control if needed
    if should_pause:
        switch = keyword_row.locator("input.switch__control").first
        if switch.is_visible(timeout=1000):
            # Check if currently active (checked = active)
            is_checked = switch.is_checked()
            if is_checked:
                switch.click()
                page.wait_for_timeout(1000)
                log.info(f"  Toggled status to paused for '{keyword}'")
        else:
            log.warning(f"  Could not find status toggle for '{keyword}'")

    # Clear search for next keyword
    _clear_search(page)
    return True


def main():
    # Find or load bid changes
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if sys.argv[1] == '--dry-run':
            filepath = find_latest_bid_changes()
            dry_run = True
        else:
            dry_run = '--dry-run' in sys.argv
    else:
        filepath = find_latest_bid_changes()
        dry_run = False

    if not filepath or not os.path.exists(filepath):
        log.error("No bid changes CSV found. Run generate_bid_changes_csv.py first.")
        return

    log.info(f"Using bid changes file: {filepath}")
    log.info(f"Dry run: {dry_run}")

    changes = load_bid_changes(filepath)

    if not changes:
        log.info("No bid changes to apply")
        return

    # Show summary before proceeding
    print(f"\n{'='*60}")
    print(f"KEYWORD BID UPDATE PLAN")
    print(f"{'='*60}")
    print(f"File: {os.path.basename(filepath)}")
    print(f"Keywords to update: {len(changes)}")
    print(f"Campaign: Top Converters Test ({CAMPAIGN_ID})")
    print()

    increases = [c for c in changes if not c['pause'] and float(c['new_bid']) > float(c['current_bid'])]
    decreases = [c for c in changes if not c['pause'] and float(c['new_bid']) < float(c['current_bid'])]
    pauses = [c for c in changes if c['pause']]

    print(f"  Increases: {len(increases)}")
    print(f"  Decreases: {len(decreases)}")
    print(f"  Pauses: {len(pauses)}")
    print()

    # Show top 5
    for i, c in enumerate(changes[:5]):
        status = "PAUSE" if c['pause'] else f"${c['current_bid']} -> ${c['new_bid']}"
        print(f"  {i+1}. {c['keyword']:<35} {status}")

    if len(changes) > 5:
        print(f"  ... and {len(changes) - 5} more")
    print()

    if not dry_run:
        update_keyword_bids(changes, dry_run=False)
    else:
        log.info("DRY RUN complete - no changes made")


if __name__ == "__main__":
    main()
