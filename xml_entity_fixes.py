"""
Fix XML entity reference errors in eBay API calls.
Properly escape special characters for XML transmission.
"""

import html
import re

def escape_xml_entities(text: str) -> str:
    """
    Properly escape text for XML transmission to eBay API.
    
    eBay's XML parser requires proper entity encoding for special characters.
    This function handles the most common issues that cause XML parse errors.
    """
    if not text:
        return text
    
    # First, unescape any existing HTML entities to get raw characters
    # This converts things like &amp; back to & so we can re-escape properly
    text = html.unescape(text)
    
    # Now escape for XML in the correct order
    # Order matters! & must be done first
    text = text.replace('&', '&amp;')  # Must be first!
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    # Remove any control characters that XML doesn't like
    # Keep only printable characters and common whitespace
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    # Remove any stray/incomplete entity references that might remain
    # Pattern: & followed by anything that's not a valid entity
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', text)
    
    return text

def fix_title_for_xml(title: str) -> str:
    """
    Fix title specifically for XML transmission.
    Handles length, escaping, and cleanup.
    """
    if not title:
        return ""
    
    # First escape XML entities
    title = escape_xml_entities(title)
    
    # Truncate if too long (eBay limit is 80)
    if len(title) > 80:
        title = title[:77] + "..."
    
    # Clean up whitespace
    title = ' '.join(title.split())
    
    return title

def fix_description_for_xml(description: str) -> str:
    """
    Fix description specifically for XML transmission.
    Handles HTML content within XML properly.
    """
    if not description:
        return ""
    
    # For descriptions, we need to be more careful since they contain HTML
    # But that HTML needs to be properly escaped for XML transmission
    
    # First, fix any broken HTML entities in the description
    # Convert things like & that should be &amp; in HTML
    description = fix_broken_html_entities(description)
    
    # Don't escape < and > in descriptions as they're HTML tags
    # But DO escape standalone & characters
    description = fix_ampersands_only(description)
    
    # Remove control characters
    description = ''.join(char for char in description if ord(char) >= 32 or char in '\n\r\t')
    
    # Wrap in CDATA for safety (this prevents XML parsing of HTML content)
    # The CDATA wrapper tells XML parser to treat content as raw text
    # This is the safest way to transmit HTML content via XML
    return f"<![CDATA[{description}]]>"

def fix_broken_html_entities(html_text: str) -> str:
    """
    Fix broken or incomplete HTML entities in text.
    This handles cases like & instead of &amp; in HTML.
    """
    if not html_text:
        return html_text
    
    # Pattern to find & that are NOT part of valid HTML entities
    # Valid entities are like &amp; &lt; &gt; &quot; &#123; &#xAB;
    pattern = r'&(?!(?:[a-zA-Z][a-zA-Z0-9]{0,10}|#\d{1,5}|#x[0-9a-fA-F]{1,4});)'
    
    # Replace standalone & with &amp;
    html_text = re.sub(pattern, '&amp;', html_text)
    
    return html_text

def fix_ampersands_only(text: str) -> str:
    """
    Fix only ampersands in text, leaving other HTML intact.
    Used for HTML content that will be wrapped in CDATA.
    """
    if not text:
        return text
    
    # Find & that are not part of HTML entities
    # This regex matches & that are NOT followed by valid entity patterns
    pattern = r'&(?!(?:[a-zA-Z][a-zA-Z0-9]{0,10}|#\d{1,5}|#x[0-9a-fA-F]{1,4});)'
    
    # Replace with &amp;
    text = re.sub(pattern, '&amp;', text)
    
    return text

def validate_xml_content(text: str, field_name: str = "field") -> tuple[bool, str]:
    """
    Validate that text is safe for XML transmission.
    Returns (is_valid, error_message).
    """
    if not text:
        return True, ""
    
    # Check for unescaped ampersands
    if '&' in text:
        # Check if it's a proper entity
        pattern = r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)'
        if re.search(pattern, text):
            return False, f"{field_name} contains unescaped ampersand"
    
    # Check for control characters
    for char in text:
        if ord(char) < 32 and char not in '\n\r\t':
            return False, f"{field_name} contains control character (ASCII {ord(char)})"
    
    return True, ""

# Monkey patch for ebay_utils
def apply_xml_fixes():
    """
    Apply XML entity fixes to ebay_utils functions.
    """
    try:
        import ebay_utils
        
        # Store original function if not already stored
        if not hasattr(ebay_utils, '_original_update_title_xml'):
            ebay_utils._original_update_title_xml = ebay_utils.update_item_title
        
        # Create wrapped version
        def wrapped_update_title(item_id: str, new_title: str, is_fixed_price: bool = True) -> bool:
            # Fix the title for XML
            fixed_title = fix_title_for_xml(new_title)
            print(f"[XML FIX] Title fixed for XML: '{new_title[:30]}...' -> '{fixed_title[:30]}...'")
            
            # Call original with fixed title
            if hasattr(ebay_utils, '_original_update_title_xml'):
                return ebay_utils._original_update_title_xml(item_id, fixed_title, is_fixed_price)
            else:
                # Fallback if original not found
                return False
        
        # Apply patch
        ebay_utils.update_item_title = wrapped_update_title
        print("[INFO] Applied XML entity fixes to ebay_utils")
        return True
        
    except Exception as e:
        print(f"[WARNING] Could not apply XML fixes: {e}")
        return False

if __name__ == "__main__":
    # Test the fixes
    print("Testing XML entity fixes...")
    print("="*60)
    
    # Test cases
    test_cases = [
        ("Books & Magazines", "Books &amp; Magazines"),
        ("Items < $50 & > $20", "Items &lt; $50 &amp; &gt; $20"),
        ("Already &amp; escaped", "Already &amp; escaped"),
        ("Mix & match < items >", "Mix &amp; match &lt; items &gt;"),
        ("Tom's \"Special\" Item", "Tom&apos;s &quot;Special&quot; Item"),
    ]
    
    print("Title escaping tests:")
    for original, expected in test_cases:
        result = escape_xml_entities(original)
        status = "OK" if result == expected else "FAIL"
        print(f"{status} '{original}' -> '{result}'")
        if result != expected:
            print(f"   Expected: '{expected}'")
    
    print("\nDescription test:")
    desc = "<p>Great item & fast shipping</p>"
    fixed = fix_description_for_xml(desc)
    print(f"Original: {desc}")
    print(f"Fixed: {fixed}")
    
    print("\nValidation tests:")
    test_strings = [
        "Good title",
        "Bad & unescaped",
        "Good &amp; escaped",
        "Control char: \x01",
    ]
    
    for test in test_strings:
        valid, msg = validate_xml_content(test)
        print(f"'{test}': {'Valid' if valid else f'Invalid - {msg}'}")
    
    print("="*60)