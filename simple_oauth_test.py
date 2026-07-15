"""
Simple test of OAuth token generation without importing ebay_utils
"""

import requests
import base64
import json

def load_credentials():
    """Load credentials from file"""
    creds = {}
    with open("credentials.txt", "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                creds[key.strip()] = val.strip()
    return creds

def test_oauth_generation():
    """Test OAuth token generation"""
    print("="*60)
    print("SIMPLE OAUTH TOKEN TEST")
    print("="*60)
    
    # Load credentials
    creds = load_credentials()
    client_id = creds.get("appid")
    client_secret = creds.get("certid")
    
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret[:30]}...")
    
    # Generate OAuth token
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }
    
    # Test different scopes
    scope_tests = [
        ("No scope", ""),
        ("Public scope", "https://api.ebay.com/oauth/api_scope"),
        ("Analytics only", "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly"),
        ("Marketing (will fail)", "https://api.ebay.com/oauth/api_scope/sell.marketing"),
    ]
    
    for scope_name, scope in scope_tests:
        print(f"\n--- Testing: {scope_name} ---")
        
        data = {
            "grant_type": "client_credentials",
            "scope": scope
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 0)
                token_type = token_data.get("token_type")
                
                print(f"[SUCCESS] Token generated!")
                print(f"  Type: {token_type}")
                print(f"  Length: {len(access_token)} chars")
                print(f"  Expires: {expires_in} seconds")
                print(f"  Preview: {access_token[:30]}...")
                
                # Test this token with Marketing API
                if scope_name != "Marketing (will fail)":
                    test_marketing_with_token(access_token)
                    
            else:
                print(f"[FAILED] {response.status_code}")
                if response.text:
                    try:
                        error = response.json()
                        print(f"  Error: {error.get('error', '')}")
                        print(f"  Description: {error.get('error_description', '')}")
                    except:
                        print(f"  Raw: {response.text[:100]}")
                        
        except Exception as e:
            print(f"[ERROR] {e}")

def test_marketing_with_token(token):
    """Test Marketing API with a token"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    url = "https://api.ebay.com/sell/marketing/v1/ad_campaign"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"  [MARKETING] SUCCESS! Can access campaigns")
        elif response.status_code == 403:
            print(f"  [MARKETING] 403 Forbidden (expected for client creds)")
        elif response.status_code == 401:
            print(f"  [MARKETING] 401 Unauthorized")
        else:
            print(f"  [MARKETING] {response.status_code}")
    except Exception as e:
        print(f"  [MARKETING] Error: {e}")

if __name__ == "__main__":
    test_oauth_generation()