# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an eBay automation and product listing management system that integrates with eBay's API, Amazon product data, and various e-commerce platforms. The codebase includes tools for:
- Managing eBay listings (creating, updating, ending)
- Processing item specifics and categories
- AI-powered description and title generation using OpenAI
- Web scraping for product data from Amazon and other sources
- Automated listing optimization and performance monitoring
- Bulk operations for CSV imports/exports

## Common Development Commands

### Running Tests
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest test_ebay_utils.py

# Run with verbose output
python -m pytest -v
```

### Running Main Scripts
```bash
# Process eBay listings with AI
python aiprocessebay.py [--force] [--refresh ITEM_ID] [--model_name MODEL]

# Download and process listings
python ai_download_all_listings.py
python ai_process_all_listings.py

# eBay utilities test
python test_ebay_utils.py [--min-description-rating N] [--min-title-rating N]
```

### Dependencies
```bash
# Install requirements
pip install -r requirements.txt
```

### Monitoring Commands
```bash
# Check Python processes (auto-approved)
tasklist | findstr python

# Check Python memory usage (auto-approved) 
wmic process where "name='python.exe'" get processid,workingsetsize
```

## Architecture & Key Components

### Core Modules
- **ebay_utils.py**: Central utility module containing eBay API integration, OpenAI integration for title/description generation, caching mechanisms, and helper functions for processing listings
- **aiprocessebay.py**: Main script for AI-powered eBay listing processing with multi-threading support
- **listing_ai_stats.py**: Tracks and logs AI processing statistics

### Caching System
The project uses extensive caching to minimize API calls:
- `.cache_item_details/`: eBay item details cache
- `.cache_llm_data_desc/`: LLM-generated descriptions cache
- `.cache_category_names/`: Category name mappings
- `.cache_category_specifics/`: Category-specific attributes
- `.ebay_api_cache/`: General eBay API response cache

### API Integration
- **eBay API**: Uses credentials from `credentials.txt` with appid, devid, certid, and token
- **OpenAI API**: Requires `OPENAI_API_KEY` environment variable, uses GPT-4o model by default
- **Crawlbase**: Web scraping API credentials in `crawlbase_creds.txt`

### Data Processing Flow
1. Scripts typically read Excel files from download directories
2. Process listings through AI models for enhancement
3. Cache results to avoid redundant API calls
4. Generate updated CSV/Excel files for bulk upload
5. Log all operations to various log files

## Auto-approved Commands

These commands can be run without explicit permission for monitoring and debugging:

```bash
# Check if Python processes are running
tasklist | findstr python

# Check Python memory usage
wmic process where "name='python.exe'" get processid,workingsetsize

# Kill Python processes if needed
wmic process where "name='python.exe'" delete
```

## Named Dispatch Tasks

These are named automation tasks that can be run by simply asking Claude to execute them by name. They use Playwright with a persistent browser profile (`.playwright_profile/`). First run requires manual eBay login; after that the session is remembered.

### ebay_ads_report
Generate eBay promoted listings campaign report for the past 14 days.
- Opens Chrome with existing profile (no login needed)
- Navigates to: https://www.ebay.com/sh/ads/dashboard/campaign/12402748019?tab=listings
- Clicks "Generate Report", selects "Past 14 Days", clicks "Generate"
- Downloads the CSV report to `~/Downloads/`
```bash
python ai_ebay_download_automagical.py ebay_ads_report
```

### ebay_ads_report_7days / ebay_ads_report_30days
Same as above but for 7-day or 30-day ranges.
```bash
python ai_ebay_download_automagical.py ebay_ads_report_7days
python ai_ebay_download_automagical.py ebay_ads_report_30days
```

### top_converters_keyword_report
Download Top Converters campaign keyword report.
- Navigates to: https://www.ebay.com/sh/ads/dashboard/campaign/158950352019
- Clicks "Generate Report", checks "Keyword report", clicks "Generate"
- Downloads as `Top Converters Test_Keyword_YYYYMMDD.csv` to `~/Downloads/`
```bash
python ai_ebay_download_top_converters_keyword_report.py
```

### promoted_offsite_report
Download Promoted Offsite campaign listing report.
- Navigates to: https://www.ebay.com/sh/ads/dashboard/campaign/159005538019?tab=listings
- Clicks "Generate Report", clicks "Generate"
- Downloads as `Promoted offsite - MM_DD_YYYY, HH_MM_Listing_YYYYMMDD.csv` to `~/Downloads/`
```bash
python ai_ebay_download_promoted_offsite_report.py
```

### listings_traffic_report
Download active listings traffic report from Seller Hub.
- Navigates to: https://www.ebay.com/sh/performance/traffic
- Clicks the download button (aria-label="Download active listings traffic report")
- Downloads as `eBay-ListingsTrafficReport-*.csv` to `~/Downloads/`
```bash
python ai_ebay_downlaod_listings_traffic_report.py
```

### update_keyword_bids
Update Top Converters campaign keyword bids based on recommendations.
- Reads latest `bid_changes_detailed_*.csv` from `generate_bid_changes_csv.py`
- Opens campaign keywords tab, searches for each keyword, updates bid
- Supports `--dry-run` flag
```bash
python generate_bid_changes_csv.py        # Generate recommendations first
python ai_ebay_update_keyword_bids.py     # Apply the changes
python ai_ebay_update_keyword_bids.py --dry-run  # Preview only
```

### send_offers
Send offers to all eligible buyers at a percentage discount.
- Opens SIO-eligible listings: https://www.ebay.com/sh/lst/active?pill_status=sioEligible
- Selects all, clicks "Send offer", enters discount, clicks "Send offers"
```bash
python ai_ebay_send_offers.py       # 5% off (default)
python ai_ebay_send_offers.py 10    # 10% off
```

### refresh_oauth_token
Refresh eBay OAuth token using the refresh token (no browser needed).
```bash
python ai_ebay_refresh_oauth_token.py
```

### get_oauth_token
Get a new OAuth token via the eBay Developer Portal (browser required, for when refresh token expires).
```bash
python ai_ebay_get_oauth_token.py
```

### Remote Control Web Panel
Start the web server for phone-based control:
```bash
python remote_control_server.py
# or
start_remote_control.bat
```
Access from phone at `http://<PC-IP>:5000`. All named tasks above are also available as buttons.

## Important Considerations

- Always check for existing cache before making API calls
- The codebase uses Windows paths (D:\) and batch files (.bat)
- Python version: 3.10.9
- HTTP/HTTPS proxy settings are configured in batch files for some operations
- Maximum eBay item specifics: 45 per listing, 65 characters per value
- Test files follow the pattern `test_*.py` but don't use a formal test framework structure