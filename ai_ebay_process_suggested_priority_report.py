"""
Process eBay Suggested Priority Listing Report and deactivate underperformers.

Reads the latest Suggested Priority report, identifies listings that should
be deactivated based on performance, then uses Playwright to end them on eBay.

Deactivation criteria:
- High impressions (100+) with 0 clicks = not relevant to buyers
- High clicks (10+) with 0 sales and high ad fees = spending money for nothing
- High ad fees (>$2) with 0 sales = negative ROI

Usage:
    python ai_ebay_process_suggested_priority_report.py
    python ai_ebay_process_suggested_priority_report.py --dry-run
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
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.getcwd(), '.playwright_profile')
LOCAL_DOWNLOADS = os.path.join(os.getcwd(), 'downloads')
USER_DOWNLOADS = os.path.expanduser('~/Downloads')


def find_latest_report():
    """Find the most recent Suggested Priority report."""
    for search_dir in [LOCAL_DOWNLOADS, USER_DOWNLOADS]:
        pattern = os.path.join(search_dir, 'Suggested Priority_Listing_*.csv')
        files = glob.glob(pattern)
        if files:
            return max(files, key=os.path.getmtime)
    return None


def analyze_report(filepath):
    """Analyze the report and return item IDs to deactivate with reasons."""
    df = pd.read_csv(filepath, skiprows=1)
    log.info(f"Loaded {len(df)} listings from {os.path.basename(filepath)}")

    # Only look at ACTIVE listings
    active = df[df['Status'] == 'ACTIVE'].copy()
    log.info(f"Active listings: {len(active)}")

    # Clean numeric columns
    for col in ['Impressions', 'Clicks', 'Sold quantity']:
        active[col] = pd.to_numeric(active[col], errors='coerce').fillna(0).astype(int)

    active['Ad fees clean'] = active['Ad fees'].str.replace('$', '').str.replace(',', '').astype(float)
    active['Sales clean'] = active['Sales'].str.replace('$', '').str.replace(',', '').astype(float)

    to_deactivate = []

    for _, row in active.iterrows():
        item_id = str(row['Item ID'])
        title = row['Title'][:60]
        impressions = row['Impressions']
        clicks = row['Clicks']
        sold = row['Sold quantity']
        ad_fees = row['Ad fees clean']
        sales = row['Sales clean']
        reason = None

        # Rule 1: High impressions, zero clicks = irrelevant to buyers
        if impressions >= 100 and clicks == 0:
            reason = f"IRRELEVANT - {impressions} impressions, 0 clicks"

        # Rule 2: High clicks, zero sales, spending money
        elif clicks >= 10 and sold == 0 and ad_fees > 1:
            reason = f"NO CONVERSIONS - {clicks} clicks, 0 sales, ${ad_fees:.2f} ad fees"

        # Rule 3: Any ad fees with zero sales
        elif ad_fees > 2 and sold == 0:
            reason = f"NEGATIVE ROI - ${ad_fees:.2f} ad fees, 0 sales"

        if reason:
            to_deactivate.append({
                'item_id': item_id,
                'title': title,
                'reason': reason,
                'impressions': impressions,
                'clicks': clicks,
                'sold': sold,
                'ad_fees': ad_fees,
            })

    log.info(f"Listings to deactivate: {len(to_deactivate)}")
    return to_deactivate


def deactivate_listings(items, dry_run=False):
    """End listings on eBay using Playwright via active listings page."""
    if not items:
        log.info("No listings to deactivate")
        return

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900})

        page = context.pages[0] if context.pages else context.new_page()

        try:
            ended = 0
            failed = 0

            for i, item in enumerate(items):
                item_id = item['item_id']
                log.info(f"[{i+1}/{len(items)}] {item['title']}...")
                log.info(f"  Reason: {item['reason']}")

                if dry_run:
                    log.info(f"  DRY RUN - skipping")
                    continue

                try:
                    # Go to active listings page (only on first item or after ending)
                    if i == 0 or ended > 0 or failed > 0:
                        page.goto("https://www.ebay.com/sh/lst/active", wait_until="load", timeout=60000)
                        if "signin" in page.url.lower():
                            log.warning("Please log in to eBay.")
                            page.wait_for_url("**/sh/lst/**", timeout=120000)
                        page.wait_for_timeout(3000)

                    # Use the listings search box (NOT the top eBay search bar)
                    # The listings search has name="query" or similar, not id="gh-ac"
                    search_box = page.locator("input#shui-sls-search-input, input[name='query'], input[data-testid*='search-input']").first
                    if not search_box.is_visible(timeout=3000):
                        # Fallback: find the search box that is NOT the global eBay search
                        all_inputs = page.locator("input[type='text']").all()
                        for inp in all_inputs:
                            inp_id = inp.get_attribute("id") or ""
                            inp_name = inp.get_attribute("name") or ""
                            if inp_id == "gh-ac" or inp_name == "_nkw":
                                continue  # Skip global search
                            if inp.is_visible():
                                search_box = inp
                                log.info(f"  Found search box: id={inp_id} name={inp_name}")
                                break

                    if not search_box.is_visible(timeout=3000):
                        log.warning(f"  Could not find listings search box")
                        failed += 1
                        continue

                    search_box.scroll_into_view_if_needed()
                    page.wait_for_timeout(300)
                    search_box.fill("")
                    search_box.fill(item_id)
                    search_box.press("Enter")
                    page.wait_for_timeout(3000)

                    # Find the listing row
                    row = page.locator(f"tr:has-text('{item_id}'), [role='row']:has-text('{item_id}')").first
                    if not row.is_visible(timeout=5000):
                        log.warning(f"  Could not find item {item_id} in search results")
                        failed += 1
                        continue

                    # Select the checkbox for this listing
                    checkbox = row.locator("input[type='checkbox']").first
                    if checkbox.is_visible(timeout=2000):
                        checkbox.evaluate("el => el.click()")
                        page.wait_for_timeout(1000)
                    else:
                        log.warning(f"  Could not find checkbox for {item_id}")
                        failed += 1
                        continue

                    # Click Actions dropdown
                    actions_btn = page.locator("button:has-text('Actions')").first
                    if not actions_btn.is_visible(timeout=3000):
                        log.warning(f"  Could not find Actions button")
                        failed += 1
                        continue

                    actions_btn.click()
                    page.wait_for_timeout(1000)

                    # Click End listings
                    end_btn = page.locator("text='End listings'").first
                    if not end_btn.is_visible(timeout=2000):
                        log.warning(f"  Could not find 'End listings' option")
                        failed += 1
                        continue

                    end_btn.click()
                    page.wait_for_timeout(3000)

                    # Screenshot the confirmation dialog
                    ss_confirm = os.path.join(USER_DOWNLOADS, f"sp_confirm_{item_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    page.screenshot(path=ss_confirm, full_page=False)
                    log.info(f"  Confirm dialog screenshot: {ss_confirm}")

                    # Try multiple selectors for the confirm button
                    confirm_btn = None
                    for selector in [
                        "button.btn--primary:has-text('End listings')",
                        "button.btn--primary:has-text('End listing')",
                        "button[data-testid='submit-button']",
                        "div[role='dialog'] button.btn--primary",
                        "button.btn--primary:has-text('End')",
                        "button.btn--primary:has-text('Confirm')",
                    ]:
                        loc = page.locator(selector).first
                        if loc.is_visible(timeout=2000):
                            confirm_btn = loc
                            log.info(f"  Found confirm button: {selector}")
                            break

                    if confirm_btn:
                        confirm_btn.click()
                        page.wait_for_timeout(3000)
                        log.info(f"  Ended successfully")
                        ended += 1
                    else:
                        log.warning(f"  No confirmation button found -- check screenshot")
                        failed += 1

                except Exception as e:
                    log.error(f"  Error: {e}")
                    failed += 1

            # Summary
            log.info(f"\n{'='*60}")
            log.info(f"DEACTIVATION SUMMARY")
            log.info(f"{'='*60}")
            log.info(f"Total flagged: {len(items)}")
            log.info(f"Ended: {ended}")
            log.info(f"Failed: {failed}")
            if dry_run:
                log.info(f"Skipped (dry run): {len(items)}")

        except Exception as e:
            log.error(f"Failed: {e}")
            raise

        finally:
            context.close()
            log.info("Browser closed")


def main():
    dry_run = '--dry-run' in sys.argv

    # Find latest report
    filepath = find_latest_report()
    if not filepath:
        log.error("No Suggested Priority report found in Downloads")
        return

    log.info(f"Using report: {filepath}")
    log.info(f"Dry run: {dry_run}")

    # Analyze
    to_deactivate = analyze_report(filepath)

    if not to_deactivate:
        log.info("No underperforming listings found")
        return

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUGGESTED PRIORITY - UNDERPERFORMERS")
    print(f"{'='*60}")
    print(f"Report: {os.path.basename(filepath)}")
    print(f"Listings to deactivate: {len(to_deactivate)}")
    print()

    for i, item in enumerate(to_deactivate):
        print(f"  {i+1}. {item['title']}")
        print(f"     {item['reason']}")
        print(f"     Impressions={item['impressions']} Clicks={item['clicks']} Sold={item['sold']} Fees=${item['ad_fees']:.2f}")
        print()

    # Deactivate
    deactivate_listings(to_deactivate, dry_run=dry_run)


if __name__ == "__main__":
    main()
