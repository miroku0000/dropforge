@echo off
REM Tunable listing knobs -- auto-adjusted by check_limits.py based on headroom.
REM Edit MAX_LISTINGS to set your target store size; the rest self-tune.
set PLAN_LIMIT=5000
set MAX_LISTINGS=4980
set MAX_URLS=280
set RELIST_MAX=100
set DELETE_MAX=333
set MIN_PRICE=50
REM Upper price bound for new scraping. Store is bound by eBay's ~$484,882 total-
REM listed-value limit, so cheaper items = more listings under the same cap.
REM $150 keeps new inventory in the cap-efficient band (~$97 avg fills the 5000 plan).
set MAX_PRICE=150
