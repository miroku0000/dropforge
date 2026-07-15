"""
Auto-maintain PriceYak order comments (frontend_details.orderNotes):

  * DELIVERED (shipment_state == Delivered), not returned, not fulfilled
    externally  ->  comment "delivered"
  * In transit / ordered-not-yet-delivered, not external, has an ETA
    ->  comment "ETA M/D/YYYY"   (e.g. "ETA 6/14/2026")

SAFETY: only writes when the current comment is EMPTY or one we set ourselves
("delivered" / "ETA ..."). It never overwrites a manual note (e.g. an external
order's price comment, or "Cancelled"/"Returned"). External, cancelled, and
returned/refunded orders are skipped entirely.

Comment is set via PUT /v0/account/{id}/orders/{order_id}
    {"frontend_details": {"orderNotes": "..."}}   (partial; leaves order intact)

Usage:
    python ai_priceyak_update_comments.py                 # update recent orders
    python ai_priceyak_update_comments.py --scan 600 --dry-run
"""

import argparse
import logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger(__name__)

import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY


def py_login():
    r = requests.post(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
                      json={"api_key": PY_API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def fetch_recent(token, scan):
    h = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    orders, off = [], 0
    while off < scan:
        d = requests.get(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders",
                         headers=h, params={"count": 100, "offset": off}, timeout=60).json().get("data", [])
        if not d:
            break
        orders.extend(d)
        off += len(d)
    return orders[:scan]


def _is_refunded(o):
    """Genuinely refunded (sale reversed) -- by returnStatus, not the comment."""
    rs = (o.get("destination_blob") or {}).get("returnStatus") or ""
    if "WithRefund" in rs:                            # ReturnRequestClosedWithRefund
        return True
    ret = (o.get("summary_state") or {}).get("return") or {}
    return "refund" in (str(ret.get("code") or "") + str(ret.get("state") or "")).lower()


def desired_comment(o):
    """The comment this order SHOULD have, or None if we shouldn't manage it.
    NOTE: only ever applied over an empty/own comment (see _is_ours) -- a cost
    note (external fulfillment) or any manual note is always left untouched."""
    if o.get("cancelled") or o.get("state") == "skipped":
        return None
    if _is_refunded(o):                               # refunded -> "refunded"
        return "refunded"
    if o.get("state") == "fulfilled_externally":      # external -> user owns the note (cost)
        return None
    rs = (o.get("destination_blob") or {}).get("returnStatus") or ""
    if rs and rs != "NotApplicable":                  # returned but not refunded -> leave it
        return None
    ship = o.get("shipment_state")
    if ship == "Delivered":
        return "delivered"
    eta = o.get("estimated_delivery_date")
    if ship in ("InTransit", "InfoReceived") and eta:
        d = datetime.fromtimestamp(eta, timezone.utc)   # delivery date is stored at UTC midnight
        return f"ETA {d.month}/{d.day}/{d.year}"
    return None


def _is_ours(note):
    """True only if the comment is empty or one we set -- so we NEVER overwrite a
    cost note (external order) or any other manual note."""
    n = (note or "").strip().lower()
    return n == "" or n in ("delivered", "refunded") or n.startswith("eta ")


def set_comment(token, order_id, text):
    r = requests.put(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders/{order_id}",
                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "*/*"},
                     json={"frontend_details": {"orderNotes": text}}, timeout=40)
    return r.status_code


def main():
    ap = argparse.ArgumentParser(description="Auto-set PriceYak delivered/ETA order comments")
    ap.add_argument("--scan", type=int, default=400, help="Recent orders to scan (default 400)")
    ap.add_argument("--max", type=int, default=400, help="Cap comment writes per run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = py_login()
    orders = fetch_recent(token, args.scan)
    log.info(f"Scanned {len(orders)} recent order(s).")

    updates = []
    for o in orders:
        want = desired_comment(o)
        if not want:
            continue
        cur = ((o.get("frontend_details") or {}).get("orderNotes") or "").strip()
        if cur == want or not _is_ours(cur):        # already right, or a manual/cost note -> leave it
            continue
        updates.append((o, cur, want))

    n_deliv = sum(1 for _, _, w in updates if w == "delivered")
    n_ref = sum(1 for _, _, w in updates if w == "refunded")
    n_eta = sum(1 for _, _, w in updates if w.startswith("ETA"))
    log.info(f"{len(updates)} comment(s) to set: {n_deliv} delivered, {n_ref} refunded, {n_eta} ETA.")

    done = 0
    for o, cur, want in updates[: args.max]:
        if args.dry_run:
            log.info(f"  [DRY] {o.get('id')} {o.get('buyer_username','')}: {cur!r} -> {want!r}")
            continue
        code = set_comment(token, o["id"], want)
        if code == 200:
            done += 1
        else:
            log.warning(f"  PUT {o.get('id')} -> HTTP {code}")
    if not args.dry_run:
        log.info(f"Set {done}/{len(updates[:args.max])} comment(s).")


if __name__ == "__main__":
    main()
