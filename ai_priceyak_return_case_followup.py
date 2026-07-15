"""
Follow up on PriceYak return cases that look stuck without a refund.

For every order that has NO comment yet, where PriceYak shows a return that has
NOT been refunded, we open the order page and look for a return-shipping-label
link (the support reply that contains a `coyotedownloads...pdf` URL). If:

  * the page has such a return-label link, AND
  * the order has not been refunded, AND
  * there is no text saying the order can't / won't be refunded on Amazon, AND
  * it has been > 30 days since the label/support reply was posted,

then we message the support case asking whether it has been refunded on Amazon:
  * if the case is still OPEN  -> "Reply to Case" (always works)
  * if the case is CLOSED      -> "Reopen Case", BUT PriceYak rejects reopening
    any order whose estimated delivery was >30 days ago (HTTP 400). When that
    happens we EMAIL support@priceyak.com instead (Gmail app password from
    credentials.txt: gmail_address + gmail_app_password). The email includes the
    PriceYak order URL, Amazon order ID, and eBay return ID.

After messaging, we stamp the order comment  "asked refund M/D/YYYY"  so we never
ask twice and so a later pass can check whether support refunded it or explained
why it can't be refunded.

Detection scrapes the rendered order page (the case data API is cookie-only).
The reply/reopen is done through the same web form a human uses.

SAFETY:
  * Only orders with an EMPTY comment are ever touched (the "asked refund" stamp
    excludes them from future runs; a cost/manual note is never overwritten).
  * --dry-run (DEFAULT) only reads + prints what it WOULD do. Use --live to act.

Usage:
    python ai_priceyak_return_case_followup.py                 # dry-run, scan 600
    python ai_priceyak_return_case_followup.py --live --max 1  # act on 1 (test)
    python ai_priceyak_return_case_followup.py --live          # act on all eligible
"""

import argparse
import logging
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage

import requests
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"),
                              logging.StreamHandler()])
log = logging.getLogger(__name__)

import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

COYOTE_RE = re.compile(r"https?://coyotedownloads\.s3\.amazonaws\.com/\S+?\.pdf[^\s]*")
# Case-table timestamps look like:  6/10/2026, 8:22:21 AM
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4}),?\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M")
AMAZON_OID_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")          # 111-8052883-2589017
EBAY_RETURN_ID_RE = re.compile(r"eBay\s*US\s*Return\s*Id\s*[:\s]+(\d{8,12})", re.I)

SUPPORT_EMAIL = "support@priceyak.com"
SELLER_NAME = "Randy Flood"

# Support text that means "this will NOT be refunded" -- if present, don't pester
# again. Deliberately specific so the normal "Closed No Refund" case STATE header
# and the boilerplate "...on file to ensure a refund." do NOT match.
NO_REFUND_PHRASES = [
    "will not be refunded", "will not refund", "won't be refunded",
    "cannot be refunded", "can not be refunded", "can't be refunded",
    "not be issued a refund", "no refund will be issued", "unable to refund",
    "not eligible for a refund", "refund was denied", "refund has been denied",
    "refund is denied", "not be able to refund", "ineligible for a refund",
]
# Support text that means it WAS refunded (belt-and-suspenders vs the API filter).
REFUNDED_PHRASES = ["closed with refund", "refund issued", "has been refunded",
                    "refund has been processed", "refund was issued"]

DAYS_THRESHOLD = 30

MESSAGE_TMPL = (
    "Hello, a return shipping label was provided for this order on {posted} and the "
    "item was returned, but I do not see a refund for it on Amazon. Has this order "
    "been refunded on Amazon? If it has not been refunded, could you please let me "
    "know the reason? Thank you."
)


# ---------------------------------------------------------------------------
# PriceYak API
# ---------------------------------------------------------------------------
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


def set_comment(token, order_id, text):
    r = requests.put(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders/{order_id}",
                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "*/*"},
                     json={"frontend_details": {"orderNotes": text}}, timeout=40)
    return r.status_code


# ---------------------------------------------------------------------------
# Email fallback (for closed cases PriceYak refuses to reopen)
# ---------------------------------------------------------------------------
def gmail_creds():
    """(gmail_address, gmail_app_password) from credentials.txt, or (None, None).
    Add to credentials.txt:
        gmail_address=you@gmail.com
        gmail_app_password=xxxxxxxxxxxxxxxx   (16-char Google App Password)"""
    creds = {}
    if __import__("os").path.exists("credentials.txt"):
        with open("credentials.txt") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip().lower()] = v.strip()
    return creds.get("gmail_address"), creds.get("gmail_app_password")


def send_support_email(addr, app_pw, subject, body):
    msg = EmailMessage()
    msg["From"] = addr
    msg["To"] = SUPPORT_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=40) as s:
        s.login(addr, app_pw.replace(" ", ""))
        s.send_message(msg)


def build_email(info, who, posted_s):
    subject = f"Refund status inquiry - Amazon order {info.get('amazon_oid') or '(see link)'}"
    body = (
        f"Hello PriceYak Support,\n\n"
        f"I am following up on a completed return. A return shipping label was provided "
        f"on {posted_s} and the item was returned, but I do not see a refund for this "
        f"order on Amazon.\n\n"
        f"Could you please let me know whether this order has been refunded on Amazon? "
        f"If it has not been refunded, could you tell me the reason?\n\n"
        f"Order details:\n"
        f"  PriceYak order: {info['url']}\n"
        f"  Amazon order ID: {info.get('amazon_oid') or 'n/a'}\n"
        f"  eBay return ID: {info.get('ebay_return_id') or 'n/a'}\n"
        f"  Buyer: {who}\n\n"
        f"I could not reopen this case in the PriceYak dashboard (estimated delivery is "
        f"more than 30 days ago), so I am reaching out by email.\n\n"
        f"Thank you,\n{SELLER_NAME}"
    )
    return subject, body


# ---------------------------------------------------------------------------
# Candidate pre-filter (API only -- avoids loading a page for every order)
# ---------------------------------------------------------------------------
def is_candidate(o):
    """Cheap filter: no comment yet, and a return exists that is not refunded."""
    note = ((o.get("frontend_details") or {}).get("orderNotes") or "").strip()
    if note:                                          # already commented / asked
        return False
    rs = (o.get("destination_blob") or {}).get("returnStatus") or ""
    if not rs or rs == "NotApplicable":               # no return at all
        return False
    if "WithRefund" in rs:                            # already refunded
        return False
    return True                                       # e.g. Pending / ClosedNoRefund


# ---------------------------------------------------------------------------
# Page inspection
# ---------------------------------------------------------------------------
def inspect_page(page, order_id):
    """Load the order page and return a dict describing the return case, or None."""
    url = f"https://www.priceyak.com/stores/{PY_ACCOUNT_ID}/orders/{order_id}"
    page.goto(url, wait_until="load", timeout=60000)
    time.sleep(5)
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass
    time.sleep(2)
    try:
        body = page.locator("body").inner_text(timeout=8000)
    except Exception:
        body = ""

    m = COYOTE_RE.search(body)
    if not m:
        return {"url": url, "has_label": False}

    aoid = AMAZON_OID_RE.search(body)
    rid = EBAY_RETURN_ID_RE.search(body)

    low = body.lower()
    # posted date = the latest case-table timestamp that appears BEFORE the link
    posted = None
    for dm in DATE_RE.finditer(body):
        if dm.start() < m.start():
            posted = dm
        else:
            break
    posted_dt = None
    if posted:
        mo, da, yr = int(posted.group(1)), int(posted.group(2)), int(posted.group(3))
        posted_dt = datetime(yr, mo, da, tzinfo=timezone.utc)

    # open vs closed: which button does the page expose?
    has_reply = page.locator("button:has-text('Reply to Case')").count() > 0
    has_reopen = page.locator("button:has-text('Reopen Case')").count() > 0

    return {
        "url": url,
        "has_label": True,
        "label_url": m.group(0),
        "posted_dt": posted_dt,
        "refunded_text": any(p in low for p in REFUNDED_PHRASES),
        "no_refund_text": next((p for p in NO_REFUND_PHRASES if p in low), None),
        "has_reply": has_reply,
        "has_reopen": has_reopen,
        "amazon_oid": aoid.group(1) if aoid else None,
        "ebay_return_id": rid.group(1) if rid else None,
    }


def evaluate(info, today):
    """Decide whether to act. Returns (action|None, reason)."""
    if not info.get("has_label"):
        return None, "no return-label link on page"
    if info["refunded_text"]:
        return None, "page shows it was refunded"
    if info["no_refund_text"]:
        return None, f"support already explained no refund ({info['no_refund_text']!r})"
    if not info["posted_dt"]:
        return None, "could not read the label posted date"
    days = (today - info["posted_dt"]).days
    if days < DAYS_THRESHOLD:
        return None, f"label posted only {days}d ago (<{DAYS_THRESHOLD})"
    if info["has_reopen"]:
        return ("reopen", f"closed case, label posted {days}d ago")
    if info["has_reply"]:
        return ("reply", f"open case, label posted {days}d ago")
    return None, "no Reply/Reopen button found"


# ---------------------------------------------------------------------------
# Action: message the case through the web form
# ---------------------------------------------------------------------------
# Unique substring of MESSAGE_TMPL -- used to confirm the message really posted.
MARKER = "been refunded on Amazon"


def message_case(page, action, message):
    """Click Reply/Reopen, fill the message, keep the case open, submit, then
    VERIFY the message actually landed in the case table. Returns (ok, detail).

    Both forms share id=addaxCaseMessage; submit is button[type=submit]
    ("Reply" for an open case, "Open Case" for reopening a closed one). The
    reopen form additionally has a required `reason` <select>.

    NOTE: PriceYak rejects (HTTP 400) reopening a closed case once the order's
    estimated delivery date is >30 days past -- so closed-case reopens for old
    orders fail server-side. We detect that and report it rather than stamp."""
    btn_text = "Reopen Case" if action == "reopen" else "Reply to Case"
    page.locator(f"button:has-text('{btn_text}')").first.click()
    time.sleep(2)
    ta = page.locator("textarea[name='message']:visible").first
    ta.wait_for(state="visible", timeout=8000)
    ta.fill(message)
    # reopen form requires a reason -- reuse the original "request a return label"
    reason = page.locator("select[name='reason']:visible")
    if reason.count():
        reason.first.select_option("return.request_label")
    # keep the case OPEN so support sees the question (uncheck "close_case")
    try:
        cb = page.locator("input[name='close_case']:visible")
        if cb.count() and cb.first.is_checked():
            cb.first.uncheck()
    except Exception:
        pass
    time.sleep(0.5)
    submit = page.locator("form#addaxCaseMessage button[type='submit']:visible").first
    if not submit.count():
        return False, "submit button not found"
    submit.click()
    time.sleep(4)
    # VERIFY: only a real success has our message text in the case table now.
    try:
        body = page.locator("body").inner_text(timeout=8000)
    except Exception:
        body = ""
    if MARKER in body:
        return True, "posted"
    if "cannot troubleshoot orders" in body.lower():
        return False, "blocked: PriceYak won't reopen (est. delivery >30d ago)"
    return False, "submitted but message not confirmed on page"


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Follow up on un-refunded PriceYak return cases")
    ap.add_argument("--scan", type=int, default=600, help="Recent orders to scan (default 600)")
    ap.add_argument("--max", type=int, default=0, help="Cap actions taken (0 = no cap)")
    ap.add_argument("--live", action="store_true", help="Actually message cases (default is dry-run)")
    ap.add_argument("--no-email", action="store_true",
                    help="Do not email support for closed cases PriceYak won't reopen (report only)")
    args = ap.parse_args()
    dry = not args.live
    today = datetime.now(timezone.utc)

    g_addr, g_pw = gmail_creds()
    email_on = bool(g_addr and g_pw) and not args.no_email
    if not email_on and not args.no_email:
        log.warning("Email fallback DISABLED -- add gmail_address + gmail_app_password to "
                    "credentials.txt to auto-email support for un-reopenable closed cases.")

    token = py_login()
    orders = fetch_recent(token, args.scan)
    candidates = [o for o in orders if is_candidate(o)]
    log.info(f"Scanned {len(orders)} order(s); {len(candidates)} candidate(s) "
             f"(no comment + unrefunded return). Mode: {'DRY-RUN' if dry else 'LIVE'}. "
             f"Email fallback: {'ON (' + g_addr + ')' if email_on else 'OFF'}.")

    with sync_playwright() as p:
        ctx = launch_ebay_browser(p, viewport={"width": 1400, "height": 1000})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        acted = emailed = 0
        blocked = []
        for o in candidates:
            oid = o["id"]
            who = o.get("buyer_username", "")
            try:
                info = inspect_page(page, oid)
            except Exception as e:
                log.warning(f"  {oid} {who}: page load failed: {e}")
                continue
            action, reason = evaluate(info, today)
            if not action:
                log.info(f"  SKIP {oid} {who}: {reason}")
                continue

            posted = info["posted_dt"]
            posted_s = f"{posted.month}/{posted.day}/{posted.year}"
            datestr = f"{today.month}/{today.day}/{today.year}"
            msg = MESSAGE_TMPL.format(posted=posted_s)
            log.info(f"  ACT  {oid} {who}: {action.upper()} -- {reason}")
            log.info(f"        label posted {posted_s} | {info['url']}")

            if dry:
                log.info(f"        [DRY] would post to case: {msg}")
                if action == "reopen":
                    log.info(f"        [DRY] if PriceYak blocks the reopen (likely, >30d), would "
                             f"{'EMAIL ' + SUPPORT_EMAIL if email_on else 'REPORT (email off)'}")
                log.info(f"        [DRY] would stamp comment: 'asked/emailed refund {datestr}'")
                acted += 1
                if args.max and acted >= args.max:
                    log.info(f"  Reached --max {args.max}; stopping."); break
                continue

            # --- live ---
            try:
                ok, detail = message_case(page, action, msg)
            except Exception as e:
                ok, detail = False, f"exception: {e}"

            if ok:
                code = set_comment(token, oid, f"asked refund {datestr}")
                log.info(f"        messaged case + stamped comment (PUT {code}).")
                acted += 1
            elif "blocked" in detail and email_on:
                # PriceYak won't reopen -> email support instead, then stamp.
                try:
                    subject, ebody = build_email(info, who, posted_s)
                    send_support_email(g_addr, g_pw, subject, ebody)
                    code = set_comment(token, oid, f"emailed refund {datestr}")
                    log.info(f"        reopen blocked -> EMAILED {SUPPORT_EMAIL} + stamped (PUT {code}).")
                    emailed += 1
                except Exception as e:
                    log.error(f"        reopen blocked AND email failed: {e}; comment left empty.")
                    blocked.append((oid, who, action, f"email failed: {e}", info["url"]))
            else:
                log.warning(f"        NOT messaged ({detail}); comment left empty.")
                blocked.append((oid, who, action, detail, info["url"]))
                continue

            if args.max and (acted + emailed) >= args.max:
                log.info(f"  Reached --max {args.max}; stopping.")
                break

        if dry:
            log.info(f"DRY-RUN complete: {acted} case(s) would be actioned.")
        else:
            log.info(f"LIVE complete: messaged {acted} open case(s); emailed {emailed} closed case(s).")
        if blocked:
            log.warning(f"{len(blocked)} case(s) could NOT be handled (left un-stamped):")
            for oid, who, action, detail, url in blocked:
                log.warning(f"    {oid} {who} [{action}] -- {detail}  {url}")
        ctx.close()


if __name__ == "__main__":
    main()
