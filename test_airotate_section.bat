@echo off
echo Testing airotate bid optimization section...
echo.

REM Step 11.5: Daily bid optimization via Marketing API
echo/
echo [STEP 11.5] Optimizing Top Converters bids via Marketing API...
python daily_bid_optimizer.py
if errorlevel 1 (
    echo [WARNING] API bid updates had issues - check token or eBay status
    echo [FALLBACK] Generating CSV files for manual application...
    python create_ebay_bulk_upload.py 2>nul
    if not errorlevel 1 (
        echo [INFO] Bulk upload CSV files created as backup
    )
) else (
    echo [SUCCESS] Daily bid optimization complete
)
echo "Top Converters bid optimization complete"

echo.
echo Test complete!
pause