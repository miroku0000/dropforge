"""
PriceYak order monitor -- catch failed / stuck orders before they hurt you.

Scans recent PriceYak orders and reports problems, pushing an alert via notify.py:

  * FAILED for insufficient funds  -> you need to ADD MONEY to the managed
    account (retrying is pointless until funded). failure_reason
    insufficient_zma_balance (and payment_info_problem = a payment issue).

  * FAILED for some other reason    -> RETRY the order
    (POST /v0/account/{id}/orders/{order_id}/retry). Skipped if the order is
    cancelled (cancelled flag OR an orderNotes "Cancelled" comment) or locked.

  * Not shipped / no tracking >N h  -> a stuck order needing attention
    (your workflow assigns tracking + marks shipped as soon as you order on
    Amazon, so an old order with neither is a red flag).

Order state (from PriceYak): success | fulfilled_externally | skipped (cancelled)
| failure. "handled" = marked_shipped, or has a tracking number, or
fulfilled_externally.

Retry is OFF by default (it places a real Amazon order). Use --retry to enable;
--dry-run shows what it would retry. Funding failures and cancelled/locked
orders are never retried.

Usage:
    python ai_priceyak_order_monitor.py                  # detect + alert only
    python ai_priceyak_order_monitor.py --retry          # also retry eligible failures
    python ai_priceyak_order_monitor.py --retry --dry-run
    python ai_priceyak_order_monitor.py --scan 500 --untracked-hours 24
"""

import time
import argparse
import logging

import requests
from notify import send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

# Failures that mean "fix the money", not "retry".
FUNDING_REASONS = {"insufficient_zma_balance", "payment_info_problem"}


def py_login():
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
        json={"api_key": PY_API_KEY}, timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def fetch_recent_orders(token, scan):
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    orders, offset = [], 0
    while offset < scan:
        r = requests.get(
            f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders",
            headers=headers, params={"count": 100, "offset": offset}, timeout=60,
        )
        r.raise_for_status()
        data = r.json().get("data", [])
        orders.extend(data)
        offset += len(data)
        if not data:
            break
    return orders[:scan]


def retry_order(token, order_id):
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders/{order_id}/retry",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "*/*"},
        timeout=30,
    )
    return r.status_code, r.text[:200]


def _notes(o):
    return ((o.get("frontend_details") or {}).get("orderNotes") or "")


def _handled(o):
    return (bool(o.get("marked_shipped"))
            or bool(o.get("fulfillment_tracking_number") or o.get("partner_tracking_number"))
            or o.get("state") == "fulfilled_externally")


def _is_cancelled(o):
    return bool(o.get("cancelled")) or "cancel" in _notes(o).lower()


def _is_locked(o):
    return "lock" in _notes(o).lower()


def classify(orders, untracked_hours, now):
    add_money, retry, stuck = [], [], []
    for o in orders:
        if _is_cancelled(o):
            continue
        age_h = (now - (o.get("created_time") or now)) / 3600.0
        reason = o.get("failure_reason")
        rec = {
            "id": o.get("id"), "buyer": o.get("buyer_username", ""),
            "ebay_order": o.get("destination_order_id", ""),
            "reason": reason, "age_h": age_h, "locked": _is_locked(o),
        }
        if o.get("state") == "failure":
            if reason in FUNDING_REASONS:
                add_money.append(rec)
            elif _is_locked(o):
                continue  # locked: leave it (PriceYak won't retry it anyway)
            else:
                retry.append(rec)
        elif not _handled(o) and age_h > untracked_hours:
            stuck.append(rec)
    return add_money, retry, stuck


def main():
    ap = argparse.ArgumentParser(description="Monitor PriceYak orders: failures, funding, untracked")
    ap.add_argument("--scan", type=int, default=300, help="Recent orders to scan (default 300)")
    ap.add_argument("--untracked-hours", type=float, default=24, help="Flag unshipped/untracked orders older than this (default 24)")
    ap.add_argument("--retry", action="store_true", help="Actually retry eligible (non-funding, non-cancelled, non-locked) failures")
    ap.add_argument("--max-retry", type=int, default=10, help="Cap retries per run (default 10)")
    ap.add_argument("--dry-run", action="store_true", help="With --retry, show what would retry without doing it")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    now = time.time()
    token = py_login()
    orders = fetch_recent_orders(token, args.scan)
    log.info(f"Scanned {len(orders)} recent order(s).")

    add_money, retry, stuck = classify(orders, args.untracked_hours, now)
    log.info(f"add-money: {len(add_money)} | retry: {len(retry)} | stuck-untracked: {len(stuck)}")

    # Perform retries if asked.
    retried = []
    if args.retry and retry:
        for rec in retry[: args.max_retry]:
            if args.dry_run:
                log.info(f"[DRY] would retry {rec['id']} ({rec['reason']})")
                retried.append((rec, "dry-run"))
            else:
                code, body = retry_order(token, rec["id"])
                log.info(f"retry {rec['id']} ({rec['reason']}) -> HTTP {code}: {body}")
                retried.append((rec, f"HTTP {code}"))

    # Console report
    print("=" * 64)
    print(f"PRICEYAK ORDER MONITOR  (scanned {len(orders)})")
    print(f"  add-money (funding failures): {len(add_money)}")
    print(f"  retry candidates:             {len(retry)}")
    print(f"  stuck / untracked >{args.untracked_hours:.0f}h:        {len(stuck)}")
    for label, group in (("ADD MONEY", add_money), ("RETRY", retry), ("STUCK", stuck)):
        for r in group[:10]:
            print(f"    [{label}] {r['id']} buyer={r['buyer']} reason={r['reason']} age={r['age_h']:.0f}h")
    print("=" * 64)

    if args.no_push:
        return

    # Push only when there's something actionable.
    if not (add_money or retry or stuck):
        log.info("No order problems; no push sent.")
        return

    lines, prio = [], "default"
    if add_money:
        prio = "high"
        lines.append(f"ADD MONEY: {len(add_money)} order(s) FAILED for insufficient PriceYak funds.")
    if retry:
        if args.retry and not args.dry_run:
            ok = sum(1 for _, s in retried if s == "HTTP 200")
            lines.append(f"RETRIED {len(retried)} failed order(s) ({ok} accepted); {max(0, len(retry) - args.max_retry)} over cap.")
        else:
            lines.append(f"RETRY: {len(retry)} order(s) failed (non-funding) and need a retry.")
        for r in retry[:8]:
            lines.append(f"  {r['id']} {r['buyer']} ({r['reason']})")
    if stuck:
        lines.append(f"STUCK: {len(stuck)} order(s) >{args.untracked_hours:.0f}h with no tracking.")
        for r in stuck[:8]:
            lines.append(f"  {r['id']} {r['buyer']} age {r['age_h']:.0f}h")

    title = "PriceYak: ADD MONEY (orders failing)" if add_money else "PriceYak: orders need attention"
    send(title, "\n".join(lines), priority=prio, tags="rotating_light" if add_money else "warning")


if __name__ == "__main__":
    main()
