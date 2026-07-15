import os
from ebay_utils import load_credentials  # Import from your existing utils
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError


def unlist_ebay_items(item_ids, ending_reason="NotAvailable"):
    """
    Unlists eBay items using the Trading API's EndItem call.

    Args:
        item_ids (list): List of eBay item IDs to unlist
        ending_reason (str): Reason for ending the listing (default: 'NotAvailable')

    Returns:
        dict: Results for each item ID with status and messages
    """
    creds = load_credentials()
    api = Trading(
        appid=creds["appid"],
        devid=creds["devid"],
        certid=creds["certid"],
        token=creds["token"],
        config_file=None,
        timeout=60,
    )

    results = {}
    for item_id in item_ids:
        try:
            response = api.execute(
                "EndItem", {"ItemID": item_id, "EndingReason": ending_reason}
            )
            ack = response.dict().get("Ack", "Failure")
            results[item_id] = {
                "status": "Success" if ack in ["Success", "Warning"] else "Failed",
                "message": response.dict(),
            }
        except ConnectionError as e:
            results[item_id] = {
                "status": "Failed",
                "message": f"ConnectionError: {e.response.dict() if e.response else str(e)}",
            }
        except Exception as e:
            results[item_id] = {
                "status": "Failed",
                "message": f"General error: {str(e)}",
            }
    return results


def read_item_ids_from_file(file_path):
    """
    Reads eBay item IDs from a text file

    Args:
        file_path (str): Path to input file

    Returns:
        list: Item IDs found in file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    try:
        # Read item IDs from file
        file_path = os.path.join("..", "data", "kill.txt")
        item_ids = read_item_ids_from_file(file_path)

        if not item_ids:
            print("No item IDs found in file")
        else:
            # Unlist items and print results
            results = unlist_ebay_items(item_ids)
            for item_id, result in results.items():
                status = result["status"]
                print(f"Item {item_id}: {status} - {result['message']}")
    except Exception as e:
        print(f"Script execution failed: {str(e)}")
