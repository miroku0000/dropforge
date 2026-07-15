"""
Scrape eBay Sales performance figures (Revenue + net sales after fees) for a
month, using the logged-in eBay session (same browser as the other ai_ebay_*
scripts). Feeds the monthly P&L sheet.

The Sales dashboard takes a custom date range as epoch-millis in the URL. The
ranges eBay uses are at PACIFIC midnight (America/Los_Angeles), so month bounds
are computed in that timezone to match the dashboard exactly.

Usage:
    python ai_ebay_sales_performance.py --year 2026 --month 1 --probe   # inspect
    python ai_ebay_sales_performance.py --year 2026 --month 1           # extract
    python ai_ebay_sales_performance.py --year 2026 --month 1 --json
"""

import re
import sys
import json
import argparse
import calendar
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser, needs_signin, wait_for_signin, _is_bot_blocked, _wait_for_captcha

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")
DOWNLOAD_DIR = __import__("os").path.expanduser("~/Downloads")


def month_epochs_ms(year, month):
    """(referenceStart, referenceEnd, benchmarkStart) in epoch ms, Pacific bounds."""
    start = datetime(year, month, 1, tzinfo=PACIFIC)
    # eBay encodes referenceEnd as the LAST day's midnight (inclusive), not the
    # first of next month.
    end = datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=PACIFIC)
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    bench = datetime(py, pm, 1, tzinfo=PACIFIC)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000), int(bench.timestamp() * 1000)


def sales_url(year, month):
    start, end, bench = month_epochs_ms(year, month)
    return ("https://www.ebay.com/sh/performance/sales?referencePeriodFilter=CUSTOM"
            f"&benchmarkPeriodFilter=CUSTOM&benchmarkStart={bench}"
            f"&referenceStart={start}&referenceEnd={end}")


def _goto(page, url):
    # The dashboard is an SPA; navigating to a new date range can ERR_ABORTED if
    # a client-side nav races us. Land on a neutral page first, then retry.
    for attempt in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            return
        except Exception as e:
            log.warning(f"  goto attempt {attempt + 1} failed: {str(e)[:80]}")
            try:
                page.goto("https://www.ebay.com/sh/ovw", wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)


def _ensure_ready(page, url):
    _goto(page, url)
    if _is_bot_blocked(page):
        _wait_for_captcha(page)
        _goto(page, url)
    if needs_signin(page):
        wait_for_signin(page, success_url_glob="**/sh/performance/**")
        _goto(page, url)


def _wait_for_metrics(page, timeout_s=40):
    """The summary-metrics tiles load async; wait for them to render + settle."""
    last, stable = -1, 0
    for _ in range(timeout_s):
        try:
            n = len(page.query_selector_all(".summary-metrics__base-amount"))
        except Exception:
            n = 0
        stable = stable + 1 if n == last else 0
        last = n
        if n >= 5 and stable >= 3:
            break
        page.wait_for_timeout(1000)
    log.info(f"  metric tiles stabilized at {last}")


def probe(page, year, month):
    url = sales_url(year, month)
    log.info(f"PROBE: {url}")
    _ensure_ready(page, url)
    _wait_for_metrics(page)
    ts = datetime.now(PACIFIC).strftime("%Y%m%d_%H%M%S")
    import os
    hp = os.path.join(DOWNLOAD_DIR, f"ebay_sales_probe_{ts}.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(page.content())
    try:
        page.screenshot(path=os.path.join(DOWNLOAD_DIR, f"ebay_sales_probe_{ts}.png"), full_page=True)
    except Exception:
        pass
    log.info(f"Saved HTML -> {hp}")
    log.info(f"Final URL: {page.url}")
    body = page.locator("body").inner_text(timeout=5000)
    # Show lines that mention sales/fees or contain a dollar amount.
    for line in body.splitlines():
        s = line.strip()
        if s and (re.search(r"\$[\d,]+\.\d{2}", s) or re.search(r"(?i)\b(net )?sales|fees|revenue|earnings\b", s)):
            log.info(f"  | {s[:90]}")


_COL_TEXT_JS = """e => { let n = e; for (let i = 0; i < 4; i++) {
  if (!n) break;
  if (n.className && /(^|\\s)col(\\s|$)/.test(n.className)) return n.innerText;
  n = n.parentElement;
} return ''; }"""


def _tile_value(el):
    m = re.search(r"\$([0-9,]+\.[0-9]{2})", (el.inner_text() or ""))
    return float(m.group(1).replace(",", "")) if m else None


def extract(page, year, month):
    """Return {'revenue':float,'net_sales':float} from the summary-metrics tiles.

    Each amount lives in a div.col with its label: the Total-sales col contains
    only "Total sales"; the Net-sales col contains "Net sales". Pair by that."""
    _ensure_ready(page, sales_url(year, month))
    _wait_for_metrics(page)
    revenue = net_sales = None
    els = page.query_selector_all(".summary-metrics__base-amount")
    for el in els:
        col = el.evaluate(_COL_TEXT_JS) or ""
        v = _tile_value(el)
        if v is None:
            continue
        if net_sales is None and "Net sales" in col:
            net_sales = v
        elif revenue is None and "Total sales" in col and "Net sales" not in col:
            revenue = v
    if revenue is None and els:          # fallback: first tile is Total sales
        revenue = _tile_value(els[0])
    return {"revenue": revenue, "net_sales": net_sales}


def main():
    ap = argparse.ArgumentParser(description="Scrape eBay Sales performance (revenue + net sales) for a month")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with sync_playwright() as p:
        context = launch_ebay_browser(p, viewport={"width": 1500, "height": 950}, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            if args.probe:
                probe(page, args.year, args.month)
                return
            res = extract(page, args.year, args.month)
            label = f"{calendar.month_abbr[args.month]}-{str(args.year)[2:]}"
            if args.json:
                print(json.dumps({"month": label, **res}))
            else:
                print(f"{label}: revenue={res.get('revenue')}  net_sales={res.get('net_sales')}")
            if "revenue" not in res or "net_sales" not in res:
                log.warning("Did not find both figures -- run with --probe to inspect the page.")
        finally:
            context.close()
            log.info("Disconnected from Chrome (left running).")


if __name__ == "__main__":
    main()
