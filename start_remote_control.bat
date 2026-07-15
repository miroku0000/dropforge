@echo off
echo ===============================================
echo Starting eBay Automation Remote Control Server
echo ===============================================
echo.
echo Checking network configuration...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP:~1%
echo.
echo Server will be accessible at:
echo   From your phone: http://%IP%:5000
echo   From this PC:    http://localhost:5000
echo.
echo IMPORTANT: To access from your phone:
echo 1. Make sure your phone and PC are on the same WiFi network
echo 2. Windows Firewall may block access - allow Python through firewall
echo 3. Open Claude app on your phone
echo 4. Type the URL above in a message to Claude
echo 5. Claude will help you control the system
echo.
echo Press Ctrl+C to stop the server
echo ===============================================
echo.
python remote_control_server.py
pause