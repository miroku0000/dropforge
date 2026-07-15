"""
Check status of different API tokens used by test_ebay_utils.py
"""

import os
import requests

def check_openai_token():
    """Check OpenAI API key"""
    api_key = os.environ.get('OPENAI_API_KEY')
    
    print("="*50)
    print("OPENAI API KEY STATUS")
    print("="*50)
    
    if not api_key:
        print("[ERROR] No OPENAI_API_KEY environment variable found")
        print("Set with: set OPENAI_API_KEY=your_key_here")
        return False
    
    print(f"Key found: {api_key[:20]}...{api_key[-4:]}")
    
    # Test OpenAI API
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Simple API test
    test_data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 5
    }
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=test_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("[OK] OpenAI API key is working")
            return True
        elif response.status_code == 401:
            print("[ERROR] OpenAI API key is invalid or expired")
            print("Get new key at: https://platform.openai.com/api-keys")
            return False
        elif response.status_code == 429:
            print("[ERROR] OpenAI API quota exceeded or rate limited")
            return False
        else:
            print(f"[ERROR] OpenAI API returned: {response.status_code}")
            print(response.text[:200])
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not test OpenAI API: {e}")
        return False

def check_ebay_marketing_token():
    """Check eBay Marketing API token"""
    print("\n" + "="*50)
    print("EBAY MARKETING API TOKEN STATUS")
    print("="*50)
    
    try:
        with open("credentials.txt", "r") as f:
            for line in f:
                if line.startswith("token="):
                    token = line.split("=", 1)[1].strip()
                    break
            else:
                print("[ERROR] No token found in credentials.txt")
                return False
            
        print(f"Token length: {len(token)} characters")
        
        # Test Marketing API
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(
            "https://api.ebay.com/sell/marketing/v1/ad_campaign",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("[OK] eBay Marketing API token is working")
            return True
        elif response.status_code == 401:
            print("[ERROR] eBay Marketing API token is invalid or expired")
            print("Regenerate at: https://developer.ebay.com/my/auth")
            return False
        else:
            print(f"[ERROR] eBay Marketing API returned: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not test eBay token: {e}")
        return False

def check_ebay_trading_token():
    """Check eBay Trading API token from credentials"""
    print("\n" + "="*50)
    print("EBAY TRADING API TOKEN STATUS")
    print("="*50)
    
    try:
        creds = {}
        with open("credentials.txt", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    creds[key.strip()] = val.strip()
        
        # Check for various eBay token fields
        token_fields = ['token', 'ebay_token', 'user_token', 'oauth_token']
        
        found_tokens = {}
        for field in token_fields:
            if field in creds:
                found_tokens[field] = len(creds[field])
        
        if found_tokens:
            print("Found token fields:")
            for field, length in found_tokens.items():
                print(f"  {field}: {length} characters")
            return True
        else:
            print("No eBay tokens found in credentials.txt")
            return False
            
    except Exception as e:
        print(f"[ERROR] Could not check eBay credentials: {e}")
        return False

def main():
    print("TOKEN STATUS CHECKER")
    print("Checking all tokens used by test_ebay_utils.py...")
    
    openai_ok = check_openai_token()
    ebay_marketing_ok = check_ebay_marketing_token() 
    ebay_trading_ok = check_ebay_trading_token()
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    if not openai_ok:
        print("LIKELY ISSUE: OpenAI API key expired/invalid")
        print("test_ebay_utils.py uses OpenAI for title/description generation")
        print("\nFIX:")
        print("1. Go to: https://platform.openai.com/api-keys")
        print("2. Generate new API key")
        print("3. Set environment variable: set OPENAI_API_KEY=your_new_key")
    
    if not ebay_marketing_ok:
        print("\neBay Marketing token also needs attention")
        
    if openai_ok and ebay_marketing_ok:
        print("All tokens appear to be working!")

if __name__ == "__main__":
    main()