"""
Close the loop on PriceYak return-case follow-ups.

`ai_priceyak_return_case_followup.py` stamps an order comment when it asks
support about a missing refund:
    "asked refund M/D/YYYY"    (we replied on the open case)
    "emailed refund M/D/YYYY"  (case couldn't be reopened, so we emailed support)

This script revisits those PENDING orders and finalizes them:
    * If the order is now actually refunded  -> comment "refunded"
    * If support has now said it WON'T be refunded -> comment "no refund: <reason>"
    * Otherwise it's still pending -> left as-is (re-checked next run)

REFUND DETECTION (both channels): a real Amazon refund flips PriceYak's
`destination_blob.returnStatus` to ...WithRefund -- so the cheap API field
catches every refund whether support answered on the case or by email.

REFUSAL DETECTION: we only ever asked on cases that had NO "won't be refunded"
text at ask-time (see followup's evaluate()), so any such phrase present now is
support's new answer. (For EMAILED/closed cases support answers by email, which
this page scrape can't see -- those stay pending and are reported; the actual
refund still gets caught via returnStatus.)

SAFETY: only ever touches comments that are our own pending stamps
("asked refund ..." / "emailed refund ..."). A cost/manual note is never matched.

Usage:
    python ai_priceyak_resolution_check.py                 # dry-run, scan 1500
    python ai_priceyak_resolution_check.py --live
    python ai_priceyak_resolution_check.py --live --scan 2000
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

from ai_priceyak_return_case_followup import (
    PY_ACCOUNT_ID, py_login, fetch_recent, set_comment,
    NO_REFUND_PHRASES, REFUNDED_PHRASES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"),
                              logging.StreamHandler()])
log = logging.getLogger(__name__)

PENDING_PREFIXES = ("asked refund ", "emailed refund ")


def is_pending(o):
    note = ((o.get("frontend_details") or {}).get("orderNotes") or "").strip().lower()
    return note.startswith(PENDING_PREFIXES)


def is_refunded(o):
    """Genuinely refunded (sale reversed) -- via returnStatus, not the comment."""
    rs = (o.get("destination_blob") or {}).get("returnStatus") or ""
    if "WithRefund" in rs:
        return True
    ret = (o.get("summary_state") or {}).get("return") or {}
    return "refund" in (str(ret.get("code") or "") + str(ret.get("state") or "")).lower()


def load_body(page, order_id):
    url = f"https://www.priceyak.com/stores/{PY_ACCOUNT_ID}/orders/{order_id}"
    page.goto(url, wait_until="load", timeout=60000)
    time.sleep(5)
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass
    time.sleep(2)
    try:
        return page.locator("body").inner_text(timeout=8000), url
    except Exception:
        return "", url


def resolve(page, o):
    """Return (new_comment, reason) or (None, why-still-pending)."""
    if is_refunded(o):
        return "refunded", "returnStatus shows refund"
    body, _ = load_body(page, o["id"])
    low = body.lower()
    if any(p in low for p in REFUNDED_PHRASES) or "closed with refund" in low:
        return "refunded", "case shows refund issued"
    hit = next((p for p in NO_REFUND_PHRASES if p in low), None)
    if hit:
        return (f"no refund: {hit}")[:60], f"support says no refund ({hit!r})"
    return None, "no resolution yet"


def main():
    ap = argparse.ArgumentParser(description="Finalize PriceYak return-case follow-ups (refunded / no refund)")
    ap.add_argument("--scan", type=int, default=1500, help="Recent orders to scan (default 1500)")
    ap.add_argument("--live", action="store_true", help="Actually update comments (default dry-run)")
    args = ap.parse_args()
    dry = not args.live

    token = py_login()
    orders = fetch_recent(token, args.scan)
    pending = [o for o in orders if is_pending(o)]
    log.info(f"Scanned {len(orders)} order(s); {len(pending)} awaiting resolution "
             f"(asked/emailed refund). Mode: {'DRY-RUN' if dry else 'LIVE'}.")
    if not pending:
        return

    refunded = norefund = stillpending = 0
    with sync_playwright() as p:
        ctx = launch_ebay_browser(p, viewport={"width": 1400, "height": 1000})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for o in pending:
            oid = o["id"]
            who = o.get("buyer_username", "")
            cur = ((o.get("frontend_details") or {}).get("orderNotes") or "").strip()
            try:
                new, reason = resolve(page, o)
            except Exception as e:
                log.warning(f"  {oid} {who}: check failed: {e}")
                continue
            if not new:
                stillpending += 1
                log.info(f"  PEND {oid} {who}: {cur!r} -- {reason}")
                continue
            if new.startswith("refunded"):
                refunded += 1
            else:
                norefund += 1
            log.info(f"  DONE {oid} {who}: {cur!r} -> {new!r} ({reason})")
            if not dry:
                code = set_comment(token, oid, new)
                if code != 200:
                    log.warning(f"        PUT {oid} -> HTTP {code}")
        ctx.close()

    verb = "would set" if dry else "set"
    log.info(f"Resolution complete: {verb} {refunded} -> refunded, {norefund} -> no refund; "
             f"{stillpending} still pending.")


if __name__ == "__main__":
    main()
