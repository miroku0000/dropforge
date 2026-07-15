"""
Analyze eBay API errors and check specific items for error details.
"""

import sys
from ebay_error_logger import analyze_error_patterns, get_error_details
import json

def check_specific_item(item_id):
    """Check error details for a specific item"""
    print(f"\nChecking errors for item {item_id}...")
    details = get_error_details(item_id)
    
    if details:
        print(f"\nFound error details for item {item_id}:")
        print("="*60)
        
        if isinstance(details, list):
            for i, error in enumerate(details):
                print(f"\nError {i+1}:")
                print_error_details(error)
        else:
            print_error_details(details)
    else:
        print(f"No error details found for item {item_id}")

def print_error_details(error):
    """Print formatted error details"""
    if isinstance(error, dict):
        print(f"  Timestamp: {error.get('timestamp', 'N/A')}")
        print(f"  Operation: {error.get('operation', 'N/A')}")
        
        if 'error' in error:
            err = error['error']
            print(f"  Error Code: {err.get('code', 'N/A')}")
            print(f"  Error Message: {err.get('message', 'N/A')[:200]}")
            print(f"  Severity: {err.get('severity', 'N/A')}")
        
        if 'attempted_data' in error:
            data = error['attempted_data']
            if data.get('description'):
                desc_metrics = data.get('description_metrics', {})
                print(f"  Description Length: {desc_metrics.get('length', 0)} chars")
                print(f"  Has Images: {desc_metrics.get('has_images', False)}")
                print(f"  Paragraphs: {desc_metrics.get('num_paragraphs', 0)}")
                
                # Show first 500 chars of attempted description
                desc = data['description']
                if desc:
                    print(f"  Description Preview: {desc[:500]}...")
            
            if data.get('title'):
                print(f"  Attempted Title: {data['title']}")
            
            if data.get('specifics_count'):
                print(f"  Item Specifics Count: {data['specifics_count']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "analyze":
            # Run general analysis
            analyze_error_patterns()
        else:
            # Check specific item
            item_id = sys.argv[1]
            check_specific_item(item_id)
            
            # Also run general analysis
            print("\n" + "="*60)
            print("GENERAL ERROR ANALYSIS")
            print("="*60)
            analyze_error_patterns()
    else:
        # Default: run general analysis
        analyze_error_patterns()
        print("\nUsage:")
        print("  python analyze_ebay_errors.py           # General analysis")
        print("  python analyze_ebay_errors.py 123456789 # Check specific item")
        print("  python analyze_ebay_errors.py analyze   # Full analysis")