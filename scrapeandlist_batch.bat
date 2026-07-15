@echo off
echo Starting concurrent scraping and uploading...

REM Clear the output file
echo "" > ..\data\listme.txt

REM Start the batch uploader in background (monitors queue)
echo Starting batch uploader monitor...
start /B python batch_uploader.py

REM Start the incremental scraper (writes to queue as it goes)
echo Starting incremental scraper...
python scrape_amazon_incremental.py %*

echo:
echo Scraping completed. Batch uploader will continue until all items are processed.
echo Check the status files in ..\data\ for progress.