"""
Daily P&L Summary
Uses the PriceYak sales export to calculate profit per item.
Uses Total Fulfillment Cost from PriceYak (actual Amazon cost paid)
instead of scraping Amazon prices.

Usage:
    python ai_daily_pnl.py                    # Yesterday's sales
    python ai_daily_pnl.py --days 7           # Last 7 days
    python ai_daily_pnl.py --days 30          # Last 30 days
"""

import os
import re
import sys
import glob
import argparse
import logging
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_pnl.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
LOCAL_DOWNLOADS = os.path.join(os.getcwd(), 'downloads')
PNL_LOG = 'daily_pnl_history.csv'
EBAY_FEE_RATE = 0.13


def find_priceyak_export():
    """Find the latest PriceYak sales export."""
    files = []
    for directory in [LOCAL_DOWNLOADS, DOWNLOAD_DIR]:
        files.extend(glob.glob(os.path.join(directory, 'export_*.csv')))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def clean_currency(val):
    """Convert '$  123.45' to float."""
    if pd.isna(val):
        return None
    return float(str(val).replace('$', '').replace(',', '').strip())


def get_sales(export_path, start_date, end_date):
    """Get sales from PriceYak export for the date range."""
    df = pd.read_csv(export_path, encoding='latin-1')
    df['Order Date'] = pd.to_datetime(df['Order Date'])

    sales = df[(df['Order Date'] >= start_date) & (df['Order Date'] < end_date)].copy()

    sales['Price'] = sales['Txn Price'].apply(clean_currency)
    sales['Fulfillment Cost'] = sales['Total Fulfillment Cost'].apply(clean_currency)
    sales['FVF'] = sales['FVF Fee'].apply(clean_currency)

    # Skip cancelled and returned orders
    notes = sales['Notes'].fillna('').str.lower()
    sales = sales[~notes.str.contains('cancel|return|refund')]

    # If fulfillment cost is 0 or missing, try to extract a dollar amount from Notes
    for idx, row in sales.iterrows():
        if (row['Fulfillment Cost'] is None or row['Fulfillment Cost'] == 0):
            note = str(row.get('Notes', ''))
            cost_match = re.search(r'\$?([\d]+\.?\d*)', note)
            if cost_match and 'cancel' not in note.lower() and 'return' not in note.lower():
                sales.at[idx, 'Fulfillment Cost'] = float(cost_match.group(1))

    return sales


def main():
    parser = argparse.ArgumentParser(description="Daily P&L Report")
    parser.add_argument('--days', type=int, default=1, help='Number of days to report (default: 1 = yesterday)')
    args = parser.parse_args()

    today = pd.Timestamp.now().normalize()
    start_date = today - timedelta(days=args.days)
    end_date = today

    log.info("=" * 60)
    log.info("DAILY P&L REPORT")
    log.info("=" * 60)
    log.info(f"Period: {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}")

    export_path = find_priceyak_export()
    if not export_path:
        log.error("No PriceYak export found (export_*.csv)")
        return
    log.info(f"PriceYak export: {os.path.basename(export_path)}")

    sales = get_sales(export_path, start_date, end_date)
    log.info(f"Sales in period: {len(sales)}")

    if sales.empty:
        print(f"\nNo sales found for {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}")
        return

    # Process each sale
    results = []
    for _, row in sales.iterrows():
        item_id = str(int(row['Destination Item ID'])) if pd.notna(row['Destination Item ID']) else 'N/A'
        asin = str(row['Source Item ID']) if pd.notna(row['Source Item ID']) and str(row['Source Item ID']) != 'nan' else 'N/A'
        order_date = row['Order Date'].strftime('%m/%d %H:%M')
        qty = int(row.get('Order Quantity', 1))
        ebay_price = row['Price'] or 0
        fulfillment_cost = row['Fulfillment Cost']
        fvf_fee = row['FVF'] or 0

        revenue = ebay_price * qty
        cost = fulfillment_cost if fulfillment_cost else None
        # Use actual FVF fee from PriceYak if available, otherwise estimate
        ebay_fees = fvf_fee if fvf_fee > 0 else revenue * EBAY_FEE_RATE
        profit = revenue - cost - ebay_fees if cost is not None else None

        results.append({
            'date': order_date,
            'item_id': item_id,
            'asin': asin,
            'qty': qty,
            'revenue': revenue,
            'cost': cost,
            'ebay_fees': ebay_fees,
            'profit': profit,
        })

    # Print report
    period = start_date.strftime('%Y-%m-%d')
    if args.days > 1:
        period = f"{start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}"

    print(f"\n{'='*72}")
    print(f"  DAILY P&L REPORT -- {period}")
    print(f"{'='*72}")
    print(f"  {'Date':<12} {'ASIN':<12} {'Qty':>3} {'Revenue':>9} {'Cost':>9} {'Fees':>7} {'Profit':>9}")
    print(f"  {'-'*12} {'-'*12} {'-'*3} {'-'*9} {'-'*9} {'-'*7} {'-'*9}")

    total_revenue = 0
    total_cost = 0
    total_fees = 0
    total_profit = 0
    items_without_cost = 0

    for r in results:
        cst = f"${r['cost']:.2f}" if r['cost'] is not None else "???"
        pft = f"${r['profit']:.2f}" if r['profit'] is not None else "???"
        print(f"  {r['date']:<12} {r['asin']:<12} {r['qty']:>3} ${r['revenue']:>7.2f} {cst:>9} ${r['ebay_fees']:>5.2f} {pft:>9}")

        total_revenue += r['revenue']
        total_fees += r['ebay_fees']
        if r['cost'] is not None:
            total_cost += r['cost']
        else:
            items_without_cost += 1
        if r['profit'] is not None:
            total_profit += r['profit']

    print(f"  {'-'*12} {'-'*12} {'-'*3} {'-'*9} {'-'*9} {'-'*7} {'-'*9}")
    print(f"  {'TOTALS':<12} {'':>12} {len(results):>3} ${total_revenue:>7.2f} ${total_cost:>7.2f} ${total_fees:>5.2f} ${total_profit:>7.2f}")
    print()
    print(f"  Revenue:        ${total_revenue:>9.2f}")
    print(f"  Fulfillment:   -${total_cost:>9.2f}")
    print(f"  eBay fees:     -${total_fees:>9.2f}")
    print(f"  PROFIT:         ${total_profit:>9.2f}")

    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    print(f"  Margin:          {margin:>8.1f}%")

    if items_without_cost:
        print(f"\n  ({items_without_cost} items missing fulfillment cost)")

    print(f"{'='*72}")

    # Append to history log
    log_entry = {
        'date': start_date.strftime('%Y-%m-%d'),
        'items_sold': len(results),
        'total_qty': sum(r['qty'] for r in results),
        'revenue': total_revenue,
        'fulfillment_cost': total_cost,
        'ebay_fees': total_fees,
        'profit': total_profit,
        'margin_pct': margin,
        'items_without_cost': items_without_cost,
    }

    if os.path.exists(PNL_LOG):
        history = pd.read_csv(PNL_LOG)
        history = history[history['date'] != log_entry['date']]
        history = pd.concat([history, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        history = pd.DataFrame([log_entry])

    history.to_csv(PNL_LOG, index=False)
    log.info(f"P&L saved to {PNL_LOG}")


if __name__ == "__main__":
    main()
