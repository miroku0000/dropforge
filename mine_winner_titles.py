"""
Mine product-type search terms from the titles of YOUR proven/demanded listings.

Pulls active listings from PriceYak and looks at the ones with real signal --
items that sold (order_count), are watched (watch_count), or viewed
(view_count). It extracts 2- and 3-word product-type phrases from their titles
(dropping brand gibberish, model numbers and fitment words), scores each phrase
by how much demand it appears in, and adds the top phrases to amazon_urls.txt.

Idea: if "diving case", "rain guards" or "rust converting undercoating" show up
in items that sell/get watched, searching those phrases on Amazon surfaces more
listable variants.

Usage:
    python mine_winner_titles.py                       # add top phrases
    python mine_winner_titles.py --max 40 --min-price 50
    python mine_winner_titles.py --print-only          # list phrases (pipe to expander)
"""

import re
import html
import argparse
import logging
from collections import defaultdict

import requests

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

import config
PY_ACCOUNT_ID = config.PY_ACCOUNT_ID
PY_API_KEY = config.PY_API_KEY

# Words that are not product types: fitment, packaging, filler, generic modifiers.
STOPWORDS = {
    "for", "with", "and", "the", "fit", "fits", "fitment", "compatible", "replacement",
    "replace", "set", "sets", "pair", "pack", "pcs", "pieces", "piece", "new", "oem",
    "kit", "kits", "inch", "inches", "in", "x", "plus", "of", "to", "by", "or", "a",
    "universal", "premium", "genuine", "original", "style", "type", "size", "pack",
    "include", "includes", "including", "fitted", "fitting", "model", "models",
    "year", "years", "version", "upgraded", "upgrade", "newest", "latest",
    # units / measures (spec fragments, not product types)
    "lbs", "lb", "oz", "qt", "ml", "watt", "watts", "volt", "volts", "amp", "amps",
    "min", "mins", "hr", "hrs", "hour", "hours", "day", "days", "per", "ft", "cm", "mm",
}


def py_login():
    r = requests.post(
        f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/api_login",
        json={"api_key": PY_API_KEY}, timeout=30,
    )
    r.raise_for_status()
    return r.json()["token"]


def fetch_active_listings(token):
    headers = {"Authorization": "Bearer " + token, "Accept": "*/*"}
    rows, offset = [], 0
    while True:
        url = (f"https://www.priceyak.com/v0/account/{PY_ACCOUNT_ID}/listings"
               f"?count=200&offset={offset}&include_inactive=false&accurate_count=true")
        body = requests.get(url, headers=headers, timeout=120).json()
        data = body.get("data", [])
        rows.extend(data)
        offset += len(data)
        if not data or offset >= body.get("total_count", 0):
            break
    return rows


def _is_noise(token):
    """Drop model numbers, codes, brand gibberish, and short/stop tokens."""
    if len(token) < 3:
        return True
    if token in STOPWORDS:
        return True
    if any(ch.isdigit() for ch in token):       # model/part numbers, sizes
        return True
    if not token.isalpha():
        return True
    return False


def title_to_phrases(title):
    """Yield 2- and 3-word product-type phrases from a title."""
    # Decode entities (&#8482; etc.), lowercase, split on non-letters.
    text = html.unescape(title or "").lower()
    # Break on punctuation/commas so we don't bridge unrelated clauses.
    segments = re.split(r"[^a-z]+", text)
    # Re-segment into runs of clean tokens (a noise token breaks the run).
    runs, cur = [], []
    for tok in segments:
        if tok and not _is_noise(tok):
            cur.append(tok)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)

    for run in runs:
        for n in (2, 3):
            for i in range(len(run) - n + 1):
                yield " ".join(run[i:i + n])


def mine(rows, min_watch):
    scores = defaultdict(float)
    counts = defaultdict(int)
    used = 0
    for x in rows:
        orders = x.get("order_count") or 0
        watch = x.get("watch_count") or 0
        views = x.get("view_count") or 0
        if orders <= 0 and watch < min_watch and views <= 0:
            continue
        used += 1
        weight = orders * 3 + watch + (1 if views > 0 else 0)
        for phrase in set(title_to_phrases(x.get("title", ""))):
            scores[phrase] += weight
            counts[phrase] += 1
    log.info(f"Mined phrases from {used} listing(s) with demand signal.")
    # Prefer phrases that appear across multiple winners, then by weighted score.
    ranked = sorted(scores.items(), key=lambda kv: (counts[kv[0]], kv[1]), reverse=True)
    return [p for p, _ in ranked]


def main():
    ap = argparse.ArgumentParser(description="Mine product-type terms from your winning listings' titles")
    ap.add_argument("--min-watch", type=int, default=1, help="Min watch_count to count a non-selling item (default 1)")
    ap.add_argument("--max", type=int, default=40, help="Add at most this many phrases (default 40)")
    ap.add_argument("--min-price", type=float, default=0)
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    token = py_login()
    rows = fetch_active_listings(token)
    log.info(f"Fetched {len(rows)} active listing(s).")

    phrases = mine(rows, args.min_watch)[: args.max]
    if not phrases:
        log.info("No phrases mined (not enough demand signal yet).")
        return

    for p in phrases[:25]:
        log.info(f"  {p}")
    if len(phrases) > 25:
        log.info(f"  ... and {len(phrases) - 25} more.")

    if args.print_only:
        for p in phrases:
            print(p)
        return

    added, skipped = add_search_terms(
        phrases,
        min_price=args.min_price if args.min_price > 0 else None,
        prime=not args.no_prime,
        high_rating=not args.no_high_rating,
        urls_file=args.urls_file,
    )
    print(f"Added {len(added)} new search term(s) to {args.urls_file} ({len(skipped)} already present).")
    for t in added[:40]:
        print(f"  + {t}")


if __name__ == "__main__":
    main()
