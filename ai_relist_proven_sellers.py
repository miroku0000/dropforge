"""
Relist Proven Sellers
Finds ASINs that previously sold well but are no longer listed,
then submits them to PriceYak for relisting.

Requires:
- PriceYak sales export CSV in downloads/ (export_*.csv)
- Active listing cache in .cache_item_details/

Usage:
    python ai_relist_proven_sellers.py                  # Relist top 50 with 2+ sales
    python ai_relist_proven_sellers.py --max 100        # Relist top 100
    python ai_relist_proven_sellers.py --min-sales 3    # Only 3+ sales
    python ai_relist_proven_sellers.py --dry-run        # Preview only
"""

import os
import sys
import glob
import pickle
import logging
import argparse
import requests
import pandas as pd
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

CACHE_DIR = '.cache_item_details'
DOWNLOADS_DIR = os.path.expanduser('~/Downloads')
LOCAL_DOWNLOADS = os.path.join(os.getcwd(), 'downloads')

import config
PRICEYAK_ACCOUNT_ID = config.PY_ACCOUNT_ID
PRICEYAK_API_KEY = config.PY_API_KEY


def get_active_asins():
    """Get ASINs from cached eBay item details (custom labels)."""
    active = set()
    if not os.path.exists(CACHE_DIR):
        return active
    for f in os.listdir(CACHE_DIR):
        try:
            with open(os.path.join(CACHE_DIR, f), 'rb') as fh:
                data = pickle.load(fh)
                label = data.get('CustomLabel', '')
                if label:
                    active.add(label)
        except Exception:
            continue
    return active


def find_priceyak_export():
    """Find the latest PriceYak sales export CSV."""
    for directory in [LOCAL_DOWNLOADS, DOWNLOADS_DIR]:
        pattern = os.path.join(directory, 'export_*.csv')
        files = glob.glob(pattern)
        if files:
            return max(files, key=os.path.getmtime)
    return None


def get_sold_asins(export_path):
    """Load sales history and aggregate by ASIN."""
    df = pd.read_csv(export_path, encoding='latin-1')
    sold = df[df['Source Item ID'].notna()].groupby('Source Item ID').agg(
        total_sold=('Order Quantity', 'sum'),
        last_sale=('Order Date', 'max'),
    ).sort_values('total_sold', ascending=False)
    return sold


def priceyak_login():
    """Login to PriceYak and get auth token."""
    resp = requests.post(
        f"https://www.priceyak.com/v0/account/{PRICEYAK_ACCOUNT_ID}/api_login",
        json={"api_key": PRICEYAK_API_KEY},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def submit_to_priceyak(asins, token):
    """Submit ASINs to PriceYak for listing."""
    resp = requests.post(
        f"https://www.priceyak.com:443/v0/account/{PRICEYAK_ACCOUNT_ID}/requests/create_batch",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
        json={
            "options": {
                "condition": "new",
                "disable_repricing": 0,
                "include_weight": 0,
                "list_variants": False,
                "needs_review": False,
                "payment_profile_id": "226060214021",
                "return_profile_id": "286754074021",
                "set_destination_tags": True,
                "set_source_tag": False,
                "shipping_profile_id": "280543477021",
                "slowly": False,
            },
            "product_ids": asins,
            "source": "amazon",
        },
    )
    return resp


def main():
    parser = argparse.ArgumentParser(description="Relist proven sellers via PriceYak")
    parser.add_argument('--max', type=int, default=50, help='Max ASINs to relist (default: 50)')
    parser.add_argument('--min-sales', type=int, default=2, help='Minimum past sales to qualify (default: 2)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not submit')
    args = parser.parse_args()

    # Find PriceYak export
    export_path = find_priceyak_export()
    if not export_path:
        log.error("No PriceYak export file found (export_*.csv)")
        return

    log.info(f"Using sales export: {export_path}")

    # Get active ASINs
    active_asins = get_active_asins()
    log.info(f"Active ASINs (from cache): {len(active_asins)}")

    # Get sold ASINs
    sold = get_sold_asins(export_path)
    log.info(f"ASINs with sales history: {len(sold)}")

    # Filter: sold 2+ times AND not currently listed
    qualified = sold[(sold['total_sold'] >= args.min_sales) & (~sold.index.isin(active_asins))]
    log.info(f"Qualified for relisting ({args.min_sales}+ sales, not active): {len(qualified)}")

    if qualified.empty:
        log.info("No ASINs to relist")
        return

    # Take top N
    to_relist = qualified.head(args.max)
    asins = list(to_relist.index)

    # Print summary
    print(f"\n{'='*60}")
    print(f"RELIST PROVEN SELLERS")
    print(f"{'='*60}")
    print(f"Min sales threshold: {args.min_sales}")
    print(f"Qualified ASINs: {len(qualified)}")
    print(f"Submitting: {len(asins)}")
    print()

    for i, (asin, row) in enumerate(to_relist.iterrows()):
        print(f"  {i+1:3}. {asin}: {int(row['total_sold'])} sold (last: {row['last_sale'][:10]})")

    if args.dry_run:
        print(f"\nDRY RUN -- not submitting to PriceYak")
        return

    # Submit to PriceYak
    print(f"\nSubmitting {len(asins)} ASINs to PriceYak...")
    token = priceyak_login()
    resp = submit_to_priceyak(asins, token)
    print(f"PriceYak response: {resp.status_code}")
    if resp.status_code == 200:
        log.info(f"Successfully submitted {len(asins)} ASINs for relisting")
    else:
        log.error(f"PriceYak error: {resp.text}")


if __name__ == "__main__":
    main()
