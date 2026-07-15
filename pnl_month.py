"""
Compute a month's COGS (Amazon cost) from PriceYak orders.

COGS source per order:
  * PriceYak-fulfilled: zinc_response_blob.price_components.converted_payment_total
    (cents) -- the actual total paid to Amazon.
  * Externally fulfilled (state == fulfilled_externally): the price you typed in
    the order comment (frontend_details.orderNotes). We grab the $ amount.
  * Cancelled orders are skipped (refunded -> no COGS).

This is the cost side of the monthly P&L sheet. Revenue / net-sales come from
eBay (entered separately). Reports any external order whose cost we could not
parse, so you can fill it in.

Usage:
    python pnl_month.py --year 2026 --month 1
    python pnl_month.py --year 2026 --month 1 --json
"""

import re
import sys
import json
import argparse
import calendar
from datetime import datetime, timezone

import requests

import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

# Cost amounts in freeform comments. Priority: total after '=' (e.g.
# "97.99*2=195.98"), amount after "for" (e.g. "ordered for 244"), else the
# largest money-looking number (ignoring year-like integers and eta day numbers).
_EQ = re.compile(r"=\s*\$?\s*([0-9]+(?:\.[0-9]{1,2})?)")
_FOR = re.compile(r"\bfor\s+\$?\s*([0-9]+(?:\.[0-9]{1,2})?)")
_ANY = re.compile(r"\$?([0-9]+(?:\.[0-9]{1,2})?)")


def parse_note_cost(note):
    """Best-effort cost from a freeform comment, or None."""
    for rx in (_EQ, _FOR):
        m = rx.search(note)
        if m:
            return float(m.group(1))
    nums = [float(x) for x in _ANY.findall(note)]
    # Drop bare day-of-month/year-ish integers that are clearly not the price.
    nums = [n for n in nums if not (n == int(n) and (n <= 31 or 1900 <= n <= 2100))]
    return max(nums) if nums else None


def py_login():
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
        json={"api_key": PY_API_KEY}, timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def month_bounds(year, month):
    start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
    last = calendar.monthrange(year, month)[1]
    nm_year, nm_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = int(datetime(nm_year, nm_month, 1, tzinfo=timezone.utc).timestamp())
    return start, end


def fetch_orders_until(token, before_ts):
    """Page newest-first until we pass before_ts; return all orders fetched."""
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    orders, offset = [], 0
    while offset < 5000:
        d = requests.get(
            f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders",
            headers=headers, params={"count": 100, "offset": offset}, timeout=60,
        ).json().get("data", [])
        if not d:
            break
        orders.extend(d)
        offset += len(d)
        if min((o.get("created_time") or 9e18) for o in d) < before_ts:
            break
    return orders


def _is_refunded(o):
    """A genuinely REFUNDED order carries $0 COGS (the sale was reversed; the
    refund is handled on the revenue side / eBay net sales). Only zero on an
    actual refund -- NOT on returns closed WITHOUT a refund (those sales stand
    and their cost counts), nor on pending returns."""
    rs = (o.get("destination_blob") or {}).get("returnStatus") or ""
    if "WithRefund" in rs:                      # ReturnRequestClosedWithRefund
        return True
    note = ((o.get("frontend_details") or {}).get("orderNotes") or "").lower()
    if "refund" in note:
        return True
    ret = (o.get("summary_state") or {}).get("return") or {}
    return "refund" in (str(ret.get("code") or "") + str(ret.get("state") or "")).lower()


def cost_of(o):
    """Return (cost, source, note). source in {zinc, note, refunded, none}."""
    if _is_refunded(o):
        return 0.0, "refunded", ((o.get("frontend_details") or {}).get("orderNotes") or "")
    zr = o.get("zinc_response_blob")
    if isinstance(zr, dict):
        pc = zr.get("price_components") or {}
        t = pc.get("converted_payment_total")
        if t:
            return t / 100.0, "zinc", ""
    note = ((o.get("frontend_details") or {}).get("orderNotes") or "").strip()
    c = parse_note_cost(note)
    if c is not None:
        return c, "note", note
    return 0.0, "none", note


def main():
    ap = argparse.ArgumentParser(description="Compute a month's COGS from PriceYak orders")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--json", action="store_true", help="Emit a JSON summary")
    args = ap.parse_args()

    start, end = month_bounds(args.year, args.month)
    token = py_login()
    orders = fetch_orders_until(token, start)
    month_orders = [o for o in orders
                    if start <= (o.get("created_time") or 0) < end and not o.get("cancelled")]

    cogs = 0.0
    revenue = 0.0
    by_src = {"zinc": 0, "note": 0, "none": 0, "refunded": 0}
    unknown = []     # external/other orders with no parseable cost
    note_costs = []  # external orders where we DID parse a cost (for your review)
    for o in month_orders:
        c, src, note = cost_of(o)
        cogs += c
        revenue += (o.get("amount_paid") or 0) / 100.0
        by_src[src] += 1
        rec = {"id": o.get("id"), "buyer": o.get("buyer_username", ""),
               "ebay_order": o.get("destination_order_id", ""), "state": o.get("state"),
               "note": note[:60], "parsed_cost": c}
        if src == "none":
            unknown.append(rec)
        elif src == "note":
            note_costs.append(rec)

    label = f"{calendar.month_abbr[args.month]}-{str(args.year)[2:]}"
    if args.json:
        print(json.dumps({"month": label, "orders": len(month_orders),
                          "cogs": round(cogs, 2), "py_revenue": round(revenue, 2),
                          "by_source": by_src,
                          "unknown_cost_orders": unknown, "external_parsed": note_costs}, indent=2))
        return

    print("=" * 64)
    print(f"  {label}  PriceYak COGS")
    print("=" * 64)
    print(f"  orders (non-cancelled):   {len(month_orders)}")
    print(f"  COGS (Amazon cost):       ${cogs:,.2f}")
    print(f"  PriceYak buyer-revenue:   ${revenue:,.2f}   (eBay-side sanity check)")
    print(f"  sources: zinc={by_src['zinc']}  comment={by_src['note']}  UNKNOWN={by_src['none']}")
    if note_costs:
        print(f"\n  External orders (cost read from your comment) -- please sanity check:")
        for r in note_costs:
            print(f"    ${r['parsed_cost']:>8.2f}  {r['id']}  {r['buyer']:<14} note: {r['note']!r}")
    if unknown:
        print(f"\n  !! External/other orders with NO cost found ({len(unknown)}) -- need your input:")
        for r in unknown:
            print(f"    {r['id']}  {r['buyer']:<14} state={r['state']:<20} note: {r['note']!r}")
    print("=" * 64)


if __name__ == "__main__":
    main()
