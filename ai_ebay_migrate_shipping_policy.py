"""
Migrate ALL active eBay listings onto a single shipping (fulfillment) policy.

Background: PriceYak lists with inline shipping, so eBay auto-spawns many
redundant business policies ("Flat: ShippingMethodStandard free, N business")
and eBay International Shipping adds international to them. Consolidating every
listing onto the one canonical domestic policy (PRICEYAK_SHIPPING_PROFILE,
280543477021) retires the redundant/international ones.

What it does:
  1. Enumerate active listings via GetMyeBaySelling (ItemID + current
     ShippingProfileID).
  2. Skip listings already on the target policy.
  3. ReviseFixedPriceItem the rest, setting only
     SellerProfiles/SellerShippingProfile/ShippingProfileID -> target.

Idempotent (re-running skips already-migrated items) and resumable.

NOTE: Also opt out of "eBay International Shipping" in Seller Hub shipping
preferences -- otherwise eBay keeps re-adding international to policies.

Usage:
    python ai_ebay_migrate_shipping_policy.py [--dry-run] [--limit N]
                                              [--target POLICY_ID]
"""

import sys
import time
import argparse

import ebay_utils

DEFAULT_TARGET = "280543477021"  # PRICEYAK_SHIPPING_PROFILE (domestic only)


def _trading():
    creds = ebay_utils.load_credentials()
    return ebay_utils.Trading(
        appid=creds.get("appid"),
        devid=creds.get("devid"),
        certid=creds.get("certid"),
        token=creds.get("token"),
        config_file=None,
        timeout=60,
    )


def enumerate_active(api):
    """Return list of (item_id, current_shipping_profile_id) for all active listings."""
    out = []
    page = 1
    while True:
        print("[enumerate] active listings page {}...".format(page))
        resp = api.execute(
            "GetMyeBaySelling",
            {
                "ActiveList": {
                    "Include": True,
                    "Pagination": {"EntriesPerPage": 200, "PageNumber": page},
                    "Sort": "TimeLeft",
                },
                "OutputSelector": [
                    "ActiveList.ItemArray.Item.ItemID",
                    "ActiveList.ItemArray.Item.SellerProfiles.SellerShippingProfile.ShippingProfileID",
                    "ActiveList.PaginationResult",
                ],
                "DetailLevel": "ReturnAll",
            },
        ).dict()

        active = resp.get("ActiveList") or {}
        items = (active.get("ItemArray") or {}).get("Item", []) or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            iid = it.get("ItemID")
            sp = (
                ((it.get("SellerProfiles") or {}).get("SellerShippingProfile") or {})
                .get("ShippingProfileID")
            )
            if iid:
                out.append((iid, sp))

        total_pages = int(
            (active.get("PaginationResult") or {}).get("TotalNumberOfPages", 1) or 1
        )
        if page >= total_pages or not items:
            break
        page += 1
    return out


def migrate_item(api, item_id, target):
    """Set the listing's shipping policy to target. Returns (ok, message)."""
    try:
        resp = api.execute(
            "ReviseFixedPriceItem",
            {
                "Item": {
                    "ItemID": item_id,
                    "SellerProfiles": {
                        "SellerShippingProfile": {"ShippingProfileID": target}
                    },
                }
            },
        ).dict()
        ack = resp.get("Ack")
        if ack in ("Success", "Warning"):
            return True, ack
        errs = resp.get("Errors", [])
        if isinstance(errs, dict):
            errs = [errs]
        msg = "; ".join(e.get("ShortMessage", "") for e in errs) or str(ack)
        return False, msg
    except Exception as e:
        return False, str(e)[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max items to revise (0 = all)")
    ap.add_argument("--target", default=DEFAULT_TARGET)
    args = ap.parse_args()
    target = args.target

    api = _trading()
    actives = enumerate_active(api)
    print("\nTotal active listings: {}".format(len(actives)))

    already = [i for i, sp in actives if sp == target]
    todo = [i for i, sp in actives if sp != target]
    print("  already on {}: {}".format(target, len(already)))
    print("  to migrate           : {}".format(len(todo)))

    if args.limit and len(todo) > args.limit:
        print("  (--limit {} -> only migrating first {})".format(args.limit, args.limit))
        todo = todo[: args.limit]

    if args.dry_run:
        print("\n[DRY RUN] Would migrate {} listing(s) to {}.".format(len(todo), target))
        return

    ok = 0
    fail = 0
    refreshed = False
    for n, iid in enumerate(todo, 1):
        success, msg = migrate_item(api, iid, target)
        # The OAuth user token can hard-expire mid-run on a long sweep. Rebuild
        # the client once (load_credentials auto-refreshes an expired token) and
        # retry the item.
        if not success and ("hard expired" in msg or "Auth token" in msg or "Code: 932" in msg):
            if not refreshed:
                print("  [auth] token expired -> refreshing and retrying...")
                api = _trading()
                refreshed = True
                success, msg = migrate_item(api, iid, target)
            # allow another refresh later if it expires again
            if success:
                refreshed = False
        if success:
            ok += 1
            if n % 25 == 0 or n == len(todo):
                print("  [{}/{}] migrated...".format(n, len(todo)))
        else:
            fail += 1
            print("  [{}/{}] {} FAILED: {}".format(n, len(todo), iid, msg))
        time.sleep(0.05)

    print("\nDone. Migrated {} | Failed {} | Skipped {} (already on target).".format(
        ok, fail, len(already)
    ))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
