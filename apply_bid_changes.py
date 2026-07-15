"""
Apply Top Converters bid changes using eBay's Promoted Listings API.
This uses the existing user token from credentials.txt
"""

import os
import json
import time
import requests
import pandas as pd
import glob
from datetime import datetime
import subprocess

def load_token():
    """Load the user token from credentials file."""
    creds = {}
    with open("credentials.txt", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                creds[key.strip()] = val.strip()
    
    # Return the user token
    return creds.get("token", "")

def test_token(token):
    """Test if the token works with Marketing API."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Try to get campaigns
    url = "https://api.ebay.com/sell/marketing/v1/ad_campaign"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Token test response: {response.status_code}")
        
        if response.status_code == 200:
            print("[OK] Token is valid for Marketing API")
            return True
        elif response.status_code == 401:
            print("[ERROR] Token expired or not authorized")
            
            # Try to refresh token
            print("\n[INFO] Attempting to refresh token...")
            try:
                result = subprocess.run(["python", "refresh_oauth_token.py"], 
                                      capture_output=True, text=True, timeout=30)
                if "Token refreshed successfully" in result.stdout:
                    print("[OK] Token refreshed successfully")
                    return True
                else:
                    print("[FAILED] Could not refresh token")
                    print("You need a token with 'sell.marketing' scope")
                    return False
            except Exception as e:
                print(f"[ERROR] Could not run token refresh: {e}")
                return False
        else:
            print(f"[ERROR] Unexpected response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not connect to API: {e}")
        return False

def get_bid_changes():
    """Get the bid changes from latest report."""
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if not files:
        return []
    
    latest_report = max(files, key=os.path.getmtime)
    df = pd.read_csv(latest_report, skiprows=1)
    
    # Clean and filter
    df['Bid'] = df['Bid'].str.replace('$', '').astype(float)
    active_df = df[
        (df['Status'] == 'ACTIVE') & 
        ((df['Impressions'] > 0) | (df['Clicks'] > 0))
    ]
    
    changes = []
    for _, row in active_df.iterrows():
        current = row['Bid']
        
        # Calculate new bid
        if row['Clicks'] > 0:
            new_bid = min(current * 2.0, 1.50)
        elif row['Impressions'] > 20:
            new_bid = min(current * 1.75, 1.00)
        elif row['Impressions'] > 0:
            new_bid = min(current * 1.5, 0.75)
        else:
            # No impressions - check if bid is already high
            if current >= 1.00:
                new_bid = max(current * 0.7, 0.50)  # Decrease high bids with no impressions
            else:
                new_bid = min(current * 1.5, 0.75)  # Increase low bids with no impressions
        
        if abs(new_bid - current) > 0.01:
            changes.append({
                'keyword': row['Seller Keyword'],
                'keyword_id': str(int(row['Keyword ID'])),
                'ad_group_id': str(int(row['Ad Group Id'])),
                'campaign_id': str(int(row['Campaign ID'])),
                'match_type': row['Keyword Match Type'],
                'current_bid': current,
                'new_bid': round(new_bid, 2),
                'impressions': int(row['Impressions']),
                'clicks': int(row['Clicks'])
            })
    
    return sorted(changes, key=lambda x: (x['clicks'], x['impressions']), reverse=True)

def apply_single_bid_change(token, change):
    """Apply a single bid change via API."""
    campaign_id = change['campaign_id']
    keyword_id = change['keyword_id']
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Corrected eBay Marketing API endpoint
    url = f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/keyword/{keyword_id}"
    
    payload = {
        "bid": {
            "amount": str(change['new_bid']),
            "currency": "USD"
        }
    }
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 204]:
            return True, "Success"
        elif response.status_code == 409:
            # Check for invite-only restriction
            if "35089" in response.text:
                return False, "API_RESTRICTED: Keyword bid management is currently invite-only"
            else:
                return False, f"Conflict: {response.text[:200]}"
        else:
            return False, f"Status {response.status_code}: {response.text[:500]}"
            
    except Exception as e:
        return False, str(e)

def main():
    print("="*80)
    print("APPLY TOP CONVERTERS BID CHANGES")
    print("="*80)
    
    # Load token
    print("\n[1] Loading token...")
    token = load_token()
    
    if not token:
        print("[ERROR] No token found in credentials.txt")
        print("\nTo fix this:")
        print("1. Go to: https://developer.ebay.com/my/auth")
        print("2. Generate a User Token with 'sell.marketing' scope")
        print("3. Add it to credentials.txt as: token=YOUR_TOKEN_HERE")
        return 1
    
    print(f"[OK] Token loaded (length: {len(token)})")
    
    # Test token
    print("\n[2] Testing token with Marketing API...")
    if not test_token(token):
        print("\n[SOLUTION] Your current token doesn't have marketing scope.")
        print("You need to generate a new token with the right permissions.")
        return 1
    
    # Get bid changes
    print("\n[3] Calculating bid changes...")
    changes = get_bid_changes()
    
    if not changes:
        print("No changes needed!")
        return 0
    
    print(f"Found {len(changes)} keywords to update")
    
    # Show top changes
    print("\n[4] Top bid changes:")
    print("-" * 80)
    
    for i, change in enumerate(changes[:10], 1):
        print(f"{i:2}. {change['keyword']:<30} ({change['match_type']:<7})")
        print(f"    ${change['current_bid']:.2f} -> ${change['new_bid']:.2f} "
              f"({change['impressions']} impr, {change['clicks']} clicks)")
    
    # Save changes to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    changes_file = f'bid_changes_{timestamp}.json'
    
    with open(changes_file, 'w') as f:
        json.dump(changes, f, indent=2)
    
    print(f"\nAll changes saved to: {changes_file}")
    
    # Try to apply first change as a test
    print("\n[5] Testing API with first keyword...")
    
    test_change = changes[0]
    print(f"Testing: '{test_change['keyword']}' -> ${test_change['new_bid']:.2f}")
    
    success, message = apply_single_bid_change(token, test_change)
    
    if success:
        print(f"[SUCCESS] API call worked!")
        print(f"\nReady to apply all {len(changes)} changes.")
        print("Run with --apply flag to apply all changes")
        return 0  # Success
    else:
        print(f"[FAILED] {message}")
        
        if "API_RESTRICTED" in message:
            print("\n[NOTICE] eBay's keyword bid management API is currently invite-only.")
            print("You are not yet authorized to use automated bid updates.")
            print("\nFalling back to CSV generation for manual upload...")
        else:
            print("\nThe API call didn't work. This could mean:")
            print("1. Token doesn't have correct scope")
            print("2. Campaign IDs have changed")
            print("3. API endpoint has changed")
        return 1  # Failure
        
    print("\n" + "="*80)
    print("ALTERNATIVE: Manual Application")
    print("="*80)
    print(f"1. Open: {changes_file}")
    print("2. Go to: https://www.ebay.com/sh/mkt/advertising-dashboard")
    print("3. Click on 'Top Converters Test' campaign > Keywords tab")
    print("4. Apply the bid changes manually")

if __name__ == "__main__":
    import sys
    result = main()
    if result is not None:
        sys.exit(result)
    sys.exit(1)  # Default to error if no explicit return