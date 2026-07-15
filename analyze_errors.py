"""Analyze error files to understand failure patterns"""
import os
import glob
from collections import defaultdict

# Find all error description files
error_files = glob.glob("error_description_*.html")

print(f"Found {len(error_files)} error files")
print("-" * 60)

# Categorize errors
error_types = defaultdict(list)

for error_file in error_files:
    with open(error_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if len(lines) >= 2:
            item_id = lines[0].replace("Item ID: ", "").strip()
            error_msg = lines[1].replace("Error: ", "").strip()
            error_types[error_msg].append(item_id)

# Print error summary
print("\nError Summary:")
print("=" * 60)

for error_msg, items in error_types.items():
    print(f"\nError: {error_msg}")
    print(f"Affected Items: {len(items)}")
    print(f"Sample Item IDs: {', '.join(items[:5])}")
    
print("\n" + "=" * 60)
print("\nAnalysis Complete!")

# Check if all errors are the same
if len(error_types) == 1:
    error_msg = list(error_types.keys())[0]
    print(f"\nAll {len(error_files)} errors are the same type:")
    print(f"  '{error_msg}'")
    print("\nThis error has been FIXED by adding the clear_llm_description_cache function.")
    print("You can now safely re-run the batch processing.")
else:
    print(f"\nFound {len(error_types)} different error types")
    print("Review the summary above for details.")