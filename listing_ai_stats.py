import csv
import os
from datetime import datetime
import pandas as pd

STATS_FILE = os.path.join("..", "data", "ai_listing_stats.csv")
FIELDNAMES = [
    "ItemID",
    "Timestamp",
    "TitleFromCache",
    "DescriptionFromCache",
    "OriginalTitleRating",
    "ImprovedTitleRating",
    "OriginalDescriptionRating",
    "ImprovedDescriptionRating",
    "TitleImproved",
    "DescriptionImproved",
    "FailureReason",
]


def log_entry(data: dict):
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    write_header = not os.path.exists(STATS_FILE)
    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(data)


def summarize_ai_stats(file=STATS_FILE):
    if not os.path.exists(file):
        print("No stats file found.")
        return

    df = pd.read_csv(file)
    print(f"Total entries: {len(df)}")

    def safe_mean(col):
        return df[col].dropna().astype(float).mean()

    print(f"Average Original Title Rating: {safe_mean('OriginalTitleRating'):.2f}")
    print(f"Average Improved Title Rating: {safe_mean('ImprovedTitleRating'):.2f}")
    print(
        f"Average Original Description Rating: {safe_mean('OriginalDescriptionRating'):.2f}"
    )
    print(
        f"Average Improved Description Rating: {safe_mean('ImprovedDescriptionRating'):.2f}"
    )
    print(f"Titles Improved: {df['TitleImproved'].sum()}")
    print(f"Descriptions Improved: {df['DescriptionImproved'].sum()}")
    print("Top 5 failure reasons:")
    print(df["FailureReason"].value_counts().head(5))
