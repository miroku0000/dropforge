"""
Improved eBay ROI Analyzer with better Amazon search generation
Generates multiple related search queries for each top product
"""

import os
import glob
import pandas as pd
import requests
import json
from urllib.parse import quote_plus
from datetime import datetime

def find_latest_automagical_file():
    """Find the most recent automagical_Listing_*.csv file in Downloads"""
    download_dir = os.path.expanduser("~/Downloads")
    pattern = os.path.join(download_dir, "automagical_Listing_*.csv")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    return max(files, key=os.path.getmtime)

def calculate_roi(df):
    """Calculate ROI from the dataframe"""
    # Check for existing ROI column
    if 'Return on Ad spend (Sales/Ad fees)' in df.columns:
        return df['Return on Ad spend (Sales/Ad fees)']
    
    # Calculate from Sales and Ad fees
    sales_col = next((col for col in df.columns if 'Sales' in col and 'Total' in col), None)
    fees_col = next((col for col in df.columns if 'Ad fees' in col), None)
    
    if sales_col and fees_col:
        # Clean monetary values
        df[sales_col] = pd.to_numeric(df[sales_col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
        df[fees_col] = pd.to_numeric(df[fees_col].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
        
        # Calculate ROI
        roi = df[sales_col] / df[fees_col]
        return roi.replace([float('inf'), -float('inf')], 0)
    
    return None

def generate_search_variations_with_ollama(title, product_context=None):
    """Generate multiple search variations using improved prompting"""
    
    # Enhanced prompt with better instructions
    prompt = f"""Analyze this eBay product listing and generate 5 different Amazon search queries.

Product Title: {title}

Instructions:
1. First query: Remove brand name, keep core product type and key specs
2. Second query: Broaden to category level (e.g., "brake kit" instead of specific model)
3. Third query: Target competing brands in same category
4. Fourth query: Focus on the problem it solves or use case
5. Fifth query: Related/complementary product

Rules:
- Make queries generic enough to find multiple options
- Include year ranges for auto parts (e.g., "2018-2024")
- Keep specifications that matter (wattage, size, compatibility)
- Remove eBay-specific terms (NEW, NIB, OEM, etc.)

Return ONLY 5 search queries, one per line, no numbering or explanations.

Example Input: "Power Stop KOE7873 Brake Kit for 2017-2023 Honda CR-V - Rotors & Pads"
Example Output:
brake kit Honda CRV 2017-2023 rotors pads
brake kit compact SUV front rear
Bosch Wagner brake kit Honda
SUV brake replacement kit ceramic
wheel hub bearing assembly Honda CRV

Search queries:"""

    # Check if Ollama is available
    try:
        test = requests.get("http://localhost:11434/api/tags", timeout=2)
        if test.status_code != 200:
            raise Exception("Ollama not available")
    except:
        # Fallback to simple variations
        return generate_fallback_variations(title)
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.7  # More creative for variations
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('message', {}).get('content', '')
            
            # Parse the response into separate queries
            queries = [q.strip() for q in content.strip().split('\n') if q.strip()]
            
            # Filter out any explanatory text
            queries = [q for q in queries if not q.startswith(('1.', '2.', '3.', '4.', '5.', '-', '*'))]
            
            # Clean up queries
            queries = [q.lstrip('0123456789.- ') for q in queries]
            
            return queries[:5] if queries else generate_fallback_variations(title)
        
    except Exception as e:
        print(f"Ollama error: {e}")
    
    return generate_fallback_variations(title)

def generate_fallback_variations(title):
    """Generate search variations without LLM"""
    import re
    
    # Clean the title
    cleaned = title
    
    # Remove eBay-specific terms
    ebay_terms = ['NEW', 'NIB', 'BNIB', 'NWT', 'OEM', '*', '|', '-']
    for term in ebay_terms:
        cleaned = cleaned.replace(term, ' ')
    
    # Extract key information
    words = cleaned.split()
    
    # Try to identify product type, brand, model
    variations = []
    
    # Variation 1: Full cleaned title
    base = ' '.join(cleaned.split())[:100]
    variations.append(base)
    
    # Variation 2: Remove first word if it's likely a brand
    if len(words) > 3:
        no_brand = ' '.join(words[1:])[:100]
        variations.append(no_brand)
    
    # Variation 3: Extract year range if present
    year_pattern = r'(\d{4})-(\d{4})'
    year_match = re.search(year_pattern, title)
    if year_match:
        # Add variation with extended year range
        start_year = int(year_match.group(1))
        end_year = int(year_match.group(2))
        extended = title.replace(year_match.group(), f"{start_year-1}-{end_year+1}")
        variations.append(extended[:100])
    
    # Variation 4: Category level (take last 3-4 meaningful words)
    meaningful_words = [w for w in words if len(w) > 2 and not w.isdigit()]
    if len(meaningful_words) > 3:
        category = ' '.join(meaningful_words[-4:])
        variations.append(category)
    
    # Variation 5: First and last parts
    if len(words) > 5:
        short = f"{' '.join(words[:2])} {' '.join(words[-2:])}"
        variations.append(short)
    
    return variations[:5]

def create_amazon_url_with_filters(search_term):
    """Create Amazon URL with Prime and 4+ star filters"""
    encoded = quote_plus(search_term)
    
    # Base URL with filters
    url = f"https://www.amazon.com/s?k={encoded}"
    
    # Add filters for Prime and 4+ stars
    url += "&rh=p_72%3A1248861011"  # 4+ stars
    url += "%2Cp_90%3A8308921011"   # Include out of stock (for research)
    
    return url

def iterative_prompt_refinement(title, max_iterations=3):
    """Iteratively refine the search queries"""
    
    best_queries = []
    iteration = 1
    
    while iteration <= max_iterations:
        queries = generate_search_variations_with_ollama(title)
        
        if iteration == 1:
            best_queries = queries
        else:
            # Evaluate and refine
            refinement_prompt = f"""Review these Amazon search queries for this product:
Product: {title}

Current queries:
{chr(10).join(queries)}

Improve them by:
1. Making them more likely to return multiple results
2. Removing overly specific model numbers
3. Adding alternative terms users might search
4. Ensuring year ranges are included for auto parts
5. Making sure queries aren't too narrow

Return 5 improved queries, one per line:"""
            
            refined = generate_search_variations_with_ollama(title)
            if refined and len(refined) >= len(best_queries):
                best_queries = refined
        
        iteration += 1
    
    return best_queries

def main():
    """Main function to process listings and generate Amazon searches"""
    
    print("="*80)
    print("IMPROVED eBay ROI Analyzer & Amazon Search Generator")
    print("="*80)
    
    # Find the latest file
    csv_file = find_latest_automagical_file()
    
    if not csv_file:
        print("Error: Could not find automagical_Listing_*.csv file in Downloads")
        return
    
    print(f"\nFound file: {csv_file}")
    
    # Read CSV
    try:
        df = pd.read_csv(csv_file, skiprows=2, encoding='utf-8-sig', low_memory=False)
        print(f"Loaded {len(df)} listings")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # Calculate ROI
    df['ROI'] = calculate_roi(df)
    
    if df['ROI'] is None:
        print("Could not calculate ROI")
        return
    
    # Filter and sort
    df = df[df['ROI'].notna() & (df['ROI'] > 0)]
    df_sorted = df.sort_values('ROI', ascending=False)
    
    # Get top listings
    top_n = 10
    top_listings = df_sorted.head(top_n)
    
    print(f"\nGenerating search variations for top {top_n} products...")
    print("-"*80)
    
    all_urls = []
    results_data = []
    
    for idx, row in top_listings.iterrows():
        title = row.get('Title', 'Unknown')
        roi = row['ROI']
        
        print(f"\n{len(results_data)+1}. ROI: {roi:.2f}")
        print(f"   Title: {title[:80]}...")
        
        # Generate variations with iterative refinement
        print("   Generating search variations...")
        variations = iterative_prompt_refinement(title, max_iterations=2)
        
        print(f"   Generated {len(variations)} search variations")
        
        # Create URLs for each variation
        urls = []
        for i, query in enumerate(variations[:5], 1):
            url = create_amazon_url_with_filters(query)
            urls.append(url)
            print(f"     {i}. {query[:60]}...")
        
        all_urls.extend(urls)
        
        results_data.append({
            'title': title,
            'roi': roi,
            'queries': variations,
            'urls': urls
        })
    
    # Save all URLs to file
    output_file = f"amazon_searches_improved_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Amazon Search URLs for Top ROI Products\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total URLs: {len(all_urls)}\n\n")
        
        for url in all_urls:
            f.write(url + '\n')
    
    print(f"\n{'='*80}")
    print(f"Generated {len(all_urls)} search URLs")
    print(f"Saved to: {output_file}")
    
    # Also save detailed results
    detailed_file = f"amazon_searches_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(detailed_file, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"Detailed results saved to: {detailed_file}")
    
    # Display sample URLs
    print(f"\nSample URLs (first 5):")
    print("-"*80)
    for url in all_urls[:5]:
        print(url)

if __name__ == "__main__":
    main()