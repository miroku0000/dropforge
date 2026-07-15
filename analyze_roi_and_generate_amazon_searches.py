"""
Analyze eBay listings by Return on Ad Spend (ROI) and generate Amazon search links.
Finds the highest ROI listings and creates optimized Amazon search URLs.
"""

import os
import glob
import argparse
import pandas as pd
import requests
import json
from urllib.parse import quote_plus
from datetime import datetime

def find_latest_automagical_file():
    """Find the most recent automagical_Listing_*.csv file in local downloads/ then ~/Downloads"""
    download_paths = [
        os.path.join(os.getcwd(), "downloads"),
        os.path.expanduser("~/Downloads"),
    ]

    latest_file = None
    latest_time = 0

    for download_dir in download_paths:
        pattern = os.path.join(download_dir, "automagical_Listing_*.csv")
        files = glob.glob(pattern)

        for file in files:
            mtime = os.path.getmtime(file)
            if mtime > latest_time:
                latest_time = mtime
                latest_file = file

    return latest_file

def calculate_roi(df):
    """Calculate ROI as Sales/Ad fees"""
    # Look for columns that might contain sales and ad fees
    sales_cols = [col for col in df.columns if 'sales' in col.lower() or 'revenue' in col.lower()]
    ad_fee_cols = [col for col in df.columns if 'ad' in col.lower() and ('fee' in col.lower() or 'cost' in col.lower() or 'spend' in col.lower())]
    
    if not sales_cols or not ad_fee_cols:
        print(f"Warning: Could not find sales columns {sales_cols} or ad fee columns {ad_fee_cols}")
        print(f"Available columns: {list(df.columns)}")
        
        # Try to find the exact column name
        if 'Return on Ad spend (Sales/Ad fees)' in df.columns:
            return df['Return on Ad spend (Sales/Ad fees)']
        
        # Manual calculation if we have the right columns
        if 'Sales' in df.columns and 'Ad fees' in df.columns:
            # Avoid division by zero
            df['ROI'] = df.apply(lambda row: row['Sales'] / row['Ad fees'] if row['Ad fees'] > 0 else 0, axis=1)
            return df['ROI']
    
    # Use first found columns
    sales_col = sales_cols[0] if sales_cols else None
    ad_col = ad_fee_cols[0] if ad_fee_cols else None
    
    if sales_col and ad_col:
        # Calculate ROI, avoiding division by zero
        df['ROI'] = df.apply(lambda row: row[sales_col] / row[ad_col] if row[ad_col] > 0 else 0, axis=1)
        return df['ROI']
    
    return None

def generate_search_variations(title):
    """Generate multiple search variations from eBay title"""
    import re
    
    variations = []
    
    # Clean common eBay patterns
    cleaned = title
    for term in [" - New", " - Used", " NIB", " BNIB", " NWT", " NWOT", " OEM", " *NEW*", " | "]:
        cleaned = cleaned.replace(term, " ")
    
    # Remove text in parentheses
    cleaned = re.sub(r'\([^)]*\)', '', cleaned).strip()
    
    # Extended list of brands to remove (case-insensitive)
    brands_to_remove = [
        # Camera brands
        'Godox', 'Canon', 'Nikon', 'Sony', 'Fujifilm', 'Olympus', 'Panasonic', 'Pentax',
        # Auto brands  
        'Ford', 'Chevy', 'Chevrolet', 'GMC', 'RAM', 'Dodge', 'Toyota', 'Honda', 'Nissan',
        'Remogo', 'Kingna', 'CZmenghe', 'AMTIFO', 'Quixofiber', 'NeaLia', 'JDMSPEED',
        # Tool brands
        'Huepar', 'Dewalt', 'Milwaukee', 'Makita', 'Bosch', 'Ryobi',
        # Craft brands
        'LITMIND', 'Cricut', '3M',
        # Tech brands
        'Apple', 'Samsung', 'Microsoft', 'Google', 'Amazon', 'Dell', 'HP', 'Lenovo',
        # Common product-specific brands
        'OtterBox', 'Spigen', 'Anker', 'Belkin'
    ]
    
    # Convert to lowercase for comparison
    brands_lower = [b.lower() for b in brands_to_remove]
    
    # Try to identify and remove brand from beginning
    words = cleaned.split()
    if len(words) > 2:
        # Check first word for brand
        if words[0].lower() in brands_lower:
            # Remove brand
            words = words[1:]
            # If next word looks like a model number, remove it too
            if len(words) > 0 and (any(char.isdigit() for char in words[0]) or 
                                   (len(words[0]) > 3 and any(char.isupper() for char in words[0]))):
                words = words[1:]
            cleaned = " ".join(words)
        # Check if first word itself looks like a model number (e.g., "A19", "T13A")
        elif any(char.isdigit() for char in words[0]) and len(words[0]) < 8:
            cleaned = " ".join(words[1:])
    
    # Remove everything after "for" (e.g., "Flash for Sony Cameras" -> "Flash")
    if ' for ' in cleaned.lower():
        cleaned = cleaned[:cleaned.lower().index(' for ')].strip()
    
    # Clean up extra spaces
    cleaned = ' '.join(cleaned.split())
    
    # Generate variations
    words = cleaned.split()
    
    # Variation 1: Full cleaned title (up to 100 chars)
    var1 = cleaned[:100].rsplit(' ', 1)[0] if len(cleaned) > 100 else cleaned
    variations.append(var1.strip())
    
    # Variation 2: Remove first word if it's a brand
    if len(words) > 2 and words[0][0].isupper():
        var2 = ' '.join(words[1:])[:100]
        if var2 not in variations:
            variations.append(var2.strip())
    
    # Variation 3: Core product type (middle words)
    if len(words) > 4:
        var3 = ' '.join(words[1:-1])[:100]  
        if var3 not in variations:
            variations.append(var3.strip())
    
    # Variation 4: Last significant words (product category)
    meaningful = [w for w in words if len(w) > 2 and not w.isdigit()]
    if len(meaningful) > 3:
        var4 = ' '.join(meaningful[-4:])
        if var4 not in variations:
            variations.append(var4.strip())
    
    # Variation 5: With year range expanded if present
    year_pattern = r'(\d{4})-(\d{4})'
    year_match = re.search(year_pattern, cleaned)
    if year_match:
        var5 = cleaned.replace(year_match.group(), f"{int(year_match.group(1))-1}-{int(year_match.group(2))+1}")
        if var5 not in variations:
            variations.append(var5[:100].strip())
    
    # Ensure we have at least 5 variations (duplicate last if needed)
    while len(variations) < 5:
        variations.append(variations[-1] if variations else cleaned[:100])
    
    return variations[:5]

def generate_search_term_with_ollama(title):
    """Use Ollama to generate a generic Amazon search term from eBay title"""
    
    prompt = f"""Generate 5 different Amazon search queries for this eBay product.
Each query should be progressively more general to find related products.

Product: {title}

Instructions:
1. Remove brand but keep product type and key specs (size, compatibility)
2. Broaden to category level (e.g., "brake kit SUV" not specific model)  
3. Include year ranges for auto parts (e.g., "2018-2024")
4. Focus on use case or problem solved
5. Search for competing/alternative brands

Rules:
- Remove eBay terms: NEW, NIB, OEM, NWT, BNIB
- Keep important specs: wattage, size, year range
- Make queries find multiple options, not one specific item
- One query per line, no numbering

Example for "Power Stop KOE7873 Brake Kit 2017-2023 Honda CR-V":
brake kit Honda CRV 2017-2023 rotors pads
brake kit compact SUV ceramic
Bosch Wagner brake kit Honda
brake pad rotor replacement kit
wheel hub bearing Honda CRV

Your 5 queries:"""
    
    # First check if Ollama is running
    try:
        test = requests.get("http://localhost:11434/api/tags", timeout=2)
        if test.status_code != 200:
            raise Exception("Ollama not available")
    except:
        # Ollama not running, use fallback
        return simple_title_cleanup(title)
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",  # Use chat endpoint
            json={
                "model": "llama3.2",  # More likely to be available
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.3  # Lower temperature for more consistent results
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # Try different response formats
            search_term = result.get('message', {}).get('content', '') or result.get('response', '')
            search_term = search_term.strip()
            # Clean up the response
            search_term = search_term.replace('"', '').replace("'", '')
            # If it's multi-line, take first line
            search_term = search_term.split('\n')[0].strip()
            return search_term if search_term else generate_search_variations(title)[0]
        else:
            return generate_search_variations(title)
            
    except Exception as e:
        # Fallback to simple cleanup
        return generate_search_variations(title)

def create_amazon_search_url(search_term, next_day=True, high_rating=True, min_price=None):
    """Create Amazon search URL with filters"""

    # Base Amazon search URL
    base_url = "https://www.amazon.com/s"

    # URL encode the search term
    encoded_term = quote_plus(search_term)

    # Build parameters
    params = {
        'k': search_term,  # Search keyword
        'i': 'aps',  # Search in all departments
    }

    # Build the URL
    url = f"{base_url}?k={encoded_term}"

    # Amazon honors a SINGLE rh= param with facets joined by %2C. Emitting one
    # rh= per facet makes only the LAST take effect -- which silently dropped the
    # price floor on these generated URLs. Join them so all facets apply.
    facets = []
    filters = []
    if min_price and min_price > 0:
        facets.append(f"p_36%3A{int(min_price * 100)}-")          # price in cents, "min-"
        filters.append(f"Min ${min_price:.0f}")
    if next_day:
        facets.append("p_n_free_shipping_eligible%3A2944662011")  # Prime / fast ship
        filters.append("Prime/Next-Day")
    if high_rating:
        facets.append("p_72%3A2491149011")                        # 4 stars & up
        filters.append("4+ stars")
    if facets:
        url += "&rh=" + "%2C".join(facets)
    url += "&i=aps"

    return url, filters

def main():
    """Main function to process listings and generate Amazon searches"""
    parser = argparse.ArgumentParser(description="eBay ROI Analyzer & Amazon Search Generator")
    parser.add_argument('--min-price', type=float, default=0, help='Minimum product price filter for Amazon searches (e.g. 50)')
    args = parser.parse_args()
    min_price = args.min_price

    print("="*60)
    print("eBay ROI Analyzer & Amazon Search Generator")
    if min_price > 0:
        print(f"Minimum price filter: ${min_price:.0f}")
    print("="*60)
    
    # Find the latest file
    csv_file = find_latest_automagical_file()
    
    if not csv_file:
        print("Error: Could not find automagical_Listing_*.csv file in Downloads")
        print("Please ensure the file exists and follows the pattern: automagical_Listing_*.csv")
        return
    
    print(f"\nFound file: {csv_file}")
    print(f"File date: {datetime.fromtimestamp(os.path.getmtime(csv_file)).strftime('%Y-%m-%d %H:%M')}")
    
    # Read the CSV (skip the first warning row)
    try:
        df = pd.read_csv(csv_file, skiprows=1, low_memory=False)
        print(f"Loaded {len(df)} listings")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # Calculate or find ROI
    if 'Return on Ad spend (Sales/Ad fees)' in df.columns:
        df['ROI'] = df['Return on Ad spend (Sales/Ad fees)']
        print("Using existing 'Return on Ad spend' column")
    else:
        roi_series = calculate_roi(df)
        if roi_series is not None:
            df['ROI'] = roi_series
        else:
            print("Error: Could not calculate ROI")
            return
    
    # Filter out invalid ROI values
    df = df[df['ROI'].notna() & (df['ROI'] > 0)]
    
    # Sort by ROI descending
    df_sorted = df.sort_values('ROI', ascending=False)
    
    # Get top N listings (configurable)
    top_n = 10
    top_listings = df_sorted.head(top_n)
    
    print(f"\nTop {top_n} Listings by ROI:")
    print("-"*60)
    
    results = []
    
    for idx, row in top_listings.iterrows():
        title = row.get('Title', row.get('Product Name', 'Unknown'))
        roi = row['ROI']
        
        print(f"\n{len(results)+1}. ROI: {roi:.2f}")
        print(f"   Title: {title[:80]}{'...' if len(title) > 80 else ''}")
        
        # Generate search terms (multiple variations)
        print("   Generating search variations...")
        
        # Try Ollama first, fall back to rule-based
        response = generate_search_term_with_ollama(title)
        
        # Check if we got multiple queries or just one
        if isinstance(response, str) and '\n' in response:
            # Multiple queries returned
            search_terms = [q.strip() for q in response.split('\n') if q.strip()][:5]
        elif isinstance(response, list):
            search_terms = response[:5]
        else:
            # Single query or fallback needed
            search_terms = generate_search_variations(title)
        
        # Ensure we have valid search terms
        search_terms = [term for term in search_terms if term and len(term) > 5]
        
        if not search_terms:
            search_terms = [generate_search_variations(title)[0]]
        
        print(f"   Generated {len(search_terms)} search variations")
        
        # Create Amazon URLs for first/best search term
        primary_search = search_terms[0]
        url_prime, filters_prime = create_amazon_search_url(primary_search, next_day=True, high_rating=True, min_price=min_price)
        url_basic, _ = create_amazon_search_url(primary_search, next_day=False, high_rating=False, min_price=min_price)

        # Create URLs for all variations
        all_variation_urls = []
        for term in search_terms:
            variation_url, _ = create_amazon_search_url(term, next_day=True, high_rating=True, min_price=min_price)
            all_variation_urls.append(variation_url)
        
        print(f"   Primary search: {primary_search[:60]}...")
        
        results.append({
            'original_title': title,
            'roi': roi,
            'search_term': primary_search,
            'search_variations': search_terms,
            'amazon_url_filtered': url_prime,
            'amazon_url_basic': url_basic,
            'variation_urls': all_variation_urls,
            'filters': filters_prime
        })
    
    # Save results to file
    output_file = f"amazon_search_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Amazon Search Links for High ROI eBay Listings\n")
        f.write("="*60 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Source: {os.path.basename(csv_file)}\n\n")
        
        for i, result in enumerate(results, 1):
            f.write(f"{i}. ROI: {result['roi']:.2f}\n")
            f.write(f"   eBay: {result['original_title']}\n")
            f.write(f"   Search variations:\n")
            for j, term in enumerate(result.get('search_variations', [result['search_term']]), 1):
                f.write(f"      {j}. {term}\n")
            f.write(f"   Amazon URLs:\n")
            for url in result.get('variation_urls', [result['amazon_url_filtered']]):
                f.write(f"      {url}\n")
            f.write("\n")
    
    print(f"\n{'='*60}")
    print(f"Results saved to: {output_file}")
    
    # Also create a CSV for easy import
    results_df = pd.DataFrame(results)
    csv_output = f"amazon_searches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results_df.to_csv(csv_output, index=False)
    print(f"CSV saved to: {csv_output}")
    
    # Display first few URLs for quick access
    print(f"\nTop 3 Amazon Search URLs (with Prime & 4+ stars):")
    print("-"*60)
    for i, result in enumerate(results[:3], 1):
        print(f"{i}. {result['amazon_url_filtered']}\n")
    
    # Add URLs to amazon_urls.txt if they don't exist
    amazon_urls_file = "amazon_urls.txt"
    existing_urls = set()
    
    # Read existing URLs if file exists
    if os.path.exists(amazon_urls_file):
        with open(amazon_urls_file, 'r', encoding='utf-8') as f:
            existing_urls = set(line.strip() for line in f if line.strip())
        print(f"\nFound {len(existing_urls)} existing URLs in {amazon_urls_file}")
    else:
        print(f"\nCreating new {amazon_urls_file}")
    
    # Collect new URLs (only filtered version with Prime + 4 stars)
    new_urls = []
    for result in results:
        # Only add the filtered URL (with Prime and 4+ stars)
        url = result['amazon_url_filtered']
        if url not in existing_urls:
            new_urls.append(url)
            existing_urls.add(url)
    
    # Append new URLs to file
    if new_urls:
        with open(amazon_urls_file, 'a', encoding='utf-8') as f:
            # Add newline separator if file exists and not empty
            if os.path.exists(amazon_urls_file) and os.path.getsize(amazon_urls_file) > 0:
                f.write('\n')
            for url in new_urls:
                f.write(url + '\n')
        print(f"Added {len(new_urls)} new URLs to {amazon_urls_file}")
    else:
        print(f"All URLs already exist in {amazon_urls_file}")
    
    print(f"Total unique URLs in {amazon_urls_file}: {len(existing_urls)}")

if __name__ == "__main__":
    main()