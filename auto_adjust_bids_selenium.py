"""
Alternative approach: Use Selenium to automate bid adjustments through eBay's web interface.
This bypasses API limitations and works with the actual eBay Seller Hub.
"""

import os
import time
import json
import pandas as pd
import glob
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

def setup_driver():
    """Setup Chrome driver with appropriate options."""
    options = Options()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Optional: Keep browser open after script ends
    options.add_experimental_option("detach", True)
    
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    
    return driver

def login_to_ebay(driver):
    """Navigate to eBay and wait for manual login."""
    print("\n" + "="*60)
    print("MANUAL STEP REQUIRED")
    print("="*60)
    print("1. Browser will open to eBay Seller Hub")
    print("2. Please log in manually")
    print("3. Navigate to: Marketing > Promotions > Top Converters Test")
    print("4. Click 'Edit campaign'")
    print("5. Click on 'Keywords' tab")
    print("6. Press ENTER here when ready...")
    print("="*60)
    
    driver.get("https://www.ebay.com/sh/mkt/promotions")
    
    input("\nPress ENTER when you're on the Keywords page...")
    
    return True

def find_keyword_row(driver, keyword_text, match_type):
    """Find a specific keyword row in the table."""
    try:
        # Wait for table to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        
        # Find all rows
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        for row in rows:
            try:
                # Get keyword text and match type from row
                keyword_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)")
                if keyword_text.lower() in keyword_cell.text.lower():
                    # Check match type
                    match_cell = row.find_element(By.CSS_SELECTOR, "td:nth-child(3)")
                    if match_type.lower() in match_cell.text.lower():
                        return row
            except:
                continue
                
        return None
        
    except Exception as e:
        print(f"Error finding keyword row: {e}")
        return None

def update_keyword_bid(driver, keyword, match_type, new_bid):
    """Update a single keyword bid in the eBay interface."""
    try:
        # Find the keyword row
        row = find_keyword_row(driver, keyword, match_type)
        
        if not row:
            print(f"  [SKIP] Could not find '{keyword}' ({match_type})")
            return False
        
        # Find the bid input field in this row
        bid_input = row.find_element(By.CSS_SELECTOR, "input[type='text']")
        
        # Clear and enter new bid
        bid_input.clear()
        bid_input.send_keys(str(new_bid))
        
        # Tab out to trigger validation
        bid_input.send_keys(Keys.TAB)
        
        time.sleep(0.5)  # Small delay for UI update
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to update '{keyword}': {e}")
        return False

def save_changes(driver):
    """Click the save button to apply changes."""
    try:
        # Look for save button
        save_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Save')]")
        save_button.click()
        
        # Wait for success message or page reload
        time.sleep(3)
        
        print("\n[SUCCESS] Changes saved!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Could not save changes: {e}")
        return False

def calculate_adjustments():
    """Calculate bid adjustments from the latest keyword report."""
    downloads_dir = os.path.expanduser('~/Downloads')
    pattern = os.path.join(downloads_dir, 'Top Converters Test_Keyword*.csv')
    files = glob.glob(pattern)
    
    if not files:
        print("No keyword report found!")
        return []
    
    latest_report = max(files, key=os.path.getmtime)
    print(f"Using report: {os.path.basename(latest_report)}")
    
    # Parse CSV
    df = pd.read_csv(latest_report, skiprows=1)
    df['Bid'] = df['Bid'].str.replace('$', '').astype(float)
    
    # Filter for priority keywords (those with impressions or clicks)
    priority_df = df[
        (df['Status'] == 'ACTIVE') & 
        ((df['Impressions'] > 0) | (df['Clicks'] > 0))
    ].copy()
    
    adjustments = []
    
    for _, row in priority_df.iterrows():
        current_bid = row['Bid']
        
        # Simple logic: increase all bids by 50%
        new_bid = min(current_bid * 1.5, 1.50)  # Cap at $1.50
        
        adjustments.append({
            'keyword': row['Seller Keyword'],
            'match_type': row['Keyword Match Type'],
            'current_bid': current_bid,
            'new_bid': round(new_bid, 2),
            'impressions': row['Impressions'],
            'clicks': row['Clicks']
        })
    
    # Sort by clicks (highest first), then impressions
    adjustments.sort(key=lambda x: (x['clicks'], x['impressions']), reverse=True)
    
    return adjustments

def main():
    """Main automation function."""
    print("="*60)
    print("TOP CONVERTERS BID AUTOMATION (via Selenium)")
    print("="*60)
    
    # Calculate adjustments
    adjustments = calculate_adjustments()
    
    if not adjustments:
        print("No adjustments needed!")
        return
    
    print(f"\nFound {len(adjustments)} keywords to adjust")
    print("\nTop adjustments:")
    for adj in adjustments[:10]:
        print(f"  {adj['keyword']} ({adj['match_type']}): "
              f"${adj['current_bid']:.2f} -> ${adj['new_bid']:.2f}")
    
    # Confirm before proceeding
    response = input("\nProceed with browser automation? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return
    
    # Setup browser
    driver = setup_driver()
    
    try:
        # Login and navigate
        login_to_ebay(driver)
        
        print("\nApplying bid adjustments...")
        success_count = 0
        
        for i, adj in enumerate(adjustments, 1):
            print(f"\n[{i}/{len(adjustments)}] Updating '{adj['keyword']}' "
                  f"({adj['match_type']}): ${adj['new_bid']:.2f}")
            
            if update_keyword_bid(driver, adj['keyword'], adj['match_type'], adj['new_bid']):
                success_count += 1
                print(f"  [OK] Updated")
            
            # Don't go too fast
            time.sleep(1)
            
            # Save periodically
            if i % 20 == 0:
                print("\n[Saving batch...]")
                save_changes(driver)
                time.sleep(2)
        
        # Final save
        if success_count > 0:
            print("\n[Saving final changes...]")
            save_changes(driver)
        
        print(f"\n{'='*60}")
        print(f"COMPLETE: {success_count}/{len(adjustments)} bids updated")
        print(f"{'='*60}")
        
        # Save log
        log_file = f"bid_adjustments_selenium_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total': len(adjustments),
                'successful': success_count,
                'adjustments': adjustments
            }, f, indent=2)
        
        print(f"\nLog saved to: {log_file}")
        print("\nBrowser will remain open for verification.")
        print("Close it manually when done.")
        
    except Exception as e:
        print(f"\n[ERROR] Automation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Don't close browser automatically
    # driver.quit()

if __name__ == "__main__":
    main()