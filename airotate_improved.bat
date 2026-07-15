@echo off
echo ============================================================
echo IMPROVED AIROTATE WITH ERROR HANDLING
echo ============================================================
echo Started at: %date% %time%
echo.

REM Step 1: Analyze ROI and generate searches
echo [STEP 1] Analyzing ROI and generating Amazon searches...
python analyze_roi_and_generate_amazon_searches.py
if errorlevel 1 (
    echo [WARNING] ROI analysis failed, continuing...
)

REM Step 2: Process listings and delete
echo.
echo [STEP 2] Processing all listings and deleting low performers...
call ai_process_all_listings_and_delete.bat
if errorlevel 1 (
    echo [WARNING] Listing processing had issues, continuing...
)

REM Step 3: Clear old cache
echo.
echo [STEP 3] Clearing old item cache...
python ebay_clear_old_item_cache.py
if errorlevel 1 (
    echo [WARNING] Cache clearing failed, continuing...
)

REM Step 4: Scrape and list new items
echo.
echo [STEP 4] Scraping and listing new items...
call scrapeandlist_batch.bat
if errorlevel 1 (
    echo [WARNING] Scraping had issues, continuing...
)

REM Step 5: Wait before processing
echo.
echo [STEP 5] Waiting 20 seconds before processing...
python sleep.py 20

REM Step 6: Kill batch uploader
echo.
echo [STEP 6] Killing batch uploader...
python kill_batch_uploader.py
if errorlevel 1 (
    echo [WARNING] Could not kill batch uploader
)

REM Step 7: Test and optimize listings with IMPROVED ERROR HANDLING
echo.
echo [STEP 7] Optimizing listings with OpenAI (min ratings: 8)...
echo Using improved error handling and retry logic...

REM First, fix any typos in the stats file
python fix_ebay_errors.py fix-typo

REM Run the optimization with timeout and error handling
timeout /t 2 /nobreak > nul
python test_ebay_utils.py --min-description-rating 8 --min-title-rating 8
if errorlevel 1 (
    echo [WARNING] OpenAI optimization had issues
    echo Attempting to diagnose errors...
    python diagnose_airotate_errors.py
)

echo.
echo [STEP 8] Optimizing listings with Ollama (min ratings: 9)...
python test_ebay_utils.py --min-description-rating 9 --min-title-rating 9 --use-ollama
if errorlevel 1 (
    echo [WARNING] Ollama optimization had issues
)

REM Step 9: Generate report
echo.
echo [STEP 9] Generating listing ratings report...
python generate_listing_ratings_report.py
if errorlevel 1 (
    echo [WARNING] Report generation failed
    echo Attempting to diagnose issues...
    python diagnose_airotate_errors.py
)

REM Step 10: Final diagnosis
echo.
echo [STEP 10] Running final error diagnosis...
python diagnose_airotate_errors.py

echo.
echo ============================================================
echo AIROTATE IMPROVED COMPLETED
echo Finished at: %date% %time%
echo ============================================================
echo.
echo To monitor errors in real-time, run:
echo   python diagnose_airotate_errors.py
echo.
echo To test a specific item with error handling:
echo   python fix_ebay_errors.py [ITEM_ID]
echo ============================================================