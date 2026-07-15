"""
Check the fixed listing 226955331753 to verify it meets quality thresholds
"""

from ebay_utils import (
    _get_item_details_combined,
    rate_title_with_llm,
    rate_description_with_llm
)

print("=" * 70)
print("Checking Fixed Listing 226955331753")
print("=" * 70)

item_id = '226955331753'

# Get the item details (from cache if available)
print(f"\n1. Fetching item details for {item_id}...")
details = _get_item_details_combined(item_id)

if details:
    title = details.get('Title', '')
    description = details.get('Description', '')
    specifics = details.get('SpecificsDict', {})
    
    print(f"\n2. Item Information:")
    print(f"   Title: {title}")
    print(f"   Description length: {len(description)} characters")
    print(f"   Number of specifics: {len(specifics)}")
    
    # Check if HTML is properly formatted
    print(f"\n3. HTML Analysis:")
    has_escaped = '&lt;' in description or '&gt;' in description
    has_pre = '<pre>' in description
    has_proper_html = '<h3>' in description or '<ul>' in description or '<p>' in description
    
    print(f"   Contains escaped HTML (&lt;, &gt;): {has_escaped}")
    print(f"   Contains <pre> tags: {has_pre}")
    print(f"   Contains proper HTML tags: {has_proper_html}")
    
    if has_escaped or has_pre:
        print("   ⚠ WARNING: Description still has HTML issues!")
    else:
        print("   ✓ HTML is properly formatted")
    
    # Rate the title
    print(f"\n4. Rating Title (Threshold: 9)...")
    title_rating = rate_title_with_llm(title, description)
    print(f"   Title Rating: {title_rating}/10")
    
    if title_rating >= 9:
        print("   ✓ Title meets quality threshold")
    else:
        print(f"   ✗ Title below threshold (needs {9 - title_rating} point improvement)")
    
    # Rate the description
    print(f"\n5. Rating Description (Threshold: 9)...")
    desc_rating = rate_description_with_llm(description, specifics)
    print(f"   Description Rating: {desc_rating}/10")
    
    if desc_rating >= 9:
        print("   ✓ Description meets quality threshold")
    else:
        print(f"   ✗ Description below threshold (needs {9 - desc_rating} point improvement)")
    
    # Overall summary
    print(f"\n6. Summary:")
    print(f"   HTML Format: {'GOOD' if not has_escaped and not has_pre else 'NEEDS FIX'}")
    print(f"   Title Quality: {'PASS' if title_rating >= 9 else 'NEEDS IMPROVEMENT'} ({title_rating}/10)")
    print(f"   Description Quality: {'PASS' if desc_rating >= 9 else 'NEEDS IMPROVEMENT'} ({desc_rating}/10)")
    
    # Show first 500 chars of description
    print(f"\n7. Description Preview:")
    print("-" * 50)
    print(description[:500])
    print("-" * 50)
    
else:
    print("\nERROR: Could not fetch item details")

print("\n" + "=" * 70)