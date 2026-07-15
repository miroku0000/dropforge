"""
Analyze Top Converters campaign reports from eBay.
Processes Keyword, Listing, and Search Query reports to provide insights.
"""

import os
import glob
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def find_latest_top_converters_reports(downloads_dir=None):
    """
    Find the latest Top Converters Test reports in the downloads directory.
    
    Returns:
        dict: Dictionary with paths to keyword, listing, and search_query reports
    """
    if downloads_dir is None:
        downloads_dir = os.path.expanduser('~/Downloads')
    
    reports = {
        'keyword': None,
        'listing': None,
        'search_query': None
    }
    
    # Find all Top Converters Test files
    pattern = os.path.join(downloads_dir, 'Top Converters Test*.csv')
    files = glob.glob(pattern)
    
    for file_path in files:
        filename = os.path.basename(file_path)
        if 'Keyword' in filename:
            reports['keyword'] = file_path
        elif 'Listing' in filename:
            reports['listing'] = file_path
        elif 'Search-query' in filename:
            reports['search_query'] = file_path
    
    return reports

def parse_top_converters_report(csv_path, report_type):
    """
    Parse a Top Converters report CSV file.
    
    Args:
        csv_path: Path to CSV file
        report_type: Type of report ('keyword', 'listing', or 'search_query')
    
    Returns:
        pandas.DataFrame: Parsed report data
    """
    # Skip the warning row and read the actual data
    df = pd.read_csv(csv_path, skiprows=1)
    
    # Convert currency columns to numeric
    currency_columns = ['Bid', 'Average cost per click', 'Average cost per sale', 
                       'Ad fees', 'Sales', 'Price (Current or Last Price)', 'Keyword Bid']
    
    for col in currency_columns:
        if col in df.columns:
            df[col] = df[col].replace('[\$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convert percentage columns
    pct_columns = ['CTR', 'Conversion rate (Total Quantity Sold/Clicks)']
    for col in pct_columns:
        if col in df.columns:
            df[col] = df[col].str.replace('%', '').astype(float) / 100
    
    # Convert numeric columns
    numeric_columns = ['Impressions', 'Clicks', 'Sold quantity', 'Total sold quantity',
                      'Quantity available', 'Return on Ad spend']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def analyze_keyword_performance(keyword_df):
    """Analyze keyword-level performance metrics."""
    print("\n" + "="*80)
    print("KEYWORD PERFORMANCE ANALYSIS")
    print("="*80)
    
    # Filter for active keywords with impressions
    active_keywords = keyword_df[keyword_df['Status'] == 'ACTIVE'].copy()
    
    # Calculate totals
    total_impressions = active_keywords['Impressions'].sum()
    total_clicks = active_keywords['Clicks'].sum()
    total_sales = active_keywords['Sales'].sum()
    total_ad_fees = active_keywords['Ad fees'].sum()
    total_sold = active_keywords['Sold quantity'].sum()
    
    print(f"\nCampaign Totals:")
    print(f"  Total Keywords: {len(active_keywords)}")
    print(f"  Total Impressions: {total_impressions:,}")
    print(f"  Total Clicks: {total_clicks}")
    print(f"  Total Sales: ${total_sales:.2f}")
    print(f"  Total Ad Fees: ${total_ad_fees:.2f}")
    print(f"  Overall CTR: {(total_clicks/total_impressions*100):.2f}%" if total_impressions > 0 else "  Overall CTR: N/A")
    print(f"  Overall ROAS: {(total_sales/total_ad_fees):.2f}x" if total_ad_fees > 0 else "  Overall ROAS: N/A")
    
    # Keywords with clicks
    clicked_keywords = active_keywords[active_keywords['Clicks'] > 0].sort_values('Clicks', ascending=False)
    
    if not clicked_keywords.empty:
        print(f"\nTop Keywords by Clicks:")
        for _, row in clicked_keywords.head(10).iterrows():
            ctr = (row['Clicks']/row['Impressions']*100) if row['Impressions'] > 0 else 0
            print(f"  {row['Seller Keyword']:<30} ({row['Keyword Match Type']:<7}): "
                  f"{row['Clicks']} clicks, {row['Impressions']} impr, {ctr:.1f}% CTR")
    
    # Keywords with impressions but no clicks
    no_clicks = active_keywords[(active_keywords['Impressions'] > 0) & (active_keywords['Clicks'] == 0)]
    if not no_clicks.empty:
        print(f"\nKeywords with Impressions but No Clicks ({len(no_clicks)} keywords):")
        for _, row in no_clicks.sort_values('Impressions', ascending=False).head(5).iterrows():
            print(f"  {row['Seller Keyword']:<30}: {row['Impressions']} impressions")
    
    # Match type performance
    print("\nPerformance by Match Type:")
    match_types = active_keywords.groupby('Keyword Match Type').agg({
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Sold quantity': 'sum',
        'Ad fees': 'sum',
        'Sales': 'sum'
    })
    
    for match_type, row in match_types.iterrows():
        ctr = (row['Clicks']/row['Impressions']*100) if row['Impressions'] > 0 else 0
        roas = (row['Sales']/row['Ad fees']) if row['Ad fees'] > 0 else 0
        print(f"  {match_type:<10}: {row['Impressions']:>6} impr, {row['Clicks']:>3} clicks, "
              f"{ctr:>5.1f}% CTR, ${row['Ad fees']:>7.2f} spend, {roas:>5.1f}x ROAS")
    
    return clicked_keywords

def analyze_listing_performance(listing_df):
    """Analyze listing-level performance metrics."""
    print("\n" + "="*80)
    print("LISTING PERFORMANCE ANALYSIS")
    print("="*80)
    
    # Filter for active listings
    active_listings = listing_df[listing_df['Status'] == 'ACTIVE'].copy()
    
    # Listings with clicks
    clicked_listings = active_listings[active_listings['Clicks'] > 0].sort_values('Clicks', ascending=False)
    
    if not clicked_listings.empty:
        print(f"\nTop Listings by Clicks:")
        for _, row in clicked_listings.head(10).iterrows():
            ctr = (row['Clicks']/row['Impressions']*100) if row['Impressions'] > 0 else 0
            title_short = row['Title'][:60] + '...' if len(row['Title']) > 60 else row['Title']
            print(f"  {row['Item ID']}: {title_short}")
            print(f"    Price: ${row['Price (Current or Last Price)']:.2f}, "
                  f"{row['Clicks']} clicks, {row['Impressions']} impr, {ctr:.1f}% CTR")
            if row['Sold quantity'] > 0:
                print(f"    SOLD {row['Sold quantity']} units! Cost per sale: ${row['Average cost per sale']:.2f}")
    
    # Listings with high impressions but no clicks
    no_click_listings = active_listings[(active_listings['Impressions'] >= 50) & (active_listings['Clicks'] == 0)]
    if not no_click_listings.empty:
        print(f"\nListings with High Impressions but No Clicks:")
        for _, row in no_click_listings.sort_values('Impressions', ascending=False).head(5).iterrows():
            title_short = row['Title'][:60] + '...' if len(row['Title']) > 60 else row['Title']
            print(f"  {row['Item ID']}: {row['Impressions']} impressions")
            print(f"    ${row['Price (Current or Last Price)']:.2f} - {title_short}")
    
    # Ad group performance
    print("\nPerformance by Ad Group:")
    ad_groups = active_listings.groupby('Ad Group Name').agg({
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Sold quantity': 'sum',
        'Ad fees': 'sum',
        'Sales': 'sum'
    }).sort_values('Clicks', ascending=False)
    
    for ad_group, row in ad_groups.head(10).iterrows():
        ctr = (row['Clicks']/row['Impressions']*100) if row['Impressions'] > 0 else 0
        roas = (row['Sales']/row['Ad fees']) if row['Ad fees'] > 0 else 0
        group_short = ad_group[:40] + '...' if len(ad_group) > 40 else ad_group
        print(f"  {group_short:<42}: {row['Impressions']:>5} impr, {row['Clicks']:>3} clicks, "
              f"{ctr:>5.1f}% CTR")
    
    return clicked_listings

def analyze_search_queries(search_query_df):
    """Analyze actual search queries that triggered ads."""
    print("\n" + "="*80)
    print("SEARCH QUERY ANALYSIS")
    print("="*80)
    
    # Group by search query
    query_performance = search_query_df.groupby('Search Query').agg({
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Sold quantity': 'sum',
        'Ad fees': 'sum',
        'Sales': 'sum'
    }).sort_values('Impressions', ascending=False)
    
    # Queries with clicks
    clicked_queries = query_performance[query_performance['Clicks'] > 0].sort_values('Clicks', ascending=False)
    
    if not clicked_queries.empty:
        print(f"\nTop Search Queries by Clicks:")
        for query, row in clicked_queries.head(10).iterrows():
            ctr = (row['Clicks']/row['Impressions']*100) if row['Impressions'] > 0 else 0
            print(f"  '{query}':")
            print(f"    {row['Clicks']} clicks from {row['Impressions']} impressions ({ctr:.1f}% CTR)")
            if row['Sold quantity'] > 0:
                print(f"    CONVERTED! {row['Sold quantity']} sales, ${row['Sales']:.2f} revenue")
    
    # Queries with impressions but no clicks
    no_click_queries = query_performance[(query_performance['Impressions'] > 0) & (query_performance['Clicks'] == 0)]
    
    if len(no_click_queries) > 0:
        print(f"\nQueries with Impressions but No Clicks ({len(no_click_queries)} queries):")
        for query, row in no_click_queries.head(5).iterrows():
            print(f"  '{query}': {row['Impressions']} impressions")
    
    # Misspellings and variations
    print("\nPotential Query Issues (misspellings or unexpected variations):")
    for _, row in search_query_df.iterrows():
        search_query = str(row['Search Query']) if pd.notna(row['Search Query']) else ''
        seller_keyword = str(row['Seller Keyword']) if pd.notna(row['Seller Keyword']) else ''
        
        if search_query and seller_keyword and search_query != seller_keyword:
            # Check for potential misspellings or significant variations
            if 'watrproof' in search_query or 'waterpoof' in search_query:
                print(f"  Misspelling: '{search_query}' triggered by keyword '{seller_keyword}'")
    
    return query_performance

def generate_recommendations(keyword_df, listing_df, search_query_df):
    """Generate actionable recommendations based on the analysis."""
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    recommendations = []
    
    # 1. Keywords with high impressions but no clicks
    high_impr_no_clicks = keyword_df[(keyword_df['Impressions'] >= 10) & (keyword_df['Clicks'] == 0)]
    if len(high_impr_no_clicks) > 0:
        recommendations.append(f"1. Review {len(high_impr_no_clicks)} keywords with impressions but no clicks - consider pausing or adjusting bids")
        for _, row in high_impr_no_clicks.head(3).iterrows():
            print(f"   - '{row['Seller Keyword']}' ({row['Keyword Match Type']}): {row['Impressions']} impressions")
    
    # 2. Check for bid optimization opportunities
    active_keywords = keyword_df[keyword_df['Status'] == 'ACTIVE']
    if len(active_keywords) > 0:
        avg_bid = active_keywords['Bid'].mean()
        if avg_bid == 0.50:  # All at default
            recommendations.append("2. All keywords are at $0.50 bid - consider testing bid adjustments for top performers")
    
    # 3. Listings needing attention
    active_listings = listing_df[listing_df['Status'] == 'ACTIVE']
    high_price_no_clicks = active_listings[(active_listings['Price (Current or Last Price)'] > 200) & 
                                          (active_listings['Clicks'] == 0) & 
                                          (active_listings['Impressions'] > 20)]
    if len(high_price_no_clicks) > 0:
        recommendations.append(f"3. {len(high_price_no_clicks)} high-priced items (>${200}) have impressions but no clicks - review pricing")
    
    # 4. Match type recommendations
    match_type_perf = keyword_df.groupby('Keyword Match Type')['CTR'].mean()
    best_match_type = match_type_perf.idxmax() if not match_type_perf.empty else None
    if best_match_type:
        recommendations.append(f"4. {best_match_type} match type has best CTR - consider adding more {best_match_type} keywords")
    
    # 5. Ad group optimization
    listing_groups = listing_df.groupby('Ad Group Name')['Clicks'].sum()
    zero_click_groups = listing_groups[listing_groups == 0]
    if len(zero_click_groups) > 0:
        recommendations.append(f"5. {len(zero_click_groups)} ad groups have zero clicks - consider pausing or restructuring")
    
    # Print recommendations
    if recommendations:
        for rec in recommendations:
            print(f"\n{rec}")
    else:
        print("\nNo specific recommendations at this time - campaign just started")
    
    return recommendations

def save_daily_summary(reports_data, output_dir=None):
    """Save a daily summary of the campaign performance."""
    if output_dir is None:
        output_dir = os.getcwd()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = os.path.join(output_dir, f'top_converters_summary_{timestamp}.txt')
    
    with open(summary_file, 'w') as f:
        f.write(f"Top Converters Campaign Summary\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        # Add key metrics
        if 'keyword_metrics' in reports_data:
            metrics = reports_data['keyword_metrics']
            f.write("Overall Performance:\n")
            f.write(f"  Total Impressions: {metrics['impressions']:,}\n")
            f.write(f"  Total Clicks: {metrics['clicks']}\n")
            f.write(f"  Total Sales: ${metrics['sales']:.2f}\n")
            f.write(f"  Total Ad Spend: ${metrics['ad_fees']:.2f}\n")
            f.write(f"  ROAS: {metrics['roas']:.2f}x\n\n")
        
        if 'recommendations' in reports_data:
            f.write("Key Recommendations:\n")
            for rec in reports_data['recommendations']:
                f.write(f"  - {rec}\n")
    
    print(f"\nSummary saved to: {summary_file}")
    return summary_file

def main():
    """Main analysis function."""
    print("="*80)
    print("TOP CONVERTERS CAMPAIGN ANALYSIS")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Find latest reports
    print("\nFinding Top Converters reports...")
    reports = find_latest_top_converters_reports()
    
    # Check what reports we found
    found_reports = []
    for report_type, path in reports.items():
        if path:
            print(f"  Found {report_type} report: {os.path.basename(path)}")
            found_reports.append(report_type)
        else:
            print(f"  No {report_type} report found")
    
    if not found_reports:
        print("\nNo Top Converters Test reports found in Downloads directory!")
        return
    
    # Parse available reports
    keyword_df = None
    listing_df = None
    search_query_df = None
    
    if reports['keyword']:
        keyword_df = parse_top_converters_report(reports['keyword'], 'keyword')
        print(f"\nLoaded keyword report: {len(keyword_df)} keywords")
    
    if reports['listing']:
        listing_df = parse_top_converters_report(reports['listing'], 'listing')
        print(f"Loaded listing report: {len(listing_df)} listings")
    
    if reports['search_query']:
        search_query_df = parse_top_converters_report(reports['search_query'], 'search_query')
        print(f"Loaded search query report: {len(search_query_df)} queries")
    
    # Perform analysis
    reports_data = {}
    
    if keyword_df is not None:
        clicked_keywords = analyze_keyword_performance(keyword_df)
        
        # Store metrics for summary
        active_keywords = keyword_df[keyword_df['Status'] == 'ACTIVE']
        reports_data['keyword_metrics'] = {
            'impressions': active_keywords['Impressions'].sum(),
            'clicks': active_keywords['Clicks'].sum(),
            'sales': active_keywords['Sales'].sum(),
            'ad_fees': active_keywords['Ad fees'].sum(),
            'roas': (active_keywords['Sales'].sum() / active_keywords['Ad fees'].sum()) 
                    if active_keywords['Ad fees'].sum() > 0 else 0
        }
    
    if listing_df is not None:
        clicked_listings = analyze_listing_performance(listing_df)
    
    if search_query_df is not None:
        query_performance = analyze_search_queries(search_query_df)
    
    # Generate recommendations
    if keyword_df is not None and listing_df is not None:
        recommendations = generate_recommendations(
            keyword_df if keyword_df is not None else pd.DataFrame(),
            listing_df if listing_df is not None else pd.DataFrame(),
            search_query_df if search_query_df is not None else pd.DataFrame()
        )
        reports_data['recommendations'] = recommendations
    
    # Save summary
    save_daily_summary(reports_data)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    # Campaign is very new (started March 2, 2026)
    print("\nNote: Campaign started on March 2, 2026 - very limited data so far")
    print("Continue monitoring daily as data accumulates")

if __name__ == "__main__":
    main()