#!/usr/bin/env python3
"""
eBay Listing Removal Recommendation System

This system identifies which listings should be removed to make room for new products.
It uses a scoring algorithm that considers multiple factors to prioritize removal candidates.
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import ebay_utils

@dataclass
class RemovalConfig:
    """Configuration for the removal recommendation system"""
    
    # Scoring weights (must sum to 1.0)
    weight_age: float = 0.25           # Age penalty
    weight_views: float = 0.25         # View performance
    weight_sales: float = 0.20         # Sales performance
    weight_watchers: float = 0.10      # Watcher engagement
    weight_photos: float = 0.10        # Photo quality
    weight_title_quality: float = 0.05 # Title rating
    weight_desc_quality: float = 0.05  # Description rating
    
    # Thresholds for scoring
    max_age_days: int = 365            # Age at which listings get max age penalty
    min_views_30d: int = 50            # Minimum expected views in 30 days
    min_photos: int = 8                # Minimum expected photos
    min_title_rating: int = 7          # Minimum expected title rating
    min_desc_rating: int = 7           # Minimum expected description rating
    
    # Performance categories
    high_performer_threshold: float = 0.7   # Keep high performers
    low_performer_threshold: float = 0.3    # Remove low performers first
    
    def validate(self) -> bool:
        """Validate configuration weights sum to 1.0"""
        total_weight = (
            self.weight_age + self.weight_views + self.weight_sales + 
            self.weight_watchers + self.weight_photos + 
            self.weight_title_quality + self.weight_desc_quality
        )
        return abs(total_weight - 1.0) < 0.01

class ListingRemovalSystem:
    """Main class for identifying listings to remove"""
    
    def __init__(self, config: RemovalConfig = None):
        self.config = config or RemovalConfig()
        if not self.config.validate():
            raise ValueError("Configuration weights must sum to 1.0")
    
    def get_all_listing_data(self) -> List[Dict]:
        """Fetch all active listings with comprehensive data"""
        print("Fetching all active listings...")
        listings = ebay_utils.get_all_active_listings()
        
        # Get analytics data for more accurate view counts
        print("Fetching analytics data...")
        analytics_views = ebay_utils.get_all_hitcounts_analytics()
        
        enhanced_listings = []
        total = len(listings)
        
        for idx, listing in enumerate(listings, 1):
            item_id = listing.get("ItemID")
            print(f"Processing {idx}/{total}: {item_id}")
            
            # Get additional data
            try:
                photo_count = ebay_utils.get_image_count_for_item(item_id)
                description = ebay_utils.get_ebay_description(item_id)
                specifics = ebay_utils.get_item_specifics(item_id)
                
                # Use analytics views if available, fallback to regular views
                views_30d = analytics_views.get(item_id, listing.get("Views", 0))
                
                enhanced_listing = {
                    **listing,
                    "PhotoCount": photo_count or 0,
                    "Description": description or "",
                    "AnalyticsViews": views_30d,
                    "Specifics": specifics or {}
                }
                enhanced_listings.append(enhanced_listing)
                
            except Exception as e:
                print(f"Warning: Error processing {item_id}: {e}")
                # Add listing with basic data only
                enhanced_listings.append({
                    **listing,
                    "PhotoCount": 0,
                    "Description": "",
                    "AnalyticsViews": listing.get("Views", 0),
                    "Specifics": {}
                })
        
        return enhanced_listings
    
    def calculate_removal_score(self, listing: Dict) -> Tuple[float, Dict[str, float]]:
        """
        Calculate removal score for a listing (0-1, higher = more likely to remove)
        Also returns breakdown of score components for analysis
        """
        scores = {}
        
        # Age score (older = higher removal score)
        days_active = listing.get("DaysActive", 0) or 0
        age_score = min(days_active / self.config.max_age_days, 1.0)
        scores["age"] = age_score
        
        # Views score (fewer views = higher removal score)
        views = listing.get("AnalyticsViews", 0) or listing.get("Views", 0) or 0
        view_score = max(1.0 - (views / self.config.min_views_30d), 0.0)
        scores["views"] = view_score
        
        # Sales score (no sales = higher removal score)
        sales = listing.get("QuantitySold", 0) or 0
        if sales == 0:
            sales_score = 1.0  # Never sold anything
        elif sales <= 2:
            sales_score = 0.5  # Minimal sales
        else:
            sales_score = 0.0  # Good sales performance
        scores["sales"] = sales_score
        
        # Watchers score (fewer watchers = higher removal score)
        watchers = listing.get("Watchers", 0) or 0
        if watchers == 0:
            watchers_score = 1.0
        elif watchers <= 2:
            watchers_score = 0.6
        elif watchers <= 5:
            watchers_score = 0.3
        else:
            watchers_score = 0.0
        scores["watchers"] = watchers_score
        
        # Photos score (fewer photos = higher removal score)
        photo_count = listing.get("PhotoCount", 0) or 0
        photo_score = max(1.0 - (photo_count / self.config.min_photos), 0.0)
        scores["photos"] = photo_score
        
        # Title quality score (would need to rate titles - placeholder for now)
        title = listing.get("Title", "")
        if len(title) < 30:
            title_score = 1.0  # Very short title
        elif len(title) < 50:
            title_score = 0.5  # Short title
        else:
            title_score = 0.0  # Reasonable length
        scores["title_quality"] = title_score
        
        # Description quality score (basic heuristics for now)
        description = listing.get("Description", "")
        if len(description) < 100:
            desc_score = 1.0  # Very short description
        elif len(description) < 300:
            desc_score = 0.5  # Short description
        else:
            desc_score = 0.0  # Reasonable description
        scores["desc_quality"] = desc_score
        
        # Calculate weighted total
        total_score = (
            scores["age"] * self.config.weight_age +
            scores["views"] * self.config.weight_views +
            scores["sales"] * self.config.weight_sales +
            scores["watchers"] * self.config.weight_watchers +
            scores["photos"] * self.config.weight_photos +
            scores["title_quality"] * self.config.weight_title_quality +
            scores["desc_quality"] * self.config.weight_desc_quality
        )
        
        return total_score, scores
    
    def categorize_listings(self, listings: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize listings by performance level"""
        categorized = {
            "high_performers": [],
            "medium_performers": [],
            "low_performers": [],
            "removal_candidates": []
        }
        
        for listing in listings:
            score, breakdown = self.calculate_removal_score(listing)
            listing["removal_score"] = score
            listing["score_breakdown"] = breakdown
            
            if score <= (1.0 - self.config.high_performer_threshold):
                categorized["high_performers"].append(listing)
            elif score >= self.config.low_performer_threshold:
                categorized["removal_candidates"].append(listing)
            else:
                categorized["medium_performers"].append(listing)
        
        return categorized
    
    def recommend_removals(self, target_count: int, exclude_categories: List[str] = None) -> List[Dict]:
        """
        Recommend specific listings for removal
        
        Args:
            target_count: Number of listings to recommend for removal
            exclude_categories: List of category IDs to exclude from removal
        
        Returns:
            List of listings recommended for removal, sorted by removal score
        """
        print(f"Analyzing listings to recommend {target_count} for removal...")
        
        # Get all listing data
        listings = self.get_all_listing_data()
        
        # Filter out excluded categories
        if exclude_categories:
            exclude_set = set(str(cat) for cat in exclude_categories)
            listings = [
                listing for listing in listings 
                if str(listing.get("PrimaryCategory", "")) not in exclude_set
            ]
        
        # Calculate scores and categorize
        categorized = self.categorize_listings(listings)
        
        # Start with removal candidates, then medium performers if needed
        candidates = categorized["removal_candidates"].copy()
        
        if len(candidates) < target_count:
            # Add medium performers sorted by removal score
            medium_sorted = sorted(
                categorized["medium_performers"], 
                key=lambda x: x["removal_score"], 
                reverse=True
            )
            candidates.extend(medium_sorted)
        
        # Sort by removal score (highest first = most likely to remove)
        candidates_sorted = sorted(candidates, key=lambda x: x["removal_score"], reverse=True)
        
        return candidates_sorted[:target_count]
    
    def generate_removal_report(self, recommendations: List[Dict], filename: str = None) -> str:
        """Generate a detailed report of removal recommendations"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"removal_recommendations_{timestamp}.csv"
        
        # Prepare data for CSV
        report_data = []
        for listing in recommendations:
            breakdown = listing.get("score_breakdown", {})
            
            report_data.append({
                "ItemID": listing.get("ItemID"),
                "Title": listing.get("Title", "")[:60] + ("..." if len(listing.get("Title", "")) > 60 else ""),
                "DaysActive": listing.get("DaysActive", 0),
                "Views30d": listing.get("AnalyticsViews", 0),
                "RegularViews": listing.get("Views", 0),
                "Sales": listing.get("QuantitySold", 0),
                "Watchers": listing.get("Watchers", 0),
                "Photos": listing.get("PhotoCount", 0),
                "Category": listing.get("PrimaryCategory", ""),
                "RemovalScore": round(listing.get("removal_score", 0), 3),
                "AgeScore": round(breakdown.get("age", 0), 3),
                "ViewsScore": round(breakdown.get("views", 0), 3),
                "SalesScore": round(breakdown.get("sales", 0), 3),
                "WatchersScore": round(breakdown.get("watchers", 0), 3),
                "PhotosScore": round(breakdown.get("photos", 0), 3),
                "TitleScore": round(breakdown.get("title_quality", 0), 3),
                "DescScore": round(breakdown.get("desc_quality", 0), 3),
            })
        
        # Save to CSV
        df = pd.DataFrame(report_data)
        df.to_csv(filename, index=False)
        
        # Generate summary statistics
        total_listings = len(recommendations)
        avg_score = df["RemovalScore"].mean() if total_listings > 0 else 0
        avg_age = df["DaysActive"].mean() if total_listings > 0 else 0
        total_views = df["Views30d"].sum()
        
        summary = f"""
=== LISTING REMOVAL RECOMMENDATIONS REPORT ===
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

SUMMARY:
- Total recommendations: {total_listings:,}
- Average removal score: {avg_score:.3f}
- Average listing age: {avg_age:.0f} days
- Total views (30d): {total_views:,}

TOP 10 REMOVAL CANDIDATES:
"""
        
        for i, listing in enumerate(recommendations[:10], 1):
            summary += f"""
{i:2d}. ItemID: {listing.get("ItemID")} (Score: {listing.get("removal_score", 0):.3f})
    Title: {listing.get("Title", "")[:80]}
    Age: {listing.get("DaysActive", 0)} days | Views: {listing.get("AnalyticsViews", 0)} | Sales: {listing.get("QuantitySold", 0)}
"""
        
        summary += f"\nDetailed report saved to: {filename}\n"
        
        print(summary)
        return filename

def main():
    """Example usage of the listing removal system"""
    print("=== eBay Listing Removal System ===")
    
    # Create system with default configuration
    config = RemovalConfig(
        weight_age=0.30,        # Emphasize old listings
        weight_views=0.25,      # Emphasize low views
        weight_sales=0.20,      # Emphasize no sales
        weight_watchers=0.15,   # Moderate weight on watchers
        weight_photos=0.10      # Less weight on photos
    )
    
    removal_system = ListingRemovalSystem(config)
    
    # Calculate daily removal target (25,000 / 30 = ~833)
    daily_target = 833
    print(f"Daily removal target: {daily_target}")
    
    # Get removal recommendations
    recommendations = removal_system.recommend_removals(
        target_count=daily_target,
        exclude_categories=[]  # Add category IDs to exclude if needed
    )
    
    # Generate report
    report_file = removal_system.generate_removal_report(recommendations)
    print(f"Report saved to: {report_file}")
    
    return recommendations

if __name__ == "__main__":
    main()