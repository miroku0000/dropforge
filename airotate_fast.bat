@echo off
echo ============================================================
echo AIROTATE FAST MODE - SINGLE PHASE BATCH PROCESSING
echo ============================================================
echo Started at: %date% %time%
echo/

REM Step 1: Analyze ROI and generate Amazon searches
echo [STEP 1] Analyzing ROI and generating Amazon searches...
python analyze_roi_and_generate_amazon_searches.py
if errorlevel 1 (
    echo [WARNING] ROI analysis had issues, continuing...
)

REM Step 2: Process listings and delete low performers
echo/
echo [STEP 2] Processing all listings and deleting low performers...
REM this will process the most recent download of "all listings" and delete
REM up to 333 of them
call ai_process_all_listings_and_delete.bat
if errorlevel 1 (
    echo [WARNING] Listing processing had issues, continuing...
)

REM Step 3: Clear old cache
echo/
echo [STEP 3] Clearing old item cache...
python ebay_clear_old_item_cache.py
if errorlevel 1 (
    echo [WARNING] Cache clearing failed, continuing...
)

REM Step 4: Scrape and list new items
echo/
echo [STEP 4] Scraping and listing new items...
call scrapeandlist_batch.bat
if errorlevel 1 (
    echo [WARNING] Scraping had issues, continuing...
)

REM Step 5: Wait before processing
echo/
echo [STEP 5] Waiting 20 seconds before processing...
python sleep.py 20

REM Step 6: Kill batch uploader
echo/
echo [STEP 6] Killing batch uploader...
python kill_batch_uploader.py
if errorlevel 1 (
    echo [WARNING] Could not kill batch uploader
)

REM Step 7: Apply error handling patches if available
echo/
echo [STEP 7] Applying error handling patches...
REM Try combined patches first (avoids conflicts)
python -c "try: from combined_ebay_fixes import apply_combined_patches; apply_combined_patches(); print('[OK] Combined patches applied (retry + XML fixes)')" 2>nul
if errorlevel 1 (
    REM Fallback to individual patches if combined not available
    python -c "try: from ebay_utils_error_fixes import apply_monkey_patches; apply_monkey_patches(); print('[OK] Error patches applied')" 2>nul
    if errorlevel 1 (
        echo [INFO] Running without error patches
    )
    python -c "try: from xml_entity_fixes import apply_xml_fixes; apply_xml_fixes(); print('[OK] XML fixes applied')" 2>nul
    if errorlevel 1 (
        echo [INFO] Running without XML fixes
    )
)

REM Step 8: Test and optimize listings with OpenAI using SINGLE-PHASE batch mode
echo/
echo [STEP 8] Optimizing listings with OpenAI FAST MODE (single-phase, min ratings: 9)...
echo [INFO] Using single-phase processing for faster completion (no separate rating phase)

python test_ebay_utils_batch.py --batch --min-description-rating 9 --min-title-rating 9

if errorlevel 1 (
    echo [WARNING] OpenAI optimization had issues, falling back to regular processing
    echo [FALLBACK] Trying non-batch mode with lower ratings...
    python test_ebay_utils.py --min-description-rating 8 --min-title-rating 8
)
echo "test_ebay_utils using openai is complete"

REM Step 9: Generate report
echo/
echo [STEP 9] Generating listing ratings report...
python generate_listing_ratings_report.py
if errorlevel 1 (
    echo [WARNING] Report generation failed
)
echo "Listing ratings report complete"

echo/
echo ============================================================
echo AIROTATE FAST MODE COMPLETED
echo Finished at: %date% %time%
echo ============================================================
echo/
echo NOTE: This used single-phase batch processing for speed.
echo For more thorough optimization, use the regular airotate.bat
echo ============================================================