"""
Analyze recent errors from the latest airotate run.
Provides detailed breakdown and suggested fixes.
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from collections import Counter

def analyze_recent_run():
    """Analyze errors from the most recent run"""
    
    print("="*70)
    print("RECENT ERROR ANALYSIS - " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("="*70)
    
    # Read the stats file
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    if not os.path.exists(stats_file):
        print("Stats file not found")
        return
    
    # Load data
    df = pd.read_csv(stats_file, low_memory=False)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    # Get data from last 2 hours
    cutoff_time = datetime.now() - timedelta(hours=2)
    recent_df = df[df['Timestamp'] > cutoff_time]
    
    print(f"\nAnalyzing last 2 hours of activity...")
    print(f"Total operations: {len(recent_df)}")
    
    # Count successes and failures
    failures = recent_df[recent_df['FailureReason'].notna()]
    successes = recent_df[recent_df['FailureReason'].isna()]
    
    print(f"Successful operations: {len(successes)}")
    print(f"Failed operations: {len(failures)}")
    
    if len(recent_df) > 0:
        success_rate = (len(successes) / len(recent_df)) * 100
        print(f"Success rate: {success_rate:.2f}%")
    
    # Analyze failures
    if not failures.empty:
        print("\n" + "-"*50)
        print("ERROR BREAKDOWN:")
        print("-"*50)
        
        error_counts = failures['FailureReason'].value_counts()
        for reason, count in error_counts.items():
            percentage = (count / len(failures)) * 100
            print(f"{reason}: {count} ({percentage:.1f}%)")
        
        # Get sample item IDs for each error type
        print("\n" + "-"*50)
        print("SAMPLE ITEMS WITH ERRORS:")
        print("-"*50)
        
        for error_type in error_counts.index[:3]:  # Top 3 error types
            sample_items = failures[failures['FailureReason'] == error_type]['ItemID'].head(3)
            print(f"\n{error_type}:")
            for item_id in sample_items:
                print(f"  - Item {item_id}")
    
    # Analyze success patterns
    print("\n" + "-"*50)
    print("SUCCESS ANALYSIS:")
    print("-"*50)
    
    titles_improved = successes['TitleImproved'].apply(lambda x: str(x).lower() == 'true').sum()
    descs_improved = successes['DescriptionImproved'].apply(lambda x: str(x).lower() == 'true').sum()
    
    print(f"Titles improved: {titles_improved}")
    print(f"Descriptions improved: {descs_improved}")
    
    # Check for patterns in timing
    if not failures.empty:
        failures_copy = failures.copy()
        failures_copy['Hour'] = failures_copy['Timestamp'].dt.hour
        hourly_errors = failures_copy.groupby('Hour').size()
        
        if not hourly_errors.empty:
            print("\n" + "-"*50)
            print("ERRORS BY HOUR:")
            print("-"*50)
            for hour, count in hourly_errors.items():
                print(f"  Hour {hour:02d}: {count} errors")

def identify_root_causes():
    """Identify root causes and suggest fixes"""
    
    print("\n" + "="*70)
    print("ROOT CAUSE ANALYSIS & FIXES")
    print("="*70)
    
    issues_and_fixes = [
        {
            "issue": "Title optimization error (123 instances)",
            "causes": [
                "1. LLM API timeout or rate limiting",
                "2. Title generation returning invalid format",
                "3. Title rating function failing",
                "4. Cache corruption"
            ],
            "fixes": [
                "- Check OpenAI API key is valid and has credits",
                "- Verify Ollama is running if --use-ollama is set",
                "- Clear title cache: delete .cache_llm_data_title/",
                "- Add timeout handling for LLM calls",
                "- Implement fallback from OpenAI to Ollama"
            ]
        },
        {
            "issue": "Missing required item specifics (Model, Type)",
            "causes": [
                "1. Category requires these specifics but they're not provided",
                "2. LLM not generating required specifics",
                "3. Item in wrong category"
            ],
            "fixes": [
                "- Skip items with missing required specifics",
                "- Generate default values for Model/Type when missing",
                "- Check category mapping is correct",
                "- Add validation before attempting updates"
            ]
        },
        {
            "issue": "Description update errors",
            "causes": [
                "1. Description too long or invalid HTML",
                "2. Network timeout during update",
                "3. Item was ended/sold during processing"
            ],
            "fixes": [
                "- Already fixed with retry logic",
                "- Check item status before updating",
                "- Validate HTML structure before sending"
            ]
        }
    ]
    
    for item in issues_and_fixes:
        print(f"\n{item['issue'].upper()}")
        print("-"*50)
        print("\nPossible causes:")
        for cause in item['causes']:
            print(f"  {cause}")
        print("\nRecommended fixes:")
        for fix in item['fixes']:
            print(f"  {fix}")

def check_api_health():
    """Quick health check of APIs"""
    print("\n" + "="*70)
    print("API HEALTH CHECK")
    print("="*70)
    
    # Check OpenAI
    print("\n1. OpenAI API:")
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if api_key:
        print(f"   API key found: {api_key[:8]}...")
    else:
        print("   [WARNING] No OpenAI API key in environment")
    
    # Check Ollama
    print("\n2. Ollama:")
    import subprocess
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            models = result.stdout.strip().split('\n')[1:]
            print(f"   Running with {len(models)} models available")
        else:
            print("   [WARNING] Ollama not running")
    except:
        print("   [WARNING] Ollama not accessible")
    
    # Check eBay API by looking at recent success
    print("\n3. eBay API:")
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    if os.path.exists(stats_file):
        df = pd.read_csv(stats_file, low_memory=False)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        recent_time = datetime.now() - timedelta(minutes=30)
        recent = df[df['Timestamp'] > recent_time]
        successes = recent[recent['FailureReason'].isna()]
        if len(successes) > 0:
            print(f"   Working - {len(successes)} successful operations in last 30 min")
        else:
            print("   [WARNING] No successful operations in last 30 minutes")

def suggest_immediate_actions():
    """Suggest immediate actions to take"""
    print("\n" + "="*70)
    print("RECOMMENDED IMMEDIATE ACTIONS")
    print("="*70)
    
    actions = [
        "1. Clear LLM caches to resolve potential corruption:",
        "   rmdir /s /q .cache_llm_data_title",
        "   rmdir /s /q .cache_llm_data_desc",
        "",
        "2. Check Ollama status:",
        "   ollama list",
        "   ollama serve  (if not running)",
        "",
        "3. Verify OpenAI API key:",
        "   echo %OPENAI_API_KEY%",
        "",
        "4. Run diagnostic:",
        "   python diagnose_airotate_errors.py",
        "",
        "5. Test with a single item:",
        "   python fix_ebay_errors.py 227101505466",
        "",
        "6. Monitor real-time:",
        "   python monitor_airotate.py"
    ]
    
    for action in actions:
        print(action)

if __name__ == "__main__":
    analyze_recent_run()
    identify_root_causes()
    check_api_health()
    suggest_immediate_actions()
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)