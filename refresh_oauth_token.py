"""
Refresh eBay OAuth token using refresh token.
This ensures we always have a valid access token.
"""

import requests
import base64
import json
import time
from datetime import datetime, timedelta

def load_credentials():
    """Load credentials from credentials.txt."""
    creds = {}
    with open("credentials.txt", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                creds[key.strip()] = val.strip()
    return creds

def save_token(token_data, creds):
    """Save the new token to credentials.txt."""
    # Update the token in creds dict
    creds['token'] = token_data['access_token']
    
    # Save token expiry info if available
    if 'expires_in' in token_data:
        expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
        creds['token_expiry'] = expiry.isoformat()
    
    # Rewrite credentials file
    lines = []
    with open("credentials.txt", "r") as f:
        for line in f:
            if line.startswith("token="):
                lines.append(f"token={creds['token']}\n")
            elif line.startswith("token_expiry="):
                continue  # Skip old expiry
            else:
                lines.append(line)
    
    # Add token expiry if we have it
    if 'token_expiry' in creds:
        lines.append(f"# Token expires at: {creds['token_expiry']}\n")
    
    with open("credentials.txt", "w") as f:
        f.writelines(lines)
    
    print(f"[SUCCESS] Token saved to credentials.txt")
    if 'token_expiry' in creds:
        print(f"Token expires at: {creds['token_expiry']}")

def refresh_token(refresh_token, app_id, cert_id):
    """Refresh the OAuth access token using refresh token."""
    
    # eBay OAuth2 token endpoint
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    
    # Create base64 encoded credentials
    credentials = f"{app_id}:{cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://api.ebay.com/oauth/api_scope " \
                "https://api.ebay.com/oauth/api_scope/sell.marketing " \
                "https://api.ebay.com/oauth/api_scope/sell.inventory " \
                "https://api.ebay.com/oauth/api_scope/sell.account " \
                "https://api.ebay.com/oauth/api_scope/sell.fulfillment"
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, str(e)

def get_new_token_from_auth_code(auth_code, app_id, cert_id):
    """Exchange authorization code for access token."""
    
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    
    credentials = f"{app_id}:{cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": "Randy_Flores-RandyFlo-AIItem-nxdvxnid"  # Your RuName
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, str(e)

def check_token_validity(token):
    """Check if current token is still valid."""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Simple API call to check token
    url = "https://api.ebay.com/sell/account/v1/fulfillment_policy"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code != 401
    except:
        return False

def main():
    print("="*80)
    print("EBAY OAUTH TOKEN REFRESH")
    print("="*80)
    
    # Load credentials
    creds = load_credentials()
    
    app_id = creds.get('appid', '')
    cert_id = creds.get('certid', '')
    current_token = creds.get('token', '')
    refresh_token_val = creds.get('refresh_token', '')
    
    if not all([app_id, cert_id]):
        print("[ERROR] Missing app_id or cert_id in credentials.txt")
        return
    
    # Check if current token is valid
    if current_token:
        print("\n[1] Checking current token validity...")
        if check_token_validity(current_token):
            print("[OK] Current token is still valid")
            return
        else:
            print("[INFO] Current token has expired or is invalid")
    
    # Try to refresh token
    if refresh_token_val:
        print("\n[2] Attempting to refresh token...")
        success, result = refresh_token(refresh_token_val, app_id, cert_id)
        
        if success:
            print("[SUCCESS] Token refreshed successfully")
            save_token(result, creds)
            
            # Save refresh token if provided
            if 'refresh_token' in result:
                creds['refresh_token'] = result['refresh_token']
                print(f"New refresh token saved")
            
            return
        else:
            print(f"[FAILED] Could not refresh token: {result}")
    
    # If no refresh token or refresh failed
    print("\n[3] Manual token generation required")
    print("-"*80)
    print("To get a new token:")
    print("1. Go to: https://developer.ebay.com/my/auth")
    print("2. Select your app")
    print("3. Get OAuth tokens")
    print("4. Copy the User Access Token")
    print("5. Update credentials.txt with: token=YOUR_TOKEN_HERE")
    print("\nFor automated refresh, also get the refresh token and add:")
    print("refresh_token=YOUR_REFRESH_TOKEN_HERE")

if __name__ == "__main__":
    main()