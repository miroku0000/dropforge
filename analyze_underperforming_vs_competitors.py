"""
Analyze underperforming items (clicks but no sales) by comparing prices to eBay competitors.
This helps determine if pricing is the reason items get clicks but don't convert.
"""

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
from typing import Dict, List, Tuple, Optional
import re

# Import eBay utilities
from ebay_utils import (
    find_latest_traffic_report,
    parse_traffic_report,
    _get_item_details_combined,
    get_item_price,
    search_ebay_competitors
)

def identify_underperformers(traffic_df: pd.DataFrame, min_clicks: int = 1) -> pd.DataFrame:
    """Identify items with clicks but no sales."""
    # Filter for items with clicks but zero sales
    underperformers = traffic_df[
        (traffic_df['Page views'] >= min_clicks) & 
        (traffic_df['Quantity sold'] == 0)
    ].copy()
    
    # Sort by most clicks first (these are most problematic)
    underperformers = underperformers.sort_values('Page views', ascending=False)
    
    return underperformers

def extract_search_terms(title: str) -> str:
    """Extract key search terms from listing title for competitor search."""
    # Remove common eBay fluff words
    fluff_words = ['new', 'free shipping', 'fast ship', 'usa seller', 'authentic', 
                   'genuine', '100%', 'oem', 'original', 'brand new', 'sealed']
    
    title_lower = title.lower()
    for word in fluff_words:
        title_lower = title_lower.replace(word, '')
    
    # Extract brand and key product identifiers
    # Look for patterns like model numbers, part numbers
    patterns = [
        r'\b[A-Z0-9]{2,}[-]?[A-Z0-9]+\b',  # Model numbers like KOE7873
        r'\b\d{4,}\b',  # Long numbers like part numbers
    ]
    
    important_terms = []
    for pattern in patterns:
        matches = re.findall(pattern, title, re.IGNORECASE)
        important_terms.extend(matches)
    
    # Take first few words if we have them
    words = title.split()[:5]
    
    # Combine important terms and first words
    search_query = ' '.join(important_terms[:2] + words[:3])
    
    # Clean up extra spaces
    search_query = ' '.join(search_query.split())
    
    return search_query if search_query else title[:50]

def analyze_competitor_pricing(item_id: str, title: str, current_price: float, 
                             max_competitors: int = 10) -> Dict:
    """Analyze how an item's price compares to eBay competitors."""
    
    print(f"\n  Analyzing: {title[:60]}...")
    print(f"  Current price: ${current_price:.2f}")
    
    # Generate search query from title
    search_query = extract_search_terms(title)
    print(f"  Search query: {search_query}")
    
    # Search for competitors on eBay
    try:
        competitors = search_ebay_competitors(search_query, max_results=max_competitors)
        
        if not competitors:
            print("  No competitors found")
            return {
                'item_id': item_id,
                'title': title,
                'current_price': current_price,
                'competitor_count': 0,
                'price_percentile': None,
                'avg_competitor_price': None,
                'min_competitor_price': None,
                'price_difference': None,
                'recommendation': 'No competitor data available'
            }
        
        # Extract competitor prices
        competitor_prices = []
        for comp in competitors:
            try:
                # Handle different price formats from eBay API
                if 'sellingStatus' in comp:
                    price_info = comp['sellingStatus'][0].get('currentPrice', [{}])[0]
                    price = float(price_info.get('__value__', 0))
                elif 'price' in comp:
                    price = float(comp['price'].get('value', 0))
                else:
                    continue
                    
                if price > 0:
                    competitor_prices.append(price)
            except (KeyError, ValueError, TypeError):
                continue
        
        if not competitor_prices:
            print("  Could not extract competitor prices")
            return {
                'item_id': item_id,
                'title': title,
                'current_price': current_price,
                'competitor_count': len(competitors),
                'price_percentile': None,
                'avg_competitor_price': None,
                'min_competitor_price': None,
                'price_difference': None,
                'recommendation': 'Could not extract competitor prices'
            }
        
        # Calculate statistics
        avg_price = sum(competitor_prices) / len(competitor_prices)
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        
        # Calculate where our price falls in the distribution
        below_ours = sum(1 for p in competitor_prices if p < current_price)
        percentile = (below_ours / len(competitor_prices)) * 100
        
        # Price difference from average
        price_diff_pct = ((current_price - avg_price) / avg_price) * 100
        
        print(f"  Found {len(competitor_prices)} competitors")
        print(f"  Competitor prices: ${min_price:.2f} - ${max_price:.2f} (avg: ${avg_price:.2f})")
        print(f"  Our price percentile: {percentile:.0f}%")
        
        # Generate recommendation
        if percentile > 75:
            recommendation = f"Price too high (top {100-percentile:.0f}% most expensive). Consider reducing to ${avg_price:.2f}"
        elif percentile < 25:
            recommendation = f"Price competitive (bottom {percentile:.0f}%). Issue likely not price-related"
        else:
            recommendation = f"Price in middle range. Minor reduction to ${avg_price*0.95:.2f} may help"
        
        return {
            'item_id': item_id,
            'title': title,
            'current_price': current_price,
            'competitor_count': len(competitor_prices),
            'price_percentile': percentile,
            'avg_competitor_price': avg_price,
            'min_competitor_price': min_price,
            'max_competitor_price': max_price,
            'price_difference_pct': price_diff_pct,
            'recommendation': recommendation
        }
        
    except Exception as e:
        print(f"  Error analyzing competitors: {e}")
        return {
            'item_id': item_id,
            'title': title,
            'current_price': current_price,
            'competitor_count': 0,
            'price_percentile': None,
            'avg_competitor_price': None,
            'min_competitor_price': None,
            'price_difference': None,
            'recommendation': f'Error: {str(e)}'
        }

def main():
    print("=" * 80)
    print("ANALYZING UNDERPERFORMING ITEMS VS EBAY COMPETITORS")
    print("=" * 80)
    
    # Find and parse latest traffic report
    print("\nFinding latest traffic report...")
    report_path = find_latest_traffic_report()
    if not report_path:
        print("No traffic report found!")
        return
    
    print(f"Using report: {os.path.basename(report_path)}")
    traffic_df = parse_traffic_report(report_path)
    
    # Identify underperformers
    print("\nIdentifying underperforming items...")
    underperformers = identify_underperformers(traffic_df)
    
    print(f"Found {len(underperformers)} items with clicks but no sales")
    
    # Limit analysis to top underperformers to avoid too many API calls
    max_analyze = 20
    if len(underperformers) > max_analyze:
        print(f"Analyzing top {max_analyze} items with most clicks...")
        underperformers = underperformers.head(max_analyze)
    
    # Analyze each underperformer
    results = []
    for idx, row in underperformers.iterrows():
        item_id = str(row['Item ID']).strip()
        title = row['Title']
        views = row['Page views']
        
        print(f"\n[{len(results)+1}/{len(underperformers)}] Item {item_id} ({views} views)")
        
        # Get current price from eBay
        try:
            current_price = get_item_price(item_id)
            if current_price == 0:
                print(f"  Could not get item price, skipping")
                continue
                
        except Exception as e:
            print(f"  Error getting item price: {e}")
            continue
        
        # Analyze against competitors
        analysis = analyze_competitor_pricing(item_id, title, current_price)
        analysis['page_views'] = views
        results.append(analysis)
        
        # Be nice to eBay API
        time.sleep(1)
    
    # Create summary report
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    if results:
        # Convert to DataFrame for analysis
        results_df = pd.DataFrame(results)
        
        # Items where price is likely the issue (>75th percentile)
        overpriced = results_df[results_df['price_percentile'] > 75] if 'price_percentile' in results_df.columns else pd.DataFrame()
        
        print(f"\nItems likely overpriced: {len(overpriced)}")
        if not overpriced.empty:
            for _, item in overpriced.iterrows():
                print(f"  - {item['item_id']}: ${item['current_price']:.2f} "
                      f"(avg competitor: ${item['avg_competitor_price']:.2f})")
        
        # Items where price is competitive (<50th percentile)
        competitive = results_df[results_df['price_percentile'] <= 50] if 'price_percentile' in results_df.columns else pd.DataFrame()
        
        print(f"\nItems with competitive pricing: {len(competitive)}")
        if not competitive.empty:
            print("  These items have other issues (photos, description, trust, shipping, etc.)")
            for _, item in competitive.iterrows():
                print(f"  - {item['item_id']}: ${item['current_price']:.2f} "
                      f"({item['price_percentile']:.0f}th percentile)")
        
        # Save detailed results
        output_file = f"underperformer_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        results_df.to_csv(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")
        
        # Overall statistics
        print("\nOVERALL STATISTICS:")
        valid_prices = results_df.dropna(subset=['price_percentile'])
        if not valid_prices.empty:
            print(f"  Average price percentile: {valid_prices['price_percentile'].mean():.0f}%")
            print(f"  Items above 75th percentile: {len(valid_prices[valid_prices['price_percentile'] > 75])}")
            print(f"  Items below 50th percentile: {len(valid_prices[valid_prices['price_percentile'] <= 50])}")
            
            avg_diff = valid_prices['price_difference_pct'].mean()
            if avg_diff > 0:
                print(f"  On average, your prices are {avg_diff:.1f}% ABOVE competitors")
            else:
                print(f"  On average, your prices are {abs(avg_diff):.1f}% BELOW competitors")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()