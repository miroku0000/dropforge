"""
Patches for ebay_utils.py to fix common errors with retry logic and validation.
This module adds wrapper functions with error handling.
"""

import time
import traceback
from functools import wraps
from typing import Optional, Dict, Any
import re

# Retry decorator with exponential backoff
def retry_with_backoff(max_retries=3, initial_delay=1, backoff_factor=2, exceptions=(Exception,)):
    """
    Decorator that retries a function with exponential backoff.
    """
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
                        'unsupported api call', 'invalid category'
                    ]):
                        raise e
                    
                    if attempt < max_retries - 1:
                        print(f"  Retry {attempt + 1}/{max_retries} after {delay}s due to: {error_msg[:100]}")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        raise e
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

def validate_and_fix_title(title: str) -> str:
    """
    Validate and fix title to meet eBay requirements.
    Returns fixed title or raises ValueError if unfixable.
    """
    if not title:
        raise ValueError("Title is empty")
    
    # Remove extra whitespace
    title = ' '.join(title.split())
    
    # Truncate if too long (eBay limit is 80 chars)
    if len(title) > 80:
        # Try to truncate at a word boundary
        title = title[:77] + "..."
        # Find last complete word
        last_space = title.rfind(' ', 0, 77)
        if last_space > 40:  # Only use word boundary if we keep reasonable length
            title = title[:last_space] + "..."
    
    # Remove invalid characters
    invalid_chars = {
        '<': '',
        '>': '',
        '&lt;': '',
        '&gt;': '',
        '&amp;': '&',
        '\n': ' ',
        '\r': ' ',
        '\t': ' '
    }
    
    for char, replacement in invalid_chars.items():
        title = title.replace(char, replacement)
    
    # Remove multiple spaces again after replacements
    title = ' '.join(title.split())
    
    return title.strip()

def validate_and_fix_description(description: str) -> str:
    """
    Validate and fix description to meet eBay requirements.
    Returns fixed description or raises ValueError if unfixable.
    """
    if not description:
        raise ValueError("Description is empty")
    
    # Check length (eBay limit is 500,000 chars)
    if len(description) > 500000:
        # Truncate description, keeping HTML valid
        description = description[:499900]
        # Try to close any open tags
        description += "...</p>"
    
    # Fix common HTML issues
    description = fix_html_issues(description)
    
    # Remove null characters and other control characters
    description = ''.join(char for char in description if ord(char) >= 32 or char in '\n\r\t')
    
    return description

def fix_html_issues(html: str) -> str:
    """Fix common HTML issues that cause eBay API errors."""
    
    # Balance HTML tags
    html = balance_html_tags(html)
    
    # Fix unclosed tags
    html = fix_unclosed_tags(html)
    
    # Remove script and style tags (eBay doesn't allow them)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Fix broken image tags
    html = re.sub(r'<img([^>]*)(?<!/)>', r'<img\1/>', html)
    
    # Remove javascript: links
    html = re.sub(r'href\s*=\s*["\']?javascript:[^"\'>\s]*["\']?', '', html, flags=re.IGNORECASE)
    
    return html

def balance_html_tags(html: str) -> str:
    """Balance opening and closing HTML tags."""
    # Count common tags
    tags_to_check = ['p', 'div', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th']
    
    for tag in tags_to_check:
        open_count = len(re.findall(f'<{tag}[^>]*>', html, re.IGNORECASE))
        close_count = len(re.findall(f'</{tag}>', html, re.IGNORECASE))
        
        # Add missing closing tags
        if open_count > close_count:
            for _ in range(open_count - close_count):
                html += f'</{tag}>'
    
    return html

def fix_unclosed_tags(html: str) -> str:
    """Fix unclosed self-closing tags."""
    # Fix br tags
    html = re.sub(r'<br(?![^>]*/)([^>]*)>', r'<br\1/>', html)
    # Fix hr tags
    html = re.sub(r'<hr(?![^>]*/)([^>]*)>', r'<hr\1/>', html)
    # Fix input tags
    html = re.sub(r'<input(?![^>]*/)([^>]*)>', r'<input\1/>', html)
    
    return html

def validate_item_specifics(specifics: Dict[str, str]) -> Dict[str, str]:
    """
    Validate and fix item specifics to meet eBay requirements.
    Returns fixed specifics dictionary.
    """
    if not specifics:
        return {}
    
    fixed_specifics = {}
    
    # eBay limits: max 45 specifics, max 65 chars per value
    for key, value in list(specifics.items())[:45]:  # Limit to 45 specifics
        # Clean the key
        key = str(key).strip()[:50]  # Limit key length
        
        # Clean the value
        value = str(value).strip()
        if len(value) > 65:
            value = value[:62] + "..."  # Truncate with ellipsis
        
        # Remove invalid characters
        value = value.replace('<', '').replace('>', '')
        
        if key and value:  # Only add non-empty pairs
            fixed_specifics[key] = value
    
    return fixed_specifics

# Patched version of update functions with retry logic
@retry_with_backoff(max_retries=3, initial_delay=2, backoff_factor=2)
def safe_update_item_title(api, item_id: str, title: str) -> bool:
    """
    Update item title with validation and retry logic.
    """
    try:
        # Validate and fix title
        fixed_title = validate_and_fix_title(title)
        
        # Update via eBay API
        request = {
            'Item': {
                'ItemID': str(item_id),
                'Title': fixed_title
            }
        }
        
        response = api.execute('ReviseItem', request)
        
        if response.reply.Ack in ['Success', 'Warning']:
            print(f"    ✓ Title updated successfully for item {item_id}")
            return True
        else:
            print(f"    ✗ Title update failed: {response.reply.Ack}")
            return False
            
    except Exception as e:
        print(f"    ✗ Title update error: {str(e)[:100]}")
        raise

@retry_with_backoff(max_retries=3, initial_delay=2, backoff_factor=2)
def safe_update_item_description(api, item_id: str, description: str) -> bool:
    """
    Update item description with validation and retry logic.
    """
    try:
        # Validate and fix description
        fixed_description = validate_and_fix_description(description)
        
        # Update via eBay API
        request = {
            'Item': {
                'ItemID': str(item_id),
                'Description': fixed_description
            }
        }
        
        response = api.execute('ReviseItem', request)
        
        if response.reply.Ack in ['Success', 'Warning']:
            print(f"    ✓ Description updated successfully for item {item_id}")
            return True
        else:
            print(f"    ✗ Description update failed: {response.reply.Ack}")
            if hasattr(response.reply, 'Errors'):
                print(f"      Error: {response.reply.Errors}")
            return False
            
    except Exception as e:
        print(f"    ✗ Description update error: {str(e)[:100]}")
        raise

@retry_with_backoff(max_retries=2, initial_delay=1, backoff_factor=2)
def safe_get_item_specifics(api, item_id: str) -> Optional[Dict]:
    """
    Get item specifics with retry logic.
    """
    try:
        request = {
            'ItemID': str(item_id),
            'IncludeItemSpecifics': True
        }
        
        response = api.execute('GetItem', request)
        
        if response.reply.Ack in ['Success', 'Warning']:
            item = response.reply.Item
            if hasattr(item, 'ItemSpecifics'):
                specifics = {}
                for spec in item.ItemSpecifics.NameValueList:
                    if hasattr(spec, 'Name') and hasattr(spec, 'Value'):
                        name = spec.Name
                        value = spec.Value[0] if isinstance(spec.Value, list) else spec.Value
                        specifics[name] = value
                return specifics
            return {}
        else:
            print(f"    ✗ Failed to get specifics: {response.reply.Ack}")
            return None
            
    except Exception as e:
        print(f"    ✗ Get specifics error: {str(e)[:100]}")
        raise

def apply_monkey_patches():
    """
    Apply monkey patches to ebay_utils module to add error handling.
    This should be called before using ebay_utils functions.
    """
    try:
        import ebay_utils
        
        # Store original functions
        if not hasattr(ebay_utils, '_original_functions_stored'):
            ebay_utils._original_update_title = getattr(ebay_utils, 'update_item_title', None)
            ebay_utils._original_update_desc = getattr(ebay_utils, 'update_item_description', None) 
            ebay_utils._original_get_specs = getattr(ebay_utils, 'get_item_specifics', None)
            ebay_utils._original_functions_stored = True
        
        # Create wrapped versions with error handling
        def wrapped_update_title(item_id: str, title: str, is_fixed_price: bool = True) -> bool:
            try:
                fixed_title = validate_and_fix_title(title)
                if ebay_utils._original_update_title:
                    return ebay_utils._original_update_title(item_id, fixed_title, is_fixed_price)
                else:
                    return safe_update_item_title(ebay_utils.api, item_id, fixed_title)
            except Exception as e:
                print(f"[PATCH] Title update failed with retry: {e}")
                return False
        
        def wrapped_update_description(item_id: str, description: str) -> bool:
            try:
                fixed_desc = validate_and_fix_description(description)
                if ebay_utils._original_update_desc:
                    return ebay_utils._original_update_desc(item_id, fixed_desc)
                else:
                    return safe_update_item_description(ebay_utils.api, item_id, fixed_desc)
            except Exception as e:
                print(f"[PATCH] Description update failed with retry: {e}")
                return False
        
        def wrapped_get_specifics(item_id: str) -> Optional[Dict]:
            try:
                if ebay_utils._original_get_specs:
                    # Add retry logic to original function
                    for attempt in range(3):
                        try:
                            return ebay_utils._original_get_specs(item_id)
                        except Exception as e:
                            if attempt < 2:
                                time.sleep(2 ** attempt)
                            else:
                                raise
                else:
                    return safe_get_item_specifics(ebay_utils.api, item_id)
            except Exception as e:
                print(f"[PATCH] Get specifics failed with retry: {e}")
                return {}
        
        # Apply patches
        ebay_utils.update_item_title = wrapped_update_title
        ebay_utils.update_item_description = wrapped_update_description  
        ebay_utils.get_item_specifics = wrapped_get_specifics
        
        print("[INFO] Applied error handling patches to ebay_utils")
        return True
        
    except Exception as e:
        print(f"[WARNING] Could not apply patches: {e}")
        return False

if __name__ == "__main__":
    # Test the validation functions
    print("Testing validation functions...")
    
    # Test title validation
    test_title = "This is a very long title that exceeds the eBay limit of 80 characters and needs to be truncated properly"
    fixed = validate_and_fix_title(test_title)
    print(f"Original title ({len(test_title)} chars): {test_title}")
    print(f"Fixed title ({len(fixed)} chars): {fixed}")
    
    # Test description validation
    test_desc = "<p>Test description with <img src='test.jpg'> and <br> tags</p><div>Unclosed div"
    fixed_desc = validate_and_fix_description(test_desc)
    print(f"\nOriginal description: {test_desc}")
    print(f"Fixed description: {fixed_desc}")
    
    # Test specifics validation
    test_specs = {
        "Very Long Specific Name That Exceeds Limit": "Very long value that exceeds the 65 character limit and needs to be truncated",
        "Normal": "Normal value"
    }
    fixed_specs = validate_item_specifics(test_specs)
    print(f"\nOriginal specifics: {test_specs}")
    print(f"Fixed specifics: {fixed_specs}")