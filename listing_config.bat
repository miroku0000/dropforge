@echo off
REM Tunable listing knobs -- auto-adjusted by check_limits.py based on headroom.
REM Edit MAX_LISTINGS to set your target store size; the rest self-tune.
set PLAN_LIMIT=5000
set MAX_LISTINGS=4980
set MAX_URLS=200
set RELIST_MAX=100
set DELETE_MAX=333
set MIN_PRICE=50
