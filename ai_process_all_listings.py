import os
import glob
import pandas as pd
from datetime import datetime
import argparse

# Configuration
DOWNLOAD_DIR = "C:/Users/mirok/Downloads"
FILE_PATTERN = "eBay-ListingsTrafficReport*.csv"
HEADER_LINE_INDEX = 5  # Line with actual headers (0-indexed)
DAYS_THRESHOLD = 10


def get_latest_file(directory, pattern):
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        raise FileNotFoundError("No matching report files found.")
    return max(files, key=os.path.getmtime)


def clean_item_id(raw_id):
    """Remove =""..."" wrapping from eBay item ID"""
    return str(raw_id).replace('="', "").replace('"', "").strip()


def parse_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except:
        return 0


def process_traffic_report(filepath, max_listings=None):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    headers = [h.strip() for h in lines[HEADER_LINE_INDEX].strip().split(",")]
    if headers[-1] == "":
        headers = headers[:-1]  # remove trailing empty column

    df = pd.read_csv(filepath, skiprows=HEADER_LINE_INDEX + 1, header=None)
    df.columns = headers

    today = datetime.now()
    output_count = 0

    for _, row in df.iterrows():
        if max_listings is not None and output_count >= max_listings:
            break

        item_id = clean_item_id(row.get("eBay item ID", "Unknown"))

        # Parse and check item start date
        try:
            start_date = datetime.strptime(
                str(row["Item Start Date"]).strip(), "%Y-%m-%d"
            )
        except:
            continue

        if (today - start_date).days <= DAYS_THRESHOLD:
            continue  # too recent

        quantity_sold = parse_int(row.get("Quantity sold", 0))
        quantity_available = parse_int(row.get("Quantity available", 0))
        total_views = parse_int(row.get("Total page views", 0))

        if (quantity_sold == 0 and total_views == 0) or (
            quantity_sold == 0 and quantity_available == 0
        ):
            print(f"{item_id}")
            output_count += 1


# Run the script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process eBay traffic report and output item IDs")
    parser.add_argument("--numlistings", type=int, help="Maximum number of listings to output")
    args = parser.parse_args()
    
    latest_file = get_latest_file(DOWNLOAD_DIR, FILE_PATTERN)
    process_traffic_report(latest_file, args.numlistings)
