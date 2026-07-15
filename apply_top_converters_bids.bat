@echo off
echo ============================================================
echo TOP CONVERTERS BID AUTOMATION
echo ============================================================

REM Try API method first
echo [1] Attempting API-based bid changes...
python apply_bid_changes.py
if %errorlevel% EQU 0 (
    echo [SUCCESS] Bids updated via API
    goto :end
)

:manual_fallback
echo [INFO] eBay's keyword bid API is currently invite-only
echo ============================================================
echo GENERATING CSV FILES FOR MANUAL UPLOAD
echo ============================================================

REM Generate CSV for manual upload
echo [2] Generating CSV files for manual upload...
echo | python generate_bid_changes_csv.py
if errorlevel 1 (
    echo [ERROR] Could not generate CSV files
    goto :end
)
echo ============================================================
echo NEXT STEPS:
echo ============================================================
echo 1. CSV files have been created with bid recommendations
echo 2. Go to: https://www.ebay.com/sh/mkt/advertising-dashboard
echo 3. Click 'Top Converters Test' campaign
echo 4. Apply the bid changes using one of these methods:
echo    - Manual: Update each keyword individually
echo    - Bulk: Use eBay's bulk upload feature
echo To get API access for automation:
echo Run: python generate_marketing_token.py

:end