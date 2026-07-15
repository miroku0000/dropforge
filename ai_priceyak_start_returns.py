"""
For each new eBay return that needs a label, try to start a return on PriceYak
(Amazon "gift return"). If that fails (it usually does), open a PriceYak case
with reason "Returns -> Request a return label" so support will reply with the
return-shipping-label URL.

Script B (ai_ebay_upload_return_labels.py) handles the second half: detects
when the label URL is available on the PriceYak order page, downloads it, and
uploads it to the matching eBay return case.

State is stored in data/return_state.json so we don't act on a return twice.

Usage:
    python ai_priceyak_start_returns.py [--dry-run]
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

import ebay_utils
from priceyakblacklistadd import ACCOUNT_ID as PY_ACCOUNT_ID, API_KEY as PY_API_KEY, login as py_login

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
STATE_FILE = os.path.join(DATA_DIR, "return_state.json")

POST_ORDER_BASE = "https://api.ebay.com/post-order/v2"

# eBay return states we act on -- buyer has requested a return and the seller
# needs to provide a label / make a decision.
ACTIONABLE_STATES = {"ITEM_READY_TO_SHIP"}


# ----------------------------------------------------------------------------
# eBay Post-Order API
# ----------------------------------------------------------------------------
def ebay_headers():
    tok = ebay_utils.load_credentials()["token"]
    return {
        "Authorization": "TOKEN " + tok,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }


def get_returns(headers, limit=50, offset=0):
    """Fetch returns from eBay Post-Order, paginated."""
    out = []
    while True:
        r = requests.get(
            f"{POST_ORDER_BASE}/return/search?limit={limit}&offset={offset}",
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        d = r.json()
        members = d.get("members", []) or []
        out.extend(members)
        po = d.get("paginationOutput") or {}
        total = int(po.get("totalEntries") or 0)
        offset += limit
        if offset >= total or not members:
            break
    return out


# ----------------------------------------------------------------------------
# PriceYak helpers
# ----------------------------------------------------------------------------
def py_headers(token):
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}


def py_find_order_by_buyer(token, buyer_username):
    """Return list of PriceYak orders for a buyer (most-recent first if possible)."""
    h = {"Authorization": "Bearer " + token}
    r = requests.get(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders?buyer_username={buyer_username}&count=20",
        headers=h,
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("data", []) or []


def py_gift_return(token, zinc_order_id):
    """Try to initiate a gift return. Returns (success, message)."""
    url = f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/addax/orders/{zinc_order_id}/gift_return"
    r = requests.post(
        url,
        headers=py_headers(token),
        json={"status_only": False, "require_zinc": False},
        timeout=60,
    )
    if r.ok:
        return True, "queued"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


def py_open_case(token, zinc_order_id, message):
    """Open a case asking for a return label. Returns (success, message)."""
    url = f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/addax/orders/{zinc_order_id}/case"
    body = {
        "zinc_order_id": zinc_order_id,
        "reason": "return.request_label",
        "message": message,
        "close_case": False,
    }
    r = requests.post(url, headers=py_headers(token), json=body, timeout=60)
    if r.ok:
        return True, "opened"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=1)


def match_priceyak_order(orders, ebay_return):
    """Pick the best PriceYak order for an eBay return. Strategy: most recent
    non-cancelled order for the buyer. Returns the order or None."""
    if not orders:
        return None
    candidates = [o for o in orders if not o.get("cancelled")]
    if not candidates:
        return None
    candidates.sort(key=lambda o: o.get("created_time") or 0, reverse=True)
    return candidates[0]


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    dry = "--dry-run" in sys.argv
    state = load_state()
    eh = ebay_headers()
    pt = py_login(PY_ACCOUNT_ID, PY_API_KEY)

    returns = get_returns(eh)
    print(f"eBay returns total: {len(returns)}")
    actionable = [r for r in returns if r.get("state") in ACTIONABLE_STATES]
    print(f"actionable (state in {sorted(ACTIONABLE_STATES)}): {len(actionable)}")

    new_today = 0
    for r in actionable:
        rid = str(r.get("returnId"))
        if rid in state and state[rid].get("attempted"):
            # Already attempted -- Script B will handle label upload when ready
            continue
        new_today += 1
        buyer = r.get("buyerLoginName") or ""
        ebay_oid = r.get("orderId")
        print(f"\n=== eBay return {rid}  buyer={buyer}  eBay orderId={ebay_oid} ===")

        py_orders = py_find_order_by_buyer(pt, buyer) if buyer else []
        match = match_priceyak_order(py_orders, r)
        if not match:
            # No PriceYak order behind this eBay sale -> the item was sourced
            # externally (not fulfilled through PriceYak/Amazon). There is no
            # PriceYak return label to request, so we must NOT open a PriceYak
            # case or run gift_return. Flag it for manual handling and let
            # Script B skip it entirely.
            print(f"  EXTERNAL ORDER (no PriceYak order for buyer={buyer!r}) -> manual label, skipping PriceYak.")
            state[rid] = {
                "ebay_return_id": rid,
                "ebay_order_id": ebay_oid,
                "buyer": buyer,
                "attempted": False,
                "external_order": True,
                "needs_manual_label": True,
                "case_opened": False,
                "error": "no_priceyak_order",
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
            continue

        py_oid = match.get("id")
        zinc_oid = match.get("zinc_order_id")
        py_dest = match.get("destination_order_id")
        print(f"  matched PriceYak order id={py_oid} zinc={zinc_oid} dest_oid={py_dest}")

        # If the order already shows a return error / open case, skip the gift_return
        # attempt and treat as "case opened" (Script B will pick up the label).
        ret_state = ((match.get("summary_state") or {}).get("return") or {}).get("state")
        if ret_state == "return_error":
            print(f"  PriceYak order already in return_error state -> case likely already open; skipping gift_return.")
            state[rid] = {
                "ebay_return_id": rid,
                "ebay_order_id": ebay_oid,
                "buyer": buyer,
                "priceyak_order_id": py_oid,
                "zinc_order_id": zinc_oid,
                "attempted": True,
                "gift_return": "skipped:already_return_error",
                "case_opened": True,
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
            continue

        if dry:
            print(f"  [DRY RUN] would POST gift_return on zinc_order_id={zinc_oid}")
            continue

        # 1) Try gift return
        ok, msg = py_gift_return(pt, zinc_oid)
        print(f"  gift_return -> ok={ok} msg={msg}")
        rec = {
            "ebay_return_id": rid,
            "ebay_order_id": ebay_oid,
            "buyer": buyer,
            "priceyak_order_id": py_oid,
            "zinc_order_id": zinc_oid,
            "attempted": True,
            "gift_return": "queued" if ok else f"failed: {msg}",
            "case_opened": False,
            "updated": datetime.now().isoformat(timespec="seconds"),
        }

        # 2) If gift_return errored synchronously, open a case for a return label
        if not ok:
            cm = (
                "Auto-generated request from seller's automation. The Amazon return "
                "could not be initiated automatically. Please reply with a return "
                "shipping label for this order. Thanks!"
            )
            cok, cmsg = py_open_case(pt, zinc_oid, cm)
            print(f"  open_case -> ok={cok} msg={cmsg}")
            rec["case_opened"] = cok
            rec["case_status"] = "opened" if cok else f"failed: {cmsg}"

        state[rid] = rec
        # be gentle with the PriceYak API
        time.sleep(0.5)

    if not dry:
        save_state(state)
    print(f"\nProcessed {new_today} new actionable return(s). State -> {STATE_FILE}")


if __name__ == "__main__":
    main()
