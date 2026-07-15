#!/usr/bin/env python3
"""
AI-Enhanced Listing Removal System using existing ebay_utils AI functions
"""

import pandas as pd
from datetime import datetime
from listing_removal_system import RemovalConfig
import ebay_utils

def ai_enhanced_removal_demo():
    """Run removal analysis with AI-powered title and description quality scoring"""
    print("=== AI-Enhanced Removal System ===")
    print("Using your existing AI functions for quality analysis...")
    
    # Create config with higher weight for quality factors
    config = RemovalConfig(
        weight_age=0.20,                # Reduced age weight
        weight_views=0.25,              # Keep views weight high
        weight_sales=0.20,              # Keep sales weight high
        weight_watchers=0.15,           # Keep watchers weight
        weight_photos=0.05,             # Reduced photo weight
        weight_title_quality=0.075,     # Increased title quality weight
        weight_desc_quality=0.075       # Increased description quality weight
    )
    
    print("Getting basic listing data...")
    
    # Get basic listing data
    listings = ebay_utils.get_all_active_listings()
    print(f"Processing {len(listings)} listings with AI quality analysis...")
    
    # Process a manageable subset to avoid timeouts (for demo)
    # For production, you might process in batches or overnight
    sample_size = min(100, len(listings))  # Adjust this number as needed
    sample_listings = listings[:sample_size]
    
    print(f"Analyzing quality for {sample_size} listings (sample for demo)...")
    
    scored_listings = []
    
    for idx, listing in enumerate(sample_listings, 1):
        if idx % 10 == 0:
            print(f"  Processing {idx}/{sample_size}...")
            
        # Basic data
        item_id = listing.get("ItemID")
        days_active = listing.get("DaysActive", 0) or 0
        views = listing.get("Views", 0) or 0
        sales = listing.get("QuantitySold", 0) or 0
        watchers = listing.get("Watchers", 0) or 0
        title = listing.get("Title", "")
        
        # Skip very new listings or high-watcher items
        if days_active < 14 or watchers >= 10:
            continue
        
        # Calculate basic performance scores
        age_score = min(days_active / 365, 1.0)
        view_score = max(1.0 - (views / 50), 0.0)
        
        if sales == 0:
            sales_score = 1.0
        elif sales <= 2:
            sales_score = 0.5
        else:
            sales_score = 0.0
            
        if watchers == 0:
            watchers_score = 1.0
        elif watchers <= 2:
            watchers_score = 0.6
        else:
            watchers_score = 0.3
            
        # Photo score (get actual photo count)
        try:
            photo_count = ebay_utils.get_image_count_for_item(item_id) or 0
            photo_score = max(1.0 - (photo_count / 8), 0.0)  # 8 photos = good
        except Exception as e:
            print(f"    Warning: Could not get photo count for {item_id}: {e}")
            photo_score = 0.5  # Neutral if can't determine
        
        # AI-POWERED TITLE QUALITY ANALYSIS
        try:
            print(f"    Analyzing title quality for {item_id}...")
            
            # Get description for title context
            description = ebay_utils.get_ebay_description(item_id) or ""
            
            # Use your existing AI title rating function
            title_rating = ebay_utils.rate_title_with_llm(title, description)
            
            # Convert 1-10 rating to 0-1 removal score (lower rating = higher removal score)
            title_score = max(0, (7 - title_rating) / 7)  # 7+ rating = good title
            
            print(f"      Title rating: {title_rating}/10 (removal score: {title_score:.3f})")
            
        except Exception as e:
            print(f"    Warning: AI title analysis failed for {item_id}: {e}")
            # Fallback to basic title scoring
            if len(title) < 30:
                title_score = 1.0
            elif len(title) < 50:
                title_score = 0.5
            else:
                title_score = 0.0
        
        # AI-POWERED DESCRIPTION QUALITY ANALYSIS
        try:
            print(f"    Analyzing description quality for {item_id}...")
            
            # Get item specifics for description context
            specifics = ebay_utils.get_item_specifics(item_id) or {}
            
            # Use your existing AI description rating function
            desc_rating = ebay_utils.rate_description_with_llm(description, specifics)
            
            # Convert 1-10 rating to 0-1 removal score
            desc_score = max(0, (7 - desc_rating) / 7)  # 7+ rating = good description
            
            print(f"      Description rating: {desc_rating}/10 (removal score: {desc_score:.3f})")
            
        except Exception as e:
            print(f"    Warning: AI description analysis failed for {item_id}: {e}")
            # Fallback to basic description scoring
            if description and len(description) > 300:
                desc_score = 0.0  # Good length
            elif description and len(description) > 100:
                desc_score = 0.5  # Medium length
            else:
                desc_score = 1.0  # Poor/no description
        
        # Calculate total weighted score
        total_score = (
            age_score * config.weight_age +
            view_score * config.weight_views +
            sales_score * config.weight_sales +
            watchers_score * config.weight_watchers +
            photo_score * config.weight_photos +
            title_score * config.weight_title_quality +
            desc_score * config.weight_desc_quality
        )
        
        listing_with_score = {
            **listing,
            "removal_score": total_score,
            "age_score": age_score,
            "view_score": view_score,
            "sales_score": sales_score,
            "watchers_score": watchers_score,
            "photo_score": photo_score,
            "ai_title_score": title_score,
            "ai_desc_score": desc_score,
            "ai_title_rating": title_rating if 'title_rating' in locals() else 0,
            "ai_desc_rating": desc_rating if 'desc_rating' in locals() else 0,
            "photo_count": photo_count if 'photo_count' in locals() else 0
        }
        
        scored_listings.append(listing_with_score)
        
        # Reset variables for next iteration
        title_rating = 0
        desc_rating = 0
        photo_count = 0
    
    print(f"\nCompleted AI analysis for {len(scored_listings)} listings")
    
    # Sort by removal score
    sorted_listings = sorted(scored_listings, key=lambda x: x["removal_score"], reverse=True)
    
    # Take top candidates
    recommendations = sorted_listings[:50]
    
    print(f"Generated {len(recommendations)} AI-enhanced removal recommendations")
    
    # Create enhanced report
    report_data = []
    for listing in recommendations:
        views_per_day = (listing.get("Views", 0) or 0) / max(listing.get("DaysActive", 1), 1)
        
        report_data.append({
            "ItemID": listing.get("ItemID"),
            "Title": listing.get("Title", "")[:60] + "...",
            "DaysActive": listing.get("DaysActive", 0),
            "Views": listing.get("Views", 0),
            "ViewsPerDay": round(views_per_day, 2),
            "Sales": listing.get("QuantitySold", 0),
            "Watchers": listing.get("Watchers", 0),
            "Photos": listing.get("photo_count", 0),
            "Category": listing.get("PrimaryCategory", ""),
            "RemovalScore": round(listing.get("removal_score", 0), 4),
            "AgeScore": round(listing.get("age_score", 0), 3),
            "ViewsScore": round(listing.get("view_score", 0), 3),
            "SalesScore": round(listing.get("sales_score", 0), 3),
            "WatchersScore": round(listing.get("watchers_score", 0), 3),
            "PhotosScore": round(listing.get("photo_score", 0), 3),
            "AI_TitleRating": listing.get("ai_title_rating", 0),
            "AI_TitleScore": round(listing.get("ai_title_score", 0), 3),
            "AI_DescRating": listing.get("ai_desc_rating", 0),
            "AI_DescScore": round(listing.get("ai_desc_score", 0), 3),
            "QualityFlag": "POOR" if (listing.get("ai_title_rating", 7) < 5 or listing.get("ai_desc_rating", 7) < 5) else "OK"
        })
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_enhanced_removal_report_{timestamp}.csv"
    
    df = pd.DataFrame(report_data)
    df.to_csv(filename, index=False)
    
    # Show enhanced summary
    if len(recommendations) > 0:
        avg_score = df["RemovalScore"].mean()
        avg_age = df["DaysActive"].mean()
        avg_title_rating = df["AI_TitleRating"].mean()
        avg_desc_rating = df["AI_DescRating"].mean()
        poor_quality_count = len(df[df["QualityFlag"] == "POOR"])
        
        print(f"\n=== AI-ENHANCED REMOVAL ANALYSIS ===")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total recommendations: {len(recommendations):,}")
        print(f"Average removal score: {avg_score:.4f}")
        print(f"Average listing age: {avg_age:.0f} days")
        print(f"Average AI title rating: {avg_title_rating:.1f}/10")
        print(f"Average AI description rating: {avg_desc_rating:.1f}/10")
        print(f"Poor quality listings: {poor_quality_count} ({poor_quality_count/len(recommendations)*100:.1f}%)")
        
        print(f"\nTOP 10 REMOVAL CANDIDATES (with AI quality analysis):")
        for i, listing in enumerate(recommendations[:10], 1):
            title = listing.get("Title", "")[:45]
            score = listing.get("removal_score", 0)
            age = listing.get("DaysActive", 0)
            views = listing.get("Views", 0)
            title_rating = listing.get("ai_title_rating", 0)
            desc_rating = listing.get("ai_desc_rating", 0)
            quality_flag = report_data[i-1]["QualityFlag"]
            
            print(f"{i:2d}. [{quality_flag:4}] Score: {score:.3f} | Age: {age:3d}d | Views: {views:3d}")
            print(f"    Title: {title_rating}/10 | Desc: {desc_rating}/10 | {title}...")
        
        print(f"\nDetailed AI-enhanced report saved to: {filename}")
        print(f"\nKey insights:")
        print(f"- Items with 'POOR' quality flag have AI ratings <5/10")
        print(f"- Quality scores now factor into removal decisions")
        print(f"- Poor quality + poor performance = highest removal priority")
        
        return filename
    
    return None

if __name__ == "__main__":
    ai_enhanced_removal_demo()