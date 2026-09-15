"""
Pre-submit ASIN filter -- drop ASINs PriceYak will predictably reject BEFORE
spending a create_batch attempt on them (and before they inflate the failure
rate). This is what turns the 5000-slot plan into actual listings: ~90% of
attempts fail, mostly on PERMANENT reasons that ARE knowable the second time.
Nothing used to remember them, so the same junk got re-submitted every cycle.

Drops an ASIN when it is:
  - blacklisted  : on data/blacklist.txt (VeRO/banned ASINs synced from the
                   PriceYak blacklist by the sweep + unsupported-item pipelines)
  - known_reject : on data/rejected_asins.txt -- an ASIN PriceYak already failed
                   for a PERMANENT reason (veromatic*, banned_*, max_source_price).
                   Populated by harvest_rejected_asins.py from /requests history.
  - duplicate    : already an ACTIVE PriceYak listing (live dedup; needs token).
  - dup_in_batch : repeated within the same submit call.

Fail-closed on the local lists (always applied); fail-open on the live duplicate
dedup (if the active-listing fetch fails, a duplicate just wastes one attempt --
never block real submissions over it). ASINs compare case-insensitively
(PriceYak lowercases product_ids; the scrapers store UPPERCASE).

Used by ai_relist_proven_sellers.submit_to_priceyak and
batch_uploader.upload_batch_to_priceyak.
"""

import os
import logging

import requests
import config

log = logging.getLogger(__name__)

DATA_DIR = os.path.join("..", "data")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.txt")
REJECTED_FILE = os.path.join(DATA_DIR, "rejected_asins.txt")
ACCOUNT_ID = config.PY_ACCOUNT_ID

_active_cache = None  # memoized set of active-listing ASINs (UPPERCASE), per process


class NoopResp:
    """Response-shim returned when a submit is filtered down to nothing, so
    callers' `resp.status_code == 200` / `resp.text` checks keep working."""
    status_code = 200
    text = "prefilter: nothing to submit (all ASINs filtered)"


def _load_set(path):
    s = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                a = ln.strip().upper()
                if a:
                    s.add(a)
    return s


def load_blacklist():
    return _load_set(BLACKLIST_FILE)


def load_rejected():
    return _load_set(REJECTED_FILE)


def active_asins(token, force=False):
    """Set of ASINs (UPPERCASE) that are ACTIVE PriceYak listings. Memoized per
    process; fails open (returns empty) so dedup never blocks submits."""
    global _active_cache
    if _active_cache is not None and not force:
        return _active_cache
    out, off = set(), 0
    h = {"Authorization": "Bearer " + token}
    try:
        while True:
            d = requests.get(
                "https://www.priceyak.com/v0/account/{}/listings".format(ACCOUNT_ID),
                headers=h, params={"count": 200, "offset": off}, timeout=120,
            ).json().get("data", [])
            if not d:
                break
            for it in d:
                a = (((it.get("product") or {}).get("product_id")) or it.get("seller_sku") or "").strip().upper()
                if a:
                    out.add(a)
            off += 200
            if off > 20000:
                break
        _active_cache = out
        log.info("prefilter: %d active-listing ASIN(s) loaded for duplicate dedup.", len(out))
    except Exception as e:  # noqa: BLE001 -- fail open, dedup is best-effort
        log.warning("prefilter: active-listing fetch failed (%s); skipping duplicate dedup.", e)
        _active_cache = set()
    return _active_cache


def filter_asins(asins, token=None, use_active=True):
    """Return (kept, dropped) where dropped = {reason: [asins]}. Order preserved."""
    bl = load_blacklist()
    rej = load_rejected()
    act = active_asins(token) if (use_active and token) else set()
    kept, seen = [], set()
    dropped = {"blacklisted": [], "known_reject": [], "duplicate": [], "dup_in_batch": []}
    for a in asins:
        if not a:
            continue
        u = a.strip().upper()
        if u in seen:
            dropped["dup_in_batch"].append(a)
            continue
        seen.add(u)
        if u in bl:
            dropped["blacklisted"].append(a)
        elif u in rej:
            dropped["known_reject"].append(a)
        elif u in act:
            dropped["duplicate"].append(a)
        else:
            kept.append(a)
    return kept, dropped


def clean(asins, token=None, use_active=True, label=""):
    """Filter `asins`, log a one-line summary, and return the kept list."""
    kept, dropped = filter_asins(asins, token=token, use_active=use_active)
    n_drop = sum(len(v) for v in dropped.values())
    if n_drop:
        summary = ", ".join("{} {}".format(len(v), k) for k, v in dropped.items() if v)
        log.info("prefilter%s: %d in -> %d kept, %d dropped (%s)",
                 (" " + label) if label else "", len(asins), len(kept), n_drop, summary)
    return kept
