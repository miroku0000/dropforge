@echo off
echo Killing scrape_amazon_incremental.py processes...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *scrape_amazon_incremental.py*" /NH 2^>nul') do (
    echo Killing process %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM Alternative method - kill any python process running scrape_amazon_incremental.py
wmic process where "name='python.exe' and commandline like '%%scrape_amazon_incremental.py%%'" delete 2>nul

echo Done.
