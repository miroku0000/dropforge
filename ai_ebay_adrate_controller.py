"""
Auto-manage the Promoted Listings ad rate on the `automagical` general campaign.

The campaign is COST_PER_SALE with a DYNAMIC ad rate capped at adRateCapPercent
(you only pay the ad fee when a promoted sale happens). eBay's dynamic rate rises
toward the cap when competition warrants; so the cap is the real lever. This
controller nudges the cap to chase impression share WITHOUT letting ad spend eat
the margin:

  effective_rate = ad_fees / promoted_sales      (from the latest ads report CSV)
  roas           = promoted_sales / ad_fees  = 1 / effective_rate
  cap_constrained = effective_rate >= cap - 0.5  (eBay wants to bid >= the cap)

  * roas >= ROAS_FLOOR and cap_constrained -> RAISE cap by STEP (eBay would spend
    more and it's still profitable) up to MAX_CAP.
  * roas <  ROAS_FLOOR                      -> LOWER cap by STEP (ads eating margin)
    down to MIN_CAP.
  * otherwise                               -> HOLD (either not constrained, so a
    higher cap wouldn't spend, or comfortably inside the band).

Only adjusts when the report is fresh and has enough promoted sales for signal,
and moves at most one STEP per run. Reads the newest automagical *ads_report*.csv
in ~/Downloads (download via ai_ebay_download_automagical.py ebay_ads_report_7days).

Usage:
    python ai_ebay_adrate_controller.py --dry-run
    python ai_ebay_adrate_controller.py
    python ai_ebay_adrate_controller.py --roas-floor 7 --max-cap 15 --min-cap 5 --step 2
"""

import os
import re
import csv
import glob
import time
import argparse
import logging

import requests
import ebay_utils

try:
    from notify import send as notify_send
except Exception:
    def notify_send(title, message, priority="default", tags=None):
        return False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ebay_ads_automation.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

CAMPAIGN_ID = "12402748019"  # automagical general campaign
CAMPAIGN_URL = "https://api.ebay.com/sell/marketing/v1/ad_campaign/{}".format(CAMPAIGN_ID)
UPDATE_URL = CAMPAIGN_URL + "/update_ad_rate_strategy"
DOWNLOADS = os.path.expanduser("~/Downloads")


def _money(s):
    s = (s or "").replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def latest_report():
    pats = ["automagical_*ads_report*.csv", "*automagical*Listing*ads*report*.csv"]
    files = []
    for p in pats:
        files += glob.glob(os.path.join(DOWNLOADS, p))
    return max(files, key=os.path.getmtime) if files else None


def report_metrics(path):
    """Sum ad fees + promoted sales across the listing rows -> (fees, sales, sold)."""
    lines = open(path, encoding="utf-8-sig").read().split("\n")
    # header is the first line that contains 'Ad fees'
    hidx = next((i for i, ln in enumerate(lines) if "Ad fees" in ln), 0)
    import io
    rd = csv.DictReader(io.StringIO("\n".join(lines[hidx:])))
    fees = sales = sold = 0.0
    for r in rd:
        fees += _money(r.get("Ad fees"))
        sales += _money(r.get("Total Promoted Listings Sales"))
        sold += _money((r.get("Total Promoted Listings Sold quantity") or "0").replace(",", ""))
    return fees, sales, sold


def get_cap(token):
    r = requests.get(CAMPAIGN_URL, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, timeout=60)
    fs = r.json().get("fundingStrategy") or {}
    prefs = (fs.get("dynamicAdRatePreferences") or [{}])[0]
    return float(prefs.get("adRateCapPercent") or 0), fs.get("adRateStrategy")


def set_cap(token, cap_pct):
    payload = {"adRateStrategy": "DYNAMIC",
               "dynamicAdRatePreferences": [{"adRateAdjustmentPercent": "0.0",
                                             "adRateCapPercent": "{:.1f}".format(cap_pct)}]}
    r = requests.post(UPDATE_URL, headers={"Authorization": "Bearer " + token,
                                           "Content-Type": "application/json"}, json=payload, timeout=60)
    return r.status_code, r.text[:200]


def main():
    ap = argparse.ArgumentParser(description="Auto-manage the automagical Promoted Listings ad rate cap")
    ap.add_argument("--roas-floor", type=float, default=7.0, help="Min ROAS to keep raising (default 7.0 = ~14%% rate)")
    ap.add_argument("--max-cap", type=float, default=15.0)
    ap.add_argument("--min-cap", type=float, default=5.0)
    ap.add_argument("--step", type=float, default=2.0)
    ap.add_argument("--min-sales", type=int, default=5, help="Min promoted sales in report to act (default 5)")
    ap.add_argument("--max-report-age-days", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    rep = latest_report()
    if not rep:
        log.warning("No automagical ads report in %s; run ai_ebay_download_automagical.py first. Skipping.", DOWNLOADS)
        return
    age_d = (time.time() - os.path.getmtime(rep)) / 86400.0
    if age_d > args.max_report_age_days:
        log.warning("Latest report is %.1fd old (> %.0f); skipping to avoid acting on stale data.", age_d, args.max_report_age_days)
        return

    fees, sales, sold = report_metrics(rep)
    log.info("Report %s (%.1fd old): fees=$%.2f sales=$%.2f sold=%.0f", os.path.basename(rep), age_d, fees, sales, sold)
    if sold < args.min_sales or fees <= 0:
        log.info("Only %.0f promoted sales / $%.2f fees -- too little signal (need >=%d). Holding.", sold, fees, args.min_sales)
        return

    eff = 100.0 * fees / sales if sales else 0
    roas = sales / fees if fees else 0
    token = ebay_utils.load_credentials()["token"]
    cap, strat = get_cap(token)
    constrained = eff >= cap - 0.5
    log.info("effective_rate=%.1f%% roas=%.1fx cap=%.1f%% (%s) constrained=%s", eff, roas, cap, strat, constrained)

    if roas < args.roas_floor:
        new = max(args.min_cap, cap - args.step)
        action = "LOWER (roas {:.1f} < floor {:.1f})".format(roas, args.roas_floor)
    elif constrained and roas >= args.roas_floor:
        new = min(args.max_cap, cap + args.step)
        action = "RAISE (constrained, roas {:.1f} >= floor {:.1f})".format(roas, args.roas_floor)
    else:
        new = cap
        action = "HOLD (not cap-constrained)" if not constrained else "HOLD"

    if abs(new - cap) < 0.05:
        log.info("Decision: %s -> keep cap at %.1f%%.", action, cap)
        return

    log.info("Decision: %s -> cap %.1f%% -> %.1f%%", action, cap, new)
    if args.dry_run:
        log.info("[DRY] would set cap to %.1f%%.", new)
        return
    code, body = set_cap(token, new)
    ok = code in (200, 204)
    log.info("update_ad_rate_strategy -> HTTP %s %s", code, "OK" if ok else body)
    if ok and not args.no_push:
        notify_send("eBay ad rate {}".format("raised" if new > cap else "lowered"),
                    "automagical ad-rate cap {:.0f}%->{:.0f}% (eff {:.1f}%, ROAS {:.1f}x). {}".format(
                        cap, new, eff, roas, action),
                    priority="default", tags="chart_with_upwards_trend")


if __name__ == "__main__":
    main()
