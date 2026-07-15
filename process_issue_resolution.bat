@echo off
REM ===========================================================================
REM  eBay Issue Resolution Center -> end listings + blacklist Amazon ASINs
REM
REM  1) Scrape https://resolution.ebay.com/rw/IssueResolutionCenter for every
REM     flagged listing, resolve each eBay item id to its Amazon ASIN via
REM     PriceYak, and write:
REM        data\kill.txt           (eBay item ids)
REM        data\blacklist_add.txt  (Amazon ASINs)
REM  2) End the flagged eBay listings via PriceYak bulk delist (priceyakbulkdelete.py)
REM  3) Add the Amazon ASINs to the PriceYak blacklist (priceyakblacklistadd.py)
REM
REM  NOTE: First run may open a Chrome window asking you to sign in to
REM        resolution.ebay.com -- complete the sign-in and it will continue.
REM ===========================================================================

REM Run from this script's own folder so relative imports / paths resolve.
cd /d "%~dp0"

set DATA=d:\zikprocessor\data

echo ============================================================
echo  ISSUE RESOLUTION -> END + BLACKLIST
echo  Started at: %date% %time%
echo ============================================================
echo/

REM Keep a rolling backup of the previous kill list.
if exist "%DATA%\kill.txt" copy /y "%DATA%\kill.txt" "%DATA%\kill.prev.txt" >nul

REM --- Step 1: Scrape Issue Resolution Center -------------------------------
echo [STEP 1] Scraping eBay Issue Resolution Center and resolving ASINs...
python ai_ebay_issue_resolution_to_blacklist.py
if errorlevel 1 (
    echo/
    echo [ERROR] Scrape/resolve failed -- ABORTING so a stale kill list is not deleted.
    goto end
)

REM --- Step 2: End the flagged eBay listings via PriceYak -------------------
echo/
echo [STEP 2] Ending flagged eBay listings via PriceYak bulk delist...
python priceyakbulkdelete.py
if errorlevel 1 (
    echo [WARNING] Bulk delist reported an error -- continuing to blacklist step.
)

REM --- Step 3: Add the Amazon ASINs to the PriceYak blacklist ---------------
echo/
echo [STEP 3] Adding Amazon ASINs to the PriceYak blacklist...
python priceyakblacklistadd.py
if errorlevel 1 (
    echo [WARNING] Blacklist update reported an error.
)

:end
echo/
echo ============================================================
echo  DONE at %date% %time%
echo ============================================================
