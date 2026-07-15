import sys
import logging
from datetime import datetime

# Setup logging to both file and console
log_filename = f"test_ebay_utils_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)

logging.info("[DEBUG] Starting test_ebay_utils.py")
logging.info(f"[DEBUG] Logging to file: {log_filename}")
logging.info("[DEBUG] Importing modules...")

# Apply combined patches (retry logic + XML fixes) to avoid conflicts
try:
    from combined_ebay_fixes import apply_combined_patches
    apply_combined_patches()
    logging.info("[DEBUG] Applied combined patches (retry + XML fixes)")
except ImportError:
    # Fallback to individual patches if combined not available
    try:
        from ebay_utils_error_fixes import apply_monkey_patches
        apply_monkey_patches()
        logging.info("[DEBUG] Applied error handling patches")
    except ImportError:
        logging.warning("[DEBUG] Could not import error fixes, continuing without patches")
    
    try:
        from xml_entity_fixes import apply_xml_fixes
        apply_xml_fixes()
        logging.info("[DEBUG] Applied XML entity fixes")
    except ImportError:
        logging.warning("[DEBUG] Could not import XML fixes, continuing without")

from listing_ai_stats import summarize_ai_stats
logging.info("[DEBUG] Imported listing_ai_stats")
import ebay_utils
logging.info("[DEBUG] Imported ebay_utils")
import json
import copy
import argparse
import re
from colorama import init, Fore, Style
logging.info("[DEBUG] All imports complete")

# Helper function to log with colors (still shows in console, also logs to file without colors)
def log_print(message, level=logging.INFO, end='\n'):
    """Print to console and log to file"""
    # Print to console (with colors)
    print(message, end=end)
    # Log to file (strip ANSI color codes for cleaner file output)
    import re
    clean_message = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
    logging.log(level, clean_message)

# Setup argument parser
parser = argparse.ArgumentParser(
    description="Process eBay listings for missing item specifics."
)
parser.add_argument(
    "--min-description-rating",
    type=int,
    default=6,
    help="Minimum acceptable description rating",
)
parser.add_argument(
    "--min-title-rating", type=int, default=6, help="Minimum acceptable title rating"
)

parser.add_argument(
    "--summarize-only", action="store_true", help="Only run AI statistics summary"
)

parser.add_argument(
    "--model-preset",
    choices=['fast', 'balanced', 'quality'],
    default=None,
    help="LLM model preset: 'fast' (~0.3s/call), 'balanced' (~0.7s/call), 'quality' (~60s/call)"
)

parser.add_argument(
    "--show-models",
    action="store_true",
    help="Show available model presets and exit"
)

parser.add_argument(
    "--analyze-only",
    action="store_true",
    help="Analyze listings and estimate processing times for each model preset (doesn't make changes)"
)

parser.add_argument(
    "--sample-size",
    type=int,
    default=10,
    help="Number of listings to sample for analysis (default: 10)"
)

parser.add_argument(
    "--use-ollama",
    action="store_true",
    help="Use Ollama for processing instead of OpenAI (default: use OpenAI)"
)

args = parser.parse_args()
logging.info(f"[DEBUG] Args parsed: {args}")

# Show available models if requested
if args.show_models:
    ebay_utils.print_available_models()
    exit(0)

# Configure provider (OpenAI by default, Ollama if specified)
import os
if args.use_ollama:
    log_print("Using Ollama for processing")
    os.environ['USE_OLLAMA'] = 'true'
    # Set model preset if specified
    if args.model_preset:
        os.environ['OLLAMA_MODEL_PRESET'] = args.model_preset
        log_print(f"Using Ollama model preset: {args.model_preset}")
        # Reload the default model setting
        ebay_utils.DEFAULT_MODEL_PRESET = args.model_preset
        ebay_utils.OLLAMA_DEFAULT_MODEL = ebay_utils.get_ollama_model(args.model_preset)
else:
    log_print("Using OpenAI for processing (default)")
    os.environ['USE_OLLAMA'] = 'false'
    if args.model_preset:
        log_print(f"Warning: --model-preset is only used with --use-ollama flag")

MIN_DESCRIPTION_RATING = args.min_description_rating
MIN_TITLE_RATING = args.min_title_rating


if args.summarize_only:
    log_print("summarize_only called")
    summarize_ai_stats()
    exit(0)

if args.analyze_only:
    log_print("Analysis mode: Estimating processing times for different model presets...")
    
    # Import and run the analysis function
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    
    # Run analysis inline
    from datetime import timedelta
    import time
    from colorama import init, Fore, Style
    
    log_print(f"\n{Fore.CYAN}{'='*80}")
    log_print(f"{Fore.CYAN}eBay Listings Analysis & Time Estimation")
    log_print(f"{Fore.CYAN}{'='*80}\n")
    
    log_print(f"Fetching all active listings...")
    all_listings = ebay_utils.get_all_active_listings()
    if not all_listings:
        log_print(f"{Fore.RED}No active listings found!")
        exit(1)
    
    total_listings = len(all_listings)
    log_print(f"Total active listings: {Fore.GREEN}{total_listings}")
    
    # Sample listings to estimate ratings
    sample_size = min(args.sample_size, total_listings)
    log_print(f"\nSampling {sample_size} listings to estimate rating distribution...")
    log_print(f"(Using current model: {ebay_utils.OLLAMA_DEFAULT_MODEL})\n")
    
    sample_listings = all_listings[:sample_size]
    
    desc_ratings = []
    title_ratings = []
    items_needing_desc_update = 0
    items_needing_title_update = 0
    items_needing_any_update = 0
    
    for i, listing in enumerate(sample_listings, 1):
        item_id = listing.get('ItemID')
        title = listing.get('Title', '')
        
        log_print(f"Sampling {i}/{sample_size}: Item {item_id}", end=' ')
        
        # Get item description and specifics
        description = ebay_utils.get_ebay_description(item_id)
        if not description:
            log_print(f"{Fore.RED}[Failed to get description]")
            continue
            
        specifics = ebay_utils.get_item_specifics(item_id)
        if not specifics:
            specifics = {}
        
        # Rate description and title
        desc_rating = ebay_utils.rate_description_with_llm(description, specifics)
        title_rating = ebay_utils.rate_title_with_llm(title, description)
        
        desc_ratings.append(desc_rating)
        title_ratings.append(title_rating)
        
        needs_desc = desc_rating < args.min_description_rating
        needs_title = title_rating < args.min_title_rating
        
        if needs_desc:
            items_needing_desc_update += 1
        if needs_title:
            items_needing_title_update += 1
        if needs_desc or needs_title:
            items_needing_any_update += 1
        
        log_print(f"Desc: {desc_rating}/10, Title: {title_rating}/10")
    
    # Calculate estimates
    if desc_ratings:
        avg_desc_rating = sum(desc_ratings) / len(desc_ratings)
        avg_title_rating = sum(title_ratings) / len(title_ratings)
        
        sample_ratio = total_listings / len(sample_listings)
        est_items_needing_any = int(items_needing_any_update * sample_ratio)
        
        log_print(f"\n{Fore.YELLOW}Analysis Results:")
        log_print(f"  Average Description Rating: {avg_desc_rating:.1f}/10")
        log_print(f"  Average Title Rating: {avg_title_rating:.1f}/10")
        log_print(f"  Estimated items needing updates: {Fore.RED}{est_items_needing_any}")
        
        log_print(f"\n{Fore.GREEN}Time Estimates by Model Preset:")
        
        # Estimate 2 operations per item that needs updates (rate + generate)
        ops_per_needing_item = 2
        
        for preset, model_info in ebay_utils.OLLAMA_MODELS.items():
            model_time = model_info['avg_time']
            total_time = est_items_needing_any * ops_per_needing_item * model_time
            
            hours = int(total_time // 3600)
            minutes = int((total_time % 3600) // 60)
            
            color = Fore.GREEN if preset == 'fast' else Fore.YELLOW if preset == 'balanced' else Fore.RED
            
            log_print(f"{color}  {preset:10} - {hours:02d}h {minutes:02d}m ({model_info['description']})")
        
        log_print(f"\n{Fore.CYAN}💡 Recommendation:")
        if est_items_needing_any < 100:
            log_print(f"  Use 'quality' preset - only {est_items_needing_any} items need work")
        elif est_items_needing_any < 500:
            log_print(f"  Use 'balanced' preset - good speed/quality for {est_items_needing_any} items")
        else:
            log_print(f"  Use 'fast' preset initially - {est_items_needing_any} items is a lot!")
    
    exit(0)
else:
    log_print("summarize_only is false")

logging.info("\n" + "=" * 30 + " Generating Missing Specifics Report " + "=" * 30)
final_report = ebay_utils.get_missing_item_specifics_report(
    MIN_DESCRIPTION_RATING, MIN_TITLE_RATING
)

if final_report:
    log_print(
        f"\n--- Report generated with {len(final_report)} entries. Now processing for LLM suggestions ---"
    )
    updates_made_count = 0
    llm_suggestions_attempted = 0

    for entry in final_report:
        item_id = entry.get("ItemID")
        current_specifics = entry.get("PresentSpecifics", {})
        missing = list(
            set(entry.get("MissingRequired", []) + entry.get("MissingPreferred", []))
        )
        
        # ALWAYS check for Model and Type - if not present in current_specifics and not in missing list, add them
        if "Model" not in current_specifics and "Model" not in missing:
            log_print(f"Item {item_id}: Adding 'Model' to missing list (required but not present)")
            missing.append("Model")
        
        if "Type" not in current_specifics and "Type" not in missing:
            log_print(f"Item {item_id}: Adding 'Type' to missing list (required but not present)")
            missing.append("Type")
        
        missing = tuple(
            sorted([m for m in missing if "N/A" not in m])
        )  # Use sorted tuple for caching
        description = entry.get("Description", "")

        if not item_id:
            continue  # Skip if somehow ItemID is missing

        if missing and description and "N/A" not in description:
            log_print(
                f"\n--- Item {item_id}: Attempting LLM Suggestions ({len(missing)} missing) ---"
            )
            llm_suggestions_attempted += 1
            try:
                # If Model is in missing list, enhance description with title for better Model detection
                enhanced_description = description
                if "Model" in missing:
                    title = entry.get("Title", "")
                    if title:
                        enhanced_description = f"Title: {title}\n\n{description}"
                        log_print(f"Enhanced description with title for better Model detection")
                
                llm_suggestions = ebay_utils.generate_specifics_with_ollama(
                    item_id=item_id,
                    description=enhanced_description,
                    missing_specifics=missing,
                )

                if llm_suggestions is not None:
                    log_print(f"LLM suggested: {llm_suggestions}")

                    if not llm_suggestions:
                        print("LLM returned no suggestions.")
                        llm_suggestions = {}
                        
                        # If Model was required but not suggested, try to extract from title as fallback
                        if "Model" in missing and "Model" not in current_specifics:
                            title = entry.get("Title", "")
                            if title:
                                # Simple heuristic: use first alphanumeric sequence that looks like a model
                                model_patterns = [
                                    r'\b[A-Z0-9]{3,}[-]?[A-Z0-9]+\b',  # Model numbers like ABC123 or XY-456
                                    r'\b\d{3,}\b',  # Pure numeric models
                                    r'\bModel\s+([A-Z0-9]+)\b',  # Explicit "Model XYZ"
                                ]
                                for pattern in model_patterns:
                                    match = re.search(pattern, title, re.IGNORECASE)
                                    if match:
                                        model_value = match.group(0) if match.lastindex is None else match.group(1)
                                        llm_suggestions["Model"] = model_value[:65]  # Limit to 65 chars
                                        log_print(f"Extracted Model from title as fallback: {model_value}")
                                        break
                                else:
                                    # Ultimate fallback - use generic model based on title
                                    title_words = title.split()[:3]  # First 3 words
                                    if title_words:
                                        model_value = " ".join(title_words)[:65]
                                        llm_suggestions["Model"] = model_value
                                        log_print(f"Using title prefix as Model fallback: {model_value}")
                        
                        # If Type was required but not suggested, try to extract from title/description
                        if "Type" in missing and "Type" not in current_specifics:
                            title = entry.get("Title", "")
                            # For Type, look for common product type keywords
                            type_keywords = {
                                "Antenna": ["antenna", "aerial"],
                                "Cable": ["cable", "cord", "wire"],
                                "Adapter": ["adapter", "adaptor", "converter"],
                                "Charger": ["charger", "charging"],
                                "Battery": ["battery", "batteries"],
                                "Case": ["case", "cover", "shell"],
                                "Screen Protector": ["screen protector", "tempered glass"],
                                "Stand": ["stand", "mount", "holder"],
                                "Speaker": ["speaker", "loudspeaker"],
                                "Headphones": ["headphone", "earphone", "earbuds"],
                                "Keyboard": ["keyboard"],
                                "Mouse": ["mouse"],
                                "Monitor": ["monitor", "display", "screen"],
                                "Router": ["router", "modem"],
                                "Switch": ["switch", "hub"],
                                "Camera": ["camera", "cam", "webcam"],
                                "Microphone": ["microphone", "mic"],
                                "Remote": ["remote", "controller"],
                                "Sensor": ["sensor", "detector"],
                                "Light": ["light", "lamp", "bulb", "LED"],
                                "Fan": ["fan", "cooling"],
                                "Power Bank": ["power bank", "powerbank"],
                                "Memory Card": ["memory card", "SD card", "microSD"],
                                "USB Drive": ["USB drive", "flash drive", "thumb drive"],
                                "Hard Drive": ["hard drive", "HDD", "SSD"],
                            }
                            
                            type_found = None
                            title_lower = title.lower()
                            for type_name, keywords in type_keywords.items():
                                for keyword in keywords:
                                    if keyword.lower() in title_lower:
                                        type_found = type_name
                                        break
                                if type_found:
                                    break
                            
                            if type_found:
                                llm_suggestions["Type"] = type_found[:65]
                                log_print(f"Extracted Type from title as fallback: {type_found}")
                            else:
                                # Generic fallback - use product category from title
                                title_words = title.split()
                                if title_words:
                                    # Try to find a noun that could be a type
                                    for word in title_words:
                                        if len(word) > 3 and word[0].isupper():
                                            llm_suggestions["Type"] = word[:65]
                                            log_print(f"Using '{word}' as Type fallback")
                                            break
                                    else:
                                        llm_suggestions["Type"] = "Accessory"  # Ultimate fallback
                                        log_print(f"Using 'Accessory' as Type fallback")
                        
                        if not llm_suggestions:
                            continue

                    updated_specifics = copy.deepcopy(current_specifics)
                    current_total_count = len(updated_specifics)
                    generated_count = 0
                    max_allowed = ebay_utils.EBAY_MAX_TOTAL_SPECIFICS

                    for name, value in llm_suggestions.items():
                        if current_total_count >= max_allowed:
                            print(
                                f"[WARNING] Reached max specifics ({max_allowed}). Skipping further LLM suggestions for {item_id}."
                            )
                            break
                        if name not in updated_specifics or not updated_specifics.get(
                            name
                        ):
                            updated_specifics[name] = [value]
                            current_total_count += 1
                            generated_count += 1

                    if generated_count > 0:
                        print(
                            f"Merged {generated_count} new/updated specifics. New total: {current_total_count}."
                        )
                        print("[ACTION] Calling update_item_specifics...")
                        success = ebay_utils.update_item_specifics(
                            item_id, updated_specifics, is_fixed_price=True
                        )
                        if success:
                            updates_made_count += 1
                            print(
                                Fore.GREEN
                                + f"[SUCCESS] Update acknowledged for ItemID {item_id}"
                            )
                        else:
                            print(
                                Fore.RED
                                + f"[FAILURE] Update failed or encountered errors for ItemID {item_id}"
                            )
                        import time

                        time.sleep(1)
                    else:
                        print(
                            "No new specifics needed to be added from LLM suggestions."
                        )
                else:
                    log_print("LLM suggestion call failed or returned None.")
            except Exception as llm_err:
                log_print(f"[ERROR] Error during LLM processing for {item_id}: {llm_err}")
        else:
            log_print(
                f"--- Item {item_id}: Skipping LLM (no missing specifics or no description) ---"
            )

    # Generate final statistics report
    log_print(f"\n" + "="*60)
    log_print(f"PROCESSING SUMMARY FOR ACTIVE LISTINGS")
    log_print(f"="*60)
    
    log_print(f"\nTotal active listings processed: {len(final_report)}")
    log_print(f"LLM suggestions attempted: {llm_suggestions_attempted}")
    log_print(f"Updates successfully made: {updates_made_count}")
    
    # Calculate success/failure rate
    if llm_suggestions_attempted > 0:
        success_rate = (updates_made_count / llm_suggestions_attempted) * 100
        failure_count = llm_suggestions_attempted - updates_made_count
        log_print(f"\nUpdate Results:")
        log_print(f"  Successful: {updates_made_count} ({success_rate:.1f}%)")
        log_print(f"  Failed: {failure_count} ({100-success_rate:.1f}%)")
    
    # Show rating statistics if available
    log_print(f"\n" + "-"*40)
    log_print(f"RATING STATISTICS (MIN THRESHOLDS: Title={MIN_TITLE_RATING}, Desc={MIN_DESCRIPTION_RATING})")
    log_print(f"-"*40)
    
    # Count items that met the rating thresholds
    items_below_title_threshold = 0
    items_below_desc_threshold = 0
    
    for entry in final_report:
        if 'TitleRating' in entry and entry['TitleRating'] is not None:
            if entry['TitleRating'] < MIN_TITLE_RATING:
                items_below_title_threshold += 1
        if 'DescriptionRating' in entry and entry['DescriptionRating'] is not None:
            if entry['DescriptionRating'] < MIN_DESCRIPTION_RATING:
                items_below_desc_threshold += 1
    
    log_print(f"Items below Title rating threshold ({MIN_TITLE_RATING}): {items_below_title_threshold}")
    log_print(f"Items below Description rating threshold ({MIN_DESCRIPTION_RATING}): {items_below_desc_threshold}")
    
    log_print(f"\n" + "="*60)
    log_print(f"Processing Complete!")
    log_print(f"="*60)
else:
    log_print("No report generated (likely no active listings or credential issues).")
