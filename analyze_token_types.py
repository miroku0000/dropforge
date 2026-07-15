"""
Compare the User Token you generated vs Application Tokens to understand the difference.
"""

import requests

def load_user_token():
    """Load the user token from credentials.txt"""
    with open("credentials.txt", "r") as f:
        for line in f:
            if line.startswith("token="):
                return line.split("=", 1)[1].strip()
    return None

def analyze_token(token, token_name):
    """Analyze a token's properties"""
    print(f"\n--- {token_name} Analysis ---")
    print(f"Length: {len(token)} characters")
    print(f"Starts with: {token[:20]}...")
    
    # Check format patterns
    if token.startswith("v^1.1#i^1#r^0#p^3"):
        print("Format: Looks like Application Access Token")
    elif token.startswith("v^1.1#i^1#p^1#I^3#r^0#f^0"):
        print("Format: Looks like User Access Token")
    elif token.startswith("v^1.1#i^1#f^0#p^3"):
        print("Format: Mixed format - might be corrupted")
    else:
        print("Format: Unknown token format")
    
    # Test with different APIs
    test_apis = [
        ("Marketing API", "https://api.ebay.com/sell/marketing/v1/ad_campaign"),
        ("Account API", "https://api.ebay.com/sell/account/v1/privilege"),
    ]
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    for api_name, url in test_apis:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            status = response.status_code
            
            if status == 200:
                print(f"  {api_name}: ✓ Working (200)")
            elif status == 401:
                print(f"  {api_name}: ✗ Unauthorized (401)")
                # Check error details
                try:
                    error = response.json()
                    error_id = error.get('errors', [{}])[0].get('errorId', '')
                    if error_id == 1001:
                        print(f"    → Invalid access token")
                    elif error_id == 1100:
                        print(f"    → Insufficient permissions")
                except:
                    pass
            elif status == 403:
                print(f"  {api_name}: ✗ Forbidden (403)")
            else:
                print(f"  {api_name}: ? Status {status}")
                
        except Exception as e:
            print(f"  {api_name}: ! Error: {str(e)[:30]}")

def main():
    print("="*60)
    print("TOKEN TYPE ANALYSIS")
    print("="*60)
    
    # Load your user token
    user_token = load_user_token()
    if not user_token:
        print("[ERROR] No user token found in credentials.txt")
        return
    
    # Generate a fresh application token
    import simple_oauth_test
    creds = simple_oauth_test.load_credentials()
    
    # Get app token
    import base64
    client_id = creds.get("appid")
    client_secret = creds.get("certid")
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }
    
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code == 200:
            app_token = response.json()["access_token"]
            
            # Analyze both tokens
            analyze_token(user_token, "YOUR USER TOKEN")
            analyze_token(app_token, "FRESH APPLICATION TOKEN")
            
            # Compare
            print("\n" + "="*60)
            print("COMPARISON SUMMARY")
            print("="*60)
            
            if user_token.startswith("v^1.1#i^1#p^1#I^3#r^0#f^0"):
                print("✓ Your user token has correct User Access Token format")
            else:
                print("✗ Your user token format looks wrong")
            
            print("\nWhy your User Token might not work:")
            print("1. Generated for SANDBOX instead of PRODUCTION")
            print("2. Token expired (User tokens have shorter lifespans)")
            print("3. Wrong OAuth flow used (needs Authorization Code, not Implicit)")
            print("4. Account doesn't have seller privileges enabled")
            print("5. eBay API endpoint changed or has issues")
            
            print("\nRecommended solution:")
            print("1. Use the bulk upload CSV files we created")
            print("2. Or try generating a NEW user token with these specific steps:")
            print("   a) Go to https://developer.ebay.com/my/auth")
            print("   b) Choose 'Authorization Code Grant'")
            print("   c) Select PRODUCTION environment")
            print("   d) Check 'sell.marketing' scope")
            print("   e) Generate and copy the FULL token")
            
        else:
            print(f"[ERROR] Could not generate app token: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] Exception: {e}")

if __name__ == "__main__":
    main()