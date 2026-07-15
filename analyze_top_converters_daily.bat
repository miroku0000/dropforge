@echo off
REM Daily Top Converters Campaign Analysis
REM Run this daily after downloading the latest reports from eBay

echo ========================================
echo Top Converters Campaign Daily Analysis
echo ========================================
echo.

REM Set the Python path if needed
set PYTHONPATH=D:\zikprocessor\src

REM Run the analysis
python analyze_top_converters.py

echo.
echo Analysis complete. Check the summary file for details.
echo.
pause