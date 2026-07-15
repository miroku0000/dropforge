"""
Automatically adjust Top Converters campaign bids based on performance.
Uses eBay Ads API to update keyword bids programmatically.
"""

import os
import json
import time
import requests
import pandas as pd
import glob
from datetime import datetime
from typing import Dict, List, Tuple

# eBay Ads API endpoints
EBAY_ADS_BASE_URL = "https://api.ebay.com/sell/marketing/v1"

def load_ebay_credentials():
    """Load eBay API credentials from file."""
    creds_file = "credentials.txt"
    if not os.path.exists(creds_file):
        raise FileNotFoundError("credentials.txt not found")
    
    creds = {}
    with open(creds_file, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                creds[key.strip()] = value.strip()
    
    # For Ads API, we need the OAuth token
    if 'token' not in creds:
        raise ValueError("OAuth token not found in credentials")
    
    return creds

def get_campaign_details(campaign_id, token):
    """Get campaign details from eBay."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # For Priority campaigns (Top Converters), we need the Ads API
    url = f"{EBAY_ADS_BASE_URL}/ad_campaign/{campaign_id}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting campaign details: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

def update_keyword_bid(campaign_id, ad_group_id, keyword_id, new_bid, token):
    """Update a single keyword bid via API."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # eBay Ads API endpoint for updating keyword bids
    url = f"{EBAY_ADS_BASE_URL}/ad_campaign/{campaign_id}/ad_group/{ad_group_id}/keyword/{keyword_id}"
    
    payload = {
        "bid": {
            "amount": str(new_bid),
            "currency": "USD"
        }
    }
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [200, 204]:
            return True
        else:
            print(f"Error updating keyword {keyword_id}: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"API Error updating keyword: {e}")
        return False

def calculate_bid_adjustments_from_csv():
    """Read the latest keyword report and calculate bid adjustments."""
    # Find latest keyword report
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if not files:
        print("No Top Converters keyword report found!")
        return None
    
    latest_report = max(files, key=os.path.getmtime)
    print(f"Using report: {os.path.basename(latest_report)}")
    
    # Parse the CSV
    df = pd.read_csv(latest_report, skiprows=1)
    
    # Clean currency columns
    df['Bid'] = df['Bid'].str.replace('$', '').astype(float)
    
    # Filter active keywords
    active_df = df[df['Status'] == 'ACTIVE'].copy()
    
    adjustments = []
    
    for _, row in active_df.iterrows():
        current_bid = row['Bid']
        impressions = row['Impressions']
        clicks = row['Clicks']
        keyword = row['Seller Keyword']
        match_type = row['Keyword Match Type']
        keyword_id = row['Keyword ID']
        ad_group_id = row['Ad Group Id']
        
        # Apply same logic as the analysis script
        if clicks > 0:
            if row['Sold quantity'] > 0:
                # Converting! Double bid
                new_bid = min(current_bid * 2.0, 2.00)
                change_reason = "Converting - maximize"
            elif clicks >= 3:
                # Not converting after chances
                new_bid = current_bid * 0.75
                change_reason = "3+ clicks no sales"
            else:
                # Has clicks, needs more data
                new_bid = current_bid * 1.5
                change_reason = "Has clicks - increase"
        elif impressions > 20:
            # Good impressions but no clicks
            new_bid = current_bid * 1.75
            change_reason = f"{impressions} impressions, 0 clicks"
        elif impressions > 0:
            # Some impressions
            new_bid = current_bid * 1.5
            change_reason = "Low impressions"
        else:
            # No impressions
            new_bid = current_bid * 2.0
            change_reason = "Zero impressions"
        
        # Apply caps based on keyword type
        if 'hood' in keyword.lower() or 'deflector' in keyword.lower():
            new_bid = min(new_bid, 1.00)
        elif 'brake' in keyword.lower():
            new_bid = min(new_bid, 1.50)
        else:
            new_bid = min(new_bid, 0.75)
        
        # Only add if there's a change
        if abs(new_bid - current_bid) > 0.01:
            adjustments.append({
                'keyword_id': keyword_id,
                'ad_group_id': ad_group_id,
                'keyword': keyword,
                'match_type': match_type,
                'current_bid': current_bid,
                'new_bid': round(new_bid, 2),
                'change': round(new_bid - current_bid, 2),
                'reason': change_reason,
                'impressions': impressions,
                'clicks': clicks
            })
    
    return adjustments

def apply_bid_adjustments(adjustments, campaign_id, token, dry_run=True):
    """Apply bid adjustments via API."""
    if not adjustments:
        print("No adjustments to make")
        return
    
    print(f"\n{'DRY RUN' if dry_run else 'LIVE'} - Bid Adjustments to Apply:")
    print("="*80)
    
    # Sort by change amount (biggest increases first)
    adjustments_sorted = sorted(adjustments, key=lambda x: x['change'], reverse=True)
    
    # Show summary
    total_keywords = len(adjustments_sorted)
    total_increase = sum(a['change'] for a in adjustments_sorted if a['change'] > 0)
    total_decrease = sum(a['change'] for a in adjustments_sorted if a['change'] < 0)
    
    print(f"Total keywords to adjust: {total_keywords}")
    print(f"Total bid increase: ${total_increase:.2f}")
    print(f"Total bid decrease: ${abs(total_decrease):.2f}")
    print(f"Net change: ${total_increase + total_decrease:.2f}")
    
    # Show top 10 changes
    print("\nTop 10 bid changes:")
    for adj in adjustments_sorted[:10]:
        print(f"  {adj['keyword']} ({adj['match_type']}): "
              f"${adj['current_bid']:.2f} -> ${adj['new_bid']:.2f} "
              f"({adj['change']:+.2f}) - {adj['reason']}")
    
    if dry_run:
        print("\n[DRY RUN] No actual changes made. Remove --dry-run to apply changes.")
        
        # Save to file for review
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'bid_adjustments_preview_{timestamp}.json'
        with open(output_file, 'w') as f:
            json.dump(adjustments_sorted, f, indent=2)
        print(f"\nPreview saved to: {output_file}")
        
        return adjustments_sorted
    else:
        # Apply changes
        print("\nApplying bid adjustments...")
        
        success_count = 0
        failed_count = 0
        
        for i, adj in enumerate(adjustments_sorted, 1):
            print(f"\n[{i}/{total_keywords}] Updating '{adj['keyword']}' "
                  f"from ${adj['current_bid']:.2f} to ${adj['new_bid']:.2f}...")
            
            success = update_keyword_bid(
                campaign_id=campaign_id,
                ad_group_id=adj['ad_group_id'],
                keyword_id=adj['keyword_id'],
                new_bid=adj['new_bid'],
                token=token
            )
            
            if success:
                print(f"  [OK] Success")
                success_count += 1
            else:
                print(f"  [FAIL] Failed")
                failed_count += 1
            
            # Rate limiting - eBay allows 5000 calls per day, be conservative
            if i % 10 == 0:
                print(f"  [Pausing to avoid rate limits...]")
                time.sleep(2)
        
        print("\n" + "="*80)
        print(f"COMPLETED: {success_count} successful, {failed_count} failed")
        
        # Log the changes
        log_file = f'bid_adjustments_applied_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'campaign_id': campaign_id,
                'total_adjustments': total_keywords,
                'successful': success_count,
                'failed': failed_count,
                'adjustments': adjustments_sorted
            }, f, indent=2)
        
        print(f"Log saved to: {log_file}")
        
        return adjustments_sorted

def main():
    """Main function to run bid adjustments."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatically adjust Top Converters bids')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Preview changes without applying them (default: True)')
    parser.add_argument('--live', action='store_true',
                       help='Actually apply the bid changes')
    parser.add_argument('--campaign-id', type=str, default='158950352019',
                       help='Campaign ID (default: your Top Converters campaign)')
    parser.add_argument('--max-bid', type=float, default=2.00,
                       help='Maximum bid cap (default: $2.00)')
    parser.add_argument('--min-impressions', type=int, default=100,
                       help='Pause keywords with this many impressions and 0 clicks')
    
    args = parser.parse_args()
    
    # Override dry-run if --live is specified
    if args.live:
        args.dry_run = False
    
    print("="*80)
    print("TOP CONVERTERS AUTOMATED BID ADJUSTMENT")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE - WILL APPLY CHANGES'}")
    print("="*80)
    
    try:
        # Load credentials
        print("\nLoading credentials...")
        creds = load_ebay_credentials()
        token = creds['token']
        
        # Get campaign details (optional - for verification)
        print(f"\nVerifying campaign {args.campaign_id}...")
        # campaign_details = get_campaign_details(args.campaign_id, token)
        # if campaign_details:
        #     print(f"Campaign found: {campaign_details.get('campaignName', 'Unknown')}")
        
        # Calculate adjustments
        print("\nCalculating bid adjustments...")
        adjustments = calculate_bid_adjustments_from_csv()
        
        if not adjustments:
            print("No bid adjustments needed!")
            return
        
        print(f"Found {len(adjustments)} keywords needing adjustment")
        
        # Apply adjustments
        if not args.dry_run:
            response = input("\n[WARNING] This will modify live bids. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled by user")
                return
        
        apply_bid_adjustments(adjustments, args.campaign_id, token, dry_run=args.dry_run)
        
        if args.dry_run:
            print("\n[TIP] To apply these changes, run:")
            print("   python auto_adjust_top_converters_bids.py --live")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()