@echo off
REM Automated bid adjustment for Top Converters campaign
REM Run this after analyzing campaign performance

echo ========================================
echo TOP CONVERTERS AUTOMATED BID ADJUSTMENT
echo ========================================
echo.

REM First show what changes would be made
echo [STEP 1] Preview bid changes (dry run)...
python auto_adjust_top_converters_bids.py --dry-run

echo.
echo ========================================
echo.

REM Ask user if they want to apply changes
set /p apply="Do you want to apply these bid changes? (yes/no): "

if /i "%apply%"=="yes" (
    echo.
    echo [STEP 2] Applying bid changes...
    REM Note: The API approach might not work due to eBay's API limitations
    REM You may need to use the Selenium approach instead
    
    REM Option 1: Try API approach (might need proper OAuth setup)
    REM python auto_adjust_top_converters_bids.py --live
    
    REM Option 2: Use Selenium browser automation
    echo.
    echo Using browser automation approach...
    python auto_adjust_bids_selenium.py
    
) else (
    echo.
    echo Cancelled - no changes made.
)

echo.
echo ========================================
echo COMPLETE
echo ========================================
pause