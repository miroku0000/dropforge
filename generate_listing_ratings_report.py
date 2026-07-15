"""
Generate a comprehensive listing ratings report from AI stats data.
This script creates a CSV file with the latest ratings for all eBay listings.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys
from ebay_utils import get_all_active_listings

def generate_ratings_report():
    """Generate current_listing_ratings.csv from ai_listing_stats.csv"""
    
    # Path to the AI stats file
    stats_file = os.path.join("..", "data", "ai_listing_stats.csv")
    
    # Check if stats file exists
    if not os.path.exists(stats_file):
        print(f"Error: Stats file not found at {stats_file}")
        return False
    
    try:
        # Read the AI stats file
        print("Reading AI stats file...")
        df = pd.read_csv(stats_file, low_memory=False)
        print(f"Total records: {len(df)}")
        
        # Get most recent rating for each unique ItemID
        print("Getting latest ratings for each item...")
        latest_ratings = df.sort_values('Timestamp').groupby('ItemID').last().reset_index()
        
        # Get list of active items from eBay
        print("Fetching active eBay listings...")
        active_items = get_all_active_listings()
        active_item_ids = set(str(item['ItemID']) for item in active_items)
        print(f"Found {len(active_item_ids)} active listings on eBay")
        
        # Filter to only active listings
        latest_ratings = latest_ratings[latest_ratings['ItemID'].astype(str).isin(active_item_ids)]
        print(f"Filtered to {len(latest_ratings)} active listings with AI stats")
        
        # Select columns for the report
        columns_to_keep = [
            'ItemID',
            'Timestamp',
            'OriginalTitleRating',
            'ImprovedTitleRating',
            'OriginalDescriptionRating',
            'ImprovedDescriptionRating',
            'TitleImproved',
            'DescriptionImproved',
            'FailureReason'
        ]
        
        # Keep only columns that exist in the dataframe
        available_columns = [col for col in columns_to_keep if col in latest_ratings.columns]
        final_df = latest_ratings[available_columns].copy()
        
        # Convert ratings to numeric where possible
        rating_columns = ['OriginalTitleRating', 'ImprovedTitleRating', 
                         'OriginalDescriptionRating', 'ImprovedDescriptionRating']
        for col in rating_columns:
            if col in final_df.columns:
                final_df[col] = pd.to_numeric(final_df[col], errors='coerce')
        
        # Sort by ItemID
        final_df = final_df.sort_values('ItemID')
        
        # Add summary columns
        if 'OriginalTitleRating' in final_df.columns and 'ImprovedTitleRating' in final_df.columns:
            final_df['TitleRatingChange'] = final_df['ImprovedTitleRating'] - final_df['OriginalTitleRating']
        
        if 'OriginalDescriptionRating' in final_df.columns and 'ImprovedDescriptionRating' in final_df.columns:
            final_df['DescriptionRatingChange'] = final_df['ImprovedDescriptionRating'] - final_df['OriginalDescriptionRating']
        
        # Save to CSV with timestamp and standard filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file_timestamped = f'current_listing_ratings_{timestamp}.csv'
        output_file_standard = 'current_listing_ratings.csv'
        
        # Save timestamped version
        final_df.to_csv(output_file_timestamped, index=False)
        print(f"\\nCreated {output_file_timestamped} with {len(final_df)} unique listings")
        
        # Also save as standard filename (overwriting if exists)
        final_df.to_csv(output_file_standard, index=False)
        print(f"Created {output_file_standard} (latest version)")
        
        # Print summary statistics
        print("\\n" + "="*60)
        print("SUMMARY STATISTICS FOR ACTIVE LISTINGS")
        print("="*60)
        print(f"Total active listings processed: {len(final_df)}")
        
        # All are active now
        active_df = final_df
        
        # Count successful updates vs failures
        if 'FailureReason' in final_df.columns:
            successful_updates = final_df['FailureReason'].isna().sum()
            failed_updates = final_df['FailureReason'].notna().sum()
            print(f"\\nUpdate Results:")
            print(f"  Successful: {successful_updates}")
            print(f"  Failed: {failed_updates}")
        
        if 'OriginalTitleRating' in final_df.columns:
            title_count = active_df['OriginalTitleRating'].notna().sum()
            print(f"\\nActive listings with Title ratings: {title_count}")
        
        if 'OriginalDescriptionRating' in final_df.columns:
            desc_count = active_df['OriginalDescriptionRating'].notna().sum()
            print(f"Active listings with Description ratings: {desc_count}")
        
        # Calculate averages for non-null values
        print("\\n" + "-"*40)
        print("AVERAGE RATINGS (ACTIVE LISTINGS ONLY)")
        print("-"*40)
        
        # Title ratings
        if 'OriginalTitleRating' in active_df.columns:
            title_orig = active_df['OriginalTitleRating'].dropna()
            if len(title_orig) > 0:
                print(f"\\nTitle Ratings:")
                print(f"  Before: {title_orig.mean():.2f} (min: {title_orig.min():.0f}, max: {title_orig.max():.0f})")
                
                if 'ImprovedTitleRating' in active_df.columns:
                    title_imp = active_df['ImprovedTitleRating'].dropna()
                    if len(title_imp) > 0:
                        print(f"  After:  {title_imp.mean():.2f} (min: {title_imp.min():.0f}, max: {title_imp.max():.0f})")
                        improvement = title_imp.mean() - title_orig.mean()
                        print(f"  Improvement: {improvement:+.2f}")
        
        # Description ratings  
        if 'OriginalDescriptionRating' in active_df.columns:
            desc_orig = active_df['OriginalDescriptionRating'].dropna()
            if len(desc_orig) > 0:
                print(f"\\nDescription Ratings:")
                print(f"  Before: {desc_orig.mean():.2f} (min: {desc_orig.min():.0f}, max: {desc_orig.max():.0f})")
                
                if 'ImprovedDescriptionRating' in active_df.columns:
                    desc_imp = active_df['ImprovedDescriptionRating'].dropna()
                    if len(desc_imp) > 0:
                        print(f"  After:  {desc_imp.mean():.2f} (min: {desc_imp.min():.0f}, max: {desc_imp.max():.0f})")
                        improvement = desc_imp.mean() - desc_orig.mean()
                        print(f"  Improvement: {improvement:+.2f}")
        
        # Count improvements
        print("\\n" + "-"*40)
        print("IMPROVEMENT COUNTS")
        print("-"*40)
        
        if 'TitleImproved' in final_df.columns:
            title_improved = final_df['TitleImproved'].fillna(False).infer_objects(copy=False)
            if title_improved.dtype == 'object':
                title_improved = title_improved.str.lower() == 'true'
            print(f"Titles improved: {title_improved.sum()}")
        
        if 'DescriptionImproved' in final_df.columns:
            desc_improved = final_df['DescriptionImproved'].fillna(False).infer_objects(copy=False)
            if desc_improved.dtype == 'object':
                desc_improved = desc_improved.str.lower() == 'true'
            print(f"Descriptions improved: {desc_improved.sum()}")
        
        # Show failure reasons if any
        if 'FailureReason' in final_df.columns:
            failures = final_df[final_df['FailureReason'].notna()]['FailureReason'].value_counts()
            if len(failures) > 0:
                print("\\n" + "-"*40)
                print("FAILURE REASONS (ACTIVE LISTINGS)")
                print("-"*40)
                total_failures = len(final_df[final_df['FailureReason'].notna()])
                print(f"Total failures: {total_failures}\\n")
                for reason, count in failures.head(10).items():
                    percentage = (count / total_failures) * 100
                    print(f"{reason}: {count} ({percentage:.1f}%)")
        
        print("\\n" + "="*60)
        print(f"Reports saved successfully!")
        print(f"  - {output_file_standard} (latest)")
        print(f"  - {output_file_timestamped} (archived)")
        print("="*60)
        
        # Open the file in the default application (Excel, etc.)
        print(f"\\nOpening {output_file_standard}...")
        os.startfile(output_file_standard)
        
        return True
        
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = generate_ratings_report()
    sys.exit(0 if success else 1)