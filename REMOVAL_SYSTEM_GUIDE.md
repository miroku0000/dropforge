# eBay Listing Removal System Guide

## Overview

This system helps you identify which eBay listings to remove daily to make room for your 25,000 monthly new product insertions. It analyzes multiple factors to prioritize removal candidates intelligently.

## Daily Usage (Recommended)

### Quick Start
```bash
python advanced_removal_system.py
```

This will:
1. Analyze all your active listings
2. Generate removal recommendations based on the "balanced" profile
3. Create a CSV report with detailed analysis
4. Show you the top removal candidates

### Configuration Profiles

**Conservative** (removes only clearly poor performers):
- Emphasizes view performance and sales data
- Higher thresholds for removal
- Good for maintaining inventory size

**Balanced** (recommended for daily use):
- Well-rounded scoring algorithm
- Targets ~833 daily removals (25,000/30 days)
- Balances age, performance, and quality factors

**Aggressive** (prioritizes making room for new items):
- Emphasizes listing age more heavily
- Lower thresholds for removal
- Good when you need to clear inventory quickly

## Key Features

### Scoring Algorithm
Each listing gets a removal score (0-1) based on:

- **Age (25% weight)**: Older listings score higher for removal
- **Views (25% weight)**: Lower views = higher removal score
- **Sales (20% weight)**: No sales = higher removal score
- **Watchers (15% weight)**: Fewer watchers = higher removal score
- **Photo Quality (10% weight)**: Fewer photos = higher removal score
- **Title Quality (2.5% weight)**: Based on title length and completeness
- **Description Quality (2.5% weight)**: Based on description length and quality

### Safety Features

- **Never removes listings with 10+ watchers** (configurable)
- **Never removes listings newer than 14 days** (configurable)
- **Protected categories** can be excluded
- **Seasonal adjustments** for holiday/seasonal items

### AI Enhancement (Optional)

Enable advanced title and description rating:
```python
# In removal_config.json
"use_ai_title_rating": true,
"use_ai_description_rating": true
```

This uses your existing LLM functions to rate title and description quality more accurately.

## Files Included

### Core System
- `listing_removal_system.py` - Basic removal system
- `advanced_removal_system.py` - Enhanced system with AI and configuration profiles
- `removal_config.json` - Configuration profiles and settings

### Testing & Demo
- `quick_removal_demo.py` - Quick demo with sample data
- `test_removal_system.py` - Full system tests

### Documentation
- `REMOVAL_SYSTEM_GUIDE.md` - This guide

## Daily Workflow

### Step 1: Generate Recommendations
```bash
python advanced_removal_system.py
```

### Step 2: Review the Report
The system generates a CSV file with:
- ItemID and title
- Performance metrics (views, sales, age, etc.)
- Removal score breakdown
- Recommendation (REMOVE/KEEP)

### Step 3: Manual Review (Recommended)
Review the top candidates to ensure:
- No seasonal items during their peak season
- No items with recent interest (recent watchers/questions)
- No high-value items you want to keep

### Step 4: Bulk Removal (Optional)
**USE WITH EXTREME CAUTION!**

```python
# Uncomment the removal code in advanced_removal_system.py
item_ids = [r["ItemID"] for r in recommendations[:833]]
results = system.bulk_remove_listings(item_ids, "Daily inventory management")
```

## Configuration Options

### Removal Targets
```json
"removal_targets": {
    "daily_target": 833,     // 25,000 ÷ 30 days
    "weekly_target": 5833,   // For weekly batches
    "monthly_target": 25000  // Your monthly limit
}
```

### Advanced Options
```json
"advanced_options": {
    "use_ai_title_rating": false,          // Enable AI title scoring
    "use_ai_description_rating": false,    // Enable AI description scoring
    "consider_seasonal_factors": true,      // Seasonal adjustments
    "minimum_listing_age_days": 14,        // Never remove items newer than this
    "never_remove_with_watchers": 10       // Never remove items with this many watchers
}
```

### Category Protection
```json
"category_settings": {
    "protected_categories": ["12345", "67890"],  // Category IDs to never remove
    "high_turnover_categories": ["11111"]        // Categories that turn over frequently
}
```

## Performance Monitoring

The system tracks:
- Views per day trends
- Category-wise removal patterns
- Success rates of past removals
- Seasonal performance patterns

## Best Practices

### Daily Routine
1. **Morning**: Run the system to generate recommendations
2. **Review**: Manually check top 50-100 candidates
3. **Execute**: Remove listings in batches throughout the day
4. **Monitor**: Track which removed listings had recent activity

### Weekly Review
- Analyze removal patterns by category
- Adjust profile weights based on results
- Review seasonal category performance
- Update protected categories list

### Monthly Analysis
- Compare removal success with new listing performance
- Optimize configuration based on sales data
- Update seasonal factors for next month

## Troubleshooting

### Common Issues

**"OAuth Error" or "401 Unauthorized"**
- Analytics API requires special permissions
- System falls back to basic view counts
- Contact eBay to enable analytics scope if needed

**"No recommendations generated"**
- Check if minimum age filter is too restrictive
- Verify listing data is being fetched correctly
- Try a more aggressive profile

**Removal operation fails**
- Check eBay API credentials
- Verify items are still active
- Some items may have pending transactions

### Performance Tips

- Run during off-peak hours to avoid API limits
- Process in smaller batches if you have many listings
- Enable caching to speed up repeated analyses
- Use conservative profile initially to test results

## Support

This system integrates with your existing `ebay_utils.py` functions and uses the same credentials and caching mechanisms. All removal operations use standard eBay API calls and are fully reversible by relisting items if needed.

For questions about specific scoring logic or configuration, refer to the detailed comments in the Python files.