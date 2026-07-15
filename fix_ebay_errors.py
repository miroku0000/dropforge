"""
Enhanced error fixing script for eBay operations.
Implements retry logic, better error handling, and validation.
"""

import time
import traceback
from typing import Dict, Optional, Any
import os
import sys

# Add retry decorator
def retry_with_backoff(max_attempts=3, initial_delay=1, backoff_factor=2):
    """Decorator to retry functions with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"  Attempt {attempt + 1} failed: {str(e)[:100]}")
                        print(f"  Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        print(f"  All {max_attempts} attempts failed")
            
            raise last_exception
        return wrapper
    return decorator

# Validation functions
def validate_title(title: str) -> tuple[bool, str]:
    """Validate eBay title requirements"""
    if not title:
        return False, "Title is empty"
    
    if len(title) > 80:
        return False, f"Title too long ({len(title)} > 80 chars)"
    
    # Check for invalid characters
    invalid_chars = ['<', '>', '&lt;', '&gt;', '&amp;']
    for char in invalid_chars:
        if char in title:
            return False, f"Title contains invalid character: {char}"
    
    return True, "OK"

def validate_description(description: str) -> tuple[bool, str]:
    """Validate eBay description requirements"""
    if not description:
        return False, "Description is empty"
    
    if len(description) > 500000:
        return False, f"Description too long ({len(description)} > 500,000 chars)"
    
    # Check for basic HTML validity
    if description.count('<') != description.count('>'):
        return False, "Unbalanced HTML tags"
    
    return True, "OK"

def validate_specifics(specifics: Dict[str, str]) -> tuple[bool, str]:
    """Validate eBay item specifics requirements"""
    if not specifics:
        return True, "OK"  # Empty specifics are allowed
    
    if len(specifics) > 45:
        return False, f"Too many specifics ({len(specifics)} > 45)"
    
    for key, value in specifics.items():
        if len(str(value)) > 65:
            return False, f"Specific value too long: {key}={value[:20]}... ({len(value)} > 65)"
    
    return True, "OK"

# Enhanced update functions with retry logic
@retry_with_backoff(max_attempts=3, initial_delay=2)
def safe_update_title(item_id: str, title: str) -> bool:
    """Update title with validation and retry logic"""
    # Validate first
    valid, message = validate_title(title)
    if not valid:
        print(f"  Title validation failed: {message}")
        return False
    
    from ebay_utils import update_item_title
    return update_item_title(item_id, title)

@retry_with_backoff(max_attempts=3, initial_delay=2)
def safe_update_description(item_id: str, description: str) -> bool:
    """Update description with validation and retry logic"""
    # Validate first
    valid, message = validate_description(description)
    if not valid:
        print(f"  Description validation failed: {message}")
        return False
    
    from ebay_utils import update_item_description
    return update_item_description(item_id, description)

@retry_with_backoff(max_attempts=2, initial_delay=1)
def safe_get_item_specifics(item_id: str) -> Optional[Dict]:
    """Get item specifics with retry logic"""
    from ebay_utils import get_item_specifics
    return get_item_specifics(item_id)

def process_item_with_error_handling(item_id: str, min_title_rating: int = 8, min_desc_rating: int = 8) -> Dict[str, Any]:
    """Process a single item with comprehensive error handling"""
    result = {
        'item_id': item_id,
        'title_updated': False,
        'description_updated': False,
        'specifics_fetched': False,
        'errors': []
    }
    
    print(f"\nProcessing item {item_id}...")
    
    # 1. Fetch item specifics
    try:
        print("  Fetching item specifics...")
        specs = safe_get_item_specifics(item_id)
        if specs:
            result['specifics_fetched'] = True
            result['specifics_count'] = len(specs)
            print(f"    Success: {len(specs)} specifics found")
        else:
            print("    No specifics found")
    except Exception as e:
        error_msg = f"Specifics fetch error: {str(e)[:100]}"
        result['errors'].append(error_msg)
        print(f"    Failed: {error_msg}")
    
    # 2. Process title if needed
    try:
        from ebay_utils import get_item_title_from_ebay, generate_better_title_if_needed
        
        print("  Processing title...")
        current_title = get_item_title_from_ebay(item_id)
        
        if current_title:
            # Check if title needs improvement
            better_title = generate_better_title_if_needed(
                current_title, 
                min_rating=min_title_rating
            )
            
            if better_title and better_title != current_title:
                print(f"    Current: {current_title[:50]}...")
                print(f"    Better:  {better_title[:50]}...")
                
                # Validate and update
                if safe_update_title(item_id, better_title):
                    result['title_updated'] = True
                    print("    Title updated successfully")
                else:
                    result['errors'].append("Title update failed after retries")
            else:
                print("    Title is already good")
    except Exception as e:
        error_msg = f"Title processing error: {str(e)[:100]}"
        result['errors'].append(error_msg)
        print(f"    Failed: {error_msg}")
    
    # 3. Process description if needed
    try:
        from ebay_utils import get_item_description_from_ebay, generate_description_if_needed
        
        print("  Processing description...")
        current_desc = get_item_description_from_ebay(item_id)
        
        if current_desc:
            # Check if description needs improvement
            better_desc = generate_description_if_needed(
                item_id,
                current_desc,
                min_rating=min_desc_rating
            )
            
            if better_desc and better_desc != current_desc:
                print(f"    Current length: {len(current_desc)} chars")
                print(f"    Better length:  {len(better_desc)} chars")
                
                # Validate and update
                if safe_update_description(item_id, better_desc):
                    result['description_updated'] = True
                    print("    Description updated successfully")
                else:
                    result['errors'].append("Description update failed after retries")
            else:
                print("    Description is already good")
    except Exception as e:
        error_msg = f"Description processing error: {str(e)[:100]}"
        result['errors'].append(error_msg)
        print(f"    Failed: {error_msg}")
    
    # Summary
    if result['errors']:
        print(f"  Completed with {len(result['errors'])} errors")
    else:
        print("  Completed successfully")
    
    return result

def fix_typo_in_failure_reasons():
    """Fix the typo in failure reasons (optimisation -> optimization)"""
    import pandas as pd
    
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    if not os.path.exists(stats_file):
        print("Stats file not found")
        return
    
    print("Fixing typo in failure reasons...")
    df = pd.read_csv(stats_file, low_memory=False)
    
    # Count before
    count_before = (df['FailureReason'] == 'Title optimisation error').sum()
    
    # Fix the typo
    df.loc[df['FailureReason'] == 'Title optimisation error', 'FailureReason'] = 'Title optimization error'
    
    # Save back
    df.to_csv(stats_file, index=False)
    print(f"Fixed {count_before} instances of 'Title optimisation error' -> 'Title optimization error'")

def test_single_item(item_id: str):
    """Test processing a single item with all error handling"""
    print("="*60)
    print(f"TESTING ITEM {item_id}")
    print("="*60)
    
    result = process_item_with_error_handling(item_id)
    
    print("\n" + "-"*40)
    print("RESULT SUMMARY:")
    print("-"*40)
    print(f"Item ID: {result['item_id']}")
    print(f"Title updated: {result['title_updated']}")
    print(f"Description updated: {result['description_updated']}")
    print(f"Specifics fetched: {result['specifics_fetched']}")
    
    if result.get('specifics_count'):
        print(f"Specifics count: {result['specifics_count']}")
    
    if result['errors']:
        print(f"\nErrors ({len(result['errors'])}):")
        for error in result['errors']:
            print(f"  - {error}")
    else:
        print("\nNo errors!")
    
    print("="*60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "fix-typo":
            fix_typo_in_failure_reasons()
        else:
            # Test with a specific item
            test_single_item(sys.argv[1])
    else:
        print("Usage:")
        print("  python fix_ebay_errors.py <item_id>  # Test single item")
        print("  python fix_ebay_errors.py fix-typo   # Fix typo in stats file")
        print("\nExample:")
        print("  python fix_ebay_errors.py 226873540779")