"""
Late-shipment / no-tracking monitor.

Late shipment is the #1 defect cause for dropshippers: if PriceYak/Amazon is
slow (or an order slips through), an eBay order can blow past its ship-by
deadline with no tracking uploaded -- which dings your seller standards.

This queries eBay's Sell Fulfillment API for orders that are NOT fully shipped
and flags any whose ship-by deadline is within --hours (default 24) or already
past. It pushes a digest via notify.py so you can act before the deadline.

Authoritative fields (eBay /sell/fulfillment/v1/order):
    orderFulfillmentStatus                 NOT_STARTED | IN_PROGRESS | FULFILLED
    lineItems[].lineItemFulfillmentStatus  per-item FULFILLED?
    lineItems[].lineItemFulfillmentInstructions.shipByDate   the deadline
    creationDate, buyer.username, lineItems[].title / legacyItemId

Usage:
    python ai_ebay_late_shipment_monitor.py                 # alert if <=24h to deadline
    python ai_ebay_late_shipment_monitor.py --hours 12
    python ai_ebay_late_shipment_monitor.py --no-push       # console only
"""

import sys
import argparse
import logging
from datetime import datetime, timezone

import requests
import ebay_utils
from notify import send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

ORDER_URL = "https://api.ebay.com/sell/fulfillment/v1/order"
# Orders that are not fully shipped yet.
UNSHIPPED_FILTER = "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}"


def _headers():
    tok = ebay_utils.load_credentials()["token"]
    return {"Authorization": "Bearer " + tok, "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}


def fetch_unshipped(headers, page=200):
    """Page through all not-fully-shipped orders."""
    orders, offset = [], 0
    while True:
        r = requests.get(
            ORDER_URL, headers=headers,
            params={"filter": UNSHIPPED_FILTER, "limit": page, "offset": offset},
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        batch = body.get("orders", []) or []
        orders.extend(batch)
        offset += len(batch)
        if not batch or offset >= body.get("total", 0):
            break
    return orders


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def earliest_ship_by(order):
    """Earliest ship-by deadline among line items that are not yet fulfilled."""
    deadlines = []
    for li in order.get("lineItems", []) or []:
        if (li.get("lineItemFulfillmentStatus") or "").upper() == "FULFILLED":
            continue
        instr = li.get("lineItemFulfillmentInstructions") or {}
        dt = _parse_dt(instr.get("shipByDate"))
        if dt:
            deadlines.append(dt)
    return min(deadlines) if deadlines else None


def assess(orders, hours, now):
    at_risk = []
    for o in orders:
        ship_by = earliest_ship_by(o)
        if ship_by is None:
            continue  # no deadline available; can't assess
        hours_left = (ship_by - now).total_seconds() / 3600.0
        if hours_left <= hours:
            li = (o.get("lineItems") or [{}])[0]
            at_risk.append({
                "order_id": o.get("orderId", ""),
                "legacy": li.get("legacyItemId", ""),
                "title": (li.get("title") or "")[:48],
                "buyer": (o.get("buyer") or {}).get("username", ""),
                "ship_by": ship_by,
                "hours_left": hours_left,
                "status": o.get("orderFulfillmentStatus", ""),
            })
    at_risk.sort(key=lambda x: x["hours_left"])
    return at_risk


def main():
    ap = argparse.ArgumentParser(description="Alert on eBay orders nearing/past their ship-by deadline with no tracking")
    ap.add_argument("--hours", type=float, default=24, help="Flag orders within this many hours of the ship-by deadline (default 24)")
    ap.add_argument("--no-push", action="store_true", help="Console only; do not send a push")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    try:
        orders = fetch_unshipped(_headers())
    except Exception as e:
        log.error(f"Fulfillment API call failed: {e}")
        if not args.no_push:
            send("Late-ship monitor ERROR", f"Could not query eBay orders: {e}", priority="high", tags="rotating_light")
        sys.exit(1)

    log.info(f"{len(orders)} order(s) not fully shipped.")
    at_risk = assess(orders, args.hours, now)

    overdue = [a for a in at_risk if a["hours_left"] < 0]
    soon = [a for a in at_risk if a["hours_left"] >= 0]

    print("=" * 64)
    print(f"LATE-SHIPMENT MONITOR  ({len(orders)} unshipped, {len(at_risk)} at risk)")
    print("=" * 64)
    for a in at_risk:
        when = f"{abs(a['hours_left']):.1f}h {'OVERDUE' if a['hours_left'] < 0 else 'left'}"
        print(f"  {when:<14} ship-by {a['ship_by']:%m-%d %H:%M}  {a['legacy']:<13} {a['title']}")
    if not at_risk:
        print("  All clear -- no orders near their ship-by deadline.")

    if args.no_push:
        return

    if at_risk:
        lines = [f"{len(overdue)} OVERDUE, {len(soon)} due within {args.hours:.0f}h (of {len(orders)} unshipped)"]
        for a in at_risk[:15]:
            tag = "OVERDUE" if a["hours_left"] < 0 else f"{a['hours_left']:.0f}h"
            lines.append(f"{tag}: {a['legacy']} {a['title']}")
        title = f"eBay: {len(overdue)} overdue, {len(soon)} shipping soon" if overdue else f"eBay: {len(soon)} order(s) shipping soon"
        send(title, "\n".join(lines), priority="high" if overdue else "default", tags="rotating_light" if overdue else "warning")
    else:
        log.info("No at-risk orders; no push sent.")


if __name__ == "__main__":
    main()
