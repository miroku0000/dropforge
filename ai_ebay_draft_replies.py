"""
Draft (NEVER auto-send) replies to eBay buyer messages.

Reads recent eBay buyer messages via the logged-in session, gathers PriceYak
context (order ETA / shipment state, and the listing's current price), asks
OpenAI to draft a reply applying your rules, and writes the drafts to
data/message_drafts_<ts>.json (+ a readable .txt) for you to review and send.

Rules baked in:
  * Shipping question -> use the PriceYak ETA: give the estimated delivery date,
    note tracking may take time to start updating but it should arrive by then.
  * Price request -> if the asked price is > 5% below the current price
    (asked < 95% of current), politely decline. Within 5% -> surface for your
    decision (they already get your 5% auto-offers).
  * No question / thanks -> needs_reply = false.

Usage:
    python ai_ebay_draft_replies.py --probe   # inspect the messages page (dev)
    python ai_ebay_draft_replies.py           # read messages -> write drafts
    python ai_ebay_draft_replies.py --max 10
"""

import os
import re
import sys
import json
import argparse
import logging
from datetime import datetime, timezone

import requests
from openai import OpenAI
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser, needs_signin, wait_for_signin, _is_bot_blocked, _wait_for_captcha

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
MESSAGES_URLS = ["https://www.ebay.com/sh/messages", "https://mesg.ebay.com/mesgweb/ViewMessages/0"]
import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY
PRICE_DECLINE_THRESHOLD = 0.95   # asked < 95% of current => more than 5% off => decline


# ----------------------------------------------------------------- eBay messages
def _ensure_ready(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if _is_bot_blocked(page):
        _wait_for_captcha(page)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if needs_signin(page):
        wait_for_signin(page, success_url_glob="**ebay.com/**")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)


def _clean(text):
    text = " ".join((text or "").split())
    text = re.sub(r"^[A-Z]\s+", "", text).strip()      # drop leading avatar initial
    return re.sub(r"^(.+?)\s*\1$", r"\1", text).strip()  # collapse eBay's doubled bubble text


def _within_days(when, days=2):
    """Is the inbox time-stamp within `days`? eBay shows '3h'/'2d' for recent and
    a date for older. Unknown -> keep (don't silently drop a real message)."""
    when = (when or "").strip().lower()
    m = re.match(r"(\d+)\s*([mhd])", when)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return True if u in ("m", "h") else (n <= days)
    for fmt in ("%b %d, %Y", "%b %d %Y", "%b %d"):
        try:
            d = datetime.strptime(when.title(), fmt)
            d = d.replace(year=datetime.now().year) if d.year == 1900 else d
            return (datetime.now() - d).days <= days
        except Exception:
            pass
    return True


def read_threads(page, max_threads=20, max_age_days=2):
    _ensure_ready(page, MESSAGES_URLS[1])
    cards = page.query_selector_all("[data-testid='conversation-item__from-member']")
    infos = []
    for card in cards[:max_threads]:
        u = card.query_selector(".card__username, .sender")
        subj = card.query_selector(".message-subject, .card__conversation-title")
        tm = card.query_selector(".card__datetime, .card__time")
        when = _clean(tm.inner_text()) if tm else ""
        if not _within_days(when, max_age_days):
            continue
        infos.append({
            "id": card.get_attribute("id"),
            "conv_id": card.get_attribute("data-conversation-id"),
            "username": _clean(u.inner_text()) if u else "",
            "item_title": _clean(subj.inner_text()) if subj else "",
            "unread": bool(card.query_selector(".card__content-unread")),
            "when": when,
        })
    log.info(f"{len(infos)} buyer thread(s) within {max_age_days} days.")

    threads = []
    for info in infos:
        el = page.query_selector("#" + info["id"]) if info["id"] else None
        if not el:
            continue
        try:
            el.click()
            page.wait_for_timeout(2500)
        except Exception as e:
            log.warning(f"  couldn't open {info['username']}: {str(e)[:60]}")
            continue
        # message text is in __message__content; timestamps are separate. DOM
        # order is newest-first, so [0] is the buyer's most recent message.
        msgs = [_clean(b.inner_text())
                for b in page.query_selector_all("[class*='message-bubble__message__content']")]
        msgs = [m for m in msgs if len(m) > 1]
        info["message"] = msgs[0] if msgs else ""
        info["recent"] = msgs[:6]      # newest first, for conversation context
        itm = page.query_selector("a[href*='/itm/']")
        m = re.search(r"/itm/(?:[^/]*/)?(\d{11,13})", itm.get_attribute("href") or "") if itm else None
        info["item_id"] = m.group(1) if m else None
        threads.append(info)
    return threads


# ----------------------------------------------------------------- PriceYak context
def py_login():
    r = requests.post(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
                      json={"api_key": PY_API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def py_context(token, username, item_id):
    h = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    ctx = {"eta": None, "shipment_state": None, "tracking": False, "current_price": None}
    try:
        d = requests.get(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/orders",
                         headers=h, params={"buyer_username": username, "count": 3}, timeout=40).json()
        orders = d.get("data", [])
        if orders:
            o = orders[0]
            eta = o.get("estimated_delivery_date")
            if eta:
                edt = datetime.fromtimestamp(eta, timezone.utc)
                ctx["eta"] = f"{edt:%A, %B} {edt.day}"

            ctx["shipment_state"] = o.get("shipment_state")
            ctx["tracking"] = bool(o.get("fulfillment_tracking_number") or o.get("partner_tracking_number"))
    except Exception as e:
        log.warning(f"  order lookup failed for {username}: {str(e)[:60]}")
    if item_id:
        try:
            s = requests.get(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/search?query={item_id}",
                             headers=h, timeout=40).json()
            lid = s.get("id")
            if lid and s.get("type") == "Listing":
                o = requests.get(f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings/{lid}",
                                 headers=h, timeout=40).json()
                if o.get("price"):
                    ctx["current_price"] = round(o["price"] / 100, 2)
        except Exception as e:
            log.warning(f"  price lookup failed for {item_id}: {str(e)[:60]}")
    return ctx


# ----------------------------------------------------------------- drafting
SYSTEM = """You draft polite, concise reply DRAFTS for an eBay dropshipping seller to buyer messages.
You never send; a human reviews. Return STRICT JSON:
{"needs_reply": bool, "intent": "shipping|price_request|other", "requested_price": number|null, "draft": string}
The buyer may have sent several messages (recent_conversation_newest_first); reply to their overall need, not just the last line. If they already got an answer and only said thanks, needs_reply=false.
Guidance:
- shipping/where-is-my-order: if an estimated delivery date is given, say it's estimated to be delivered by that date, and that tracking may take a little while to start updating but it should arrive by then. Friendly, brief.
- price_request (buyer asks for a specific price): set requested_price to the number they asked. The seller's decision on whether to accept is computed separately and given to you as PRICE_STANCE; write the draft to match that stance politely.
- if the message is just thanks/acknowledgement with no question, needs_reply=false and draft="".
Keep drafts short, warm, professional. Sign off as the seller (no name)."""


def draft_reply(client, thread, ctx, price_stance):
    user = json.dumps({
        "latest_buyer_message": thread.get("message", ""),
        "recent_conversation_newest_first": thread.get("recent", []),
        "item": thread.get("item_title", ""),
        "shipping_eta": ctx["eta"],
        "shipment_state": ctx["shipment_state"],
        "has_tracking": ctx["tracking"],
        "current_price": ctx["current_price"],
        "PRICE_STANCE": price_stance,
    })
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning(f"  draft failed: {str(e)[:80]}")
        return {"needs_reply": True, "intent": "other", "requested_price": None,
                "draft": "", "error": str(e)[:120]}


_PRICE_ASK = re.compile(r"(?i)\$|\bprice\b|\boffer\b|\btake\b|\blower\b|\bdiscount\b|\bsell .*for\b|\bdeal\b|\bnegotiat")


def price_stance_for(message, current_price):
    """If the buyer is asking about price, extract it and apply the >5%-off rule.
    Returns a neutral note when it isn't a price ask."""
    if not _PRICE_ASK.search(message or ""):
        return "not a price request."
    if current_price is None:
        return "price request but current price unknown -- surface for manual decision."
    m = re.search(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)|\b([0-9]{1,4}(?:\.[0-9]{1,2})?)\b", message or "")
    asked_str = (m.group(1) or m.group(2)) if m else None
    if not asked_str:
        return "price request but no clear amount; surface for manual decision."
    asked = float(asked_str)
    if asked < PRICE_DECLINE_THRESHOLD * current_price:
        pct = round((1 - asked / current_price) * 100)
        return f"DECLINE politely: buyer asked ${asked:.2f} vs current ${current_price:.2f} ({pct}% off, over the 5% limit)."
    return f"WITHIN 5%: asked ${asked:.2f} vs current ${current_price:.2f}; don't commit -- brief friendly reply, mention they may receive a discount offer. Flag for the seller's decision."


def main():
    ap = argparse.ArgumentParser(description="Draft replies to eBay buyer messages (no auto-send)")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--max-age-days", type=int, default=2, help="Ignore threads older than this (default 2)")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    with sync_playwright() as p:
        ctx = launch_ebay_browser(p, viewport={"width": 1500, "height": 950}, accept_downloads=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            if args.probe:
                _probe(page)
                return
            threads = read_threads(page, args.max, args.max_age_days)
        finally:
            ctx.close()

    if not threads:
        log.info("No buyer messages to draft.")
        return

    token = py_login()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    drafts = []
    for t in threads:
        pctx = py_context(token, t["username"], t.get("item_id"))
        stance = price_stance_for(t.get("message", ""), pctx["current_price"])
        res = draft_reply(client, t, pctx, stance)
        drafts.append({**t, "context": pctx, "price_stance": stance, **res})
        flag = "REPLY" if res.get("needs_reply") else "no-reply"
        log.info(f"  {t['username']:<18} [{res.get('intent')}/{flag}] {t.get('message','')[:50]}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jpath = os.path.join(DATA_DIR, f"message_drafts_{ts}.json")
    json.dump(drafts, open(jpath, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    tpath = os.path.join(DATA_DIR, f"message_drafts_{ts}.txt")
    with open(tpath, "w", encoding="utf-8") as f:
        for d in drafts:
            if not d.get("needs_reply"):
                continue
            f.write(f"=== {d['username']}  ({d.get('intent')})  item: {d.get('item_title','')[:50]}\n")
            f.write(f"BUYER: {d.get('message','')}\n")
            if d.get("context", {}).get("eta"):
                f.write(f"ETA: {d['context']['eta']} | shipment: {d['context']['shipment_state']}\n")
            f.write(f"DRAFT REPLY:\n{d.get('draft','')}\n\n")
    need = sum(1 for d in drafts if d.get("needs_reply"))
    print(f"\nWrote {len(drafts)} thread(s); {need} need a reply.")
    print(f"  review: {tpath}")
    print(f"  data:   {jpath}")


def _probe(page):
    for url in MESSAGES_URLS:
        try:
            _ensure_ready(page, url)
        except Exception:
            continue
        log.info(f"final url: {page.url}")
        cards = page.query_selector_all("[data-testid='conversation-item__from-member']")
        log.info(f"from-member cards: {len(cards)}")


if __name__ == "__main__":
    main()
