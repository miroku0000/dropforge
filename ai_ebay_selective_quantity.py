"""
Selective listing quantity -- stop wasting the eBay DOLLAR selling limit on
"second units" that never sell, while keeping PROVEN sellers at quantity 2 so a
successful listing never goes dark after a sale.

Why
---
eBay's dollar selling limit counts price * quantity. With every listing at
quantity 2, ~half the limit is spent on the second unit of listings that mostly
never sell (only a fraction of active listings ever get an order). That pins the
store far below the PriceYak plan size -> fewer listings -> fewer impressions ->
fewer sales. Setting unproven listings to quantity 1 and proven ones to quantity
2 reclaims that headroom so the store can grow toward the plan cap.

Rule (per ACTIVE listing)
-------------------------
    proven  (order_count >= --min-sales, or sold within --recent-days) -> qty 2
    unproven                                                            -> qty 1
    out-of-stock (quantity == 0 or oos_time set)                        -> skip

We set PriceYak `override_quantity` so the result is deterministic regardless of
the account's default quantity, and idempotent (skip if already at target).
PriceYak pushes the new quantity to eBay on its next repricing pass; use
--force-revise to also request an immediate revise (heavier -- eBay revise calls).

DRY-RUN by default: prints the plan + the dollar headroom it would reclaim.
    python ai_ebay_selective_quantity.py                    # dry-run, full plan
    python ai_ebay_selective_quantity.py --apply --limit 1  # canary ONE change
    python ai_ebay_selective_quantity.py --apply            # apply everything
"""

import sys
import time
import argparse
import logging
from datetime import datetime, timezone

import requests

from refresh_transactions import PY_ACCOUNT_ID, PY_API_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

BASE = f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}"
PAGE_SIZE = 200


def py_login():
    r = requests.post(f"{BASE}/api_login", json={"api_key": PY_API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def fetch_active_listings(token):
    """Page through every ACTIVE PriceYak listing."""
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    out, offset, total = [], 0, None
    while True:
        url = (f"{BASE}/listings?count={PAGE_SIZE}&offset={offset}"
               f"&include_inactive=false&accurate_count=true")
        r = requests.get(url, headers=headers, timeout=60).json()
        total = r.get("total_count", total)
        d = r.get("data") or []
        if not d:
            break
        out.extend(d)
        offset += len(d)
        if offset >= (total or 0):
            break
    return out, (total or len(out))


def set_override_quantity(token, listing_id, q, force_revise=False):
    """PUT a partial update to one listing (mirrors ai_priceyak_update_comments'
    order PUT). Returns (status_code, body_snippet)."""
    body = {"override_quantity": q}
    if force_revise:
        body["force_revise"] = True
    r = requests.put(
        f"{BASE}/listings/{listing_id}",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json", "Accept": "*/*"},
        json=body, timeout=40,
    )
    return r.status_code, r.text[:200]


def is_oos(L):
    return (L.get("quantity") or 0) == 0 or L.get("oos_time")


def is_proven(L, min_sales, recent_days, now):
    if (L.get("order_count") or 0) >= min_sales:
        return True
    if recent_days:
        lot = L.get("last_order_time")
        if lot and lot >= now - recent_days * 86400:
            return True
    return False


def effective_qty(L):
    """The quantity currently in force: explicit override wins, else the
    account-default quantity that PriceYak already applied to the listing."""
    ov = L.get("override_quantity")
    return ov if ov is not None else (L.get("quantity") or 0)


def main():
    ap = argparse.ArgumentParser(description="Set qty 1 on unproven listings, qty 2 on proven sellers (PriceYak override_quantity).")
    ap.add_argument("--apply", action="store_true", help="Actually write changes (default: dry-run).")
    ap.add_argument("--limit", type=int, default=0, help="Max number of listings to CHANGE this run (0 = no cap). Use --limit 1 to canary.")
    ap.add_argument("--min-sales", type=int, default=1, help="order_count >= this => proven => keep qty 2 (default 1).")
    ap.add_argument("--recent-days", type=int, default=0, help="Also treat as proven if it sold within this many days (0 = off).")
    ap.add_argument("--proven-qty", type=int, default=2, help="Quantity for proven sellers (default 2).")
    ap.add_argument("--lean-qty", type=int, default=1, help="Quantity for unproven listings (default 1).")
    ap.add_argument("--force-revise", action="store_true", help="Also request an immediate eBay revise (heavier).")
    ap.add_argument("--sleep", type=float, default=0.15, help="Seconds between write calls (default 0.15).")
    args = ap.parse_args()

    now = int(datetime.now(timezone.utc).timestamp())
    token = py_login()
    listings, total = fetch_active_listings(token)
    log.info(f"Fetched {len(listings)} active listings (total_count={total}).")

    reduce_changes, bump_changes, skipped_oos, already_ok = [], [], 0, 0
    reclaimed_cents = 0
    for L in listings:
        if is_oos(L):
            skipped_oos += 1
            continue
        cur = effective_qty(L)
        want = args.proven_qty if is_proven(L, args.min_sales, args.recent_days, now) else args.lean_qty
        if cur == want:
            already_ok += 1
            continue
        price = L.get("price") or 0
        rec = {"id": L.get("id"), "itemid": L.get("itemid"),
               "title": (L.get("title") or "")[:48], "price": price,
               "cur": cur, "want": want, "order_count": L.get("order_count") or 0}
        if want < cur:
            reclaimed_cents += price * (cur - want)
            reduce_changes.append(rec)
        else:
            bump_changes.append(rec)

    # Reductions first (they free dollar headroom); biggest value first so a
    # capped/canary run frees the most room per call.
    reduce_changes.sort(key=lambda r: r["price"] * (r["cur"] - r["want"]), reverse=True)
    changes = reduce_changes + bump_changes

    print("=" * 68)
    print("  SELECTIVE QUANTITY PLAN")
    print("=" * 68)
    print(f"  active (in stock):            {len(listings) - skipped_oos}")
    print(f"  skipped (out of stock):       {skipped_oos}")
    print(f"  already at target quantity:   {already_ok}")
    print(f"  REDUCE unproven -> qty {args.lean_qty}:      {len(reduce_changes)}")
    print(f"  BUMP proven    -> qty {args.proven_qty}:      {len(bump_changes)}")
    print(f"  dollar headroom reclaimed:    ${reclaimed_cents/100:,.2f}")
    if args.limit:
        print(f"  (--limit {args.limit}: only the first {args.limit} change(s) will be written)")
    print("=" * 68)
    for r in changes[: (args.limit or 10)]:
        arrow = f"{r['cur']}->{r['want']}"
        print(f"    {arrow}  ${r['price']/100:>7.2f}  oc={r['order_count']}  {r['itemid']}  {r['title']}")
    if not args.limit and len(changes) > 10:
        print(f"    ... and {len(changes) - 10} more")

    if not args.apply:
        print("\nDRY-RUN. Re-run with --apply (add --limit 1 to canary a single change).")
        return

    to_write = changes[: args.limit] if args.limit else changes
    log.info(f"Applying {len(to_write)} change(s)...")
    ok = fail = 0
    for i, r in enumerate(to_write, 1):
        code, body = set_override_quantity(token, r["id"], r["want"], args.force_revise)
        if 200 <= code < 300:
            ok += 1
            log.info(f"  [{i}/{len(to_write)}] {r['itemid']} {r['cur']}->{r['want']} OK ({code})")
        else:
            fail += 1
            log.warning(f"  [{i}/{len(to_write)}] {r['itemid']} {r['cur']}->{r['want']} FAIL {code}: {body}")
        time.sleep(args.sleep)
    log.info(f"Done. ok={ok} fail={fail}. Reclaimed ~${reclaimed_cents/100:,.0f} once reductions propagate.")


if __name__ == "__main__":
    main()
