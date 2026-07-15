"""
Generate a CSV file with bid changes for manual upload to eBay.
This is a fallback when API access is not available.
Supports both 14-day (daily optimization) and 30-day (weekly review) reports.
"""

import os
import pandas as pd
import glob
from datetime import datetime
import datetime as dt

def detect_report_duration(df):
    """Detect if this is a 14-day or 30-day report based on data patterns."""
    # Check the date range if available in the data
    if 'Start date' in df.columns and 'End date' in df.columns:
        try:
            start = pd.to_datetime(df['Start date'].iloc[0])
            end = pd.to_datetime(df['End date'].iloc[0])
            days = (end - start).days
            return days
        except:
            pass
    
    # Fallback: Check today's day
    today = dt.datetime.now()
    is_monday = today.weekday() == 0
    
    # Assume 30-day on Monday, 14-day otherwise
    return 30 if is_monday else 14

def get_adjustment_multipliers(report_days):
    """Get bid adjustment multipliers based on report duration."""
    if report_days >= 30:
        # 30-day report: Use standard adjustments
        return {
            'major_increase': 1.30,
            'moderate_increase': 1.20,
            'small_increase': 1.15,
            'small_decrease': 0.85,
            'moderate_decrease': 0.70,
            'major_decrease': 0.50,
            'aggressive_decrease': 0.35,
            'ctr_threshold_excellent': 0.10,
            'ctr_threshold_good': 0.05,
            'ctr_threshold_decent': 0.03,
            'ctr_threshold_poor': 0.01,
            'min_impressions_for_decision': 20
        }
    else:
        # 14-day report: Use gentler adjustments for daily optimization
        return {
            'major_increase': 1.15,
            'moderate_increase': 1.10,
            'small_increase': 1.08,
            'small_decrease': 0.92,
            'moderate_decrease': 0.85,
            'major_decrease': 0.70,
            'aggressive_decrease': 0.50,
            'ctr_threshold_excellent': 0.10,
            'ctr_threshold_good': 0.05,
            'ctr_threshold_decent': 0.03,
            'ctr_threshold_poor': 0.01,
            'min_impressions_for_decision': 10
        }

def get_latest_keyword_report():
    """Find the latest Top Converters keyword report."""
    for search_dir in [os.path.join(os.getcwd(), 'downloads'), os.path.expanduser('~/Downloads')]:
        pattern = os.path.join(search_dir, 'Top Converters Test_Keyword*.csv')
        files = glob.glob(pattern)
        if files:
            return max(files, key=os.path.getmtime)

    return None

def calculate_bid_changes():
    """Calculate optimal bid changes based on performance."""
    report_file = get_latest_keyword_report()
    
    if not report_file:
        print("[ERROR] No Top Converters keyword report found in Downloads")
        return None
    
    print(f"Using report: {os.path.basename(report_file)}")
    print(f"Report modified: {datetime.fromtimestamp(os.path.getmtime(report_file)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Read the report
    df = pd.read_csv(report_file, skiprows=1)
    
    # Detect report duration and get appropriate multipliers
    report_days = detect_report_duration(df)
    multipliers = get_adjustment_multipliers(report_days)
    print(f"Report duration: {report_days} days - Using {'standard' if report_days >= 30 else 'gentle'} adjustments")
    
    # Clean currency values
    df['Bid'] = df['Bid'].str.replace('$', '').astype(float)
    
    # Check if suggested bid column exists
    has_suggested_bid = 'Suggested Bid' in df.columns
    if has_suggested_bid:
        df['Suggested Bid'] = df['Suggested Bid'].str.replace('$', '').astype(float)
    
    # Filter active keywords
    active_df = df[df['Status'] == 'ACTIVE'].copy()
    
    # Handle duplicate keywords by aggregating their metrics
    # Group by Keyword ID + Keyword + Match Type + Bid to identify true duplicates
    agg_functions = {
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Sold quantity': 'sum',
        'CTR': 'first',  # Take first since it's recalculated anyway
        'Average cost per click': 'first',
        'Conversion rate (Total Quantity Sold/Clicks)': 'first',
        'Ad fees': 'sum',
        'Sales': 'sum'
    }
    
    # Include Suggested Bid if it exists
    if has_suggested_bid:
        agg_functions['Suggested Bid'] = 'first'
    
    # Group and aggregate
    active_df = active_df.groupby(['Keyword ID', 'Seller Keyword', 'Keyword Match Type', 'Bid', 'Status'], 
                                   as_index=False).agg(agg_functions)
    
    # Calculate new bids
    changes = []
    
    for _, row in active_df.iterrows():
        keyword_id = int(row['Keyword ID'])
        keyword = row['Seller Keyword']
        match_type = row['Keyword Match Type']
        current_bid = row['Bid']
        impressions = int(row['Impressions'])
        clicks = int(row['Clicks'])
        sales = int(row.get('Sold quantity', 0))
        
        # Get additional metrics
        ctr = float(row.get('CTR', '0').replace('%', '')) / 100 if pd.notna(row.get('CTR')) else 0
        avg_cpc = float(row.get('Average cost per click', '0').replace('$', '')) if pd.notna(row.get('Average cost per click')) else 0
        conversion_rate = float(row.get('Conversion rate (Total Quantity Sold/Clicks)', '0').replace('%', '')) / 100 if pd.notna(row.get('Conversion rate (Total Quantity Sold/Clicks)')) else 0
        
        # Get suggested bid if available
        suggested_bid = float(row.get('Suggested Bid', 0)) if has_suggested_bid else None
        
        # Skip keywords with insufficient data for 14-day reports
        if report_days < 30 and impressions < multipliers['min_impressions_for_decision']:
            continue
        
        # Performance-based bid strategy with dynamic multipliers
        if sales > 0:
            # Converting keywords - increase aggressively but cap based on profitability
            if conversion_rate > 0.1:  # >10% conversion rate
                new_bid = min(current_bid * 3.0, 2.50)
                action = "INCREASE - HIGH CONVERSION"
            else:
                new_bid = min(current_bid * 2.0, 2.00)
                action = "INCREASE - CONVERTING"
                
        elif clicks > 0:
            # Has clicks but no sales - adjust based on CTR and cost efficiency
            if ctr > multipliers['ctr_threshold_excellent']:  # Excellent CTR
                # Already performing well, maybe increase slightly or maintain
                if current_bid >= 1.50:
                    new_bid = current_bid  # Maintain if already high
                    action = "MAINTAIN - EXCELLENT CTR AT HIGH BID"
                else:
                    new_bid = min(current_bid * multipliers['major_increase'], 2.00)
                    action = "INCREASE - EXCELLENT CTR"
            elif ctr > multipliers['ctr_threshold_good']:  # Good CTR
                if current_bid >= 1.50:
                    new_bid = current_bid  # Maintain if already high
                    action = "MAINTAIN - GOOD CTR AT HIGH BID"
                else:
                    new_bid = min(current_bid * multipliers['moderate_increase'], 1.50)
                    action = "INCREASE - GOOD CTR"
            elif ctr > multipliers['ctr_threshold_decent']:  # Decent CTR
                if current_bid >= 1.50:
                    # Already at high bid, consider reducing slightly if CTR is just decent
                    new_bid = max(current_bid * multipliers['small_decrease'], 1.25)
                    action = "DECREASE - DECENT CTR AT HIGH BID"
                else:
                    new_bid = min(current_bid * multipliers['small_increase'], 1.25)
                    action = "INCREASE - DECENT CTR"
            else:  # Poor CTR
                new_bid = max(current_bid * multipliers['moderate_decrease'], 0.50)
                action = "DECREASE - LOW CTR"
                
        elif impressions > 0:
            # Has impressions but no clicks - bid based on impression volume and current bid efficiency
            impression_efficiency = impressions / max(current_bid * 30, 1)  # Rough impressions per dollar per day
            
            if impressions > 50:
                # High impressions but no clicks - keyword is irrelevant
                # Getting visibility but 0% CTR means wrong audience
                new_bid = 0.05  # Set to minimum to effectively pause
                action = "PAUSE - HIGH IMPRESSIONS NO CLICKS (0% CTR)"
            elif impressions > 20:
                # Moderate impressions but no clicks
                if current_bid >= 1.00:
                    # Reduce bid - not getting clicks at this price
                    if suggested_bid and suggested_bid > 0:
                        # Use eBay's suggested bid if available
                        new_bid = min(suggested_bid, current_bid * multipliers['moderate_decrease'])
                        action = "DECREASE TO SUGGESTED - NO CLICKS AT HIGH BID"
                    else:
                        # Fallback: Drop bid but maintain minimum of $0.45
                        new_bid = max(current_bid * multipliers['moderate_decrease'], 0.45)
                        action = "DECREASE - NO CLICKS AT HIGH BID"
                else:
                    # Small increase to try getting clicks
                    new_bid = min(current_bid * multipliers['small_increase'], 1.00)
                    action = "INCREASE - MODERATE IMPRESSIONS"
            elif current_bid > 0.80:
                # Low impressions with high bid - pause keyword (likely irrelevant)
                new_bid = 0.05  # Set to minimum to effectively pause
                action = "PAUSE - LOW IMPRESSIONS HIGH BID (IRRELEVANT)"
            else:
                # Low impressions with low/medium bid
                if current_bid >= 0.60:
                    # At medium bid but low impressions - try small increase to improve visibility
                    new_bid = min(current_bid * multipliers['small_increase'], 0.90)
                    action = "INCREASE - LOW IMPRESSIONS NEED VISIBILITY"
                else:
                    # Low bid - try increasing more aggressively
                    new_bid = min(current_bid * multipliers['moderate_increase'], 0.80)
                    action = "INCREASE - LOW IMPRESSIONS LOW BID"
        else:
            # No impressions - likely bid too low or keyword irrelevant
            if current_bid < 0.30:
                # Very low bid - try increasing
                new_bid = min(current_bid * 2.0, 0.50)
                action = "INCREASE - VERY LOW BID"
            elif current_bid > 0.75:
                # High bid with no impressions - likely irrelevant keyword
                # Recommend pausing instead of decreasing
                new_bid = 0.05  # Set to minimum to effectively pause
                action = "PAUSE - NO IMPRESSIONS AT HIGH BID (IRRELEVANT)"
            else:
                # Skip - likely not worth adjusting
                continue
        
        # Round to 2 decimal places
        new_bid = round(new_bid, 2)
        
        # Determine if keyword should be paused
        recommend_pause = "PAUSE" in action
        
        # Always add to report to show current status
        changes.append({
            'Keyword ID': keyword_id,
            'Keyword': keyword,
            'Match Type': match_type,
            'Current Bid': f"${current_bid:.2f}",
            'New Bid': f"${new_bid:.2f}" if not recommend_pause else "PAUSE",
            'Change': f"${new_bid - current_bid:+.2f}" if not recommend_pause else "PAUSE",
            'Action': action,
            'Recommended Status': 'PAUSE' if recommend_pause else 'ACTIVE',
            'Impressions': impressions,
            'Clicks': clicks,
            'Sales': sales,
            'CTR': f"{ctr:.2%}" if impressions > 0 else "N/A"
        })
    
    if not changes:
        return None
    
    # Sort by priority (sales > clicks > impressions)
    changes.sort(key=lambda x: (x['Sales'], x['Clicks'], x['Impressions']), reverse=True)
    
    return pd.DataFrame(changes)

def create_ebay_bulk_edit_template(changes_df):
    """Create a CSV in eBay's bulk edit format."""
    # eBay expects specific columns for bulk keyword updates
    bulk_df = pd.DataFrame({
        'Keyword ID': changes_df['Keyword ID'],
        'Keyword': changes_df['Keyword'],
        'Match Type': changes_df['Match Type'],
        'Max CPC': changes_df['New Bid'].apply(lambda x: '0.05' if x == 'PAUSE' else x.replace('$', '')),
        'Status': changes_df['Recommended Status']
    })
    
    return bulk_df

def main():
    print("=" * 80)
    print("GENERATE BID CHANGES CSV FOR MANUAL UPDATE")
    print("=" * 80)
    print()
    
    # Calculate changes
    print("[1] Analyzing keyword performance...")
    changes_df = calculate_bid_changes()
    
    if changes_df is None or changes_df.empty:
        print("No bid changes needed!")
        return
    
    print(f"Found {len(changes_df)} keywords needing bid adjustments")
    
    # Show summary
    print()
    print("[2] Top Priority Changes:")
    print("-" * 80)
    
    for i, row in changes_df.head(10).iterrows():
        print(f"{i+1:2}. {row['Keyword']:<30} ({row['Match Type']:<7})")
        print(f"    {row['Current Bid']} -> {row['New Bid']} ({row['Change']})")
        print(f"    {row['Action']}")
        print(f"    Performance: {row['Impressions']} impr, {row['Clicks']} clicks, {row['Sales']} sales")
        print()
    
    # Save detailed report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Detailed changes report
    detail_file = f'bid_changes_detailed_{timestamp}.csv'
    changes_df.to_csv(detail_file, index=False)
    print(f"[3] Detailed report saved to: {detail_file}")
    
    # eBay bulk upload format
    bulk_df = create_ebay_bulk_edit_template(changes_df)
    bulk_file = f'bid_changes_ebay_bulk_{timestamp}.csv'
    bulk_df.to_csv(bulk_file, index=False)
    print(f"[4] eBay bulk format saved to: {bulk_file}")
    
    # Instructions
    print()
    print("=" * 80)
    print("HOW TO APPLY THESE CHANGES IN EBAY:")
    print("=" * 80)
    print()
    print("OPTION 1: Individual Updates (Most Control)")
    print("-" * 40)
    print("1. Go to: https://www.ebay.com/sh/mkt/advertising-dashboard")
    print("2. Click 'Top Converters Test' campaign")
    print("3. Go to 'Keywords' tab")
    print(f"4. Open {detail_file} in Excel")
    print("5. Update each keyword's bid manually")
    print()
    print("OPTION 2: Bulk Upload (Fastest)")
    print("-" * 40)
    print("1. In the Keywords tab, click 'Bulk edit' button")
    print("2. Click 'Download template' to get eBay's format")
    print(f"3. Copy data from {bulk_file} to the template")
    print("4. Upload the modified template")
    print("5. Review and confirm changes")
    print()
    print("OPTION 3: Top 5 Critical Updates (Quick Win)")
    print("-" * 40)
    
    for i, row in changes_df.head(5).iterrows():
        print(f"{i+1}. Set '{row['Keyword']}' to {row['New Bid']}")
    
    print()
    print(f"[SUCCESS] Files saved. Apply changes in eBay Seller Hub.")

if __name__ == "__main__":
    main()