
python analyze_roi_and_generate_amazon_searches.py
rem this will process the most recent download of "all listings" and delete
rem up to 333 of them
call ai_process_all_listings_and_delete.bat
python ebay_clear_old_item_cache.py
rem magicrotate.py # deletes unviewed onld listings with no sales
rem call scrapeandlist.bat # scrapes amazon categories using crawlbase api
call scrapeandlist_batch.bat
python sleep.py 20
echo "Killing batch uploader"
kill_batch_uploader.py
echo "Calling test_ebay_utils"
rem python test_ebay_utils.py --min-description-rating 1 --min-title-rating 1
rem echo "test_ebay_utils Round 1 is complete"
python test_ebay_utils.py --min-description-rating 8 --min-title-rating 8
echo "test_ebay_utils using openai is complete"
python test_ebay_utils.py --min-description-rating 9 --min-title-rating 9 --use-ollama
echo "test_ebay_utils using ollama is complete"
echo "Generating listing ratings report..."
python generate_listing_ratings_report.py
echo "Listing ratings report complete"