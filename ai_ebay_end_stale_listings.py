"""
End Stale eBay Listings
Finds listings that have been active 45+ days with page views but zero sales,
then ends them via the active listings page.

These listings are taking up listing slots and getting traffic but never
converting. They're different from zero-view listings (which the
ai_ebay_delete_zero_view_listings.py script handles).

Usage:
    python ai_ebay_end_stale_listings.py                  # End up to 50 stale listings
    python ai_ebay_end_stale_listings.py --max 100        # End up to 100
    python ai_ebay_end_stale_listings.py --min-days 60    # Only 60+ days old
    python ai_ebay_end_stale_listings.py --min-views 10   # Only 10+ views
    python ai_ebay_end_stale_listings.py --dry-run        # Preview only
"""

import os
import sys
import glob
import logging
import argparse
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
DOWNLOAD_DIR = os.path.expanduser('~/Downloads')


def find_latest_traffic_report():
    """Find the most recent eBay traffic report."""
    pattern = os.path.join(DOWNLOAD_DIR, 'eBay-ListingsTrafficReport-*.csv')
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def find_stale_listings(filepath, min_days=45, min_views=1):
    """Find stale listings from the traffic report."""
    df = pd.read_csv(filepath, skiprows=5, low_memory=False)

    df['Item Start Date'] = pd.to_datetime(df['Item Start Date'], errors='coerce')
    df['Quantity sold'] = pd.to_numeric(df['Quantity sold'], errors='coerce').fillna(0).astype(int)
    df['Total page views'] = pd.to_numeric(df['Total page views'], errors='coerce').fillna(0).astype(int)
    df['Total impressions'] = pd.to_numeric(df['Total impressions'], errors='coerce').fillna(0).astype(int)

    now = pd.Timestamp.now()
    df['Days listed'] = (now - df['Item Start Date']).dt.days

    # Clean item IDs
    df['eBay item ID'] = df['eBay item ID'].astype(str).str.replace('="', '').str.replace('"', '').str.strip()

    # Stale: min_days+ old, has views, 0 sales
    stale = df[
        (df['Days listed'] >= min_days) &
        (df['Total page views'] >= min_views) &
        (df['Quantity sold'] == 0)
    ].sort_values('Total page views', ascending=False)

    log.info(f"Total listings: {len(df)}")
    log.info(f"Listed {min_days}+ days: {len(df[df['Days listed'] >= min_days])}")
    log.info(f"Stale ({min_days}+ days, {min_views}+ views, 0 sales): {len(stale)}")

    results = []
    for _, row in stale.iterrows():
        results.append({
            'item_id': row['eBay item ID'],
            'title': str(row['Listing title'])[:60],
            'days_listed': int(row['Days listed']),
            'views': int(row['Total page views']),
            'impressions': int(row['Total impressions']),
        })

    return results


def end_stale_listings(items, dry_run=False):
    """End stale listings via the eBay active listings page."""
    if not items:
        log.info("No stale listings to end")
        return

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900}, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("https://www.ebay.com/sh/lst/active", wait_until="load", timeout=60000)
            if "signin" in page.url.lower():
                log.warning("Please log in to eBay.")
                page.wait_for_url("**/sh/lst/**", timeout=120000)
            page.wait_for_timeout(3000)

            ended = 0
            failed = 0

            for i, item in enumerate(items):
                item_id = item['item_id']
                log.info(f"[{i+1}/{len(items)}] {item['title']}...")
                log.info(f"  {item['days_listed']}d old, {item['views']} views, {item['impressions']} impressions")

                if dry_run:
                    log.info(f"  DRY RUN - skipping")
                    continue

                try:
                    # Search for the item using the listings search box
                    search_box = None
                    all_inputs = page.locator("input[type='text']").all()
                    for inp in all_inputs:
                        inp_id = inp.get_attribute("id") or ""
                        inp_name = inp.get_attribute("name") or ""
                        if inp_id == "gh-ac" or inp_name == "_nkw":
                            continue
                        if inp.is_visible():
                            search_box = inp
                            break

                    if not search_box or not search_box.is_visible(timeout=3000):
                        log.warning(f"  Could not find search box")
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
                        log.warning(f"  Could not find item {item_id}")
                        failed += 1
                        continue

                    # Select the checkbox
                    checkbox = row.locator("input[type='checkbox']").first
                    if checkbox.is_visible(timeout=2000):
                        checkbox.evaluate("el => el.click()")
                        page.wait_for_timeout(1000)
                    else:
                        log.warning(f"  Could not find checkbox for {item_id}")
                        failed += 1
                        continue

                    # Click Actions -> End listings
                    actions_btn = page.locator("button:has-text('Actions')").first
                    if not actions_btn.is_visible(timeout=3000):
                        log.warning(f"  Could not find Actions button")
                        failed += 1
                        continue

                    actions_btn.click()
                    page.wait_for_timeout(1000)

                    end_btn = page.locator("text='End listings'").first
                    if not end_btn.is_visible(timeout=2000):
                        log.warning(f"  Could not find 'End listings' option")
                        failed += 1
                        continue

                    end_btn.click()
                    page.wait_for_timeout(2000)

                    # Confirm
                    confirm_btn = page.locator("button.btn--primary:has-text('End listing')").first
                    if confirm_btn.is_visible(timeout=5000):
                        confirm_btn.click()
                        page.wait_for_timeout(3000)
                        log.info(f"  Ended successfully")
                        ended += 1
                    else:
                        log.warning(f"  No confirmation button found")
                        failed += 1

                except Exception as e:
                    log.error(f"  Error: {e}")
                    failed += 1

            log.info(f"\n{'='*60}")
            log.info(f"STALE LISTING CLEANUP SUMMARY")
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
    parser = argparse.ArgumentParser(description="End stale eBay listings")
    parser.add_argument('--max', type=int, default=50, help='Max listings to end (default: 50)')
    parser.add_argument('--min-days', type=int, default=45, help='Min days listed (default: 45)')
    parser.add_argument('--min-views', type=int, default=1, help='Min page views (default: 1)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    args = parser.parse_args()

    filepath = find_latest_traffic_report()
    if not filepath:
        log.error("No eBay traffic report found in Downloads")
        return

    log.info(f"Using report: {filepath}")

    stale = find_stale_listings(filepath, min_days=args.min_days, min_views=args.min_views)

    if not stale:
        log.info("No stale listings found")
        return

    # Limit to --max
    stale = stale[:args.max]

    print(f"\n{'='*60}")
    print(f"STALE LISTINGS ({args.min_days}+ days, {args.min_views}+ views, 0 sales)")
    print(f"{'='*60}")
    print(f"Found: {len(stale)}")
    print()

    for i, item in enumerate(stale[:15]):
        print(f"  {i+1:3}. {item['title']}")
        print(f"       {item['days_listed']}d old | {item['views']} views | {item['impressions']} impressions")

    if len(stale) > 15:
        print(f"  ... and {len(stale) - 15} more")

    end_stale_listings(stale, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
