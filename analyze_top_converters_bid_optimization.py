"""
Detailed bid optimization analysis for Top Converters campaign.
Provides specific keyword-level bid recommendations.
"""

import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime

def find_latest_top_converters_keyword_report():
    """Find the most recent Top Converters keyword report."""
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if files:
        return max(files, key=os.path.getmtime)
    return None

def parse_keyword_report(csv_path):
    """Parse Top Converters keyword report."""
    df = pd.read_csv(csv_path, skiprows=1)
    
    # Clean currency columns
    currency_cols = ['Bid', 'Average cost per click', 'Ad fees', 'Sales']
    for col in currency_cols:
        if col in df.columns:
            df[col] = df[col].str.replace('$', '').str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Clean percentage columns
    pct_cols = ['CTR', 'Conversion rate (Total Quantity Sold/Clicks)']
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].str.replace('%', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 100
    
    # Numeric columns
    numeric_cols = ['Impressions', 'Clicks', 'Sold quantity']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

def calculate_keyword_potential(row):
    """Calculate potential score for a keyword."""
    score = 0
    
    # High impressions but low/no clicks = opportunity
    if row['Impressions'] > 10 and row['Clicks'] == 0:
        score += 30  # High opportunity
    elif row['Impressions'] > 5 and row['CTR'] < 0.01:
        score += 20  # Medium opportunity
    
    # Keywords with clicks get priority
    if row['Clicks'] > 0:
        score += 50
        # Add bonus for conversions
        if row['Sold quantity'] > 0:
            score += 100
    
    # Match type scoring
    if row['Keyword Match Type'] == 'PHRASE':
        score += 10  # Phrase has shown best CTR
    elif row['Keyword Match Type'] == 'EXACT':
        score += 5
    
    # Category relevance (based on ad group)
    high_value_categories = ['Brakes', 'Cases', 'Tools']
    for cat in high_value_categories:
        if cat.lower() in row['Ad Group Name'].lower():
            score += 15
            break
    
    return score

def recommend_bid_adjustment(row, avg_cpc_market=0.50):
    """Recommend specific bid adjustment for a keyword."""
    current_bid = row['Bid']
    
    # Base recommendations on performance
    if row['Clicks'] > 0:
        # Has clicks - most valuable
        if row['Sold quantity'] > 0:
            # Converting! Increase significantly
            new_bid = min(current_bid * 2.0, 2.00)
            reason = "CONVERTING - Double bid to maximize"
        else:
            # Clicks but no conversion yet
            if row['Clicks'] >= 3:
                # Had chance to convert, didn't
                new_bid = current_bid * 0.75
                reason = "3+ clicks, no sales - Reduce bid"
            else:
                # Give it more time
                new_bid = current_bid * 1.5
                reason = "Has clicks - Increase for more data"
    
    elif row['Impressions'] > 20:
        # Good impressions but no clicks
        if row['CTR'] == 0:
            # Significant impressions, zero clicks
            new_bid = current_bid * 1.75
            reason = f"{int(row['Impressions'])} impressions, 0 clicks - Increase bid for better position"
        else:
            new_bid = current_bid * 1.25
            reason = "Low CTR - Modest increase"
    
    elif row['Impressions'] > 0:
        # Some impressions
        new_bid = current_bid * 1.5
        reason = f"Low impressions ({int(row['Impressions'])}) - Increase for visibility"
    
    else:
        # No impressions
        new_bid = current_bid * 2.0
        reason = "Zero impressions - Double bid to enter auction"
    
    # Cap bids based on value
    if 'hood' in row['Seller Keyword'].lower() or 'deflector' in row['Seller Keyword'].lower():
        # Lower value items
        new_bid = min(new_bid, 1.00)
    elif 'brake' in row['Seller Keyword'].lower():
        # Higher value items
        new_bid = min(new_bid, 1.50)
    else:
        new_bid = min(new_bid, 0.75)
    
    # Round to cents
    new_bid = round(new_bid, 2)
    
    return {
        'current_bid': current_bid,
        'recommended_bid': new_bid,
        'change': new_bid - current_bid,
        'change_pct': ((new_bid - current_bid) / current_bid * 100) if current_bid > 0 else 0,
        'reason': reason
    }

def generate_detailed_recommendations(df):
    """Generate detailed bid recommendations report."""
    print("\n" + "="*80)
    print("TOP CONVERTERS CAMPAIGN - DETAILED BID OPTIMIZATION RECOMMENDATIONS")
    print("="*80)
    
    # Filter active keywords only
    active_df = df[df['Status'] == 'ACTIVE'].copy()
    
    # Calculate potential scores
    active_df['potential_score'] = active_df.apply(calculate_keyword_potential, axis=1)
    
    # Get bid recommendations
    recommendations = []
    for idx, row in active_df.iterrows():
        rec = recommend_bid_adjustment(row)
        rec['keyword'] = row['Seller Keyword']
        rec['match_type'] = row['Keyword Match Type']
        rec['ad_group'] = row['Ad Group Name']
        rec['impressions'] = row['Impressions']
        rec['clicks'] = row['Clicks']
        rec['sales'] = row['Sold quantity']
        rec['potential_score'] = row['potential_score']
        recommendations.append(rec)
    
    # Convert to DataFrame and sort by priority
    rec_df = pd.DataFrame(recommendations)
    rec_df = rec_df.sort_values('potential_score', ascending=False)
    
    # Print immediate actions (top 20)
    print("\n[IMMEDIATE ACTIONS] - Top 20 Keywords to Adjust")
    print("-" * 80)
    
    for i, row in rec_df.head(20).iterrows():
        print(f"\n{len(recommendations) - list(rec_df.index).index(i)}. Keyword: '{row['keyword']}' ({row['match_type']})")
        print(f"   Ad Group: {row['ad_group'][:50]}...")
        print(f"   Performance: {int(row['impressions'])} impr, {int(row['clicks'])} clicks, {int(row['sales'])} sales")
        print(f"   Current Bid: ${row['current_bid']:.2f}")
        print(f"   >>> CHANGE TO: ${row['recommended_bid']:.2f} ({row['change_pct']:+.0f}%)")
        print(f"   Reason: {row['reason']}")
    
    # Summary by action type
    print("\n" + "="*80)
    print("SUMMARY BY ACTION TYPE")
    print("="*80)
    
    # Group recommendations
    increase_bids = rec_df[rec_df['change'] > 0]
    decrease_bids = rec_df[rec_df['change'] < 0]
    no_change = rec_df[rec_df['change'] == 0]
    
    print(f"\n[INCREASE BIDS]: {len(increase_bids)} keywords")
    if not increase_bids.empty:
        print(f"   Average increase: ${increase_bids['change'].mean():.2f}")
        print(f"   Total additional spend potential: ${increase_bids['change'].sum():.2f}")
        print("\n   Top 5 to increase:")
        for _, row in increase_bids.head(5).iterrows():
            print(f"   - '{row['keyword']}': ${row['current_bid']:.2f} -> ${row['recommended_bid']:.2f}")
    
    print(f"\n[DECREASE BIDS]: {len(decrease_bids)} keywords")
    if not decrease_bids.empty:
        print(f"   Average decrease: ${decrease_bids['change'].mean():.2f}")
        print(f"   Total savings potential: ${abs(decrease_bids['change'].sum()):.2f}")
        print("\n   Top 5 to decrease:")
        for _, row in decrease_bids.head(5).iterrows():
            print(f"   - '{row['keyword']}': ${row['current_bid']:.2f} -> ${row['recommended_bid']:.2f}")
    
    # Keywords to potentially pause
    print("\n" + "="*80)
    print("KEYWORDS TO CONSIDER PAUSING")
    print("="*80)
    
    # Find poor performers
    poor_performers = active_df[
        (active_df['Impressions'] > 50) & 
        (active_df['Clicks'] == 0)
    ]
    
    if not poor_performers.empty:
        print("\n[WARNING] Keywords with 50+ impressions but zero clicks:")
        for _, row in poor_performers.iterrows():
            print(f"   - '{row['Seller Keyword']}' ({row['Keyword Match Type']}): {int(row['Impressions'])} impressions")
        print("\n   Recommendation: Pause these and reallocate budget to performing keywords")
    else:
        print("\n[OK] No keywords identified for pausing at this time")
    
    # New keywords to add
    print("\n" + "="*80)
    print("SUGGESTED NEW KEYWORDS TO ADD")
    print("="*80)
    
    # Analyze successful keywords for expansion ideas
    successful = active_df[active_df['Clicks'] > 0]
    
    print("\nBased on your performing keywords, consider adding:")
    print("\n1. PHRASE match variations of exact keywords:")
    exact_keywords = successful[successful['Keyword Match Type'] == 'EXACT']['Seller Keyword'].unique()
    for kw in exact_keywords[:5]:
        print(f"   - '{kw}' as PHRASE match (currently only EXACT)")
    
    print("\n2. Related keywords for top ad groups:")
    top_groups = successful.groupby('Ad Group Name')['Clicks'].sum().sort_values(ascending=False).head(3)
    for group, clicks in top_groups.items():
        print(f"\n   {group[:50]}... ({int(clicks)} clicks)")
        if 'brake' in group.lower():
            print("   - Add: 'brake pads', 'brake rotors', 'brake kit deal'")
        elif 'case' in group.lower():
            print("   - Add: 'protective case', 'waterproof housing', 'camera protection'")
        elif 'deflector' in group.lower():
            print("   - Add: 'bug deflector', 'wind deflector', 'hood protector'")
    
    # Budget allocation recommendation
    print("\n" + "="*80)
    print("BUDGET ALLOCATION STRATEGY")
    print("="*80)
    
    total_current_spend = (active_df['Bid'] * active_df['Impressions'] / 1000).sum()  # Rough estimate
    total_recommended_spend = (rec_df['recommended_bid'] * rec_df['impressions'] / 1000).sum()
    
    print(f"\nCurrent estimated daily spend: ${total_current_spend:.2f}")
    print(f"Recommended daily spend: ${total_recommended_spend:.2f}")
    print(f"Change: ${total_recommended_spend - total_current_spend:+.2f}")
    
    print("\n[BUDGET ALLOCATION] by Priority:")
    print("   1. Converting keywords (had sales): 40% of budget")
    print("   2. Keywords with clicks: 35% of budget")
    print("   3. High-impression keywords: 20% of budget")
    print("   4. New/test keywords: 5% of budget")
    
    # Save detailed recommendations to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'top_converters_bid_recommendations_{timestamp}.csv'
    rec_df.to_csv(output_file, index=False)
    
    print(f"\n[SAVED] Detailed recommendations saved to: {output_file}")
    
    return rec_df

def main():
    print("="*80)
    print("TOP CONVERTERS BID OPTIMIZATION ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Find latest keyword report
    report_path = find_latest_top_converters_keyword_report()
    
    if not report_path:
        print("\n[ERROR] No Top Converters keyword report found in Downloads!")
        print("Please download the keyword report first.")
        return
    
    print(f"\nUsing report: {os.path.basename(report_path)}")
    
    # Parse the report
    df = parse_keyword_report(report_path)
    
    print(f"Loaded {len(df)} keywords from report")
    print(f"Active keywords: {len(df[df['Status'] == 'ACTIVE'])}")
    
    # Generate recommendations
    recommendations = generate_detailed_recommendations(df)
    
    print("\n" + "="*80)
    print("IMPLEMENTATION STEPS")
    print("="*80)
    print("\n1. Go to eBay Seller Hub > Marketing > Promotions > Top Converters Test")
    print("2. Click 'Edit campaign' > 'Keywords'")
    print("3. Apply the bid changes listed above, starting with highest priority")
    print("4. Monitor daily and adjust based on performance")
    print("5. Add suggested new keywords with $0.50 starting bids")
    
    print("\n[TIMING] Best time to make changes: Early morning (6-8 AM) for full day of data")
    print("[FOLLOWUP] Check performance again in 48-72 hours after changes")

if __name__ == "__main__":
    main()