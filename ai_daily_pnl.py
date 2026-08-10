"""
Daily P&L Summary
Pulls orders live from the PriceYak API (same source as pnl_month.py) and
calculates profit per item. Uses the actual Amazon cost paid
(zinc_response_blob.price_components, or the cost typed in the order comment
for externally-fulfilled orders) instead of scraping Amazon prices.

Previously this read a manually-downloaded PriceYak `export_*.csv` from
~/Downloads; that export stopped being produced, so the report silently
returned nothing. It now hits the API directly and needs no CSV.

Usage:
    python ai_daily_pnl.py                    # Yesterday's sales
    python ai_daily_pnl.py --days 7           # Last 7 days
    python ai_daily_pnl.py --days 30          # Last 30 days
"""

import os
import argparse
import logging
from datetime import datetime, timedelta

import pandas as pd

# Reuse the PriceYak API helpers from the monthly P&L so there is a single
# source of truth for login / paging / per-order cost logic.
from pnl_month import py_login, fetch_orders_until, cost_of

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_pnl.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

PNL_LOG = 'daily_pnl_history.csv'
EBAY_FEE_RATE = 0.13


def _item_info(o):
    """(asin, ebay_item_id, qty) from the order's first line item."""
    items = o.get('items') or []
    it = items[0] if items else {}
    listing = it.get('listing') or {}
    asin = it.get('product_id') or 'N/A'
    item_id = listing.get('itemid') or o.get('destination_record_number') or 'N/A'
    try:
        qty = int(it.get('quantity') or 1)
    except (TypeError, ValueError):
        qty = 1
    return str(asin), str(item_id), qty


def _ebay_fees(o, revenue):
    """Actual eBay fees from PriceYak (cents), falling back to a flat estimate."""
    fees = o.get('destination_fees')
    if fees:
        return fees / 100.0
    return revenue * EBAY_FEE_RATE


def get_sales(start_ts, end_ts):
    """Fetch non-cancelled PriceYak orders created in [start_ts, end_ts)."""
    token = py_login()
    orders = fetch_orders_until(token, start_ts)
    return [o for o in orders
            if start_ts <= (o.get('created_time') or 0) < end_ts
            and not o.get('cancelled')]


def main():
    parser = argparse.ArgumentParser(description="Daily P&L Report")
    parser.add_argument('--days', type=int, default=1, help='Number of days to report (default: 1 = yesterday)')
    args = parser.parse_args()

    # Day boundaries at local midnight; .timestamp() converts to epoch seconds
    # to match PriceYak's created_time (epoch UTC).
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = today - timedelta(days=args.days)
    end_dt = today
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    log.info("=" * 60)
    log.info("DAILY P&L REPORT")
    log.info("=" * 60)
    log.info(f"Period: {start_dt.strftime('%Y-%m-%d')} to {(end_dt - timedelta(days=1)).strftime('%Y-%m-%d')}")

    orders = get_sales(start_ts, end_ts)
    log.info(f"Sales in period: {len(orders)}")

    if not orders:
        print(f"\nNo sales found for {start_dt.strftime('%Y-%m-%d')} to {(end_dt - timedelta(days=1)).strftime('%Y-%m-%d')}")
        return

    # Process each sale. Revenue (amount_paid) and cost (cost_of) are already
    # per-order totals including quantity, so we do NOT multiply by qty.
    results = []
    for o in sorted(orders, key=lambda x: x.get('created_time') or 0):
        asin, item_id, qty = _item_info(o)
        order_date = datetime.fromtimestamp(o.get('created_time') or 0).strftime('%m/%d %H:%M')
        revenue = (o.get('amount_paid') or 0) / 100.0

        cost, src, _note = cost_of(o)
        # Refunded orders carry $0 COGS but the sale was reversed -- skip them
        # so they don't inflate the day's revenue/profit.
        if src == 'refunded':
            continue
        # 'none' means we couldn't determine the Amazon cost for this order.
        cost = cost if src != 'none' else None
        ebay_fees = _ebay_fees(o, revenue)
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

    if not results:
        print(f"\nNo billable sales for {start_dt.strftime('%Y-%m-%d')} to {(end_dt - timedelta(days=1)).strftime('%Y-%m-%d')}")
        return

    # Print report
    period = start_dt.strftime('%Y-%m-%d')
    if args.days > 1:
        period = f"{start_dt.strftime('%Y-%m-%d')} to {(end_dt - timedelta(days=1)).strftime('%Y-%m-%d')}"

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
        'date': start_dt.strftime('%Y-%m-%d'),
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
