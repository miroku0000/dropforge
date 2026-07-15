"""
Script B: For each tracked return where the case is open on PriceYak but the
label hasn't been uploaded to eBay yet, navigate to the PriceYak order page via
CDP, extract the support-supplied return-label URL, download the PDF, and
upload it to the eBay return case as a UPS return shipping label.

Reads/writes state in data/return_state.json (populated by Script A,
ai_priceyak_start_returns.py).

Usage:
    python ai_ebay_upload_return_labels.py [--dry-run]
"""

import os
import re
import sys
import json
import time
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright
from playwright_browser import launch_ebay_browser

import ebay_utils

import config
ACCOUNT_ID = config.PY_ACCOUNT_ID
DATA_DIR = os.path.join("d:\\", "zikprocessor", "data")
STATE_FILE = os.path.join(DATA_DIR, "return_state.json")
LABELS_DIR = os.path.join(DATA_DIR, "return_labels")

POST_ORDER_BASE = "https://api.ebay.com/post-order/v2"

# The PriceYak page renders the support reply as plain text inside the order
# detail. Extract the presigned S3 PDF URL and the eBay Return Id from it.
LABEL_URL_RE = re.compile(r"https?://coyotedownloads\.s3\.amazonaws\.com/\S+?\.pdf[^\s]*")
EBAY_RETURN_ID_RE = re.compile(r"eBay\s*US\s*Return\s*Id\s*[:\s]+(\d{8,12})", re.I)


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=1)


# ----------------------------------------------------------------------------
# Extract from PriceYak order page via CDP
# ----------------------------------------------------------------------------
def extract_label_from_priceyak(page, py_order_id):
    """Return (label_url, ebay_return_id_seen_on_page) or (None, None)."""
    url = f"https://www.priceyak.com/stores/{ACCOUNT_ID}/orders/{py_order_id}"
    page.goto(url, wait_until="load", timeout=60000)
    # Order detail is rendered client-side; give it a moment + scroll for lazy bits.
    time.sleep(5)
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass
    time.sleep(2)
    try:
        body = page.locator("body").inner_text(timeout=8000)
    except Exception:
        body = ""
    m = LABEL_URL_RE.search(body)
    rid_m = EBAY_RETURN_ID_RE.search(body)
    return (m.group(0) if m else None, rid_m.group(1) if rid_m else None)


# ----------------------------------------------------------------------------
# Download PDF (the URL is presigned, no auth needed)
# ----------------------------------------------------------------------------
def download_pdf(url, dest):
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(64 * 1024):
            f.write(chunk)
    sz = os.path.getsize(dest)
    head = open(dest, "rb").read(8)
    if not head.startswith(b"%PDF"):
        raise RuntimeError(f"download is not a PDF (first 8 bytes: {head!r})")
    return sz


# ----------------------------------------------------------------------------
# Upload to eBay Post-Order API
#
# Endpoints (eBay Post-Order Return API):
#   POST /post-order/v2/return/{returnId}/file/upload   (multipart, returns fileId)
#   POST /post-order/v2/return/{returnId}/decide        (provide-label decision)
#
# The exact body shape for `decide` may need adjustment after the first real
# run -- the call below uses the standard PROVIDE_LABEL decision with UPS as
# the carrier. If eBay returns a schema error, the error text will name the
# missing/unknown fields and we'll iterate.
# ----------------------------------------------------------------------------
def ebay_upload_label_to_return(return_id, pdf_path):
    tok = ebay_utils.load_credentials()["token"]
    auth = {"Authorization": "TOKEN " + tok, "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}

    # 1) Upload the file (multipart). Let `requests` set the multipart boundary.
    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"fileType": "RETURN_LABEL"}
        r1 = requests.post(
            f"{POST_ORDER_BASE}/return/{return_id}/file/upload",
            headers=auth,
            files=files,
            data=data,
            timeout=120,
        )
    if not r1.ok:
        return False, f"file/upload {r1.status_code}: {r1.text[:400]}"
    try:
        up = r1.json()
    except Exception:
        return False, f"file/upload non-JSON response: {r1.text[:400]}"
    file_id = up.get("fileId") or up.get("id") or (up.get("fileReferenceId"))
    if not file_id:
        return False, f"file/upload returned no fileId: {up}"

    # 2) Decide -> PROVIDE_LABEL with UPS as carrier.
    decide_body = {
        "decision": "PROVIDE_LABEL",
        "labelDetails": {
            "shippingCarrier": "UPS",
            "fileId": file_id,
        },
    }
    h_json = dict(auth)
    h_json["Content-Type"] = "application/json"
    h_json["Accept"] = "application/json"
    r2 = requests.post(
        f"{POST_ORDER_BASE}/return/{return_id}/decide",
        headers=h_json,
        json=decide_body,
        timeout=120,
    )
    if not r2.ok:
        return False, f"decide {r2.status_code}: {r2.text[:400]} | file_id={file_id}"
    return True, f"uploaded (fileId={file_id})"


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    dry = "--dry-run" in sys.argv
    os.makedirs(LABELS_DIR, exist_ok=True)
    state = load_state()

    # Externally-sourced orders have no PriceYak order behind them, so there is
    # no PriceYak label to fetch -- never touch those here. Script A flags them
    # with external_order/needs_manual_label.
    external = [r for r in state.values() if r.get("external_order")]
    if external:
        print(f"Skipping {len(external)} external order(s) (manual label needed): "
              + ", ".join(str(r.get("ebay_return_id")) for r in external))

    pending = [
        rec for rec in state.values()
        if rec.get("case_opened")
        and not rec.get("label_uploaded")
        and not rec.get("external_order")
    ]
    print(f"Returns to look for labels on: {len(pending)}")
    if not pending:
        return

    with sync_playwright() as p:
        context = launch_ebay_browser(p)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for rec in pending:
                py_oid = rec.get("priceyak_order_id")
                ebay_rid = rec.get("ebay_return_id")
                if not (py_oid and ebay_rid):
                    print(f"  [skip] state missing priceyak_order_id or ebay_return_id: {rec}")
                    continue
                print(f"\n=== eBay return {ebay_rid}  pyak {py_oid} ===")

                try:
                    label_url, seen_rid = extract_label_from_priceyak(page, py_oid)
                except Exception as e:
                    print(f"  page load/extract failed: {e}")
                    continue

                if not label_url:
                    print(f"  label not on PriceYak page yet (support probably hasn't replied)")
                    continue
                if seen_rid and seen_rid != ebay_rid:
                    print(f"  NOTE: page shows eBay return id={seen_rid}, state has {ebay_rid}; trusting state.")

                print(f"  label URL: {label_url[:110]}...")

                pdf_path = os.path.join(LABELS_DIR, f"{ebay_rid}.pdf")
                if dry:
                    print(f"  [DRY RUN] would download to {pdf_path} and upload to eBay")
                    continue

                try:
                    sz = download_pdf(label_url, pdf_path)
                    print(f"  downloaded {sz} bytes -> {pdf_path}")
                except Exception as e:
                    print(f"  download failed: {e}")
                    rec["last_download_error"] = str(e)[:200]
                    continue

                ok, msg = ebay_upload_label_to_return(ebay_rid, pdf_path)
                print(f"  eBay upload -> ok={ok}  msg={msg}")
                if ok:
                    rec["label_uploaded"] = True
                    rec["label_url"] = label_url
                    rec["label_pdf"] = pdf_path
                    rec["uploaded_at"] = datetime.now().isoformat(timespec="seconds")
                else:
                    rec["last_upload_error"] = msg
                    rec["last_upload_attempt"] = datetime.now().isoformat(timespec="seconds")
        finally:
            context.close()

    if not dry:
        save_state(state)
    print("\nDone.")


if __name__ == "__main__":
    main()
