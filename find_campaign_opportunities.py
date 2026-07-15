"""
Find listings/keywords that should be added to the Top Converters Test campaign.
Analyzes current inventory and suggests high-potential additions.
"""

import pandas as pd
import os
from datetime import datetime, timedelta
import glob
import re

def load_current_campaign_keywords():
    """Load keywords currently in the campaign."""
    # Find the most recent campaign keyword report
    keyword_files = []
    for search_dir in [os.path.join(os.getcwd(), 'downloads'), os.path.expanduser('~/Downloads')]:
        keyword_files.extend(glob.glob(os.path.join(search_dir, "Top Converters Test_Keyword_*.csv")))

    if not keyword_files:
        print("No campaign keyword files found")
        return set()
    
    latest_file = max(keyword_files, key=os.path.getmtime)
    print(f"Loading current campaign keywords from: {os.path.basename(latest_file)}")
    
    df = pd.read_csv(latest_file, skiprows=1)
    
    # Extract unique keywords (normalized to lowercase)
    current_keywords = set()
    for keyword in df['Seller Keyword'].dropna():
        current_keywords.add(keyword.lower().strip())
    
    print(f"Found {len(current_keywords)} unique keywords in campaign")
    return current_keywords

def load_active_listings():
    """Load all active eBay listings."""
    # First check if we need fresh data
    import subprocess
    from datetime import datetime, timedelta
    
    # Check age of existing files
    local_patterns = [
        "ALL_LISTINGS_REMOVAL_PRIORITY_*.csv",
        "current_listing_ratings*.csv"
    ]
    
    local_files = []
    for pattern in local_patterns:
        local_files.extend(glob.glob(pattern))
    
    # If we have a file from today, use it
    if local_files:
        latest_file = max(local_files, key=os.path.getmtime)
        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_file))
        
        if file_age < timedelta(hours=12):
            print(f"Using recent listings file: {latest_file}")
            df = pd.read_csv(latest_file)
            print(f"Loaded {len(df)} listings")
            return df
        else:
            print(f"Listings file is {file_age.total_seconds()/3600:.1f} hours old, downloading fresh data...")
    else:
        print("No local listings files found, downloading...")
    
    # Download fresh listings
    print("Running ai_download_all_listings.py to get current listings...")
    result = subprocess.run(['python', 'ai_download_all_listings.py'], 
                          capture_output=True, text=True, timeout=60)
    
    if result.returncode == 0:
        print("Successfully downloaded listings")
        # Find the newly created file
        local_files = []
        for pattern in local_patterns:
            local_files.extend(glob.glob(pattern))
        
        if local_files:
            latest_file = max(local_files, key=os.path.getmtime)
            df = pd.read_csv(latest_file)
            print(f"Loaded {len(df)} listings from fresh download")
            return df
    else:
        print(f"Download failed: {result.stderr}")
    
    # Fallback: Try downloads folders for manual exports
    patterns = [
        "download.all.csv",
        "ebay_listings_*.csv",
        "ALL ACTIVE*.xlsx",
        "ALL ACTIVE*.csv"
    ]

    listing_files = []
    for search_dir in [os.path.join(os.getcwd(), 'downloads'), os.path.expanduser('~/Downloads')]:
        for pattern in patterns:
            listing_files.extend(glob.glob(os.path.join(search_dir, pattern)))
    
    if not listing_files:
        print("ERROR: Could not get listings data")
        print("Please manually export from eBay Seller Hub > Listings > Active > Export")
        return pd.DataFrame()
    
    latest_file = max(listing_files, key=os.path.getmtime)
    print(f"Using manual export: {os.path.basename(latest_file)}")
    
    # Load based on file type
    if latest_file.endswith('.xlsx'):
        df = pd.read_excel(latest_file)
    else:
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(latest_file, encoding=encoding)
                break
            except:
                continue
    
    print(f"Loaded {len(df)} listings")
    return df

def extract_keywords_from_title(title):
    """Extract potential keywords from a listing title."""
    if pd.isna(title):
        return []
    
    title = str(title).lower()
    
    # Remove common stop words and punctuation
    stop_words = {'for', 'the', 'and', 'with', 'new', 'oem', 'fits', 'fit', 'set', 'kit', 'pair'}
    
    # Extract brand/model patterns
    keywords = []
    
    # Look for year ranges (e.g., 2019-2024)
    year_patterns = re.findall(r'\b(19|20)\d{2}[-–](19|20)\d{2}\b', title)
    keywords.extend(year_patterns)
    
    # Look for single years
    single_years = re.findall(r'\b(19|20)\d{2}\b', title)
    keywords.extend(single_years)
    
    # Look for car makes/models
    car_brands = ['honda', 'toyota', 'ford', 'chevrolet', 'chevy', 'gmc', 'dodge', 'ram', 
                  'nissan', 'mazda', 'subaru', 'volkswagen', 'vw', 'bmw', 'mercedes', 'audi',
                  'jeep', 'chrysler', 'buick', 'cadillac', 'lincoln', 'hyundai', 'kia']
    
    for brand in car_brands:
        if brand in title:
            # Try to get brand + model
            pattern = rf'{brand}\s+\w+'
            matches = re.findall(pattern, title)
            keywords.extend(matches)
            keywords.append(brand)
    
    # Look for product types
    product_types = ['brake', 'hood', 'deflector', 'camera', 'case', 'waterproof', 'trim',
                    'headliner', 'mirror', 'light', 'filter', 'sensor', 'switch', 'cover']
    
    for product in product_types:
        if product in title:
            keywords.append(product)
            # Try to get product + descriptor
            pattern = rf'{product}\s+\w+'
            matches = re.findall(pattern, title)
            keywords.extend(matches)
    
    # Clean up and deduplicate
    keywords = [k.strip() for k in keywords if k.strip() and k.strip() not in stop_words]
    return list(set(keywords))

def analyze_listing_performance(listings_df):
    """Analyze listing performance metrics if available."""
    performance_cols = ['Views', 'Watchers', 'Sold', 'Available', 'Price']
    
    # Check which performance columns exist
    available_cols = [col for col in performance_cols if col in listings_df.columns]
    
    if not available_cols:
        print("No performance metrics found in listings data")
        return listings_df
    
    # Calculate performance score
    if 'Views' in listings_df.columns:
        listings_df['view_score'] = pd.to_numeric(listings_df['Views'], errors='coerce').fillna(0)
    
    if 'Watchers' in listings_df.columns:
        listings_df['watcher_score'] = pd.to_numeric(listings_df['Watchers'], errors='coerce').fillna(0)
    
    if 'Sold' in listings_df.columns:
        listings_df['sold_score'] = pd.to_numeric(listings_df['Sold'], errors='coerce').fillna(0)
    
    return listings_df

def find_opportunities(current_keywords, listings_df):
    """Find listings/keywords not in campaign but with high potential."""
    opportunities = []
    
    title_col = None
    for col in ['Title', 'title', 'Custom label (SKU)', 'Item title', 'Product Name']:
        if col in listings_df.columns:
            title_col = col
            break
    
    if not title_col:
        print("Could not find title column in listings data")
        return pd.DataFrame()
    
    print(f"Analyzing {len(listings_df)} listings for opportunities...")
    
    for idx, row in listings_df.iterrows():
        title = row.get(title_col, '')
        if pd.isna(title):
            continue
        
        # Extract potential keywords from title
        potential_keywords = extract_keywords_from_title(title)
        
        # Find keywords not in campaign
        new_keywords = [k for k in potential_keywords if k.lower() not in current_keywords]
        
        if new_keywords:
            opportunity = {
                'Title': title[:100],  # Truncate for readability
                'Suggested Keywords': ', '.join(new_keywords[:5]),  # Top 5 suggestions
                'Keyword Count': len(new_keywords),
                'Item ID': row.get('Item ID', row.get('ItemID', 'N/A')),
                'Price': row.get('Price', row.get('Start price', 'N/A')),
                'Views': row.get('Views', 0),
                'Watchers': row.get('Watchers', 0),
                'Sold': row.get('Sold', 0)
            }
            opportunities.append(opportunity)
    
    if not opportunities:
        return pd.DataFrame()
    
    opp_df = pd.DataFrame(opportunities)
    
    # Calculate opportunity score
    opp_df['Score'] = 0
    if 'Views' in opp_df.columns:
        opp_df['Score'] += pd.to_numeric(opp_df['Views'], errors='coerce').fillna(0) * 0.1
    if 'Watchers' in opp_df.columns:
        opp_df['Score'] += pd.to_numeric(opp_df['Watchers'], errors='coerce').fillna(0) * 2
    if 'Sold' in opp_df.columns:
        opp_df['Score'] += pd.to_numeric(opp_df['Sold'], errors='coerce').fillna(0) * 5
    opp_df['Score'] += opp_df['Keyword Count'] * 0.5
    
    # Sort by score
    opp_df = opp_df.sort_values('Score', ascending=False)
    
    return opp_df

def generate_keyword_recommendations(opportunities_df):
    """Generate specific keyword recommendations for campaign."""
    if opportunities_df.empty:
        return pd.DataFrame()
    
    # Aggregate all suggested keywords
    all_keywords = []
    for keywords_str in opportunities_df['Suggested Keywords'].dropna():
        keywords = [k.strip() for k in keywords_str.split(',')]
        all_keywords.extend(keywords)
    
    # Count frequency
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    
    # Create recommendations
    recommendations = []
    for keyword, count in keyword_counts.most_common(50):  # Top 50
        rec = {
            'Keyword': keyword,
            'Match Type': 'BROAD' if len(keyword.split()) > 1 else 'EXACT',
            'Suggested Bid': '$0.50',  # Conservative starting bid
            'Listings Using': count,
            'Priority': 'HIGH' if count > 3 else 'MEDIUM' if count > 1 else 'LOW'
        }
        recommendations.append(rec)
    
    return pd.DataFrame(recommendations)

def main():
    print("=" * 80)
    print("FIND CAMPAIGN EXPANSION OPPORTUNITIES")
    print("=" * 80)
    print()
    
    # Load current campaign keywords
    current_keywords = load_current_campaign_keywords()
    
    # Load active listings
    listings_df = load_active_listings()
    
    if listings_df.empty:
        print("No listings data found. Please export your active listings from eBay Seller Hub:")
        print("1. Go to Listings > Active")
        print("2. Click 'Export'")
        print("3. Save to Downloads folder")
        return
    
    # Find opportunities
    opportunities = find_opportunities(current_keywords, listings_df)
    
    if opportunities.empty:
        print("No new opportunities found. Your campaign may already include all relevant keywords.")
        return
    
    print(f"\nFound {len(opportunities)} listings with keyword opportunities")
    
    # Generate keyword recommendations
    keyword_recs = generate_keyword_recommendations(opportunities)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed opportunities
    opp_file = f"campaign_opportunities_{timestamp}.csv"
    opportunities.to_csv(opp_file, index=False)
    print(f"\nDetailed opportunities saved to: {opp_file}")
    
    # Save keyword recommendations
    if not keyword_recs.empty:
        keyword_file = f"new_keywords_to_add_{timestamp}.csv"
        keyword_recs.to_csv(keyword_file, index=False)
        print(f"Keyword recommendations saved to: {keyword_file}")
        
        # Display top recommendations
        print("\n" + "=" * 80)
        print("TOP 10 KEYWORD RECOMMENDATIONS TO ADD:")
        print("=" * 80)
        
        for idx, row in keyword_recs.head(10).iterrows():
            print(f"\n{idx + 1}. {row['Keyword']}")
            print(f"   Match Type: {row['Match Type']}")
            print(f"   Suggested Bid: {row['Suggested Bid']}")
            print(f"   Found in {row['Listings Using']} listings")
            print(f"   Priority: {row['Priority']}")
    
    print("\n" + "=" * 80)
    print("HOW TO ADD THESE KEYWORDS TO YOUR CAMPAIGN:")
    print("=" * 80)
    print("1. Go to eBay Seller Hub > Marketing > Advertising Dashboard")
    print("2. Click 'Top Converters Test' campaign")
    print("3. Go to 'Keywords' tab")
    print("4. Click 'Add keywords'")
    print("5. Copy keywords from new_keywords_to_add_*.csv")
    print("6. Set match types and bids as recommended")
    
    # Open the files
    os.startfile(opp_file)
    if not keyword_recs.empty:
        os.startfile(keyword_file)

if __name__ == "__main__":
    main()