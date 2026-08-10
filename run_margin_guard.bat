@echo off
REM ===========================================================================
REM  run_margin_guard.bat -- standalone daily profitability guard.
REM
REM  Runs priceyak_margin_guard.py --apply independently of airotate, so the
REM  guard still checks (and raises the margin floor if sales are losing money)
REM  on days airotate does not run. The guard's own cooldown prevents a double
REM  raise if airotate already ran it the same day.
REM
REM  Scheduled via Windows Task Scheduler ("PriceYak Margin Guard", daily).
REM ===========================================================================
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist logs mkdir logs

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
set RUNLOG=logs\margin_guard_%TS%.log

echo Running margin guard -- logging to %RUNLOG%
REM --notify-ok pushes the daily profitability summary to your phone even when
REM everything is healthy (airotate's Step 13b stays quiet to avoid double pings).
REM Plain cmd redirection (headless task) -- avoids PowerShell wrapping Python's
REM stderr logging as NativeCommandError noise.
python priceyak_margin_guard.py --apply --notify-ok >> "%RUNLOG%" 2>&1

endlocal
