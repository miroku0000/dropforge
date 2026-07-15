"""
Optimize Promoted Offsite Campaign
Analyzes the promoted offsite report and pauses the campaign if ROAS is poor.

Since Promoted Offsite is a Smart campaign that auto-includes all listings,
individual listings can't be removed. Instead, this script monitors overall
campaign performance and pauses it if ROAS drops below the threshold.

Usage:
    python ai_ebay_optimize_promoted_offsite.py
    python ai_ebay_optimize_promoted_offsite.py --dry-run
    python ai_ebay_optimize_promoted_offsite.py --min-roas 3.0
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
CAMPAIGN_ID = "159005538019"
CAMPAIGN_URL = f"https://www.ebay.com/sh/ads/dashboard/campaign/{CAMPAIGN_ID}"

# Minimum ad spend before we have enough data to make a decision
MIN_AD_SPEND = 20.0


def find_latest_report():
    """Find the most recent Promoted offsite report."""
    files = []
    for directory in [DOWNLOAD_DIR, os.path.join(os.getcwd(), 'downloads')]:
        files.extend(glob.glob(os.path.join(directory, 'Promoted offsite*')))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def analyze_report(filepath):
    """Analyze the report and return campaign stats."""
    df = pd.read_csv(filepath, skiprows=1)
    df.columns = df.columns.str.strip()

    for col in ['Impressions', 'Clicks', 'Sold quantity']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    df['Fees'] = df['Ad fees'].str.replace(r'[\$,]', '', regex=True).astype(float)
    df['Rev'] = df['Sales'].str.replace(r'[\$,]', '', regex=True).astype(float)

    total_fees = df['Fees'].sum()
    total_sales = df['Rev'].sum()
    total_clicks = df['Clicks'].sum()
    total_sold = df['Sold quantity'].sum()
    total_impressions = df['Impressions'].sum()
    roas = total_sales / total_fees if total_fees > 0 else 0
    ad_pct = (total_fees / total_sales * 100) if total_sales > 0 else 100

    return {
        'total_fees': total_fees,
        'total_sales': total_sales,
        'total_clicks': total_clicks,
        'total_sold': total_sold,
        'total_impressions': total_impressions,
        'roas': roas,
        'ad_pct': ad_pct,
        'listings': len(df),
    }


def pause_campaign(dry_run=False):
    """Pause the Promoted Offsite campaign via the eBay dashboard."""
    if dry_run:
        log.info("DRY RUN -- would pause campaign")
        return True

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1400, "height": 900}, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            log.info(f"Opening {CAMPAIGN_URL}")
            page.goto(CAMPAIGN_URL, wait_until="load", timeout=60000)

            if "signin" in page.url.lower():
                log.warning("Please log in to eBay.")
                page.wait_for_url("**/sh/ads/**", timeout=120000)

            page.wait_for_timeout(3000)

            # Try "More actions" menu first (three dots button)
            more_btn = page.locator("button[aria-label='More actions']").first
            if more_btn.is_visible(timeout=5000):
                more_btn.click()
                page.wait_for_timeout(1000)

                # Screenshot the dropdown menu
                ss = os.path.join(DOWNLOAD_DIR, f"offsite_menu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss, full_page=False)
                log.info(f"Menu screenshot: {ss}")

                # Look for pause/end option in dropdown
                for selector in [
                    "text='Pause campaign'",
                    "text='End campaign'",
                    "text='Pause'",
                    "text='End'",
                    "a:has-text('Pause')",
                    "a:has-text('End')",
                    "button:has-text('Pause')",
                    "span:has-text('Pause campaign')",
                    "span:has-text('End campaign')",
                ]:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=1000):
                        loc.click()
                        page.wait_for_timeout(3000)
                        log.info(f"Clicked: {selector}")

                        # Confirm if needed
                        for confirm_sel in [
                            "button[data-testid='submit-button']",
                            "button.btn--primary:has-text('Pause')",
                            "button.btn--primary:has-text('End')",
                            "button.btn--primary:has-text('Confirm')",
                            "button.btn--primary:has-text('Yes')",
                        ]:
                            confirm = page.locator(confirm_sel).first
                            if confirm.is_visible(timeout=3000):
                                confirm.click()
                                log.info(f"Confirmed with: {confirm_sel}")
                                page.wait_for_timeout(3000)
                                break

                        ss2 = os.path.join(DOWNLOAD_DIR, f"offsite_paused_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                        page.screenshot(path=ss2, full_page=False)
                        log.info(f"Post-pause screenshot: {ss2}")
                        return True

                log.warning("No Pause/End option found in More actions menu")

            # Fallback: try Edit campaign link -> then look for pause on edit page
            edit_link = page.locator("a:has-text('Edit campaign')").first
            if edit_link.is_visible(timeout=3000):
                edit_link.click()
                page.wait_for_timeout(5000)
                log.info("Navigated to Edit campaign page")

                ss3 = os.path.join(DOWNLOAD_DIR, f"offsite_edit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                page.screenshot(path=ss3, full_page=True)
                log.info(f"Edit page screenshot: {ss3}")

                for selector in [
                    "button:has-text('Pause campaign')",
                    "button:has-text('End campaign')",
                    "a:has-text('Pause campaign')",
                    "a:has-text('End campaign')",
                    "text='Pause campaign'",
                    "text='End campaign'",
                ]:
                    loc = page.locator(selector).first
                    if loc.is_visible(timeout=2000):
                        loc.click()
                        page.wait_for_timeout(3000)
                        log.info(f"Clicked: {selector}")

                        for confirm_sel in [
                            "button[data-testid='submit-button']",
                            "button.btn--primary:has-text('Pause')",
                            "button.btn--primary:has-text('End')",
                            "button.btn--primary:has-text('Confirm')",
                        ]:
                            confirm = page.locator(confirm_sel).first
                            if confirm.is_visible(timeout=3000):
                                confirm.click()
                                log.info(f"Confirmed: {confirm_sel}")
                                page.wait_for_timeout(3000)
                                break

                        ss4 = os.path.join(DOWNLOAD_DIR, f"offsite_paused_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                        page.screenshot(path=ss4, full_page=True)
                        return True

            log.warning("Could not find a way to pause the campaign")
            ss5 = os.path.join(DOWNLOAD_DIR, f"offsite_no_pause_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=ss5, full_page=True)
            return False

        except Exception as e:
            log.error(f"Failed to pause campaign: {e}")
            return False

        finally:
            context.close()
            log.info("Browser closed")


def main():
    parser = argparse.ArgumentParser(description="Optimize Promoted Offsite Campaign")
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--min-roas', type=float, default=2.0,
                        help='Minimum ROAS to keep campaign active (default: 2.0)')
    args = parser.parse_args()

    filepath = find_latest_report()
    if not filepath:
        log.error("No Promoted offsite report found")
        return

    log.info(f"Using report: {filepath}")

    stats = analyze_report(filepath)

    print(f"\n{'='*60}")
    print(f"PROMOTED OFFSITE CAMPAIGN STATUS")
    print(f"{'='*60}")
    print(f"Listings: {stats['listings']}")
    print(f"Impressions: {stats['total_impressions']:,}")
    print(f"Clicks: {stats['total_clicks']:,}")
    print(f"Sold: {stats['total_sold']}")
    print(f"Ad fees: ${stats['total_fees']:.2f}")
    print(f"Sales: ${stats['total_sales']:.2f}")
    print(f"ROAS: {stats['roas']:.1f}x (minimum: {args.min_roas}x)")
    print(f"Ad cost as % of sales: {stats['ad_pct']:.1f}%")

    # Not enough data yet
    if stats['total_fees'] < MIN_AD_SPEND:
        print(f"\nNot enough ad spend (${stats['total_fees']:.2f} < ${MIN_AD_SPEND:.2f}) to evaluate.")
        print("Keeping campaign active to gather more data.")
        return

    # Check ROAS
    if stats['roas'] >= args.min_roas:
        print(f"\nROAS {stats['roas']:.1f}x >= {args.min_roas}x threshold. Campaign is profitable. No action needed.")
        return

    # ROAS is bad
    print(f"\nROAS {stats['roas']:.1f}x is BELOW {args.min_roas}x threshold.")
    print(f"Campaign is losing money (ad cost = {stats['ad_pct']:.0f}% of sales).")
    print(f"ACTION: Pausing campaign.")

    success = pause_campaign(dry_run=args.dry_run)
    if success:
        log.info("Campaign paused successfully.")
    else:
        log.error("Failed to pause campaign -- may need manual intervention.")


if __name__ == "__main__":
    main()
