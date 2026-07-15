"""
Build monthly P&L rows: COGS (PriceYak) + Revenue/net-sales (eBay scrape).

Computes, for each requested month, the values we can derive automatically and
prints them. Month bounds are Pacific (to match the eBay dashboard).

Usage:
    python pnl_build.py 2026-01 2026-02 2026-03 2026-04 2026-05
    python pnl_build.py 2026-01 --no-ebay      # COGS only (fast, no browser)
    python pnl_build.py 2026-01 --json
"""

import sys
import json
import argparse
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo

from pnl_month import py_login, fetch_orders_until, cost_of

PACIFIC = ZoneInfo("America/Los_Angeles")


def pac_bounds(year, month):
    start = int(datetime(year, month, 1, tzinfo=PACIFIC).timestamp())
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    end = int(datetime(ny, nm, 1, tzinfo=PACIFIC).timestamp())
    return start, end


def month_cogs(orders, year, month):
    start, end = pac_bounds(year, month)
    mo = [o for o in orders if start <= (o.get("created_time") or 0) < end and not o.get("cancelled")]
    cogs = 0.0
    unknown = []
    for o in mo:
        c, src, note = cost_of(o)
        cogs += c
        if src == "none":
            unknown.append({"id": o.get("id"), "buyer": o.get("buyer_username"), "state": o.get("state")})
    return {"orders": len(mo), "cogs": round(cogs, 2), "unknown": unknown}


def parse_month(s):
    y, m = s.split("-")
    return int(y), int(m)


def main():
    ap = argparse.ArgumentParser(description="Build monthly P&L rows (COGS + eBay revenue/net)")
    ap.add_argument("months", nargs="+", help="Months as YYYY-MM")
    ap.add_argument("--no-ebay", action="store_true", help="Skip eBay scrape (COGS only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    months = [parse_month(m) for m in args.months]

    # --- COGS: one PriceYak pass back to the earliest month ---
    token = py_login()
    earliest = min(pac_bounds(y, m)[0] for y, m in months)
    orders = fetch_orders_until(token, earliest)
    cogs_by = {(y, m): month_cogs(orders, y, m) for y, m in months}

    # --- eBay revenue / net sales: one browser session ---
    ebay_by = {}
    if not args.no_ebay:
        from playwright.sync_api import sync_playwright
        from playwright_browser import launch_ebay_browser
        import ai_ebay_sales_performance as eb
        with sync_playwright() as p:
            ctx = launch_ebay_browser(p, viewport={"width": 1500, "height": 950}, accept_downloads=False)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                for y, m in months:
                    try:
                        ebay_by[(y, m)] = eb.extract(page, y, m)
                    except Exception as e:
                        ebay_by[(y, m)] = {"revenue": None, "net_sales": None, "error": str(e)[:80]}
            finally:
                ctx.close()

    rows = []
    for y, m in months:
        label = f"{calendar.month_abbr[m]}-{str(y)[2:]}"
        c = cogs_by[(y, m)]
        e = ebay_by.get((y, m), {})
        rows.append({"month": label, "revenue": e.get("revenue"), "net_sales": e.get("net_sales"),
                     "cogs": c["cogs"], "orders": c["orders"], "unknown_cost": c["unknown"]})

    if args.json:
        print(json.dumps(rows, indent=2))
        return

    print(f"\n{'Month':<8}{'Revenue':>12}{'Net sales':>12}{'COGS':>12}{'Orders':>8}{'?cost':>7}")
    print("-" * 59)
    for r in rows:
        rev = f"{r['revenue']:,.2f}" if r["revenue"] is not None else "--"
        net = f"{r['net_sales']:,.2f}" if r["net_sales"] is not None else "--"
        print(f"{r['month']:<8}{rev:>12}{net:>12}{r['cogs']:>12,.2f}{r['orders']:>8}{len(r['unknown_cost']):>7}")
    for r in rows:
        if r["unknown_cost"]:
            print(f"\n{r['month']} external orders with NO parseable cost:")
            for u in r["unknown_cost"]:
                print(f"   {u['id']}  {u['buyer']}  state={u['state']}")


if __name__ == "__main__":
    main()
