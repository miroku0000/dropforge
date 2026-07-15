#!/usr/bin/env python
"""
Analyze eBay listings to estimate processing times for different model presets.
This script helps you understand how long it would take to process your listings
with different quality levels and rating thresholds.

Usage:
    python analyze_ebay_listings.py --min-description-rating 7 --min-title-rating 8
"""

import argparse
import time
from datetime import timedelta
from colorama import init, Fore, Style
import ebay_utils
from ebay_utils import OLLAMA_MODELS, get_all_active_listings

init(autoreset=True)

def analyze_listings(min_desc_rating=6, min_title_rating=6, sample_size=10):
    """
    Analyze listings to determine how many need processing and estimate times.
    
    Args:
        min_desc_rating: Minimum acceptable description rating (skip if >= this)
        min_title_rating: Minimum acceptable title rating (skip if >= this)
        sample_size: Number of items to sample for rating estimation
    """
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}eBay Listings Analysis & Time Estimation")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    print(f"Fetching all active listings...")
    
    # Get all active listings
    all_listings = get_all_active_listings()
    if not all_listings:
        print(f"{Fore.RED}No active listings found!")
        return
    
    total_listings = len(all_listings)
    print(f"Total active listings: {Fore.GREEN}{total_listings}")
    
    # Sample listings to estimate ratings distribution
    print(f"\nSampling {sample_size} listings to estimate rating distribution...")
    print(f"(Using current default model: {ebay_utils.OLLAMA_DEFAULT_MODEL})\n")
    
    sample_listings = all_listings[:min(sample_size, total_listings)]
    
    # Track ratings
    desc_ratings = []
    title_ratings = []
    missing_specifics_count = 0
    items_needing_desc_update = 0
    items_needing_title_update = 0
    items_needing_any_update = 0
    
    # Time tracking for current model
    desc_rating_times = []
    title_rating_times = []
    
    for i, listing in enumerate(sample_listings, 1):
        item_id = listing.get('ItemID')
        title = listing.get('Title', '')
        
        print(f"Sampling {i}/{sample_size}: Item {item_id}", end=' ')
        
        # Get item details including description
        item_details = ebay_utils.get_item_details(item_id)
        if not item_details:
            print(f"{Fore.RED}[Failed to get details]")
            continue
            
        description = item_details.get('Description', '')
        specifics = item_details.get('ItemSpecifics', {})
        
        # Get category specifics to check for missing
        category_id = listing.get('PrimaryCategoryID')
        if category_id:
            category_specifics = ebay_utils.get_category_specifics(category_id)
            required = category_specifics.get('required', [])
            preferred = category_specifics.get('preferred', [])
            
            current_specific_names = set(specifics.keys())
            missing_required = [s for s in required if s not in current_specific_names]
            missing_preferred = [s for s in preferred if s not in current_specific_names]
            
            if missing_required or missing_preferred:
                missing_specifics_count += 1
        
        # Rate description
        start = time.time()
        desc_rating = ebay_utils.rate_description_with_llm(description, specifics)
        desc_time = time.time() - start
        desc_rating_times.append(desc_time)
        desc_ratings.append(desc_rating)
        
        # Rate title
        start = time.time()
        title_rating = ebay_utils.rate_title_with_llm(title, description)
        title_time = time.time() - start
        title_rating_times.append(title_time)
        title_ratings.append(title_rating)
        
        # Check if updates needed
        needs_desc = desc_rating < min_desc_rating
        needs_title = title_rating < min_title_rating
        
        if needs_desc:
            items_needing_desc_update += 1
        if needs_title:
            items_needing_title_update += 1
        if needs_desc or needs_title:
            items_needing_any_update += 1
        
        print(f"Desc: {desc_rating}/10, Title: {title_rating}/10")
    
    # Calculate statistics
    avg_desc_rating = sum(desc_ratings) / len(desc_ratings) if desc_ratings else 0
    avg_title_rating = sum(title_ratings) / len(title_ratings) if title_ratings else 0
    avg_desc_time = sum(desc_rating_times) / len(desc_rating_times) if desc_rating_times else 0
    avg_title_time = sum(title_rating_times) / len(title_rating_times) if title_rating_times else 0
    
    # Extrapolate to full catalog
    sample_ratio = total_listings / len(sample_listings)
    est_items_needing_desc = int(items_needing_desc_update * sample_ratio)
    est_items_needing_title = int(items_needing_title_update * sample_ratio)
    est_items_needing_any = int(items_needing_any_update * sample_ratio)
    est_missing_specifics = int(missing_specifics_count * sample_ratio)
    
    # Print analysis results
    print(f"\n{Fore.YELLOW}{'='*80}")
    print(f"{Fore.YELLOW}Analysis Results")
    print(f"{Fore.YELLOW}{'='*80}\n")
    
    print(f"{Fore.CYAN}Sample Statistics:")
    print(f"  Average Description Rating: {avg_desc_rating:.1f}/10")
    print(f"  Average Title Rating: {avg_title_rating:.1f}/10")
    print(f"  Items with missing specifics: {missing_specifics_count}/{len(sample_listings)}")
    
    print(f"\n{Fore.CYAN}Estimated Updates Needed (out of {total_listings} total):")
    print(f"  Descriptions below {min_desc_rating}: {Fore.RED}{est_items_needing_desc}")
    print(f"  Titles below {min_title_rating}: {Fore.RED}{est_items_needing_title}")
    print(f"  Items needing any update: {Fore.YELLOW}{est_items_needing_any}")
    print(f"  Items with missing specifics: {Fore.YELLOW}{est_missing_specifics}")
    
    # Calculate time estimates for each model
    print(f"\n{Fore.GREEN}{'='*80}")
    print(f"{Fore.GREEN}Time Estimates by Model Preset")
    print(f"{Fore.GREEN}{'='*80}\n")
    
    # Operations needed per item
    ops_per_item = 0
    if min_desc_rating > 0:
        ops_per_item += 1  # Rate description
    if min_title_rating > 0:
        ops_per_item += 1  # Rate title
    
    # Additional operations for items needing updates
    # (generate new title/description, re-rate, etc.)
    update_ops = 2  # Generate + re-rate
    
    for preset, model_info in OLLAMA_MODELS.items():
        model_time = model_info['avg_time']
        
        # Initial rating pass for ALL items
        initial_rating_time = total_listings * ops_per_item * model_time
        
        # Update operations only for items needing updates
        update_time = est_items_needing_any * update_ops * model_time
        
        # LLM operations for missing specifics
        specifics_time = est_missing_specifics * model_time
        
        total_time = initial_rating_time + update_time + specifics_time
        
        # Format time nicely
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        seconds = int(total_time % 60)
        
        # Color code by speed
        if preset == 'fast':
            color = Fore.GREEN
        elif preset == 'balanced':
            color = Fore.YELLOW
        else:
            color = Fore.RED
        
        print(f"{color}{preset:10} ({model_info['name']:25})")
        print(f"  {model_info['description']}")
        print(f"  Estimated time: {hours:02d}h {minutes:02d}m {seconds:02d}s")
        print(f"  Operations breakdown:")
        print(f"    - Initial ratings: {total_listings * ops_per_item:,} ops")
        print(f"    - Updates needed: {est_items_needing_any * update_ops:,} ops")
        print(f"    - Missing specifics: {est_missing_specifics:,} ops")
        print()
    
    # Recommendations
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}Recommendations")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    if est_items_needing_any < 100:
        print(f"✓ With only {est_items_needing_any} items needing updates,")
        print(f"  consider using 'quality' preset for best results.")
    elif est_items_needing_any < 500:
        print(f"✓ With {est_items_needing_any} items needing updates,")
        print(f"  'balanced' preset offers good speed/quality tradeoff.")
    else:
        print(f"✓ With {est_items_needing_any} items needing updates,")
        print(f"  consider 'fast' preset for initial pass, then 'quality' for problem items.")
    
    print(f"\n💡 Pro tip: You can skip already-good items by setting higher thresholds:")
    print(f"   --min-description-rating {min(9, min_desc_rating + 1)}")
    print(f"   --min-title-rating {min(9, min_title_rating + 1)}")
    
    # Show command examples
    print(f"\n{Fore.WHITE}Example commands:")
    print(f"  # Fast initial assessment")
    print(f"  python test_ebay_utils.py --model-preset fast --min-description-rating {min_desc_rating}")
    print(f"  \n  # Quality pass for items that need it")
    print(f"  python test_ebay_utils.py --model-preset quality --min-description-rating {min_desc_rating}")
    print(f"  \n  # Skip items that are already good enough")
    print(f"  python test_ebay_utils.py --model-preset balanced --min-description-rating {min(9, min_desc_rating + 1)}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze eBay listings and estimate processing times'
    )
    parser.add_argument(
        '--min-description-rating',
        type=int,
        default=6,
        help='Minimum acceptable description rating (default: 6)'
    )
    parser.add_argument(
        '--min-title-rating',
        type=int,
        default=6,
        help='Minimum acceptable title rating (default: 6)'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=10,
        help='Number of listings to sample for estimation (default: 10)'
    )
    parser.add_argument(
        '--model-preset',
        choices=['fast', 'balanced', 'quality'],
        default=None,
        help='Model preset to use for sampling'
    )
    
    args = parser.parse_args()
    
    # Set model preset if specified
    if args.model_preset:
        import os
        os.environ['OLLAMA_MODEL_PRESET'] = args.model_preset
        ebay_utils.DEFAULT_MODEL_PRESET = args.model_preset
        ebay_utils.OLLAMA_DEFAULT_MODEL = ebay_utils.get_ollama_model(args.model_preset)
        print(f"Using model preset '{args.model_preset}' for sampling")
    
    analyze_listings(
        min_desc_rating=args.min_description_rating,
        min_title_rating=args.min_title_rating,
        sample_size=args.sample_size
    )


if __name__ == "__main__":
    main()