# Function Signature Fix - November 25, 2025

## Problem
```
[ERROR] title optimisation error: apply_monkey_patches.<locals>.wrapped_update_title() 
takes 2 positional arguments but 3 were given
```

The monkey patch wrapper function was missing the `is_fixed_price` parameter that the original function has.

## Root Cause
- `update_item_title()` in ebay_utils.py takes 3 parameters: `item_id`, `title`, `is_fixed_price`
- The wrapper in ebay_utils_error_fixes.py only had 2 parameters
- When multiple patches were applied, function signatures conflicted

## Solution

### Created `combined_ebay_fixes.py`
- Combines all fixes in one place to avoid conflicts
- Proper function signatures for all wrappers
- Handles both retry logic AND XML entity escaping
- Single patch application prevents layering issues

### Key Changes
1. **Fixed function signature:**
   ```python
   def wrapped_update_title(item_id: str, title: str, is_fixed_price: bool = True) -> bool:
   ```

2. **Combined all fixes:**
   - Retry logic (3 attempts with exponential backoff)
   - XML entity escaping (& → &amp;, etc.)
   - Proper parameter passing

3. **Updated load order:**
   - airotate.bat tries combined fixes first
   - Falls back to individual patches if needed
   - test_ebay_utils.py uses same approach

## Files Modified
- Created: `combined_ebay_fixes.py` - All fixes in one module
- Updated: `ebay_utils_error_fixes.py` - Fixed function signature
- Updated: `test_ebay_utils.py` - Uses combined patches
- Updated: `airotate.bat` - Loads combined patches

## Impact
- Eliminates function signature errors
- Prevents patch conflicts
- Maintains all previous fixes (retry + XML)
- Cleaner, more maintainable code

## Testing
Run: `python combined_ebay_fixes.py` to verify patches apply correctly

The signature error should now be resolved and all fixes remain active.