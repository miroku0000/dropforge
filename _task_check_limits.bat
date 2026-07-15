@echo off
REM Scheduled-task wrapper: mid-day listing limit check + knob auto-tune.
cd /d "%~dp0"
python check_limits.py
