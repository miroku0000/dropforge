@echo off
REM Newegg -> PriceYak: scrape Newegg and list the items on PriceYak (source=newegg).
REM Mirror of scrapeandlist_batch.bat but for the Newegg pipeline (own queue files).
REM Defaults: list only items priced $80-$200. Extra args pass through and
REM override (e.g. scrapeandlist_newegg_batch.bat --max-urls 500, or
REM scrapeandlist_newegg_batch.bat --min-price 100 --max-price 300).
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set MIN_PRICE=80
set MAX_PRICE=200

echo Starting concurrent Newegg scraping and uploading...

REM Clear the output file
echo "" > ..\data\listme_newegg.txt

REM Start the Newegg batch uploader in background (monitors the newegg queue)
echo Starting Newegg batch uploader monitor...
start /B python batch_uploader_newegg.py

REM Start the incremental scraper (writes to the newegg queue as it goes)
echo Starting incremental Newegg scraper...
python scrape_newegg_incremental.py --min-price %MIN_PRICE% --max-price %MAX_PRICE% %*

echo:
echo Scraping completed. Batch uploader will continue until all items are processed.
echo Check ..\data\newegg_scrape_status.json for progress.
