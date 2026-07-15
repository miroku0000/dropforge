@echo off
REM ===========================================================================
REM  run_airotate.bat -- run airotate with a run-summary digest + push alert.
REM
REM  Runs airotate.bat exactly as before (live output preserved), tees the
REM  console output to logs\airotate_<timestamp>.log, then airotate_report.py
REM  parses it into an OK/WARN/FAIL digest and pushes it (see notify.py).
REM
REM  Use this as the entry point (scheduler / manual) instead of airotate.bat
REM  when you want the end-of-run notification.
REM ===========================================================================
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%I
set RUNLOG=logs\airotate_%TS%.log

echo Running airotate -- logging to %RUNLOG%
echo/

REM Tee airotate's combined output to console AND the run log.
powershell -NoProfile -ExecutionPolicy Bypass -Command "cmd /c '.\airotate.bat' 2>&1 | Tee-Object -FilePath '%RUNLOG%'"

echo/
echo [REPORT] Summarizing run and sending digest...
python airotate_report.py "%RUNLOG%"

endlocal
