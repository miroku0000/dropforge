"""
Combined fixes for eBay API issues - handles both retry logic and XML entity escaping.
This replaces separate patches to avoid conflicts.
"""

import time
import html
import re
from functools import wraps
from typing import Optional, Dict, Any

# ================== RETRY LOGIC ==================

def retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,)):
    """Decorator that retries a function with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    error_msg = str(e)
                    
                    # Don't retry for certain permanent errors
                    if any(msg in error_msg.lower() for msg in [
                        'invalid item', 'item cannot be found', 'auth token is invalid',
                        'unsupported api call', 'invalid category', 'auction ended'
                    ]):
                        raise e
                    
                    if attempt < max_retries - 1:
                        print(f"  [RETRY] Attempt {attempt + 1}/{max_retries} after {delay}s due to: {error_msg[:100]}")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        raise e
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

# ================== XML ENTITY ESCAPING ==================

def escape_xml_entities(text: str) -> str:
    """Properly escape text for XML transmission to eBay API."""
    if not text:
        return text
    
    # First, unescape any existing HTML entities to get raw characters
    text = html.unescape(text)
    
    # Now escape for XML in the correct order (& must be first!)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    # Remove control characters that XML doesn't like
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    # Remove any stray/incomplete entity references
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)
    
    return text

def validate_and_fix_title(title: str) -> str:
    """Validate and fix title to meet eBay requirements with proper XML escaping."""
    if not title:
        raise ValueError("Title is empty")
    
    # Apply XML entity escaping
    title = escape_xml_entities(title)
    
    # Remove extra whitespace
    title = ' '.join(title.split())
    
    # Truncate if too long (eBay limit is 80 chars)
    if len(title) > 80:
        title = title[:77] + "..."
    
    return title.strip()

def validate_and_fix_description(description: str) -> str:
    """Validate and fix description with proper handling for HTML within XML."""
    if not description:
        raise ValueError("Description is empty")
    
    # Check length (eBay limit is 500,000 chars)
    if len(description) > 500000:
        description = description[:499900] + "...</p>"
    
    # For descriptions with HTML, we need special handling
    # Fix broken ampersands in the HTML content
    pattern = r'&(?!(?:[a-zA-Z][a-zA-Z0-9]{0,10}|#\d{1,5}|#x[0-9a-fA-F]{1,4});)'
    description = re.sub(pattern, '&amp;', description)
    
    # Remove control characters
    description = ''.join(char for char in description if ord(char) >= 32 or char in '\n\r\t')
    
    return description

# ================== COMBINED PATCH APPLICATION ==================

def apply_combined_patches():
    """Apply all fixes to ebay_utils module in one go to avoid conflicts."""
    
    # Apply LLM timeout fixes first
    # DISABLED: To simplify debugging - uncomment if needed
    # try:
    #     from llm_timeout_fixes import patch_ebay_utils_with_timeouts
    #     patch_ebay_utils_with_timeouts()
    #     print("[INFO] Applied LLM timeout patches")
    # except ImportError:
    #     print("[WARNING] LLM timeout fixes not available")
    
    # Apply required specifics validation  
    # DISABLED: This imports ebay_category_metadata which tries to fetch from non-existent GitHub repo
    # try:
    #     from required_specifics_validator import add_required_specifics_validation
    #     add_required_specifics_validation()
    #     print("[INFO] Applied specifics validation patches")
    # except ImportError:
    #     print("[WARNING] Specifics validation not available")
    
    # Apply GitHub category specifics integration
    # DISABLED: The referenced GitHub repo 'open-ecommerce/ebay-metadata' doesn't exist
    # try:
    #     from github_category_specifics import patch_ebay_utils_with_github_specifics
    #     patch_ebay_utils_with_github_specifics()
    #     print("[INFO] Applied GitHub category specifics integration")
    # except ImportError:
    #     print("[WARNING] GitHub specifics integration not available")
    try:
        import ebay_utils
        
        # Store original functions ONCE
        if not hasattr(ebay_utils, '_originals_stored'):
            ebay_utils._original_update_title_combined = getattr(ebay_utils, 'update_item_title', None)
            ebay_utils._original_update_desc_combined = getattr(ebay_utils, 'update_item_description', None)
            ebay_utils._original_get_specs_combined = getattr(ebay_utils, 'get_item_specifics', None)
            ebay_utils._originals_stored = True
            print("[INFO] Stored original functions")
        
        # Create wrapped version with BOTH retry logic AND XML fixes
        @retry_with_backoff(max_retries=3, initial_delay=2, backoff_factor=2)
        def wrapped_update_title_with_retry(item_id: str, title: str, is_fixed_price: bool = True) -> bool:
            """Update title with retry logic and XML escaping."""
            try:
                # Apply XML entity fixes
                fixed_title = validate_and_fix_title(title)
                print(f"  [FIX] Title escaped for XML: '{title[:30]}...' -> '{fixed_title[:30]}...'")
                
                # Call the original function (which already has retry logic in ebay_utils.py)
                if ebay_utils._original_update_title_combined:
                    # The original already has its own validation, but our XML escaping is better
                    # So we'll temporarily bypass the original's validation
                    return ebay_utils._original_update_title_combined(item_id, fixed_title, is_fixed_price)
                else:
                    print("[ERROR] Original update_title not found")
                    return False
            except Exception as e:
                print(f"[ERROR] Title update failed: {e}")
                raise  # Let retry decorator handle it
        
        @retry_with_backoff(max_retries=3, initial_delay=2, backoff_factor=2)  
        def wrapped_update_description_with_retry(item_id: str, description: str, is_fixed_price: bool = True) -> bool:
            """Update description with retry logic and XML fixes."""
            try:
                # Apply description fixes
                fixed_desc = validate_and_fix_description(description)
                
                # Call original with is_fixed_price parameter
                if ebay_utils._original_update_desc_combined:
                    # The new update_item_description function accepts is_fixed_price
                    return ebay_utils._original_update_desc_combined(item_id, fixed_desc, is_fixed_price)
                else:
                    print("[ERROR] Original update_description not found")
                    return False
            except Exception as e:
                print(f"[ERROR] Description update failed: {e}")
                raise
        
        @retry_with_backoff(max_retries=2, initial_delay=1, backoff_factor=2)
        def wrapped_get_specifics_with_retry(item_id: str) -> Optional[Dict]:
            """Get specifics with retry logic."""
            try:
                if ebay_utils._original_get_specs_combined:
                    return ebay_utils._original_get_specs_combined(item_id)
                else:
                    print("[ERROR] Original get_specifics not found")
                    return {}
            except Exception as e:
                print(f"[ERROR] Get specifics failed: {e}")
                raise
        
        # Apply all patches at once
        ebay_utils.update_item_title = wrapped_update_title_with_retry
        ebay_utils.update_item_description = wrapped_update_description_with_retry
        ebay_utils.get_item_specifics = wrapped_get_specifics_with_retry
        
        print("[INFO] Applied combined patches (retry + XML fixes) to ebay_utils")
        return True
        
    except Exception as e:
        print(f"[WARNING] Could not apply combined patches: {e}")
        return False

if __name__ == "__main__":
    # Test the fixes
    print("Testing combined fixes...")
    print("="*60)
    
    # Test XML escaping
    test_cases = [
        "Books & Magazines",
        "Items < $50 & > $20",
        "Tom's \"Special\" Item",
    ]
    
    print("Title fixing tests:")
    for original in test_cases:
        try:
            fixed = validate_and_fix_title(original)
            print(f"  OK: '{original}' -> '{fixed}'")
        except Exception as e:
            print(f"  ERROR: '{original}' failed: {e}")
    
    print("\nApplying patches...")
    success = apply_combined_patches()
    print(f"Patches applied: {success}")
    
    print("="*60)