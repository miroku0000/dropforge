"""
Helper script to guide user through generating an eBay User Token with Marketing API scope.
This token is required for automated bid adjustments on Top Converters campaigns.
"""

import webbrowser
import os
from datetime import datetime

def main():
    print("=" * 80)
    print("EBAY MARKETING API - USER TOKEN GENERATION GUIDE")
    print("=" * 80)
    print()
    print("[PROBLEM DETECTED]")
    print("Your current token does not have Marketing API access.")
    print("To automate bid changes, you need a User Token with 'sell.marketing' scope.")
    print()
    print("=" * 80)
    print("STEP-BY-STEP INSTRUCTIONS")
    print("=" * 80)
    print()
    print("1. This script will open the eBay Developer portal in your browser")
    print("2. Sign in with your eBay developer account")
    print("3. Click 'Get a User Token'")
    print("4. Select 'Auth'n'Auth' (OAuth) option")
    print("5. CHECK these scopes (IMPORTANT!):")
    print("   [X] sell.marketing")
    print("   [X] sell.marketing.readonly")
    print("   [X] sell.account")
    print("   [X] sell.inventory")
    print("6. Click 'Generate Token'")
    print("7. Copy the ENTIRE token (starts with 'v^1.1#i^1#p^3#f^0#I^3...')")
    print("8. Come back here and paste it")
    print()
    
    response = input("Ready to open eBay Developer portal? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        print()
        print("Opening eBay Developer portal...")
        # Production environment token generation
        url = "https://developer.ebay.com/my/auth/?env=production&index=0"
        webbrowser.open(url)
        
        print()
        print("=" * 80)
        print("After generating the token, paste it below.")
        print("The token should be VERY long (2000+ characters)")
        print("=" * 80)
        print()
        
        token = input("Paste your User Token here: ").strip()
        
        if len(token) < 100:
            print()
            print("[WARNING] Token seems too short. User tokens are typically 2000+ characters.")
            print("Make sure you copied the ENTIRE token.")
            confirm = input("Continue anyway? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Aborted.")
                return
        
        # Back up existing credentials
        if os.path.exists("credentials.txt"):
            backup_file = f"credentials_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            os.rename("credentials.txt", backup_file)
            print(f"Backed up existing credentials to: {backup_file}")
            
            # Copy back the non-token lines
            with open(backup_file, 'r') as f:
                lines = f.readlines()
            
            with open("credentials.txt", 'w') as f:
                for line in lines:
                    if not line.strip().startswith('token='):
                        f.write(line)
                # Add the new token
                f.write(f"\n# User token with Marketing API scope (generated {datetime.now()})\n")
                f.write(f"token={token}\n")
        else:
            print("[ERROR] credentials.txt not found!")
            return
        
        print()
        print("[SUCCESS] Token saved to credentials.txt")
        print()
        print("=" * 80)
        print("TESTING NEW TOKEN")
        print("=" * 80)
        
        # Test the token
        os.system("python apply_bid_changes.py")
        
    else:
        print()
        print("=" * 80)
        print("MANUAL PROCESS")
        print("=" * 80)
        print()
        print("1. Go to: https://developer.ebay.com/my/auth/?env=production&index=0")
        print("2. Generate a User Token with 'sell.marketing' scope")
        print("3. Add to credentials.txt as: token=YOUR_TOKEN_HERE")
        print("4. Run: python apply_bid_changes.py")

if __name__ == "__main__":
    main()