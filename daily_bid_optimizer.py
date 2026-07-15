"""
Daily bid optimizer for airotate.bat integration.
Handles common scenarios and provides graceful fallbacks.
"""

import requests
import json
import pandas as pd
import glob
import os
from datetime import datetime

def load_token():
    """Load token from credentials"""
    try:
        with open("credentials.txt", "r") as f:
            for line in f:
                if line.startswith("token="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

def get_latest_keyword_report():
    """Find the latest Top Converters keyword report"""
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    return max(files, key=os.path.getmtime)

def test_marketing_api_access(token):
    """Test if we can access Marketing API"""
    if not token:
        return False, "No token found"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get("https://api.ebay.com/sell/marketing/v1/ad_campaign", 
                              headers=headers, timeout=10)
        
        if response.status_code == 200:
            return True, "API access OK"
        elif response.status_code == 401:
            return False, "Token expired - needs refresh"
        elif response.status_code == 403:
            return False, "Account access restricted"
        else:
            return False, f"API error: {response.status_code}"
            
    except Exception as e:
        return False, f"Connection error: {str(e)[:50]}"

def get_current_keywords(token, campaign_id="158950352019"):
    """Get current keywords from API"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    try:
        # Get keywords
        url = f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/keyword"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            keyword_data = response.json()
            keywords = keyword_data.get('keywords', [])
            return keywords
        else:
            return []
            
    except Exception:
        return []

def update_keyword_bid(token, campaign_id, keyword_id, new_bid):
    """Update a keyword bid"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = {
        "bid": {
            "amount": str(new_bid),
            "currency": "USD"
        }
    }
    
    url = f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/keyword/{keyword_id}"
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 204]:
            return True, "Success"
        elif response.status_code == 409:
            return False, "Currently processing (retry later)"
        elif response.status_code == 401:
            return False, "Token expired"
        else:
            return False, f"Status {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"

def calculate_optimal_bids(keywords):
    """Calculate optimal bids for current keywords"""
    bid_updates = []
    
    for kw in keywords:
        keyword_text = kw.get('keywordText', '')
        keyword_id = kw.get('keywordId')
        match_type = kw.get('matchType', '')
        
        # Simple bid optimization logic
        if 'hood' in keyword_text.lower():
            if match_type == 'BROAD':
                new_bid = 0.75  # Broader reach
            else:
                new_bid = 0.65  # More targeted
        elif 'sierra' in keyword_text.lower() or 'gmc' in keyword_text.lower():
            new_bid = 0.70  # Vehicle-specific
        elif 'deflector' in keyword_text.lower():
            new_bid = 0.60  # Product-specific
        else:
            new_bid = 0.55  # Default increase
        
        bid_updates.append({
            'keyword_id': keyword_id,
            'keyword_text': keyword_text,
            'match_type': match_type,
            'new_bid': new_bid
        })
    
    return bid_updates

def main():
    print("="*50)
    print("DAILY BID OPTIMIZER")
    print("="*50)
    
    # Load token
    token = load_token()
    
    # Test API access
    api_ok, api_message = test_marketing_api_access(token)
    print(f"API Status: {api_message}")
    
    if not api_ok:
        print(f"[SKIP] {api_message}")
        if "expired" in api_message.lower():
            print("Action needed: Regenerate User Token at https://developer.ebay.com/my/auth")
        return 1  # Error code for batch file
    
    # Get current keywords
    keywords = get_current_keywords(token)
    
    if not keywords:
        print("[SKIP] No keywords found in campaign")
        return 0  # No error, just nothing to do
    
    print(f"Found {len(keywords)} keywords")
    
    # Calculate bid updates
    bid_updates = calculate_optimal_bids(keywords)
    
    if not bid_updates:
        print("[SKIP] No bid updates calculated")
        return 0
    
    # Apply updates
    print(f"Applying {len(bid_updates)} bid updates...")
    
    success_count = 0
    failed_count = 0
    processing_count = 0
    
    for update in bid_updates:
        keyword_id = update['keyword_id']
        keyword_text = update['keyword_text']
        new_bid = update['new_bid']
        
        success, message = update_keyword_bid(token, "158950352019", keyword_id, new_bid)
        
        if success:
            success_count += 1
        elif "processing" in message.lower():
            processing_count += 1
        else:
            failed_count += 1
    
    # Results
    print(f"Results: {success_count} updated, {processing_count} processing, {failed_count} failed")
    
    if success_count > 0:
        print(f"[SUCCESS] Updated {success_count} keyword bids")
        
        # Log successful updates
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'success_count': success_count,
            'processing_count': processing_count,
            'failed_count': failed_count,
            'updates': bid_updates
        }
        
        log_file = f"daily_bid_updates_{datetime.now().strftime('%Y%m%d')}.json"
        try:
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            print(f"Log saved: {log_file}")
        except:
            pass  # Don't fail on logging issues
    
    elif processing_count > 0:
        print(f"[INFO] {processing_count} keywords are being processed by eBay")
        print("This is normal - updates will apply shortly")
    
    if failed_count > 0:
        print(f"[WARNING] {failed_count} updates failed")
        return 1  # Error code for batch file
    
    return 0  # Success

if __name__ == "__main__":
    import sys
    sys.exit(main())