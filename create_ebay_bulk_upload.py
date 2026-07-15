"""
Create an eBay-compatible bulk upload file for Top Converters bid changes.
This generates the exact format eBay expects for their bulk upload feature.
"""

import os
import pandas as pd
import glob
from datetime import datetime
import csv

def get_latest_keyword_report():
    """Find the latest Top Converters keyword report."""
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    return max(files, key=os.path.getmtime)

def create_ebay_bulk_format():
    """Create bulk upload file in eBay's exact format."""
    report_file = get_latest_keyword_report()
    
    if not report_file:
        print("[ERROR] No Top Converters keyword report found")
        return
    
    print(f"Using report: {os.path.basename(report_file)}")
    
    # Read the report
    df = pd.read_csv(report_file, skiprows=1)
    
    # Clean currency
    df['Bid'] = df['Bid'].str.replace('$', '').astype(float)
    
    # Filter active keywords
    active_df = df[df['Status'] == 'ACTIVE'].copy()
    
    # Calculate new bids and prioritize
    updates = []
    
    for _, row in active_df.iterrows():
        keyword_id = int(row['Keyword ID'])
        keyword = row['Seller Keyword']
        match_type = row['Keyword Match Type']
        current_bid = row['Bid']
        impressions = int(row['Impressions'])
        clicks = int(row['Clicks'])
        sales = int(row.get('Sold quantity', 0))
        ad_group_id = int(row['Ad Group Id'])
        campaign_id = int(row['Campaign ID'])
        
        # Calculate new bid
        if sales > 0:
            new_bid = min(current_bid * 2.5, 2.00)
            priority = 1
        elif clicks > 0:
            new_bid = min(current_bid * 2.0, 1.50)
            priority = 2
        elif impressions > 20:
            new_bid = min(current_bid * 1.75, 1.00)
            priority = 3
        elif impressions > 0:
            new_bid = min(current_bid * 1.5, 0.75)
            priority = 4
        else:
            new_bid = min(current_bid * 1.5, 0.60)
            priority = 5
        
        new_bid = round(new_bid, 2)
        
        if abs(new_bid - current_bid) > 0.01:
            updates.append({
                'Campaign ID': campaign_id,
                'Ad Group ID': ad_group_id,
                'Keyword ID': keyword_id,
                'Keyword': keyword,
                'Match Type': match_type.upper(),
                'Status': 'ACTIVE',
                'Max CPC': new_bid,
                'Priority': priority,
                'Impressions': impressions,
                'Clicks': clicks,
                'Sales': sales,
                'Old Bid': current_bid
            })
    
    if not updates:
        print("No bid changes needed")
        return
    
    # Sort by priority
    updates.sort(key=lambda x: (x['Priority'], -x['Clicks'], -x['Impressions']))
    
    # Create eBay bulk upload file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bulk_file = f'ebay_bulk_upload_keywords_{timestamp}.csv'
    
    # Write in eBay's expected format
    with open(bulk_file, 'w', newline='', encoding='utf-8') as f:
        # eBay expects these specific columns
        fieldnames = ['Keyword ID', 'Keyword', 'Match Type', 'Status', 'Max CPC']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for update in updates:
            writer.writerow({
                'Keyword ID': update['Keyword ID'],
                'Keyword': update['Keyword'],
                'Match Type': update['Match Type'],
                'Status': update['Status'],
                'Max CPC': update['Max CPC']
            })
    
    print(f"\n[SUCCESS] Created eBay bulk upload file: {bulk_file}")
    
    # Also create a detailed report
    detail_file = f'bid_changes_with_reasons_{timestamp}.csv'
    detail_df = pd.DataFrame(updates)
    detail_df = detail_df[['Keyword', 'Match Type', 'Old Bid', 'Max CPC', 
                           'Impressions', 'Clicks', 'Sales', 'Priority']]
    detail_df['Change'] = detail_df['Max CPC'] - detail_df['Old Bid']
    detail_df['Change %'] = ((detail_df['Max CPC'] / detail_df['Old Bid']) - 1) * 100
    detail_df = detail_df.round({'Change': 2, 'Change %': 0})
    
    detail_df.to_csv(detail_file, index=False)
    print(f"[SUCCESS] Created detailed report: {detail_file}")
    
    # Show summary
    print("\n" + "="*60)
    print("BID CHANGE SUMMARY")
    print("="*60)
    
    print(f"\nTotal keywords to update: {len(updates)}")
    
    # Priority breakdown
    priority_counts = {}
    for u in updates:
        p = u['Priority']
        if p not in priority_counts:
            priority_counts[p] = 0
        priority_counts[p] += 1
    
    print("\nBy priority:")
    priority_names = {
        1: "Converting (has sales)",
        2: "Has clicks",
        3: "High impressions (>20)",
        4: "Some impressions",
        5: "No impressions"
    }
    
    for p in sorted(priority_counts.keys()):
        count = priority_counts[p]
        name = priority_names.get(p, f"Priority {p}")
        print(f"  {name}: {count} keywords")
    
    # Top changes
    print("\n" + "="*60)
    print("TOP 10 PRIORITY UPDATES")
    print("="*60)
    
    for i, update in enumerate(updates[:10], 1):
        print(f"\n{i}. {update['Keyword']} ({update['Match Type']})")
        print(f"   ${update['Old Bid']:.2f} -> ${update['Max CPC']:.2f} (+${update['Max CPC']-update['Old Bid']:.2f})")
        print(f"   Performance: {update['Impressions']} impr, {update['Clicks']} clicks, {update['Sales']} sales")
    
    print("\n" + "="*60)
    print("HOW TO APPLY THESE CHANGES")
    print("="*60)
    print()
    print("1. Go to: https://www.ebay.com/sh/mkt/promotions")
    print("2. Click on 'Top Converters Test' campaign")
    print("3. Go to 'Keywords' tab")
    print("4. Click 'Bulk actions' -> 'Edit keywords'")
    print("5. Click 'Download template' (if you don't have it)")
    print(f"6. Open the template and {bulk_file} in Excel")
    print("7. Copy the data from the bulk file to the template")
    print("8. Save and upload the template back to eBay")
    print("9. Review and confirm the changes")
    print()
    print("Time required: ~5-10 minutes")
    
    # Open the files
    os.system(f'start {bulk_file}')
    os.system(f'start {detail_file}')
    
    print(f"\n[OK] Files opened in Excel")
    
    return bulk_file

if __name__ == "__main__":
    print("="*60)
    print("EBAY BULK UPLOAD FILE GENERATOR")
    print("="*60)
    print()
    
    create_ebay_bulk_format()