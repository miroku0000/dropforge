"""
Analyze eBay Promoted Offsite Ads campaign performance.
Tracks Google Shopping and other external traffic sources.
"""

import os
import glob
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def find_promoted_offsite_reports(downloads_dir=None):
    """
    Find Promoted Offsite campaign reports in downloads directory.
    
    Returns:
        list: Paths to found reports
    """
    if downloads_dir is None:
        downloads_dir = os.path.expanduser('~/Downloads')
    
    # Look for various possible report names (case-insensitive)
    patterns = [
        'Promoted*[Oo]ffsite*.csv',
        'Promoted*offsite*.csv',
        'eBay*Offsite*.csv',
        'Google*Shopping*.csv',
        '*External*Traffic*.csv',
        '*Offsite*Campaign*.csv'
    ]
    
    reports = []
    for pattern in patterns:
        full_pattern = os.path.join(downloads_dir, pattern)
        found_files = glob.glob(full_pattern)
        reports.extend(found_files)
    
    # Remove duplicates and sort by modification time
    reports = list(set(reports))
    reports.sort(key=os.path.getmtime, reverse=True)
    
    return reports

def parse_promoted_offsite_report(report_path):
    """
    Parse the Promoted Offsite report CSV.
    
    Args:
        report_path: Path to the CSV report
    
    Returns:
        pandas.DataFrame: Parsed report data
    """
    # Skip the first 2 rows (warning message and blank line)
    df = pd.read_csv(report_path, skiprows=2)
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    
    # Clean up currency columns
    currency_columns = ['Price (Current or Last Price)', 'Ad fees', 'Sales', 'Average cost per click']
    for col in currency_columns:
        if col in df.columns:
            # Remove $ and convert to float
            df[col] = df[col].str.replace('$', '').str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Clean up percentage columns
    pct_columns = ['CTR', 'Conversion rate (Sold quantity/Clicks)', 'Return on Ad spend(Sales/Ad fees)']
    for col in pct_columns:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.replace('%', '').astype(float) / 100
    
    # Convert numeric columns
    numeric_columns = ['Impressions', 'Clicks', 'Sold quantity', 'Quantity available']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def calculate_promoted_offsite_roi(budget_used, sales_generated, clicks, conversions):
    """
    Calculate ROI metrics for Promoted Offsite campaign.
    
    Args:
        budget_used: Amount spent from the $100 credit
        sales_generated: Total sales value from offsite traffic
        clicks: Number of clicks from external sources
        conversions: Number of sales from offsite traffic
    
    Returns:
        dict: ROI metrics
    """
    metrics = {
        'budget_used': budget_used,
        'budget_remaining': 100 - budget_used,  # From $100 credit
        'sales': sales_generated,
        'clicks': clicks,
        'conversions': conversions,
        'cpc': budget_used / clicks if clicks > 0 else 0,
        'conversion_rate': (conversions / clicks * 100) if clicks > 0 else 0,
        'roas': sales_generated / budget_used if budget_used > 0 else 0,
        'profit': sales_generated - budget_used,
        'cost_per_sale': budget_used / conversions if conversions > 0 else 0
    }
    
    return metrics

def track_credit_usage(daily_budget=5, campaign_start_date=None):
    """
    Track usage of the $100 promotional credit.
    
    Args:
        daily_budget: Daily budget in dollars
        campaign_start_date: Campaign start date
    
    Returns:
        dict: Credit tracking information
    """
    if campaign_start_date is None:
        campaign_start_date = datetime(2026, 3, 3)  # Today's date based on context
    
    days_elapsed = (datetime.now() - campaign_start_date).days
    max_spend = min(daily_budget * days_elapsed, 100)  # Cap at $100 credit
    
    tracking = {
        'total_credit': 100,
        'daily_budget': daily_budget,
        'days_elapsed': days_elapsed,
        'theoretical_spend': daily_budget * days_elapsed,
        'max_possible_spend': max_spend,
        'days_remaining': (100 / daily_budget) - days_elapsed if days_elapsed * daily_budget < 100 else 0,
        'credit_exhaustion_date': campaign_start_date + timedelta(days=100/daily_budget)
    }
    
    return tracking

def analyze_offsite_sources(df):
    """
    Analyze performance by external traffic source.
    """
    print("\n" + "="*80)
    print("PROMOTED OFFSITE PERFORMANCE BY SOURCE")
    print("="*80)
    
    # Common offsite sources
    sources = {
        'Google Shopping': ['google', 'shopping'],
        'Facebook': ['facebook', 'fb', 'meta'],
        'Instagram': ['instagram', 'ig'],
        'Pinterest': ['pinterest'],
        'Bing': ['bing', 'microsoft'],
        'Other': []
    }
    
    # Try to identify source columns in the data
    source_columns = [col for col in df.columns if 'source' in col.lower() or 
                      'channel' in col.lower() or 'referrer' in col.lower()]
    
    if source_columns:
        print(f"\nFound source tracking in columns: {source_columns}")
        # Analyze by source if available
        for col in source_columns:
            if col in df.columns:
                source_stats = df.groupby(col).agg({
                    'Clicks': 'sum',
                    'Impressions': 'sum',
                    'Sales': 'sum',
                    'Ad fees': 'sum'
                }).sort_values('Clicks', ascending=False)
                
                print(f"\nPerformance by {col}:")
                for source, stats in source_stats.head(5).iterrows():
                    ctr = (stats['Clicks']/stats['Impressions']*100) if stats['Impressions'] > 0 else 0
                    roas = (stats['Sales']/stats['Ad fees']) if stats['Ad fees'] > 0 else 0
                    print(f"  {source}: {stats['Clicks']} clicks, ${stats['Sales']:.2f} sales, {roas:.2f}x ROAS")
    else:
        print("\nNo source breakdown available in current report")
        print("Google Shopping is typically the primary source for Promoted Offsite Ads")

def generate_offsite_recommendations(metrics, tracking):
    """
    Generate recommendations for Promoted Offsite campaign.
    """
    print("\n" + "="*80)
    print("PROMOTED OFFSITE RECOMMENDATIONS")
    print("="*80)
    
    recommendations = []
    
    # Credit usage recommendations
    if tracking['days_remaining'] > 0:
        recommendations.append(f"You have {tracking['days_remaining']:.0f} days of free credit remaining")
        recommendations.append(f"Credit will be exhausted on {tracking['credit_exhaustion_date'].strftime('%Y-%m-%d')}")
    
    # Performance-based recommendations
    if metrics['roas'] > 3:
        recommendations.append("Excellent ROAS! Consider increasing budget after free credit expires")
    elif metrics['roas'] > 1.5:
        recommendations.append("Good performance. Monitor which product categories perform best")
    elif metrics['roas'] < 1:
        recommendations.append("ROAS below 1. Review product pricing and competitiveness on Google Shopping")
    
    # Conversion rate insights
    if metrics['conversion_rate'] < 1:
        recommendations.append(f"Low conversion rate ({metrics['conversion_rate']:.1f}%). Consider:")
        recommendations.append("  - Ensure pricing is competitive with other Google Shopping results")
        recommendations.append("  - Improve product images (first image is crucial for Google)")
        recommendations.append("  - Add more product identifiers (GTIN, MPN, Brand)")
    
    # Click cost analysis
    if metrics['cpc'] > 1:
        recommendations.append(f"High CPC (${metrics['cpc']:.2f}). Focus on products with higher margins")
    
    # Budget optimization
    if metrics['roas'] > 2 and tracking['days_remaining'] < 10:
        recommendations.append("Strong performance + credit ending soon. Plan your post-credit strategy")
    
    for rec in recommendations:
        print(f"\n* {rec}")
    
    return recommendations

def create_offsite_dashboard():
    """
    Create a simple dashboard summary for Promoted Offsite campaign.
    """
    print("\n" + "="*80)
    print("PROMOTED OFFSITE DASHBOARD")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Track credit usage
    tracking = track_credit_usage(daily_budget=5)
    
    print("\n[CREDIT STATUS]")
    print(f"  Total Credit: ${tracking['total_credit']}")
    print(f"  Daily Budget: ${tracking['daily_budget']}")
    print(f"  Days Active: {tracking['days_elapsed']}")
    print(f"  Max Spend So Far: ${tracking['max_possible_spend']:.2f}")
    print(f"  Days Remaining: {tracking['days_remaining']:.0f}")
    print(f"  Credit Expires: {tracking['credit_exhaustion_date'].strftime('%Y-%m-%d')}")
    
    print("\n[CAMPAIGN GOALS]")
    print("  Primary Goal: Test product performance on Google Shopping")
    print("  Secondary Goal: Identify high-converting products for future investment")
    print("  Budget Strategy: Use full $100 credit at $5/day")
    
    print("\n[KEY METRICS TO WATCH]")
    print("  1. ROAS (Return on Ad Spend) - Target: >2.0x")
    print("  2. Conversion Rate - Target: >2%")
    print("  3. Cost Per Click - Target: <$0.50")
    print("  4. Best Performing Categories")
    print("  5. Time of Day/Day of Week patterns")
    
    print("\n[OPTIMIZATION TIPS]")
    print("  * Google Shopping favors products with:")
    print("    - Competitive pricing")
    print("    - High-quality main image")
    print("    - Complete product identifiers (GTIN/UPC)")
    print("    - Detailed titles with key attributes")
    print("    - Free or fast shipping")
    
    return tracking

def save_offsite_summary(metrics, tracking, output_dir=None):
    """
    Save Promoted Offsite campaign summary.
    """
    if output_dir is None:
        output_dir = os.getcwd()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = os.path.join(output_dir, f'promoted_offsite_summary_{timestamp}.txt')
    
    with open(summary_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write("PROMOTED OFFSITE CAMPAIGN SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        
        f.write("CREDIT USAGE\n")
        f.write(f"  Budget Used: ${metrics.get('budget_used', 0):.2f}\n")
        f.write(f"  Credit Remaining: ${tracking['total_credit'] - metrics.get('budget_used', 0):.2f}\n")
        f.write(f"  Days Remaining: {tracking['days_remaining']:.0f}\n\n")
        
        f.write("PERFORMANCE METRICS\n")
        f.write(f"  Total Sales: ${metrics.get('sales', 0):.2f}\n")
        f.write(f"  Total Clicks: {metrics.get('clicks', 0)}\n")
        f.write(f"  Conversions: {metrics.get('conversions', 0)}\n")
        f.write(f"  ROAS: {metrics.get('roas', 0):.2f}x\n")
        f.write(f"  Conversion Rate: {metrics.get('conversion_rate', 0):.1f}%\n")
        f.write(f"  Avg CPC: ${metrics.get('cpc', 0):.2f}\n\n")
        
        f.write("STATUS\n")
        if metrics.get('roas', 0) > 2:
            f.write("  [OK] Campaign performing well - consider continuing after credit\n")
        elif metrics.get('roas', 0) > 1:
            f.write("  [WARN] Moderate performance - optimize before investing own funds\n")
        else:
            f.write("  [FAIL] Below break-even - review pricing and competition\n")
    
    print(f"\nSummary saved to: {summary_file}")
    return summary_file

def main():
    """
    Main analysis function for Promoted Offsite campaign.
    """
    print("="*80)
    print("PROMOTED OFFSITE ADS ANALYSIS")
    print("Campaign: $100 Free Credit at $5/day")
    print("="*80)
    
    # Create dashboard first
    tracking = create_offsite_dashboard()
    
    # Look for reports
    print("\n" + "="*80)
    print("SEARCHING FOR REPORTS")
    print("="*80)
    
    reports = find_promoted_offsite_reports()
    
    if reports:
        print(f"\nFound Promoted Offsite report: {os.path.basename(reports[0])}")
        
        # Parse the report
        df = parse_promoted_offsite_report(reports[0])
        print(f"Loaded {len(df)} listings from report")
        
        # Calculate actual metrics from report
        total_clicks = df['Clicks'].sum()
        total_ad_fees = df['Ad fees'].sum()
        total_sales = df['Sales'].sum()
        total_sold = df['Sold quantity'].sum()
        total_impressions = df['Impressions'].sum()
        
        metrics = calculate_promoted_offsite_roi(
            budget_used=total_ad_fees,
            sales_generated=total_sales,
            clicks=total_clicks,
            conversions=total_sold
        )
        
        # Display actual performance
        print("\n" + "="*80)
        print("ACTUAL CAMPAIGN PERFORMANCE")
        print("="*80)
        
        print(f"\n[OVERVIEW]")
        print(f"  Total Listings: {len(df)}")
        print(f"  Active Listings: {len(df[df['Status'] == 'Active'])} / Ended: {len(df[df['Status'] == 'Ended'])}")
        print(f"  Total Impressions: {total_impressions:,}")
        print(f"  Total Clicks: {total_clicks}")
        print(f"  Total Ad Spend: ${total_ad_fees:.2f}")
        print(f"  Total Sales: ${total_sales:.2f}")
        print(f"  Conversions: {total_sold}")
        
        print(f"\n[KEY METRICS]")
        print(f"  ROAS: {metrics['roas']:.2f}x" if metrics['roas'] > 0 else "  ROAS: No sales yet")
        print(f"  CTR: {(total_clicks/total_impressions*100):.2f}%" if total_impressions > 0 else "  CTR: No impressions yet")
        print(f"  Conversion Rate: {metrics['conversion_rate']:.1f}%")
        print(f"  Average CPC: ${metrics['cpc']:.2f}" if metrics['cpc'] > 0 else "  Average CPC: N/A")
        print(f"  Cost per Sale: ${metrics['cost_per_sale']:.2f}" if metrics['cost_per_sale'] > 0 else "  Cost per Sale: No sales yet")
        
        # Top performers by clicks
        if total_clicks > 0:
            top_clicked = df[df['Clicks'] > 0].sort_values('Clicks', ascending=False)
            if not top_clicked.empty:
                print(f"\n[TOP ITEMS BY CLICKS]")
                for _, item in top_clicked.head(5).iterrows():
                    title = item['Title'][:60] + '...' if len(item['Title']) > 60 else item['Title']
                    print(f"  {item['Item ID']}: {item['Clicks']} clicks @ ${item['Average cost per click']:.2f}/click")
                    print(f"    {title}")
                    print(f"    Price: ${item['Price (Current or Last Price)']:.2f}, Sales: {item['Sold quantity']}")
        
        # Items with sales
        sold_items = df[df['Sold quantity'] > 0]
        if not sold_items.empty:
            print(f"\n[ITEMS WITH SALES]")
            for _, item in sold_items.iterrows():
                title = item['Title'][:60] + '...' if len(item['Title']) > 60 else item['Title']
                roas = item['Sales'] / item['Ad fees'] if item['Ad fees'] > 0 else 0
                print(f"  {item['Item ID']}: {item['Sold quantity']} sold, ${item['Sales']:.2f} revenue, {roas:.1f}x ROAS")
                print(f"    {title}")
        
        # Generate recommendations based on actual data
        recommendations = generate_offsite_recommendations(metrics, tracking)
        
        # Save summary with actual metrics
        save_offsite_summary(metrics, tracking)
        
    else:
        print("\nNo Promoted Offsite reports found yet.")
        print("Reports may take 24-48 hours to appear after campaign start.")
        print("\nTo get reports:")
        print("1. Go to eBay Seller Hub > Marketing > Promoted Offsite")
        print("2. Click 'Download Report' or 'View Performance'")
        print("3. Save to Downloads folder")
        print("4. Run this script again")
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Monitor daily for the first week to establish baseline")
    print("2. After 7 days, identify top performing products")
    print("3. Consider pausing poor performers to focus budget")
    print("4. Plan strategy for when free credit expires")
    print("5. Compare ROAS to your other campaigns (Automagical, Top Converters)")

if __name__ == "__main__":
    main()