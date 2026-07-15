"""
eBay Issue Resolution Center -> kill list + Amazon-ASIN blacklist.

Scrapes https://resolution.ebay.com/rw/IssueResolutionCenter (using the same
authenticated Chrome / .playwright_profile that the airotate.bat report scripts
use, via playwright_browser.launch_ebay_browser), reads every problematic
listing, and for each one resolves the Amazon ASIN from PriceYak.

For each flagged listing it collects:
    - eBay item id          (from the page: button id="product-<itemid>")
    - Amazon ASIN / SKU     (from PriceYak: search?query=<itemid> -> listings/<id>)
    - title + policy type   (from the page, for the report/summary)

It writes two files that feed the existing tooling:
    data\\kill.txt           one eBay item id per line  -> priceyakbulkdelete.py
    data\\blacklist_add.txt  one Amazon ASIN per line   -> priceyakblacklistadd.py
and a timestamped CSV report for your records.

Why PriceYak for the ASIN (not eBay GetItem)? eBay hides/removes the very
listings we care about ("...hidden until you can fix it" / "...removed for
violating policy"), so GetItem fails for them. PriceYak still has the
source-ASIN mapping for removed listings.

Usage:
    python ai_ebay_issue_resolution_to_blacklist.py [--apply-blacklist] [--no-scrape]

    --apply-blacklist  After writing files, immediately run priceyakblacklistadd.py
                       to add the ASINs to the PriceYak blacklist. (Ending the eBay
                       listings is left to you: run priceyakbulkdelete.py.)
    --no-scrape        Skip the browser; re-resolve ASINs from an existing
                       data\\kill.txt (handy for re-runs / testing).
"""

import os
import re
import sys
import time
import csv
import subprocess
import logging
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright
from playwright_browser import (
    launch_ebay_browser,
    _is_bot_blocked,
    _wait_for_captcha,
    needs_signin as _needs_signin,
    wait_for_signin as _wait_for_signin,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# --- PriceYak (same store/credentials as priceyakbulkdelete.py) ---
import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

IRC_URL = "https://resolution.ebay.com/rw/IssueResolutionCenter"

DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
KILL_FILE = os.path.join(DATA_DIR, "kill.txt")
BLACKLIST_ADD_FILE = os.path.join(DATA_DIR, "blacklist_add.txt")


# ----------------------------------------------------------------------------
# PriceYak resolver: eBay item id -> Amazon ASIN
# ----------------------------------------------------------------------------
def py_login():
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
        json={"api_key": PY_API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def py_resolve_asin(itemid, token):
    """Return (asin, title) for an eBay item id via PriceYak, or (None, None)."""
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    try:
        s = requests.get(
            f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/search?query={itemid}",
            headers=headers,
            timeout=60,
        ).json()
    except Exception as e:
        log.warning(f"  search failed for {itemid}: {e}")
        return None, None

    listing_id = s.get("id")
    if not listing_id or s.get("type") != "Listing":
        log.warning(f"  {itemid}: no PriceYak listing found (hit_type={s.get('hit_type')})")
        return None, None

    try:
        o = requests.get(
            f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings/{listing_id}",
            headers=headers,
            timeout=60,
        ).json()
    except Exception as e:
        log.warning(f"  listing fetch failed for {itemid}/{listing_id}: {e}")
        return None, None

    asin = (o.get("product") or {}).get("product_id") or o.get("seller_sku")
    return asin, o.get("title")


# ----------------------------------------------------------------------------
# Scrape the Issue Resolution Center
# ----------------------------------------------------------------------------
def _clear_filters(page):
    """Click 'Clear filters' if a filter is active (it can hide most rows)."""
    try:
        body = page.locator("body").inner_text(timeout=5000)
        if "Showing" in body:
            m = re.search(r"Showing\s+(\d+)\s+of\s+(\d+)", body)
            if m and m.group(1) == m.group(2):
                return  # nothing filtered out
    except Exception:
        pass
    for el in page.query_selector_all("button, a"):
        try:
            if (el.inner_text() or "").strip().lower() == "clear filters" and el.is_visible():
                el.click()
                log.info("Clicked 'Clear filters' to reveal all listings.")
                time.sleep(2)
                return
        except Exception:
            continue


def scrape_irc():
    """Return list of dicts: {itemid, title, policy} for every flagged listing."""
    with sync_playwright() as p:
        context = launch_ebay_browser(p)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            log.info(f"Opening {IRC_URL}")
            page.goto(IRC_URL, wait_until="load", timeout=60000)

            if _is_bot_blocked(page):
                _wait_for_captcha(page)
                page.goto(IRC_URL, wait_until="load", timeout=60000)
            time.sleep(4)

            # resolution.ebay.com requires its own sign-in (separate from Seller
            # Hub). Detect it by URL *and* page content (eBay's password step can
            # stay on a URL the URL-only check missed).
            if _needs_signin(page):
                _wait_for_signin(page)
                page.goto(IRC_URL, wait_until="load", timeout=60000)
                time.sleep(5)

            # Wait for the listing rows to render.
            try:
                page.wait_for_selector('button[id^="product-"]', timeout=30000)
            except Exception:
                # No rows could mean genuinely 0 issues -- OR that we're stuck on
                # a sign-in/password/CAPTCHA page that slipped past the check above.
                # Do NOT silently return 0 in that case: main() would blank
                # kill.txt/blacklist_add.txt and we'd lose the real work list.
                if _needs_signin(page):
                    _wait_for_signin(page)
                    page.goto(IRC_URL, wait_until="load", timeout=60000)
                    time.sleep(5)
                    if _needs_signin(page):
                        raise RuntimeError(
                            "Still on the eBay sign-in/password page after waiting; "
                            "aborting so a stale kill list is not cleared."
                        )
                    try:
                        page.wait_for_selector('button[id^="product-"]', timeout=30000)
                    except Exception:
                        log.warning("No product rows appeared. Maybe there are 0 issues.")
                elif _is_bot_blocked(page):
                    _wait_for_captcha(page)
                    page.goto(IRC_URL, wait_until="load", timeout=60000)
                    time.sleep(3)
                    try:
                        page.wait_for_selector('button[id^="product-"]', timeout=30000)
                    except Exception:
                        log.warning("No product rows appeared. Maybe there are 0 issues.")
                else:
                    log.warning("No product rows appeared. Maybe there are 0 issues.")

            # IMPORTANT: the IRC remembers a previously-applied "Issue type" filter
            # in the profile, which can hide most rows (e.g. "Showing 1 of 24").
            # Click "Clear filters" so every listing is shown before scraping.
            _clear_filters(page)

            # Wait until the rendered row count matches the "Showing X of Y" total
            # (or stabilizes). Max ~30s.
            def _expected():
                try:
                    m = re.search(r"Showing\s+(\d+)\s+of\s+(\d+)", page.locator("body").inner_text(timeout=5000))
                    return int(m.group(2)) if m else None
                except Exception:
                    return None

            expected = _expected()
            if expected is not None:
                log.info(f"Page reports {expected} total listing issue(s).")

            stable, last = 0, -1
            for _ in range(30):
                count = len(set(re.findall(r'id="product-(\d{6,})"', page.content())))
                if expected is not None and count >= expected:
                    break
                stable = stable + 1 if count == last else 0
                last = count
                if count > 0 and stable >= 5:
                    break
                time.sleep(1)
            final = len(set(re.findall(r'id="product-(\d{6,})"', page.content())))
            log.info(f"Rendered {final} product row(s) before scrape (expected {expected}).")

            products = page.eval_on_selector_all(
                'button[id^="product-"]',
                """els => els.map(e => ({
                    itemid: e.id.replace('product-',''),
                    title: (e.innerText||'').trim()
                }))""",
            )
            policies = page.eval_on_selector_all(
                ".policy-violation-tags",
                "els => els.map(e => (e.innerText||'').trim().replace(/\\s+/g,' '))",
            )

            rows = []
            seen = set()
            for i, prod in enumerate(products):
                iid = prod["itemid"]
                if not re.fullmatch(r"\d{10,}", iid) or iid in seen:
                    continue
                seen.add(iid)
                rows.append(
                    {
                        "itemid": iid,
                        "title": prod["title"],
                        "policy": policies[i] if i < len(policies) else "",
                    }
                )

            log.info(f"Scraped {len(rows)} flagged listing(s) from the Issue Resolution Center.")
            return rows

        except Exception as e:
            log.error(f"Scrape failed: {e}")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                page.screenshot(path=os.path.join(DATA_DIR, f"irc_error_{ts}.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            context.close()
            log.info("Disconnected from Chrome (left running).")


def load_itemids_from_kill_file():
    """For --no-scrape: read existing kill.txt (matches priceyakbulkdelete.py logic)."""
    if not os.path.exists(KILL_FILE):
        log.error(f"{KILL_FILE} not found.")
        return []
    with open(KILL_FILE, "r", encoding="utf-8") as f:
        ids = [ln.strip() for ln in f if ln.strip()]
    return [{"itemid": i, "title": "", "policy": ""} for i in ids]


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    apply_blacklist = "--apply-blacklist" in sys.argv
    no_scrape = "--no-scrape" in sys.argv

    os.makedirs(DATA_DIR, exist_ok=True)

    rows = load_itemids_from_kill_file() if no_scrape else scrape_irc()
    if not rows:
        # No flagged listings. Blank out the work files so a stale kill.txt
        # from a previous run can't be acted on by priceyakbulkdelete.py.
        if not no_scrape:
            open(KILL_FILE, "w").close()
            open(BLACKLIST_ADD_FILE, "w").close()
            log.info("No flagged listings found. Wrote empty kill.txt / blacklist_add.txt.")
        else:
            log.info("Nothing to process. Exiting.")
        return

    token = py_login()
    log.info("Resolving Amazon ASINs from PriceYak...")
    resolved = []
    for r in rows:
        asin, py_title = py_resolve_asin(r["itemid"], token)
        if py_title and (not r["title"] or set(r["title"]) <= set("*")):
            r["title"] = py_title  # IRC sometimes masks titles; PriceYak may have it
        r["asin"] = asin or ""
        resolved.append(r)
        log.info(f"  {r['itemid']} -> {asin or 'NOT FOUND':<12} | {r.get('policy','')[:28]:<28} | {r['title'][:45]}")

    item_ids = [r["itemid"] for r in resolved]
    asins = [r["asin"] for r in resolved if r["asin"]]
    missing = [r["itemid"] for r in resolved if not r["asin"]]

    # --- write kill.txt (one item id per line; trailing newline so the existing
    #     priceyakbulkdelete.py txt_to_lst pop() drops an empty line, not an id) ---
    with open(KILL_FILE, "w", encoding="utf-8") as f:
        for iid in item_ids:
            f.write(iid + "\n")
    log.info(f"Wrote {len(item_ids)} eBay item id(s) -> {KILL_FILE}")

    # --- write blacklist_add.txt (one ASIN per line) ---
    with open(BLACKLIST_ADD_FILE, "w", encoding="utf-8") as f:
        for a in asins:
            f.write(a + "\n")
    log.info(f"Wrote {len(asins)} Amazon ASIN(s) -> {BLACKLIST_ADD_FILE}")

    # --- timestamped CSV report ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = os.path.join(DATA_DIR, f"issue_resolution_{ts}.csv")
    with open(report, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ebay_item_id", "amazon_asin", "policy", "title"])
        for r in resolved:
            w.writerow([r["itemid"], r["asin"], r.get("policy", ""), r["title"]])
    log.info(f"Wrote report -> {report}")

    print("\n" + "=" * 70)
    print(f"Issue Resolution Center: {len(resolved)} flagged listing(s)")
    print(f"  eBay ids written to     : {KILL_FILE}")
    print(f"  Amazon ASINs written to : {BLACKLIST_ADD_FILE}  ({len(asins)} resolved)")
    if missing:
        print(f"  ASIN NOT FOUND for {len(missing)} item(s): {', '.join(missing)}")
    print("=" * 70)
    print("\nNext steps:")
    print(f"  1) End the eBay listings : python priceyakbulkdelete.py")
    print(f"  2) Add ASINs to blacklist: python priceyakblacklistadd.py")
    if apply_blacklist:
        print("\n--apply-blacklist set: running priceyakblacklistadd.py now...")
        subprocess.run([sys.executable, "priceyakblacklistadd.py", BLACKLIST_ADD_FILE])


if __name__ == "__main__":
    main()
