"""
eBay monthly selling-limit headroom via GetMyeBaySelling, authenticated with the
OAuth token (X-EBAY-API-IAF-TOKEN) that airotate already refreshes -- the legacy
Auth'n'Auth token in credentials.txt is expired.

Returns (quantity_remaining, amount_remaining) = how many more items / how much
$ value you can list THIS calendar month.
"""

import requests
import xml.etree.ElementTree as ET

import ebay_utils

ENDPOINT = "https://api.ebay.com/ws/api.dll"
NS = {"e": "urn:ebay:apis:eBLBaseComponents"}
_BODY = """<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <ErrorLanguage>en_US</ErrorLanguage>
  <DetailLevel>ReturnSummary</DetailLevel>
  <SellingSummary><Include>true</Include></SellingSummary>
</GetMyeBaySellingRequest>"""


def get_limits():
    """Return (quantity_remaining:int, amount_remaining:float). Raises on failure."""
    tok = ebay_utils.load_credentials()["token"]
    headers = {
        "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
        "X-EBAY-API-CALL-NAME": "GetMyeBaySelling",
        "X-EBAY-API-SITEID": "0",
        "Content-Type": "text/xml",
        "X-EBAY-API-IAF-TOKEN": tok,
    }
    r = requests.post(ENDPOINT, headers=headers, data=_BODY, timeout=40)
    r.raise_for_status()
    summ = ET.fromstring(r.text).find(".//e:Summary", NS)
    if summ is None:
        raise RuntimeError("no <Summary> in GetMyeBaySelling response: " + r.text[:300])
    q = summ.find("e:QuantityLimitRemaining", NS)
    a = summ.find("e:AmountLimitRemaining", NS)
    return int(q.text), float(a.text)


if __name__ == "__main__":
    q, a = get_limits()
    print(f"eBay monthly headroom: {q} items, ${a:,.2f}")
