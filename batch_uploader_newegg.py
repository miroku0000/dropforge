"""
Newegg batch uploader: drains the Newegg scrape queue and lists the items on
PriceYak with source="newegg".

Mirror of batch_uploader.py -- same PriceYak create_batch endpoint, options and
business-policy profile ids; the only differences are source="newegg" and that
product_ids come from each queued item's data["newegg_item"] (the Newegg item
number) instead of an Amazon ASIN. Uses its own queue (scrape_newegg_batch) so
it never touches the Amazon pipeline.
"""

import requests
import sys
import json
import time
import os
from scrape_newegg_batch import batch_manager

# Make stdout/stderr tolerate Unicode glyphs on the Windows cp1252 console.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# PriceYak configuration
import config
account_id = config.PY_ACCOUNT_ID
api_key = config.PY_API_KEY

SOURCE = "newegg"


def login(account_id, api_key):
    """Login to PriceYak and get auth token."""
    response = requests.post(
        f"https://www.priceyak.com/v0/account/{account_id}/api_login",
        headers={"Content-Type": "application/json"},
        json={"api_key": api_key},
    )
    return response.json()["token"]


def upload_batch_to_priceyak(product_ids, token):
    """Upload a batch of Newegg item numbers to PriceYak."""
    url = f"https://www.priceyak.com:443/v0/account/{account_id}/requests/create_batch"
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.priceyak.com",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": "Bearer " + token,
    }
    json_data = {
        "options": {
            "condition": "new",
            "disable_repricing": 0,
            "include_weight": 0,
            "list_variants": False,
            "needs_review": False,
            "payment_profile_id": "226060214021",
            "return_profile_id": "286754074021",
            "set_destination_tags": True,
            "set_source_tag": False,
            "shipping_profile_id": "280543477021",
            "slowly": False,
        },
        "product_ids": product_ids,
        "source": SOURCE,
    }
    return requests.post(url, headers=headers, json=json_data)


def _product_ids_from_items(items):
    """Pull Newegg item numbers out of queued items (data.newegg_item)."""
    ids = []
    for item in items:
        data = item.get("data") or {}
        pid = data.get("newegg_item")
        if pid:
            ids.append(pid)
    return ids


def monitor_and_upload():
    """Monitor the batch queue and upload when ready."""
    print("Starting Newegg batch uploader monitor...")

    token = login(account_id, api_key)
    print("✓ Logged into PriceYak")

    upload_count = 0
    check_interval = 30
    idle_timeout = 600  # 10 minutes
    last_upload_time = time.time()

    while True:
        try:
            items = batch_manager.get_batch_for_upload()
        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error in queue file: {e}")
            print("Clearing corrupted queue file...")
            qf = os.path.join("..", "data", "newegg_scrape_queue.jsonl")
            if os.path.exists(qf):
                os.rename(qf, qf.replace(".jsonl", f"_corrupted_{int(time.time())}.jsonl"))
                open(qf, "w").close()
            time.sleep(5)
            continue
        except Exception as e:
            print(f"Error getting batch: {e}")
            time.sleep(5)
            continue

        if items:
            product_ids = _product_ids_from_items(items)
            if product_ids:
                print(f"\n🚀 Uploading batch of {len(product_ids)} Newegg items...")
                print(f"Items: {product_ids[:5]}{'...' if len(product_ids) > 5 else ''}")
                try:
                    response = upload_batch_to_priceyak(product_ids, token)
                    if response.status_code == 200:
                        print(f"✓ Successfully uploaded batch {upload_count + 1}")
                        batch_manager.mark_uploaded(items)
                        upload_count += 1
                        last_upload_time = time.time()
                    else:
                        print(f"✗ Upload failed with status {response.status_code}")
                        print(f"Response: {response.text[:300]}")
                        # Leave items unmarked so they retry next loop.
                except Exception as e:
                    print(f"✗ Upload error: {e}")
        else:
            status = batch_manager.get_status()
            if status:
                pending = status.get("items_pending", 0)
                scraped = status.get("items_scraped", 0)
                uploaded = status.get("items_uploaded", 0)
                if pending == 0 and scraped > 0:
                    print(f"\n✅ All items processed! Total: {uploaded}/{scraped} uploaded")
                    break
                idle_time = time.time() - last_upload_time
                if idle_time >= idle_timeout:
                    print(f"\n⏱️ No new uploads for {idle_timeout/60:.0f} minutes. Auto-exiting...")
                    print(f"Final status: {uploaded} items uploaded")
                    break
                remaining_idle = idle_timeout - idle_time
                print(f"⏳ Waiting... Scraped: {scraped}, Uploaded: {uploaded}, Pending: {pending} "
                      f"(Auto-exit in {remaining_idle/60:.1f}min if no uploads)")
            else:
                idle_time = time.time() - last_upload_time
                if idle_time >= idle_timeout:
                    print(f"\n⏱️ No uploads for {idle_timeout/60:.0f} minutes. Auto-exiting...")
                    break
                remaining_idle = idle_timeout - idle_time
                print(f"⏳ Waiting for scraper to start... (Auto-exit in {remaining_idle/60:.1f}min)")

        time.sleep(check_interval)

    print(f"\n🎉 Newegg batch uploading complete! Uploaded {upload_count} batches total.")


def upload_from_file(file_path):
    """Upload Newegg item numbers directly from a file (one per line)."""
    print(f"Uploading from file: {file_path}")
    try:
        with open(file_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            print("No items to upload")
            return
        token = login(account_id, api_key)
        response = upload_batch_to_priceyak(lines, token)
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) > 1:
        upload_from_file(sys.argv[1])
    else:
        monitor_and_upload()


if __name__ == "__main__":
    main()
