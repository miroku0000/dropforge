"""
Expand seed search terms into related real buyer queries via autocomplete
engines, then add the new ones to amazon_urls.txt (the scrape input).

Autocomplete returns the queries shoppers actually type, ranked by popularity --
a cheap, high-yield multiplier on any seed. Three engines (use any/all):
    amazon  completion.amazon.com   (Amazon's own demand; default)
    ebay    autosug.ebay.com        (the platform you sell on)
    google  suggestqueries.google   (broad shopping intent)

Seeds come from positional args, --file, and/or --stdin -- so you can pipe in
the output of mine_converting_keywords.py to expand your proven winners:
    python mine_converting_keywords.py --print-only | python amazon_keyword_expander.py --stdin

Examples:
    python amazon_keyword_expander.py "cordless drill" "label maker"
    python amazon_keyword_expander.py --file seeds.txt --engine amazon,ebay --min-price 50
    python amazon_keyword_expander.py --alpha "rock tumbler"     # deeper: seed + a..z
"""

import os
import sys
import time
import json
import random
import string
import argparse
import logging

import requests

from amazon_search_urls import add_search_terms, AMAZON_URLS_FILE, keyword_of

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_HEADERS = {"User-Agent": _UA, "Accept": "*/*"}


def _suggest_amazon(prefix):
    r = requests.get(
        "https://completion.amazon.com/api/2017/suggestions",
        params={"limit": 11, "prefix": prefix, "alias": "aps",
                "site-variant": "desktop", "mid": "ATVPDKIKX0DER", "lop": "en_US"},
        headers=_HEADERS, timeout=20,
    )
    r.raise_for_status()
    return [s.get("value", "") for s in r.json().get("suggestions", [])]


def _suggest_ebay(prefix):
    r = requests.get("https://autosug.ebay.com/autosug",
                     params={"kwd": prefix, "sId": "0", "fmt": "osr"},
                     headers=_HEADERS, timeout=20)
    r.raise_for_status()
    data = json.loads(r.text)
    return data[1] if isinstance(data, list) and len(data) > 1 else []


def _suggest_google(prefix):
    r = requests.get("https://suggestqueries.google.com/complete/search",
                     params={"client": "firefox", "q": prefix},
                     headers=_HEADERS, timeout=20)
    r.raise_for_status()
    data = json.loads(r.text)
    return data[1] if isinstance(data, list) and len(data) > 1 else []


_ENGINES = {"amazon": _suggest_amazon, "ebay": _suggest_ebay, "google": _suggest_google}

_ALLOWED = set(string.ascii_lowercase + string.digits + " &'-./+")


def _clean(term):
    t = " ".join((term or "").split()).strip()
    low = t.lower()
    if not (2 <= len(low) <= 80):
        return None
    if any(c not in _ALLOWED for c in low):
        return None
    return t


def expand(seeds, engines, alpha=False, per_seed=40, sleep=0.3):
    """Return a de-duplicated list of related queries for `seeds`."""
    out, seen = [], set()
    seed_set = {s.strip().lower() for s in seeds}
    for seed in seeds:
        seed = seed.strip()
        if not seed:
            continue
        prefixes = [seed]
        if alpha:
            prefixes += [f"{seed} {c}" for c in string.ascii_lowercase]
        got = 0
        for prefix in prefixes:
            for eng in engines:
                try:
                    suggestions = _ENGINES[eng](prefix)
                except Exception as e:
                    log.warning(f"  {eng} suggest failed for '{prefix}': {e}")
                    continue
                for s in suggestions:
                    c = _clean(s)
                    if not c:
                        continue
                    low = c.lower()
                    if low in seen or low in seed_set:
                        continue
                    seen.add(low)
                    out.append(c)
                    got += 1
                    if got >= per_seed:
                        break
                time.sleep(sleep)
                if got >= per_seed:
                    break
            if got >= per_seed:
                break
        log.info(f"  '{seed}' -> {got} related term(s)")
    return out


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]


def main():
    ap = argparse.ArgumentParser(description="Expand seed terms via autocomplete into amazon_urls.txt")
    ap.add_argument("seeds", nargs="*", help="Seed terms")
    ap.add_argument("--file", help="Read seeds from a file (one per line)")
    ap.add_argument("--stdin", action="store_true", help="Read seeds from stdin")
    ap.add_argument("--from-urls", type=int, default=0, metavar="N",
                    help="Seed from N random existing keywords in the urls file (for daily auto-expansion)")
    ap.add_argument("--engine", default="amazon", help="Comma list: amazon,ebay,google (default amazon)")
    ap.add_argument("--alpha", action="store_true", help="Also expand 'seed a'..'seed z' (deeper harvest)")
    ap.add_argument("--per-seed", type=int, default=40, help="Max related terms per seed (default 40)")
    ap.add_argument("--min-price", type=float, default=0, help="Min price filter on generated searches")
    ap.add_argument("--no-prime", action="store_true")
    ap.add_argument("--no-high-rating", action="store_true")
    ap.add_argument("--urls-file", default=AMAZON_URLS_FILE)
    ap.add_argument("--print-only", action="store_true", help="Print expanded terms; do not write")
    args = ap.parse_args()

    seeds = list(args.seeds)
    if args.file:
        seeds += _read_lines(args.file)
    if args.stdin:
        seeds += [ln.strip() for ln in sys.stdin if ln.strip() and not ln.strip().startswith("#")]
    if args.from_urls > 0 and os.path.exists(args.urls_file):
        kws = []
        with open(args.urls_file, "r", encoding="utf-8") as f:
            for line in f:
                k = keyword_of(line.strip())
                if k:
                    kws.append(k)
        if kws:
            sample = random.sample(kws, min(args.from_urls, len(kws)))
            log.info(f"Seeding from {len(sample)} random existing keyword(s) in {args.urls_file}")
            seeds += sample
    if not seeds:
        ap.error("No seeds. Pass terms as arguments, --file, --stdin, and/or --from-urls.")

    engines = [e.strip() for e in args.engine.split(",") if e.strip() in _ENGINES]
    if not engines:
        ap.error(f"No valid engines in '{args.engine}'. Choose from: {', '.join(_ENGINES)}")

    log.info(f"Expanding {len(seeds)} seed(s) via {', '.join(engines)}...")
    terms = expand(seeds, engines, alpha=args.alpha, per_seed=args.per_seed)
    log.info(f"Got {len(terms)} unique related term(s).")

    if args.print_only:
        for t in terms:
            print(t)
        return

    added, skipped = add_search_terms(
        terms,
        min_price=args.min_price if args.min_price > 0 else None,
        prime=not args.no_prime,
        high_rating=not args.no_high_rating,
        urls_file=args.urls_file,
    )
    print(f"Added {len(added)} new search term(s) to {args.urls_file} "
          f"({len(skipped)} already present).")
    for t in added[:40]:
        print(f"  + {t}")
    if len(added) > 40:
        print(f"  ... and {len(added) - 40} more.")


if __name__ == "__main__":
    main()
