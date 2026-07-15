"""
Enforce a maximum number of active eBay listings.
Checks current count and deletes zero-view listings until under the limit.

Usage:
    python ai_ebay_enforce_max_listings.py 2500
    python ai_ebay_enforce_max_listings.py --max 2500
"""

import sys
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ebay_ads_automation.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def get_listing_count():
    result = subprocess.run(
        [sys.executable, "ai_ebay_count_current_listings.py"],
        capture_output=True, text=True, timeout=120
    )
    return int(result.stdout.strip())


def delete_zero_view_batch():
    result = subprocess.run(
        [sys.executable, "ai_ebay_delete_zero_view_listings.py"],
        capture_output=True, text=True, timeout=300
    )
    log.info(result.stdout.strip().split('\n')[-1] if result.stdout.strip() else "No output")
    return result.returncode == 0


def main():
    # Parse max listings argument
    max_listings = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--max' and i < len(sys.argv) - 1:
            max_listings = int(sys.argv[i + 1])
        elif arg.isdigit():
            max_listings = int(arg)

    if not max_listings:
        print("Usage: python ai_ebay_enforce_max_listings.py 2500")
        sys.exit(1)

    log.info(f"Max listings allowed: {max_listings}")

    # Check current count
    current = get_listing_count()
    log.info(f"Current active listings: {current}")

    if current <= max_listings:
        log.info(f"Under limit ({current} <= {max_listings}). Nothing to do.")
        return

    # Cancel pending PriceYak listings before deleting
    log.info("Cancelling pending PriceYak listings...")
    subprocess.run([sys.executable, "ai_priceyak_cancel_pending_listings.py"], timeout=30)


    rounds = 0
    while current > max_listings:
        over = current - max_listings
        rounds += 1
        log.info(f"Over limit by {over}. Deleting zero-view listings (round {rounds})...")

        if not delete_zero_view_batch():
            log.error("Delete script failed. Stopping.")
            break

        current = get_listing_count()
        log.info(f"Current active listings after round {rounds}: {current}")

    if current <= max_listings:
        log.info(f"Done. Now at {current} listings (limit: {max_listings}).")
    else:
        log.warning(f"Still at {current} listings after {rounds} rounds. May need manual cleanup.")


if __name__ == "__main__":
    main()
