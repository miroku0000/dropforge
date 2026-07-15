"""
Utility functions for collecting data for batch processing without making LLM calls
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def collect_listings_for_batch(ebay_utils) -> List[Dict[str, Any]]:
    """
    Collect all active listings and their data WITHOUT making any LLM calls
    
    Returns:
        List of dictionaries containing listing information
    """
    print("\n" + "=" * 30 + " Collecting Listings for Batch " + "=" * 30)
    
    # Get all active listings
    listings = ebay_utils.get_all_active_listings()
    
    if not listings:
        print("[INFO] No active listings found.")
        return []
    
    print(f"[INFO] Found {len(listings)} active listings")
    
    report = []
    total = len(listings)
    
    for idx, listing in enumerate(listings, 1):
        item_id = listing.get("ItemID")
        title = listing.get("Title", "N/A")
        category_id = listing.get("PrimaryCategory")
        
        if idx % 100 == 0:
            print(f"[INFO] Collecting data: {idx}/{total} listings...")
        
        # Initialize entry
        report_entry = {
            "ItemID": item_id,
            "Title": title,
            "CategoryID": category_id,
            "Description": "N/A",
            "MissingRequired": [],
            "MissingPreferred": [],
            "MissingOptional": [],
            "PresentSpecifics": {},
        }
        
        # Get description (from cache if available)
        try:
            description = ebay_utils.get_ebay_description(item_id)
            if description:
                # Clean it but don't rate it
                description = ebay_utils._strip_openai_tag(description)
                description = ebay_utils.remove_undesired_characters(description)
                description = ebay_utils.clean_llm_description_output(description)
                report_entry["Description"] = description
        except Exception as e:
            logger.error(f"Error fetching description for {item_id}: {e}")
            report_entry["Description"] = ""
        
        # Get current item specifics
        try:
            current_specifics = ebay_utils.get_item_specifics(item_id)
            if current_specifics:
                report_entry["PresentSpecifics"] = current_specifics
        except Exception as e:
            logger.error(f"Error fetching specifics for {item_id}: {e}")
        
        # Get category-specific requirements
        if category_id:
            try:
                category_specifics = ebay_utils.get_category_specifics(category_id)
                if category_specifics:
                    # Determine what's missing
                    for spec in category_specifics:
                        spec_name = spec.get("Name", "")
                        if not spec_name:
                            continue
                            
                        # Check if we have this specific
                        if spec_name not in current_specifics:
                            # Categorize by requirement level
                            if spec.get("MinValues", 0) > 0:
                                report_entry["MissingRequired"].append(spec_name)
                            elif spec.get("SelectionMode") == "SelectionOnly":
                                report_entry["MissingPreferred"].append(spec_name)
                            else:
                                report_entry["MissingOptional"].append(spec_name)
            except Exception as e:
                logger.error(f"Error fetching category specifics for {category_id}: {e}")
        
        report.append(report_entry)
    
    print(f"[INFO] Collected data for {len(report)} listings")
    return report

def get_listings_data_only(ebay_utils) -> List[Dict[str, Any]]:
    """
    Get listing data without any processing or LLM calls
    This is a lightweight version that just collects the raw data
    """
    return collect_listings_for_batch(ebay_utils)