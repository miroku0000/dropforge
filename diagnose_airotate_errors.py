"""
Diagnostic script to analyze and fix airotate.bat errors.
Identifies root causes of failures and provides solutions.
"""

import pandas as pd
import os
import sys
from datetime import datetime
from collections import defaultdict
import time
from ebay_utils import (
    get_all_active_listings,
    get_item_specifics,
    get_category_id_for_item
)
from ebaysdk.trading import Connection as Trading

def diagnose_errors():
    """Analyze errors from ai_listing_stats.csv and identify patterns"""
    
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    
    if not os.path.exists(stats_file):
        print(f"Error: Stats file not found at {stats_file}")
        return
    
    print("="*60)
    print("AIROTATE ERROR DIAGNOSIS")
    print("="*60)
    
    # Read the stats file
    df = pd.read_csv(stats_file, low_memory=False)
    print(f"Total records: {len(df)}")
    
    # Get failure reasons
    failures = df[df['FailureReason'].notna()]
    print(f"Total failures: {len(failures)}")
    
    # Group by failure reason
    failure_counts = failures['FailureReason'].value_counts()
    print("\n" + "-"*40)
    print("FAILURE BREAKDOWN:")
    print("-"*40)
    for reason, count in failure_counts.items():
        percentage = (count / len(failures)) * 100
        print(f"{reason}: {count} ({percentage:.1f}%)")
    
    # Analyze specific error types
    print("\n" + "="*60)
    print("ERROR ANALYSIS:")
    print("="*60)
    
    # 1. Description Update Errors
    desc_errors = failures[failures['FailureReason'] == 'Description update error']
    if not desc_errors.empty:
        print("\n1. DESCRIPTION UPDATE ERRORS (3240 occurrences)")
        print("-"*40)
        print("Possible causes:")
        print("  - Description too long (eBay limit: 500,000 characters)")
        print("  - Invalid HTML in description")
        print("  - API rate limiting")
        print("  - Network timeouts")
        
        # Check for patterns
        unique_items = desc_errors['ItemID'].nunique()
        print(f"\nAffected unique items: {unique_items}")
        
        # Sample some items with this error
        sample_items = desc_errors['ItemID'].value_counts().head(5)
        print("\nMost affected items:")
        for item_id, count in sample_items.items():
            print(f"  Item {item_id}: {count} failures")
    
    # 2. Specifics Fetch Errors
    spec_errors = failures[failures['FailureReason'] == 'Specifics fetch error']
    if not spec_errors.empty:
        print("\n2. SPECIFICS FETCH ERRORS (1681 occurrences)")
        print("-"*40)
        print("Possible causes:")
        print("  - Item no longer exists on eBay")
        print("  - API authentication issues")
        print("  - Network connectivity problems")
        print("  - API rate limiting")
        
        unique_items = spec_errors['ItemID'].nunique()
        print(f"\nAffected unique items: {unique_items}")
        
        # Check if these items still exist
        print("\nChecking if sample items still exist...")
        sample_items = spec_errors['ItemID'].unique()[:3]
        for item_id in sample_items:
            try:
                specs = get_item_specifics(item_id)
                if specs:
                    print(f"  Item {item_id}: EXISTS (has {len(specs)} specifics)")
                else:
                    print(f"  Item {item_id}: NO SPECIFICS FOUND")
            except Exception as e:
                print(f"  Item {item_id}: ERROR - {str(e)[:50]}")
    
    # 3. Title Optimization Errors
    title_errors = failures[failures['FailureReason'].str.contains('Title optim', case=False, na=False)]
    if not title_errors.empty:
        print("\n3. TITLE OPTIMIZATION ERRORS (401 total)")
        print("-"*40)
        print("Possible causes:")
        print("  - Title exceeds 80 character limit")
        print("  - Special characters in title")
        print("  - API update failures")
        print("  - Cache corruption")
        
        unique_items = title_errors['ItemID'].nunique()
        print(f"\nAffected unique items: {unique_items}")
        
        # Check for typo variants
        title_opt_errors = failures[failures['FailureReason'] == 'Title optimisation error']
        title_optim_errors = failures[failures['FailureReason'] == 'Title optimization error']
        print(f"\n'Title optimisation error': {len(title_opt_errors)}")
        print(f"'Title optimization error': {len(title_optim_errors)}")
    
    # 4. Description Rating Errors
    desc_rating_errors = failures[failures['FailureReason'] == 'Description rating or generation error']
    if not desc_rating_errors.empty:
        print("\n4. DESCRIPTION RATING/GENERATION ERRORS (99 occurrences)")
        print("-"*40)
        print("Possible causes:")
        print("  - OpenAI API failures")
        print("  - Ollama model not running")
        print("  - Invalid description content")
        print("  - API key issues")
        
        unique_items = desc_rating_errors['ItemID'].nunique()
        print(f"\nAffected unique items: {unique_items}")

def test_api_health():
    """Test various API connections"""
    print("\n" + "="*60)
    print("API HEALTH CHECK:")
    print("="*60)
    
    # Test eBay API
    print("\n1. Testing eBay API...")
    try:
        # Read credentials
        with open('credentials.txt', 'r') as f:
            creds = {}
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    creds[key.strip()] = value.strip()
        
        api = Trading(
            appid=creds.get('appid'),
            devid=creds.get('devid'),
            certid=creds.get('certid'),
            token=creds.get('token'),
            config_file=None
        )
        response = api.execute('GeteBayOfficialTime', {})
        if response.reply.Ack == 'Success':
            print(f"   [OK] eBay API is working")
            print(f"   Server time: {response.reply.Timestamp}")
        else:
            print(f"   [FAIL] eBay API returned: {response.reply.Ack}")
    except Exception as e:
        print(f"   [FAIL] eBay API error: {e}")
    
    # Test OpenAI
    print("\n2. Testing OpenAI API...")
    try:
        import openai
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            print("   [OK] OpenAI API key found")
        else:
            print("   [FAIL] OpenAI API key not found in environment")
    except ImportError:
        print("   [FAIL] OpenAI module not installed")
    
    # Test Ollama
    print("\n3. Testing Ollama...")
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            print("   [OK] Ollama is running")
            models = result.stdout.strip().split('\n')[1:]  # Skip header
            if models:
                print(f"   Available models: {len(models)}")
        else:
            print("   [FAIL] Ollama not running or not installed")
    except Exception as e:
        print(f"   [FAIL] Ollama check failed: {e}")

def suggest_fixes():
    """Suggest specific fixes for the errors"""
    print("\n" + "="*60)
    print("RECOMMENDED FIXES:")
    print("="*60)
    
    fixes = [
        {
            "error": "Description update error",
            "fixes": [
                "1. Implement retry logic with exponential backoff",
                "2. Check description length before sending (max 500,000 chars)",
                "3. Validate HTML structure before API call",
                "4. Add request timeout handling (30 seconds)",
                "5. Cache successful updates to avoid re-processing"
            ]
        },
        {
            "error": "Specifics fetch error",
            "fixes": [
                "1. Check if item exists before fetching specifics",
                "2. Implement connection pooling for API calls",
                "3. Add retry logic for network errors",
                "4. Skip deleted/ended items",
                "5. Increase timeout for API calls"
            ]
        },
        {
            "error": "Title optimization error",
            "fixes": [
                "1. Validate title length (max 80 chars) before update",
                "2. Remove special characters that eBay doesn't support",
                "3. Implement fallback to original title on error",
                "4. Fix typo: standardize to 'optimization' everywhere",
                "5. Add title validation before API call"
            ]
        },
        {
            "error": "Description rating error",
            "fixes": [
                "1. Check OpenAI API key is valid",
                "2. Ensure Ollama is running when --use-ollama flag is used",
                "3. Implement timeout for LLM calls (60 seconds)",
                "4. Add fallback from OpenAI to Ollama on failure",
                "5. Skip items with corrupted descriptions"
            ]
        }
    ]
    
    for fix_group in fixes:
        print(f"\n{fix_group['error'].upper()}:")
        print("-"*40)
        for fix in fix_group['fixes']:
            print(f"  {fix}")

def check_rate_limits():
    """Check if we're hitting API rate limits"""
    print("\n" + "="*60)
    print("RATE LIMIT ANALYSIS:")
    print("="*60)
    
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    if not os.path.exists(stats_file):
        return
    
    df = pd.read_csv(stats_file, low_memory=False)
    # Timestamps are mixed ISO8601 (some with microseconds, some without);
    # parse leniently and drop any rows that still don't parse.
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601', errors='coerce')
    df = df[df['Timestamp'].notna()]

    # Group by hour to see patterns
    df['Hour'] = df['Timestamp'].dt.floor('h')
    hourly_errors = df[df['FailureReason'].notna()].groupby('Hour').size()
    
    if not hourly_errors.empty:
        print("\nErrors per hour (last 5 hours with errors):")
        for hour, count in hourly_errors.tail(5).items():
            print(f"  {hour}: {count} errors")
        
        # Check for bursts
        max_errors = hourly_errors.max()
        if max_errors > 100:
            print(f"\n⚠ High error rate detected: {max_errors} errors in one hour")
            print("  This suggests API rate limiting. Consider:")
            print("  - Adding delays between API calls")
            print("  - Implementing exponential backoff")
            print("  - Spreading processing over longer time period")

if __name__ == "__main__":
    print("Starting airotate error diagnosis...")
    print("Timestamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Run diagnostics
    diagnose_errors()
    test_api_health()
    check_rate_limits()
    suggest_fixes()
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)