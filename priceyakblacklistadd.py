"""
Add Amazon product IDs (ASINs) to the PriceYak listing blacklist.

The PriceYak "Manage blacklist" page
(https://www.priceyak.com/stores/<account>/listings/blacklist) is backed by:

    GET  /v0/account/<account>/requests/blacklist
        -> {"brand": [...], "keyword": [...], "product_id": [...]}

    POST /v0/account/<account>/requests/blacklist
        body: {"data": {"brand": [...], "keyword": [...],
                        "product_id": [...], "apply_to_all_accounts": false}}

The POST *replaces* the entire blacklist, so we GET the current values first,
append the new product_ids (de-duped, order preserved), and POST the merged
document back. Authentication uses the same api_login token flow as
priceyakbulkdelete.py -- no website login required.

Usage:
    python priceyakblacklistadd.py [input_file] [--dry-run]

    input_file  Path to a text file with one Amazon product ID per line.
                Defaults to d:\\zikprocessor\\data\\blacklist_add.txt
    --dry-run   Show what would change without POSTing.
"""

import sys
import requests

import config
ACCOUNT_ID = config.PY_ACCOUNT_ID
API_KEY = config.PY_API_KEY
DEFAULT_INPUT = "d:\\zikprocessor\\data\\blacklist_add.txt"
BLACKLIST_URL = (
    "https://www.priceyak.com/v0/account/{id}/requests/blacklist".format(id=ACCOUNT_ID)
)


def login(account_id, api_key):
    response = requests.post(
        "https://www.priceyak.com/v0/account/{id}/api_login".format(id=account_id),
        json={"api_key": api_key},
    )
    response.raise_for_status()
    return response.json()["token"]


def read_product_ids(file_path):
    """Read one product id per line, strip blanks/whitespace.

    PriceYak stores/compares product_ids in lowercase, so we normalize to
    lowercase here to keep de-duplication correct and idempotent.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            ids = [line.strip().lower() for line in f]
        return [i for i in ids if i]
    except FileNotFoundError:
        print("Input file not found: {}".format(file_path))
        return []


def get_blacklist(token):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    r = requests.get(BLACKLIST_URL, headers=headers)
    r.raise_for_status()
    data = r.json()
    # Be defensive in case any field is missing.
    return {
        "brand": data.get("brand", []) or [],
        "keyword": data.get("keyword", []) or [],
        "product_id": data.get("product_id", []) or [],
    }


def post_blacklist(token, doc):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    # The web app's HTTP helper sends JSON.stringify(options.data) as the raw body,
    # and it calls apiPostPromise(url, {data: <doc>}). So the body is the doc itself
    # (all blacklist kinds at the top level), NOT wrapped in a "data" key.
    body = {
        "brand": doc["brand"],
        "keyword": doc["keyword"],
        "product_id": doc["product_id"],
        "apply_to_all_accounts": False,
    }
    r = requests.post(BLACKLIST_URL, headers=headers, json=body)
    return r


def main():
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    input_file = args[0] if args else DEFAULT_INPUT

    new_ids = read_product_ids(input_file)
    if not new_ids:
        print("No product IDs to add. Nothing to do.")
        return
    print("Read {} product ID(s) from {}".format(len(new_ids), input_file))

    token = login(ACCOUNT_ID, API_KEY)
    current = get_blacklist(token)
    existing = current["product_id"]
    # Compare case-insensitively: PriceYak lowercases product_ids server-side.
    existing_set = set(e.lower() for e in existing)
    print("Current blacklist has {} product ID(s).".format(len(existing)))

    # Append only IDs not already present, preserving order and de-duping input.
    to_add = []
    seen = set(existing_set)
    for pid in new_ids:
        if pid not in seen:
            to_add.append(pid)
            seen.add(pid)

    if not to_add:
        print("All {} input ID(s) are already blacklisted. Nothing to do.".format(len(new_ids)))
        return

    print("Adding {} new product ID(s):".format(len(to_add)))
    for pid in to_add:
        print("  + {}".format(pid))

    merged = dict(current)
    merged["product_id"] = existing + to_add

    if dry_run:
        print(
            "\n[DRY RUN] Would POST blacklist with {} product ID(s) "
            "({} brand, {} keyword unchanged).".format(
                len(merged["product_id"]), len(merged["brand"]), len(merged["keyword"])
            )
        )
        return

    r = post_blacklist(token, merged)
    print("\nPOST status: {}".format(r.status_code))
    print(r.text)
    if r.ok:
        print(
            "Blacklist saved. product_id count is now {}.".format(
                len(merged["product_id"])
            )
        )
    else:
        print("ERROR: blacklist was not saved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
