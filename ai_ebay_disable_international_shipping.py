"""
Disable international shipping on ALL eBay fulfillment (shipping) policies.

eBay keeps spawning new business policies (named like
"Flat: ShippingMethodStandard free, N business (<id>)") and international
shipping gets added to some of them -- either eBay International Shipping
auto-enrollment, or policy copies that inherit an INTERNATIONAL option with
deterrent pricing. This sweep removes the INTERNATIONAL shipping option from
every fulfillment policy and restricts ship-to to domestic only, then PUTs the
policy back.

It is IDEMPOTENT (only PUTs policies that actually have international enabled),
so it is safe to run on a schedule (e.g. from airotate.bat) and will self-heal
whenever eBay/PriceYak turns international back on.

Uses the eBay Sell Account API with the OAuth user token from ebay_utils.

Usage:
    python ai_ebay_disable_international_shipping.py [--dry-run]
"""

import sys
import requests
import ebay_utils

BASE = "https://api.ebay.com/sell/account/v1/fulfillment_policy"


def _headers():
    tok = ebay_utils.load_credentials()["token"]
    return {
        "Authorization": "Bearer " + tok,
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }


def _has_international(p):
    """True if the policy enables any international shipping."""
    has_intl_option = any(
        o.get("optionType") == "INTERNATIONAL" for o in p.get("shippingOptions", [])
    )
    included = (p.get("shipToLocations") or {}).get("regionIncluded", []) or []
    ships_worldwide = any(r.get("regionName") == "Worldwide" for r in included)
    gsp = p.get("globalShipping") is True
    return has_intl_option or ships_worldwide or gsp


def _make_domestic_only(p):
    """Return a PUT body for p with all international shipping removed."""
    body = dict(p)
    # 1) Keep only DOMESTIC shipping options.
    body["shippingOptions"] = [
        o for o in p.get("shippingOptions", []) if o.get("optionType") != "INTERNATIONAL"
    ]
    # 2) Restrict ship-to to domestic: drop "Worldwide" regionIncluded,
    #    keep regionExcluded (matches the known-good domestic policy).
    stl = dict(p.get("shipToLocations") or {})
    stl.pop("regionIncluded", None)
    body["shipToLocations"] = stl
    # 3) Make sure Global Shipping Program is off.
    body["globalShipping"] = False
    # fulfillmentPolicyId goes in the URL, not the body.
    body.pop("fulfillmentPolicyId", None)
    return body


def main():
    dry = "--dry-run" in sys.argv
    h = _headers()

    r = requests.get(BASE + "?marketplace_id=EBAY_US", headers=h, timeout=60)
    r.raise_for_status()
    policies = r.json().get("fulfillmentPolicies", [])
    print("{} fulfillment policies found.".format(len(policies)))

    changed = 0
    for p in policies:
        pid = p.get("fulfillmentPolicyId")
        name = (p.get("name") or "")[:48]
        if not _has_international(p):
            print("  OK    {}  {}".format(pid, name))
            continue

        print("  INTL  {}  {}  <- disabling international".format(pid, name))
        if dry:
            changed += 1
            continue

        body = _make_domestic_only(p)
        pr = requests.put("{}/{}".format(BASE, pid), headers=h, json=body, timeout=60)
        if pr.status_code in (200, 204):
            print("        -> updated (domestic only)")
            changed += 1
        else:
            print("        -> ERROR {}: {}".format(pr.status_code, pr.text[:400]))

    verb = "Would update" if dry else "Updated"
    print("\n{} {} policy(ies) to domestic-only.".format(verb, changed))


if __name__ == "__main__":
    main()
