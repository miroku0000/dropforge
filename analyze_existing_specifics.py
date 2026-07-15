"""
Analyze your existing listings to understand common item specifics per category.
This learns from what's already working on eBay.
"""

import json
from collections import defaultdict, Counter
from ebay_utils import get_all_active_listings

def analyze_category_specifics():
    """Analyze existing listings to find common specifics per category"""
    
    print("Fetching active listings...")
    listings = get_all_active_listings()
    
    # Group by category
    categories = defaultdict(lambda: {
        'name': '',
        'items': [],
        'specifics_frequency': Counter(),
        'all_specifics': set()
    })
    
    print(f"Analyzing {len(listings)} listings...")
    
    for listing in listings:
        if not listing or not isinstance(listing, dict):
            continue
            
        # Get category info
        primary_cat = listing.get('PrimaryCategory') if listing else None
        if not primary_cat:
            continue
        cat_id = primary_cat.get('CategoryID') if isinstance(primary_cat, dict) else None
        cat_name = primary_cat.get('CategoryName', 'Unknown') if isinstance(primary_cat, dict) else 'Unknown'
        
        if not cat_id:
            continue
        
        categories[cat_id]['name'] = cat_name
        categories[cat_id]['items'].append(listing.get('ItemID'))
        
        # Get item specifics
        specifics = listing.get('ItemSpecifics', {})
        if specifics:
            nvl = specifics.get('NameValueList', [])
            if not isinstance(nvl, list):
                nvl = [nvl]
            
            for spec in nvl:
                if spec and isinstance(spec, dict):
                    spec_name = spec.get('Name')
                    if spec_name:
                        categories[cat_id]['specifics_frequency'][spec_name] += 1
                        categories[cat_id]['all_specifics'].add(spec_name)
    
    # Analyze results
    results = {}
    for cat_id, data in categories.items():
        total_items = len(data['items'])
        if total_items == 0:
            continue
        
        # Determine likely required (appears in >80% of listings)
        # and recommended (appears in >30% of listings)
        required = []
        recommended = []
        
        for spec_name, count in data['specifics_frequency'].items():
            frequency = count / total_items
            if frequency > 0.8:
                required.append(spec_name)
            elif frequency > 0.3:
                recommended.append(spec_name)
        
        results[cat_id] = {
            'category_name': data['name'],
            'total_items': total_items,
            'required': sorted(required),
            'recommended': sorted(recommended),
            'all_specifics': sorted(list(data['all_specifics'])),
            'frequency_threshold': '80% for required, 30% for recommended'
        }
    
    # Save results
    output_file = 'category_specifics_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print("CATEGORY SPECIFICS ANALYSIS")
    print(f"{'='*60}")
    print(f"Analyzed {len(categories)} categories")
    print(f"Results saved to {output_file}")
    
    # Print summary
    for cat_id, data in list(results.items())[:5]:  # First 5 categories
        print(f"\nCategory: {data['category_name']}")
        print(f"  Items analyzed: {data['total_items']}")
        print(f"  Likely required: {', '.join(data['required'][:5])}...")
        print(f"  Likely recommended: {', '.join(data['recommended'][:5])}...")
    
    return results

def get_specifics_for_category(category_id):
    """Quick lookup of likely specifics for a category"""
    
    # Try to load from analysis
    try:
        with open('category_specifics_analysis.json', 'r') as f:
            data = json.load(f)
            return data.get(str(category_id), {})
    except:
        # Run analysis if not available
        print("Running initial analysis...")
        analyze_category_specifics()
        return get_specifics_for_category(category_id)

if __name__ == "__main__":
    print("Analyzing your existing listings to determine category specifics...")
    print("This works without OAuth by learning from what's already working!")
    print("="*60)
    
    results = analyze_category_specifics()
    
    print("\n\nThis analysis shows:")
    print("1. Which specifics appear in most listings (likely required)")
    print("2. Which specifics are common (likely recommended)")
    print("3. All specifics used in each category")
    print("\nUse this data to ensure your AI-generated content includes the right attributes!")