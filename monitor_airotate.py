"""
Real-time monitoring script for airotate operations.
Shows live statistics and errors as they occur.
"""

import pandas as pd
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict

def monitor_stats(refresh_interval=10):
    """Monitor ai_listing_stats.csv for new entries and errors"""
    
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    
    if not os.path.exists(stats_file):
        print(f"Stats file not found: {stats_file}")
        return
    
    print("="*60)
    print("AIROTATE REAL-TIME MONITOR")
    print("="*60)
    print(f"Monitoring: {stats_file}")
    print(f"Refresh interval: {refresh_interval} seconds")
    print("Press Ctrl+C to stop\n")
    
    last_size = 0
    last_check = datetime.now()
    error_counts = defaultdict(int)
    success_counts = {'titles': 0, 'descriptions': 0}
    
    try:
        while True:
            # Read the file
            df = pd.read_csv(stats_file, low_memory=False)
            current_size = len(df)
            
            # Check for new entries
            if current_size > last_size:
                new_entries = current_size - last_size
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {new_entries} new entries")
                
                # Analyze new entries
                new_df = df.tail(new_entries)
                
                # Count successes and failures
                for _, row in new_df.iterrows():
                    if pd.notna(row.get('FailureReason')):
                        error_counts[row['FailureReason']] += 1
                    else:
                        if row.get('TitleImproved') == True or row.get('TitleImproved') == 'True':
                            success_counts['titles'] += 1
                        if row.get('DescriptionImproved') == True or row.get('DescriptionImproved') == 'True':
                            success_counts['descriptions'] += 1
                
                # Show current statistics
                print("\nCurrent Session Statistics:")
                print("-"*40)
                print(f"Successful title updates: {success_counts['titles']}")
                print(f"Successful description updates: {success_counts['descriptions']}")
                
                if error_counts:
                    print("\nErrors encountered:")
                    for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {error}: {count}")
                
                # Show processing rate
                time_elapsed = datetime.now() - last_check
                if time_elapsed.total_seconds() > 0:
                    rate = new_entries / (time_elapsed.total_seconds() / 60)
                    print(f"\nProcessing rate: {rate:.1f} items/minute")
                
                last_size = current_size
                last_check = datetime.now()
            
            # Show heartbeat
            else:
                print(".", end="", flush=True)
            
            # Check for recent errors
            recent_time = datetime.now() - timedelta(minutes=5)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            recent_errors = df[(df['Timestamp'] > recent_time) & (df['FailureReason'].notna())]
            
            if len(recent_errors) > 50:
                print(f"\n\n⚠ HIGH ERROR RATE: {len(recent_errors)} errors in last 5 minutes!")
                print("Consider pausing the process and investigating.")
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        
        # Final summary
        print("\n" + "="*60)
        print("FINAL SESSION SUMMARY")
        print("="*60)
        print(f"Total items processed: {current_size - last_size + new_entries if 'new_entries' in locals() else 0}")
        print(f"Successful title updates: {success_counts['titles']}")
        print(f"Successful description updates: {success_counts['descriptions']}")
        
        if error_counts:
            print("\nTotal errors by type:")
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / sum(error_counts.values())) * 100
                print(f"  {error}: {count} ({percentage:.1f}%)")
        
        print("="*60)

def show_recent_errors(minutes=10):
    """Show errors from the last N minutes"""
    
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    
    if not os.path.exists(stats_file):
        print(f"Stats file not found: {stats_file}")
        return
    
    df = pd.read_csv(stats_file, low_memory=False)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    recent = df[df['Timestamp'] > cutoff_time]
    
    print(f"\nActivity in last {minutes} minutes:")
    print("-"*40)
    print(f"Total entries: {len(recent)}")
    
    # Count failures
    failures = recent[recent['FailureReason'].notna()]
    if not failures.empty:
        print(f"Failures: {len(failures)}")
        failure_counts = failures['FailureReason'].value_counts()
        for reason, count in failure_counts.items():
            print(f"  {reason}: {count}")
    
    # Count successes
    title_improved = recent['TitleImproved'].apply(lambda x: x in [True, 'True']).sum()
    desc_improved = recent['DescriptionImproved'].apply(lambda x: x in [True, 'True']).sum()
    
    print(f"\nSuccesses:")
    print(f"  Titles improved: {title_improved}")
    print(f"  Descriptions improved: {desc_improved}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "recent":
        minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_recent_errors(minutes)
    else:
        print("Starting real-time monitoring...")
        print("(You can also run 'python monitor_airotate.py recent [minutes]' to see recent activity)\n")
        monitor_stats()