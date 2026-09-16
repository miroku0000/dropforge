"""
Fix listings PriceYak miscategorized into PRE-1900 ANTIQUE bottle categories.

We don't sell antiques, but PriceYak's auto-categorizer drops modern "bottle/jar"
products (water bottles, candles, glass jars) into eBay's Collectibles > Bottles &
Insulators > Bottles > Antique (Pre-1900) subtree. Buyers browsing antiques never
find them, and it's just wrong. We can't control PriceYak's category pick, so this
sweeps the LIVE eBay listings and recategorizes any that landed in an antique
bottle category to an appropriate MODERN leaf category, chosen by title keyword.

Detection: a listing's eBay PrimaryCategory ID is in ANTIQUE_CATEGORIES.
Target: first KEYWORD_MAP entry whose keyword is in the title -> that modern leaf.
        No keyword match -> reported as "needs manual" (never guessed).
Change: ReviseFixedPriceItem sets the new PrimaryCategory + ConditionID=1000
        (eBay requires a condition when the category changes -- err 21916884).

All target category IDs were verified by hand against eBay browse URLs
(ebay.com/b/<name>/<id>) because eBay retired the category-name/suggestion APIs
(Taxonomy 403, GetCategories/GetSuggestedCategories 410).

Usage:
    python ai_ebay_fix_antique_categories.py --dry-run   # show planned changes
    python ai_ebay_fix_antique_categories.py             # apply + report + push
    python ai_ebay_fix_antique_categories.py --no-push
"""

import os
import re
import sys
import csv
import argparse
import logging
from datetime import datetime

import requests
import config
import ebay_utils

try:
    from notify import send as notify_send
except Exception:  # notify optional
    def notify_send(title, message, priority="default", tags=None):
        return False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
EBAY_XML_URL = "https://api.ebay.com/ws/api.dll"

# eBay Collectibles > Bottles & Insulators > Bottles > Antique (Pre-1900) subtree.
# Verified from eBay browse URLs. Extend if PriceYak surfaces another pre-1900 leaf.
ANTIQUE_CATEGORIES = {
    "889":    "Antique Bottles (Pre-1900) [parent]",
    "895":    "Antique Bottles Pre 1900",
    "1351":   "Liquor Bottles (Pre-1900)",
    "156282": "Beer Bottles (Pre-1900)",
    "13909":  "Utility & Black Glass Bottles (Pre-1900)",
    "13910":  "Other Antique Bottles (Pre-1900)",
}

# Title keyword -> (modern leaf category id, human name). Ordered: first match wins,
# so put more specific product types before generic ones. All IDs hand-verified.
KEYWORD_MAP = [
    (("candle",),                                              "46782",  "Candles"),
    (("jar", "jars", "canister", "mason"),                     "13913",  "Jars (Modern)"),
    (("water bottle", "bottle", "flask", "tumbler", "mug",
      "thermos", "growler", "canteen", "drinkware"),           "177006", "Vacuum Flasks & Mugs"),
]


def get_active_listings(token):
    h = {"Authorization": "Bearer " + token}
    items, off = [], 0
    while True:
        d = requests.get(
            "https://www.priceyak.com/v0/account/{}/listings".format(config.PY_ACCOUNT_ID),
            headers=h, params={"count": 200, "offset": off}, timeout=120,
        ).json().get("data", [])
        if not d:
            break
        items += d
        off += 200
        if off > 20000:
            break
    return items


def pick_target(title):
    tl = (title or "").lower()
    for keywords, cid, name in KEYWORD_MAP:
        if any(k in tl for k in keywords):
            return cid, name
    return None, None


def revise_category(item_id, category_id, ebay_token):
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<ReviseFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
        "<Item><ItemID>{iid}</ItemID>"
        "<PrimaryCategory><CategoryID>{cat}</CategoryID></PrimaryCategory>"
        "<ConditionID>1000</ConditionID>"
        "</Item></ReviseFixedPriceItemRequest>"
    ).format(iid=item_id, cat=category_id)
    headers = {
        "X-EBAY-API-CALL-NAME": "ReviseFixedPriceItem", "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967", "X-EBAY-API-IAF-TOKEN": ebay_token,
        "Content-Type": "text/xml",
    }
    r = requests.post(EBAY_XML_URL, data=body.encode("utf-8"), headers=headers, timeout=60)
    ack = (re.findall(r"<Ack>(.*?)</Ack>", r.text) or ["Unknown"])[0]
    msgs = re.findall(r"<ShortMessage>(.*?)</ShortMessage>", r.text)
    return ack, msgs


def main():
    ap = argparse.ArgumentParser(description="Recategorize listings stuck in Pre-1900 antique bottle categories")
    ap.add_argument("--dry-run", action="store_true", help="Show planned changes without applying")
    ap.add_argument("--no-push", action="store_true", help="Suppress the ntfy/Telegram alert")
    args = ap.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)

    py_token = requests.post(
        "https://www.priceyak.com/v0/account/{}/api_login".format(config.PY_ACCOUNT_ID),
        json={"api_key": config.PY_API_KEY}, timeout=30,
    ).json()["token"]
    listings = get_active_listings(py_token)
    log.info("Scanned %d active listing(s).", len(listings))

    flagged = [it for it in listings if str(it.get("category")) in ANTIQUE_CATEGORIES]
    log.info("In antique-bottle categories: %d", len(flagged))
    if not flagged:
        log.info("Nothing to fix.")
        return

    ebay_token = ebay_utils.load_credentials()["token"] if not args.dry_run else None

    fixed, manual, failed = [], [], []
    for it in flagged:
        iid = str(it.get("itemid"))
        title = it.get("title") or ""
        cur = str(it.get("category"))
        cur_name = ANTIQUE_CATEGORIES.get(cur, cur)
        tgt, tgt_name = pick_target(title)
        if not tgt:
            manual.append((iid, cur_name, title))
            log.warning("NEEDS MANUAL (no keyword): %s [%s] %s", iid, cur_name, title[:55])
            continue
        if args.dry_run:
            fixed.append((iid, cur_name, tgt, tgt_name, title, "DRY"))
            log.info("[DRY] %s: %s -> %s (%s)  %s", iid, cur_name, tgt, tgt_name, title[:45])
            continue
        ack, msgs = revise_category(iid, tgt, ebay_token)
        if ack in ("Success", "Warning"):
            fixed.append((iid, cur_name, tgt, tgt_name, title, ack))
            log.info("FIXED %s: %s -> %s (%s) [%s]", iid, cur_name, tgt_name, tgt, ack)
        else:
            failed.append((iid, cur_name, tgt, tgt_name, title, "; ".join(msgs)[:160]))
            log.error("FAILED %s -> %s: %s", iid, tgt, "; ".join(msgs)[:160])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = os.path.join(DATA_DIR, "antique_category_fix_{}.csv".format(ts))
    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["result", "item_id", "from_category", "to_category_id", "to_category", "title", "note"])
        for iid, cn, tgt, tn, title, note in fixed:
            w.writerow(["FIXED" if not args.dry_run else "DRY", iid, cn, tgt, tn, title, note])
        for iid, cn, tgt, tn, title, note in failed:
            w.writerow(["FAILED", iid, cn, tgt, tn, title, note])
        for iid, cn, title in manual:
            w.writerow(["NEEDS_MANUAL", iid, cn, "", "", title, "no keyword match"])
    log.info("Report -> %s", report)

    print("=" * 64)
    print("ANTIQUE CATEGORY FIX  (scanned {})".format(len(listings)))
    print("  fixed:        {}".format(len(fixed)))
    print("  failed:       {}".format(len(failed)))
    print("  needs manual: {}".format(len(manual)))
    print("=" * 64)

    if args.no_push or args.dry_run:
        return
    if fixed or failed or manual:
        lines = ["Antique-category sweep: {} fixed, {} failed, {} need manual.".format(
            len(fixed), len(failed), len(manual))]
        for iid, cn, tgt, tn, title, note in (failed + [])[:5]:
            lines.append("  FAIL {} -> {}: {}".format(iid, tn, note))
        for iid, cn, title in manual[:5]:
            lines.append("  MANUAL {} [{}] {}".format(iid, cn, title[:40]))
        prio = "high" if (failed or manual) else "default"
        notify_send("eBay: antique-category fix", "\n".join(lines), priority=prio,
                    tags="card_index_dividers")


if __name__ == "__main__":
    main()
