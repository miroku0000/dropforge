# XML Entity Reference Fix - November 25, 2025

## Problem Identified
```
ERROR - ReviseFixedPriceItem: Class: RequestError, Severity: Error, Code: 5, 
XML Parse error. The entity name must immediately follow the '&' in the entity reference.
```

The eBay API was rejecting titles/descriptions with unescaped ampersands (&) and other special characters.

## Root Cause
- Ampersands (&) in titles like "Books & Magazines" were not being escaped to `&amp;`
- Other special characters (<, >, ", ') also needed XML entity encoding
- The previous fix was removing these characters instead of properly escaping them

## Solution Implemented

### 1. Created `xml_entity_fixes.py`
- Properly escapes XML entities in correct order (& first!)
- Handles already-escaped entities correctly
- Removes control characters that XML doesn't allow
- Wraps descriptions in CDATA for safety

### 2. Updated `ebay_utils.py` 
- Title update function now properly escapes:
  - `&` → `&amp;`
  - `<` → `&lt;` 
  - `>` → `&gt;`
  - `"` → `&quot;`
  - `'` → `&apos;`

### 3. Updated `test_ebay_utils.py` and `airotate.bat`
- Auto-loads XML entity fixes
- Falls back gracefully if module not found

## How It Works

### Before (Causing Errors):
```
Title: "Books & Magazines < $50"
Sent to API: "Books & Magazines < $50"  ❌ XML Parse Error
```

### After (Fixed):
```
Title: "Books & Magazines < $50"
Sent to API: "Books &amp; Magazines &lt; $50"  ✅ Valid XML
```

## Files Modified
- `ebay_utils.py` - Added proper XML entity escaping to update_item_title()
- `test_ebay_utils.py` - Auto-loads XML fixes
- `airotate.bat` - Auto-loads XML fixes
- Created: `xml_entity_fixes.py` - XML entity handling functions

## Testing
Run: `python xml_entity_fixes.py` to test entity escaping

## Impact
This should eliminate the XML parse errors (Code: 5) that were occurring even with retry logic.

## To Apply Manually
If the auto-loading doesn't work, you can manually apply:
```python
from xml_entity_fixes import apply_xml_fixes
apply_xml_fixes()
```