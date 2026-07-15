@echo off
REM Force UTF-8 for all Python child processes so console prints of Unicode
REM glyphs (checkmarks, arrows, minus signs) don't crash on the cp1252 console.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo ============================================================
echo AIROTATE - EBAY LISTING AUTOMATION (WITH ERROR FIXES)
echo ============================================================
echo Started at: %date% %time%
echo/

REM Load tunable listing knobs (auto-adjusted by check_limits.py based on headroom)
call listing_config.bat
REM Snapshot active-listing count so the mid-day check can measure net growth
python check_limits.py --snapshot

REM Step 0: Refresh eBay OAuth token (no browser needed)
echo [STEP 0] Refreshing eBay OAuth token...
python ai_ebay_refresh_oauth_token.py
if errorlevel 1 (
    echo [WARNING] Token refresh failed - may need to run ai_ebay_get_oauth_token.py manually
)

REM Step 0-IRC: Process eBay Issue Resolution Center
REM Scrape problematic listings, end them via PriceYak, and blacklist their ASINs.
REM Run early (before relist/scrape steps) so blacklisted ASINs are not relisted.
echo/
echo [STEP 0-IRC] Processing eBay Issue Resolution Center (end + blacklist)...
call process_issue_resolution.bat
if errorlevel 1 (
    echo [WARNING] Issue Resolution processing had issues, continuing...
)

REM Step 0-SWEEP: Pre-emptive blacklist sweep -- get ahead of the IRC.
REM End active listings matching a blacklisted ASIN or brand (report keyword
REM matches), blacklist their ASINs, and sync ASINs into the scrape filter.
echo/
echo [STEP 0-SWEEP] Pre-emptive blacklist sweep (end blacklisted-brand/ASIN listings)...
python ai_ebay_blacklist_sweep.py
if errorlevel 1 (
    echo [WARNING] Blacklist sweep had issues, continuing...
)

REM Step 0-OOS: Remove listings that have been out of stock (Amazon source)
REM for too long. PriceYak reports quantity==0 + oos_time; end anything OOS for
REM >= 14 days via the same bulk_delist endpoint priceyakbulkdelete.py uses.
REM OOS is not a policy violation, so these ASINs are NOT blacklisted.
echo/
echo [STEP 0-OOS] Removing long-out-of-stock listings (^>= 14 days)...
python ai_ebay_remove_oos_listings.py --days 14
if errorlevel 1 (
    echo [WARNING] OOS removal had issues, continuing...
)

REM Step 0-SHIP: Consolidate all active listings onto the domestic-only
REM PRICEYAK_SHIPPING_PROFILE policy (skips any already on it). Keeps new
REM listings off the auto-created "Flat:..." policies that pick up international.
echo/
echo [STEP 0-SHIP] Migrating listings to domestic shipping policy...
python ai_ebay_migrate_shipping_policy.py
if errorlevel 1 (
    echo [WARNING] Shipping policy migration had issues, continuing...
)

REM Step 0-RET-A: For each new eBay return needing a label, try a PriceYak
REM gift-return; if it fails, open a "Returns -> Request a return label" case.
echo/
echo [STEP 0-RET-A] Starting PriceYak returns for new eBay return requests...
python ai_priceyak_start_returns.py
if errorlevel 1 (
    echo [WARNING] Start-returns had issues, continuing...
)

REM Step 0-RET-B: For returns whose PriceYak case got a support reply with a
REM return-label link, download the PDF and upload it to the matching eBay
REM return case as a UPS return shipping label.
echo/
echo [STEP 0-RET-B] Uploading PriceYak return labels to eBay...
python ai_ebay_upload_return_labels.py
if errorlevel 1 (
    echo [WARNING] Upload-return-labels had issues, continuing...
)

REM Step 0-RET-C: For orders with NO comment whose return was never refunded,
REM if the case has a return-label link >30 days old, ask support if it was
REM refunded on Amazon. Open case -> reply; closed case (PriceYak won't reopen
REM if est. delivery >30d ago) -> email support@priceyak.com. Stamps
REM "asked/emailed refund M/D/YYYY" so it never asks twice.
echo/
echo [STEP 0-RET-C] Following up on un-refunded PriceYak return cases...
python ai_priceyak_return_case_followup.py --scan 1500 --live
if errorlevel 1 (
    echo [WARNING] Return-case follow-up had issues, continuing...
)

REM Step 0-RET-D: Close the loop on 0-RET-C. Re-check orders stamped "asked/
REM emailed refund": if now actually refunded (returnStatus flips to WithRefund,
REM works for both case + email channels) -> comment "refunded"; if support now
REM says it won't be refunded -> "no refund: <reason>"; else leave pending.
echo/
echo [STEP 0-RET-D] Resolving PriceYak return-case follow-ups (refunded / no refund)...
python ai_priceyak_resolution_check.py --scan 1500 --live
if errorlevel 1 (
    echo [WARNING] Return-case resolution check had issues, continuing...
)

REM Step 0-ORD: Monitor PriceYak orders. Failed orders -> if insufficient funds,
REM alert to ADD MONEY; if another reason, flag for RETRY (cancelled/locked are
REM skipped). Also flags stuck orders with no tracking >24h. Alert-only here;
REM add --retry to auto-retry non-funding failures once you've validated it.
echo/
echo [STEP 0-ORD] Monitoring PriceYak orders (failures / untracked)...
python ai_priceyak_order_monitor.py --scan 300 --untracked-hours 24
if errorlevel 1 (
    echo [WARNING] PriceYak order monitor had issues, continuing...
)

REM Step 0-CMT: Auto-set PriceYak order comments -- "delivered" for delivered
REM (non-returned, non-external) orders, "ETA M/D/YYYY" for in-transit ones.
REM Only touches empty/own comments; never clobbers manual notes.
echo/
echo [STEP 0-CMT] Updating PriceYak order comments (delivered / ETA)...
python ai_priceyak_update_comments.py --scan 400
if errorlevel 1 (
    echo [WARNING] Order-comment update had issues, continuing...
)

REM Step 0a: Download Listings Traffic Report
echo [STEP 0a] Downloading Listings Traffic Report...
python ai_ebay_downlaod_listings_traffic_report.py
if errorlevel 1 (
    echo [WARNING] Listings traffic report download had issues, continuing...
)

REM Step 0c: Download eBay Ads Report (Automagical)
echo [STEP 0c] Downloading eBay Ads Report (Past 14 days)...
python ai_ebay_download_automagical.py ebay_ads_report
if errorlevel 1 (
    echo [WARNING] Ads report download had issues, continuing...
)

REM === DISABLED: Top Converters Test no longer checked/managed ===
REM REM Step 0d: Download Top Converters Keyword Report
REM echo [STEP 0d] Downloading Top Converters Keyword Report...
REM python ai_ebay_download_top_converters_keyword_report.py
REM if errorlevel 1 (
REM     echo [WARNING] Top Converters keyword report download had issues, continuing...
REM )

REM Step 0e: Download Suggested Priority Listing Report
echo [STEP 0e] Downloading Suggested Priority Listing Report...
python ai_ebay_download_suggested_priority_report.py
if errorlevel 1 (
    echo [WARNING] Suggested Priority report download had issues, continuing...
)

REM Step 0e2: Process Suggested Priority report and deactivate underperformers
echo [STEP 0e2] Processing Suggested Priority report...
python ai_ebay_process_suggested_priority_report.py
if errorlevel 1 (
    echo [WARNING] Suggested Priority processing had issues, continuing...
)

REM Step 0f: Add eBay trending categories to Amazon search URLs
echo [STEP 0f] Adding eBay trending categories to Amazon searches...
python ai_ebay_trending_to_amazon.py --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Trending keywords had issues, continuing...
)

REM Step 0g: Mine converting eBay keywords into Amazon searches.
REM Reads the latest Top Converters keyword report and adds buyer search phrases
REM that drove impressions/clicks/sales to amazon_urls.txt. Bounded (--max 150)
REM and self-activating: adds nothing until the campaign accrues traffic data.
echo [STEP 0g] Mining converting keywords into Amazon searches...
python mine_converting_keywords.py --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Keyword mining had issues, continuing...
)

REM Step 0h: Mine product-type terms from your winning listings' titles.
echo [STEP 0h] Mining winner-title product terms into Amazon searches...
python mine_winner_titles.py --min-price %MIN_PRICE% --max 40
if errorlevel 1 (
    echo [WARNING] Winner-title mining had issues, continuing...
)

REM Step 0i: Expand a random slice of existing search terms via autocomplete.
REM No output cap on purpose -- amazon_urls.txt is allowed to grow; scrape cost
REM is bounded instead by the --max-urls random subset at Step 4. Seeding from a
REM different 40 random terms each run keeps discovering new related queries.
echo [STEP 0i] Expanding random existing terms via autocomplete...
python amazon_keyword_expander.py --from-urls 40 --engine amazon --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Keyword expansion had issues, continuing...
)

REM Step 0j: Mine rising/steady-demand terms from Amazon Best Sellers &
REM Movers & Shakers (a few random category pages via Crawlbase per run).
echo [STEP 0j] Mining Amazon Best Sellers / Movers ^& Shakers terms...
python mine_amazon_movers.py --max-pages 5 --max 50 --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Amazon movers mining had issues, continuing...
)

REM Step 0k: Discover rising-demand terms via Google Trends (best-effort).
REM Google rate-limits this IP intermittently (HTTP 429); the script degrades
REM gracefully and just adds nothing on a blocked run. Kept small on purpose.
echo [STEP 0k] Discovering rising terms via Google Trends (best-effort)...
python mine_google_trends.py --from-urls 8 --rising-only --top-n 8 --sleep 4 --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Google Trends step had issues, continuing...
)

REM Step 0l: Mine "what's selling across eBay" terms from Terapeak Product
REM Research (uses the warm logged-in eBay browser session). For a few random
REM existing terms, reads the sold-listing titles and adds product-type phrases.
echo [STEP 0l] Mining Terapeak sold-listing terms...
python ai_ebay_terapeak_terms.py --from-urls 6 --min-count 3 --max 40 --min-price %MIN_PRICE%
if errorlevel 1 (
    echo [WARNING] Terapeak mining had issues, continuing...
)

REM Step 1: Analyze ROI and generate Amazon searches
echo [STEP 1] Analyzing ROI and generating Amazon searches...
python analyze_roi_and_generate_amazon_searches.py --min-price %MIN_PRICE%
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

REM Step 4: Optional - Uncomment if you want to use magicrotate
rem echo.
rem echo [STEP 4] Running magicrotate to delete unviewed old listings...
rem python magicrotate.py
rem Deletes unviewed old listings with no sales

REM Step 3a: Selective listing quantity -- set unproven listings to qty 1 and
REM proven sellers (order_count>=1) to qty 2. eBay's DOLLAR selling limit counts
REM price*quantity, so qty-2-on-everything wastes ~half the limit on second units
REM that never sell -> pins the store below the plan size. Runs BEFORE relist +
REM scrape so the reclaimed dollar headroom is available for new listings.
echo/
echo [STEP 3a] Setting selective listing quantity (free eBay $ headroom)...
python ai_ebay_selective_quantity.py --apply
if errorlevel 1 (
    echo [WARNING] Selective quantity had issues, continuing...
)

REM Step 3b: Relist proven sellers (ASINs that sold before but aren't listed)
echo/
echo [STEP 3b] Relisting proven sellers...
python ai_relist_proven_sellers.py --max %RELIST_MAX% --min-sales 2
if errorlevel 1 (
    echo [WARNING] Relist proven sellers had issues, continuing...
)

REM Step 4: Scrape and list new items
echo/
echo [STEP 4] Scraping and listing new items...
rem call scrapeandlist.bat # Old single-threaded version
REM --max-urls scrapes a random subset so the (growing) term list does not
REM blow up Crawlbase cost; the whole list is covered over several runs. Tune
REM the number to your daily scrape budget.
call scrapeandlist_batch.bat --min-price %MIN_PRICE% --max-urls %MAX_URLS%
if errorlevel 1 (
    echo [WARNING] Scraping had issues, continuing...
)

rem REM Step 5: Wait before processing
rem echo/
rem echo [STEP 5] Waiting 20 seconds before processing...
rem python sleep.py 20

REM Step 6: Kill batch uploader
echo/
echo [STEP 6] Killing batch uploader...
python kill_batch_uploader.py
if errorlevel 1 (
    echo [WARNING] Could not kill batch uploader
)

REM Step 6b: Monitor PriceYak listing failures + re-submit TRANSIENT (fetcher)
REM failures once PriceYak recovers. A high fetcher-error rate = PriceYak outage
REM (high-priority alert). The retry self-skips while the fetcher is still down.
echo/
echo [STEP 6b] Checking PriceYak listing failures (retry transient)...
python ai_priceyak_listing_failures.py --hours 24 --retry --max 300
if errorlevel 1 (
    echo [WARNING] Listing-failure monitor had issues, continuing...
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

REM Step 8: Test and optimize listings with OpenAI using batch mode
echo/
echo [STEP 8] Optimizing listings with OpenAI (min ratings: 8)...
rem python test_ebay_utils.py --min-description-rating 1 --min-title-rating 1
rem echo "test_ebay_utils Round 1 is complete"
python test_ebay_utils.py --min-description-rating 8 --min-title-rating 8

  rem python test_ebay_utils_batch.py --batch --min-description-rating 9 --min-title-rating 9 --two-phase

if errorlevel 1 (
    echo [WARNING] OpenAI optimization had issues
)
echo "test_ebay_utils using openai is complete"

REM Step 9: Test and optimize listings with Ollama
rem echo/
rem echo [STEP 9] Optimizing listings with Ollama (min ratings: 9)...
rem python test_ebay_utils.py --min-description-rating 9 --min-title-rating 9 --use-ollama
rem if errorlevel 1 (
rem     echo [WARNING] Ollama optimization had issues
rem )
rem echo "test_ebay_utils using ollama is complete"

REM Step 10: Generate report
echo/
echo [STEP 10] Generating listing ratings report...
python generate_listing_ratings_report.py
if errorlevel 1 (
    echo [WARNING] Report generation failed
)
echo "Listing ratings report complete"

REM === DISABLED: Top Converters Test campaign no longer checked/managed ===
REM REM Step 11: Comprehensive Campaign Optimization
REM echo/
REM echo ===============================================================================
REM echo [STEP 11] TOP CONVERTERS CAMPAIGN OPTIMIZATION
REM echo ===============================================================================
REM
REM REM Step 11.1: Analyze current keyword performance
REM echo/
REM echo [11.1] Analyzing current keyword performance and generating bid changes...
REM python generate_bid_changes_csv.py
REM if errorlevel 1 (
REM     echo [WARNING] Bid analysis had issues - check keyword report
REM     goto skip_optimization
REM )
REM
REM REM Step 11.2: Find new keyword opportunities
REM echo/
REM echo [11.2] Finding new keyword opportunities from listings...
REM python find_campaign_opportunities.py
REM if errorlevel 1 (
REM     echo [WARNING] Could not find new opportunities - continuing
REM )
REM
REM REM Step 11.3: Generate combined HTML report
REM echo/
REM echo [11.3] Generating combined optimization report...
REM python generate_combined_optimization_report.py
REM if errorlevel 1 (
REM     echo [WARNING] Could not generate HTML report
REM     goto skip_html
REM )
REM
REM REM Open the HTML report
REM for /f "tokens=*" %%i in ('dir /b /od campaign_optimization_report_*.html 2^>nul') do set LATEST_REPORT=%%i
REM if exist "%LATEST_REPORT%" (
REM     start "" "%LATEST_REPORT%"
REM     echo [SUCCESS] Optimization report opened: %LATEST_REPORT%
REM )
REM
REM :skip_html
REM REM Step 11.4: Apply bid changes (original method)
REM echo/
REM echo [11.4] Attempting to apply bid changes...
REM call apply_top_converters_bids.bat
REM if errorlevel 1 (
REM     echo [INFO] API updates not available - use manual upload from CSV files
REM ) else (
REM     echo [SUCCESS] Top Converters bid updates applied
REM )
REM
REM :skip_optimization
REM echo "Top Converters campaign optimization complete"
REM echo ===============================================================================

REM Step 13: Generate unified HTML report and open in browser
echo/
echo [STEP 13] Generating unified campaign report...
python generate_daily_campaign_report.py
if errorlevel 1 (
    echo [WARNING] Report generation had issues
)
echo "Daily campaign report generated and opened in browser"

REM Step 14: Send offers to eligible buyers (5% off)
echo/
echo [STEP 14] Sending offers to eligible buyers (5%% off)...
python ai_ebay_send_offers.py
if errorlevel 1 (
    echo [WARNING] Send offers had issues
)
echo "Send offers complete"

REM Step 15: Enforce max listings (delete zero-view if over limit)
echo/
echo [STEP 15] Enforcing max listings (%MAX_LISTINGS%)...
python ai_ebay_enforce_max_listings.py %MAX_LISTINGS%
if errorlevel 1 (
    echo [WARNING] Max listings enforcement had issues
)
echo "Max listings enforcement complete"

REM Step 16: Daily P&L Report
echo/
echo [STEP 16] Generating daily P&L report...
python ai_daily_pnl.py
if errorlevel 1 (
    echo [WARNING] P&L report had issues
)
echo "Daily P&L report complete"

REM Step 16b: Update the monthly P&L workbook for every COMPLETE month through
REM last month (auto-derived from today's date). Scrapes eBay revenue/net,
REM refreshes the transactions tab so COGS auto-computes, computes crawlbase from
REM Account-API usage x $/1000 rate, writes priceyak + formulas. Re-upload the
REM xlsx (or keep it in a Drive-synced folder) to sync the online sheet.
echo/
echo [STEP 16b] Updating monthly P&L workbook (complete months through last month)...
python update_pnl.py
if errorlevel 1 (
    echo [WARNING] Monthly P&L update had issues
)
echo "Monthly P&L update complete"

echo/
echo ============================================================
echo AIROTATE COMPLETED
echo Finished at: %date% %time%
echo ============================================================
echo/
echo To monitor errors, run: python monitor_airotate.py
echo To diagnose issues, run: python diagnose_airotate_errors.py
echo ============================================================