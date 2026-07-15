"""
Batch processing version of test_ebay_utils.py

This script processes eBay listings in batches using OpenAI's batch API for 50% cost reduction.
It collects all LLM requests first, submits them as a batch, then applies the results.

Usage:
    python test_ebay_utils_batch.py --batch --min-description-rating 8 --min-title-rating 8
    python test_ebay_utils_batch.py --batch --check-batch BATCH_ID
"""

import sys
import logging
from datetime import datetime
import json
import copy
import argparse
import re
import time
from colorama import init, Fore, Style
from batch_llm_processor import BatchLLMProcessor

# Setup logging
log_filename = f"test_ebay_utils_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.info("[DEBUG] Starting test_ebay_utils_batch.py")
logging.info(f"[DEBUG] Logging to file: {log_filename}")

# Import eBay utilities
try:
    from combined_ebay_fixes import apply_combined_patches
    apply_combined_patches()
    logging.info("[DEBUG] Applied combined patches (retry + XML fixes)")
except ImportError:
    logging.warning("[DEBUG] Could not import combined fixes")

import ebay_utils
from listing_ai_stats import summarize_ai_stats
from batch_collection_utils import collect_listings_for_batch

# Initialize colorama
init(autoreset=True)

def log_print(message, level=logging.INFO, end='\n'):
    """Print to console and log to file"""
    print(message, end=end)
    import re
    clean_message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
    logging.log(level, clean_message)

def collect_batch_requests(MIN_DESCRIPTION_RATING=6, MIN_TITLE_RATING=6):
    """
    Collect all LLM requests for batch processing WITHOUT making individual API calls
    
    Returns:
        tuple: (processor, listings_data) where listings_data contains all the info needed for updates
    """
    log_print("\n" + "=" * 30 + " Collecting Batch Requests " + "=" * 30)
    
    processor = BatchLLMProcessor()
    listings_data = []
    
    # Get listings data WITHOUT processing them
    final_report = collect_listings_for_batch(ebay_utils)
    
    if not final_report:
        log_print("No listings to process")
        return processor, []
    
    log_print(f"\nPreparing batch requests for {len(final_report)} listings...")
    
    # Track request types for summary
    rating_requests = 0
    specifics_requests = 0
    
    for idx, entry in enumerate(final_report, 1):
        item_id = entry.get("ItemID")
        if not item_id:
            continue
            
        listing_data = {
            "item_id": item_id,
            "entry": entry,
            "request_ids": {}
        }
        
        # Show progress every 50 items instead of each one
        if idx % 50 == 0 or idx == 1:
            log_print(f"  Preparing requests: {idx}/{len(final_report)} listings...")
        
        # Collect rating requests (these determine if we need to generate)
        description = entry.get("Description", "")
        title = entry.get("Title", "")
        current_specifics = entry.get("PresentSpecifics", {})
        
        if description and description != "N/A":
            # Add description rating request
            request_id = processor.add_description_rating_request(
                item_id, description, current_specifics
            )
            listing_data["request_ids"]["rate_description"] = request_id
            rating_requests += 1
            
            # Add title rating request if we have a title
            if title and title != "N/A":
                request_id = processor.add_title_rating_request(
                    item_id, title, description
                )
                listing_data["request_ids"]["rate_title"] = request_id
                rating_requests += 1
        
        # Collect missing specifics requests
        missing = list(
            set(entry.get("MissingRequired", []) + entry.get("MissingPreferred", []))
        )
        
        # Always check for Model and Type
        if "Model" not in current_specifics and "Model" not in missing:
            missing.append("Model")
        if "Type" not in current_specifics and "Type" not in missing:
            missing.append("Type")
        
        missing = [m for m in missing if "N/A" not in m]
        
        if missing and description and "N/A" not in description:
            request_id = processor.add_specifics_generation_request(
                item_id, description, missing, title
            )
            listing_data["request_ids"]["generate_specifics"] = request_id
            listing_data["missing_specifics"] = missing
            specifics_requests += 1
        
        listings_data.append(listing_data)
    
    log_print(f"\n" + "=" * 50)
    log_print(f"Batch Request Summary:")
    log_print(f"  Total listings: {len(final_report)}")
    log_print(f"  Rating requests: {rating_requests}")
    log_print(f"  Specifics requests: {specifics_requests}")
    log_print(f"  Total batch requests: {len(processor.requests)}")
    log_print("=" * 50)
    return processor, listings_data

def collect_generation_requests(processor, listings_data, results, 
                               MIN_DESCRIPTION_RATING, MIN_TITLE_RATING):
    """
    Based on rating results, collect generation requests
    
    Returns:
        Updated listings_data with generation request IDs
    """
    log_print("\n" + "=" * 30 + " Collecting Generation Requests " + "=" * 30)
    
    generation_count = 0
    
    for listing in listings_data:
        item_id = listing["item_id"]
        item_results = results.get(item_id, {})
        entry = listing["entry"]
        
        description = entry.get("Description", "")
        title = entry.get("Title", "")
        current_specifics = entry.get("PresentSpecifics", {})
        
        # Check if description needs improvement
        desc_rating = item_results.get("rate_description", 10)
        if desc_rating < MIN_DESCRIPTION_RATING and description and description != "N/A":
            request_id = processor.add_description_generation_request(
                item_id, description, current_specifics
            )
            listing["request_ids"]["generate_description"] = request_id
            generation_count += 1
            log_print(f"  Item {item_id}: Description needs improvement (rating: {desc_rating})")
        
        # Check if title needs improvement
        title_rating = item_results.get("rate_title", 10)
        if title_rating < MIN_TITLE_RATING and title and title != "N/A":
            request_id = processor.add_title_generation_request(
                item_id, title, description
            )
            listing["request_ids"]["generate_title"] = request_id
            generation_count += 1
            log_print(f"  Item {item_id}: Title needs improvement (rating: {title_rating})")
    
    log_print(f"\nTotal generation requests: {generation_count}")
    return listings_data

def apply_batch_results(listings_data, rating_results, generation_results=None):
    """
    Apply the batch results to eBay listings
    """
    log_print("\n" + "=" * 30 + " Applying Batch Results " + "=" * 30)
    
    updates_made = 0
    titles_updated = 0
    descriptions_updated = 0
    specifics_updated = 0
    
    for listing in listings_data:
        item_id = listing["item_id"]
        entry = listing["entry"]
        
        # Combine results
        item_results = rating_results.get(item_id, {})
        if generation_results:
            item_results.update(generation_results.get(item_id, {}))
        
        log_print(f"\n--- Processing Item {item_id} ---")
        
        # Update title if generated
        if "generate_title" in item_results:
            new_title = item_results["generate_title"]
            if new_title and len(new_title) <= 80:
                log_print(f"  Updating title: {new_title[:50]}...")
                if ebay_utils.update_item_title(item_id, new_title):
                    titles_updated += 1
                    updates_made += 1
                    log_print(Fore.GREEN + "  ✓ Title updated successfully")
                else:
                    log_print(Fore.RED + "  ✗ Title update failed")
        
        # Update description if generated
        if "generate_description" in item_results:
            new_desc = item_results["generate_description"]
            if new_desc:
                # Clean the description
                new_desc = ebay_utils._strip_openai_tag(new_desc)
                new_desc = ebay_utils.clean_llm_description_output(new_desc)
                
                log_print(f"  Updating description ({len(new_desc)} chars)...")
                if ebay_utils.update_item_description(item_id, new_desc, is_fixed_price=True):
                    descriptions_updated += 1
                    updates_made += 1
                    log_print(Fore.GREEN + "  ✓ Description updated successfully")
                else:
                    log_print(Fore.RED + "  ✗ Description update failed")
        
        # Update specifics if generated
        if "generate_specifics" in item_results:
            llm_suggestions = item_results["generate_specifics"]
            
            # Add fallback for Model and Type if still missing
            if "missing_specifics" in listing:
                missing = listing["missing_specifics"]
                title = entry.get("Title", "")
                
                # Fallback for Model
                if "Model" in missing and "Model" not in llm_suggestions:
                    model_patterns = [
                        r'\b[A-Z0-9]{3,}[-]?[A-Z0-9]+\b',
                        r'\b\d{3,}\b',
                        r'\bModel\s+([A-Z0-9]+)\b',
                    ]
                    for pattern in model_patterns:
                        match = re.search(pattern, title, re.IGNORECASE)
                        if match:
                            model_value = match.group(0) if match.lastindex is None else match.group(1)
                            llm_suggestions["Model"] = model_value[:65]
                            log_print(f"  Added Model from title: {model_value}")
                            break
                    else:
                        title_words = title.split()[:3]
                        if title_words:
                            llm_suggestions["Model"] = " ".join(title_words)[:65]
                            log_print(f"  Added Model from title prefix")
                
                # Fallback for Type
                if "Type" in missing and "Type" not in llm_suggestions:
                    type_keywords = {
                        "Antenna": ["antenna", "aerial"],
                        "Cable": ["cable", "cord", "wire"],
                        "Adapter": ["adapter", "adaptor"],
                        "Charger": ["charger", "charging"],
                        "Battery": ["battery"],
                        "Case": ["case", "cover"],
                        "Stand": ["stand", "mount", "holder"],
                    }
                    
                    title_lower = title.lower()
                    for type_name, keywords in type_keywords.items():
                        if any(kw in title_lower for kw in keywords):
                            llm_suggestions["Type"] = type_name
                            log_print(f"  Added Type from title: {type_name}")
                            break
                    else:
                        llm_suggestions["Type"] = "Accessory"
                        log_print(f"  Added Type fallback: Accessory")
            
            if llm_suggestions:
                current_specifics = entry.get("PresentSpecifics", {})
                updated_specifics = copy.deepcopy(current_specifics)
                
                for name, value in llm_suggestions.items():
                    if name not in updated_specifics or not updated_specifics.get(name):
                        updated_specifics[name] = [value]
                
                log_print(f"  Updating specifics: {list(llm_suggestions.keys())}")
                if ebay_utils.update_item_specifics(item_id, updated_specifics, is_fixed_price=True):
                    specifics_updated += 1
                    updates_made += 1
                    log_print(Fore.GREEN + "  ✓ Specifics updated successfully")
                else:
                    log_print(Fore.RED + "  ✗ Specifics update failed")
        
        # Small delay between updates
        if updates_made > 0:
            time.sleep(0.5)
    
    log_print(f"\n" + "=" * 50)
    log_print(f"Batch processing complete:")
    log_print(f"  Titles updated: {titles_updated}")
    log_print(f"  Descriptions updated: {descriptions_updated}")
    log_print(f"  Specifics updated: {specifics_updated}")
    log_print(f"  Total updates: {updates_made}")
    
def main():
    parser = argparse.ArgumentParser(
        description="Batch process eBay listings with OpenAI batch API"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use batch processing (50% cost reduction, but takes longer)"
    )
    
    parser.add_argument(
        "--min-description-rating",
        type=int,
        default=6,
        help="Minimum acceptable description rating"
    )
    
    parser.add_argument(
        "--min-title-rating",
        type=int,
        default=6,
        help="Minimum acceptable title rating"
    )
    
    parser.add_argument(
        "--check-batch",
        type=str,
        help="Check status of an existing batch by ID"
    )
    
    parser.add_argument(
        "--get-results",
        type=str,
        help="Get results from a completed batch by ID"
    )
    
    parser.add_argument(
        "--two-phase",
        action="store_true",
        help="Use two-phase processing: first rate, then generate based on ratings"
    )
    
    args = parser.parse_args()
    
    if args.check_batch:
        # Check batch status
        processor = BatchLLMProcessor()
        status = processor.check_batch_status(args.check_batch)
        log_print(f"\nBatch Status for {args.check_batch}:")
        log_print(f"  Status: {status['status']}")
        log_print(f"  Created: {datetime.fromtimestamp(status['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        if status['completed_at']:
            log_print(f"  Completed: {datetime.fromtimestamp(status['completed_at']).strftime('%Y-%m-%d %H:%M:%S')}")
        log_print(f"  Progress: {status['request_counts']['completed']}/{status['request_counts']['total']}")
        if status['request_counts']['failed'] > 0:
            log_print(f"  Failed: {status['request_counts']['failed']}")
        return
    
    if args.get_results:
        # Get batch results
        processor = BatchLLMProcessor()
        results = processor.get_batch_results(args.get_results)
        
        # Save results to file
        output_file = f"batch_results_{args.get_results}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        log_print(f"\nResults saved to {output_file}")
        log_print(f"Total items with results: {len(results)}")
        
        # Show summary
        for item_id, item_results in list(results.items())[:5]:
            log_print(f"\nItem {item_id}:")
            for key, value in item_results.items():
                if isinstance(value, str) and len(value) > 100:
                    log_print(f"  {key}: {value[:100]}...")
                else:
                    log_print(f"  {key}: {value}")
        
        if len(results) > 5:
            log_print(f"\n... and {len(results) - 5} more items")
        return
    
    if args.batch:
        if args.two_phase:
            # Two-phase batch processing
            log_print("\n" + "=" * 50)
            log_print("PHASE 1: Rating Collection")
            log_print("=" * 50)
            
            # Phase 1: Collect and process rating requests
            processor, listings_data = collect_batch_requests(
                args.min_description_rating, 
                args.min_title_rating
            )
            
            if not processor.requests:
                log_print("No requests to process")
                return
            
            # Submit rating batch
            batch_id_1 = processor.submit_batch("eBay Listing Ratings")
            log_print(f"\nPhase 1 Batch ID: {batch_id_1}")
            log_print(f"Waiting for rating results (timeout: 4 hours, checking every 60 seconds)...")
            log_print(f"Batch contains {len(processor.requests)} requests")
            
            if not processor.wait_for_batch(batch_id_1, check_interval=60, max_wait=14400):
                log_print(Fore.RED + "Rating batch failed")
                return
            
            try:
                rating_results = processor.get_batch_results(batch_id_1)
            except ValueError as e:
                if "No output file available" in str(e):
                    log_print(Fore.YELLOW + f"Rating batch stuck in finalizing state: {e}")
                    log_print("Attempting recovery with extended wait...")
                    try:
                        rating_results = processor.get_batch_results(batch_id_1, wait_for_output=True, max_wait=600)
                        log_print(Fore.GREEN + "Recovery successful!")
                    except Exception as recovery_error:
                        log_print(Fore.RED + f"Recovery failed: {recovery_error}")
                        log_print("Batch appears to be stuck. Please check OpenAI dashboard or try again later.")
                        return
                else:
                    raise
            
            # Phase 2: Collect generation requests based on ratings
            log_print("\n" + "=" * 50)
            log_print("PHASE 2: Content Generation")
            log_print("=" * 50)
            
            processor = BatchLLMProcessor()  # New processor for phase 2
            listings_data = collect_generation_requests(
                processor, listings_data, rating_results,
                args.min_description_rating, args.min_title_rating
            )
            
            if processor.requests:
                batch_id_2 = processor.submit_batch("eBay Content Generation")
                log_print(f"\nPhase 2 Batch ID: {batch_id_2}")
                log_print(f"Waiting for generation results (timeout: 4 hours, checking every 60 seconds)...")
                log_print(f"Batch contains {len(processor.requests)} requests")
                
                if processor.wait_for_batch(batch_id_2, check_interval=60, max_wait=14400):
                    try:
                        generation_results = processor.get_batch_results(batch_id_2)
                        # Apply all results
                        apply_batch_results(listings_data, rating_results, generation_results)
                    except ValueError as e:
                        if "No output file available" in str(e):
                            log_print(Fore.YELLOW + f"Batch stuck in finalizing state: {e}")
                            log_print("Attempting recovery with extended wait...")
                            try:
                                # Try again with force_retry if implemented
                                generation_results = processor.get_batch_results(batch_id_2, wait_for_output=True, max_wait=600)
                                apply_batch_results(listings_data, rating_results, generation_results)
                                log_print(Fore.GREEN + "Recovery successful!")
                            except Exception as recovery_error:
                                log_print(Fore.RED + f"Recovery failed: {recovery_error}")
                                log_print("Batch appears to be stuck. Please check OpenAI dashboard or try again later.")
                        else:
                            raise
                else:
                    log_print(Fore.RED + "Generation batch failed")
            else:
                log_print("No content generation needed")
                # Still apply specifics updates
                apply_batch_results(listings_data, rating_results)
        
        else:
            # Single-phase batch processing (original behavior)
            processor, listings_data = collect_batch_requests(
                args.min_description_rating,
                args.min_title_rating
            )
            
            if not processor.requests:
                log_print("No requests to process")
                return
            
            log_print(f"\nSubmitting batch with {len(processor.requests)} requests...")
            log_print("Note: Large batches can take 1-3 hours depending on OpenAI load")
            log_print("Timeout set to 4 hours with status checks every 60 seconds")
            
            batch_id = processor.submit_batch("eBay Listing Processing")
            
            log_print(f"\nBatch ID: {batch_id}")
            log_print("You can check status with: python test_ebay_utils_batch.py --check-batch " + batch_id)
            log_print("\nWaiting for batch to complete...")
            
            if processor.wait_for_batch(batch_id, check_interval=60, max_wait=14400):
                results = processor.get_batch_results(batch_id)
                apply_batch_results(listings_data, results)
            else:
                log_print(Fore.RED + "\nBatch processing failed or timed out")
                log_print(f"Check status with: python test_ebay_utils_batch.py --check-batch {batch_id}")
    
    else:
        log_print("Use --batch flag to enable batch processing")
        log_print("Example: python test_ebay_utils_batch.py --batch --min-description-rating 8")

if __name__ == "__main__":
    main()