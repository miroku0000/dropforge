# PowerShell script to download and install Python 3.12

Write-Host "Downloading Python 3.12 installer..." -ForegroundColor Cyan
$pythonUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
$installerPath = "$env:TEMP\python-3.12.8-amd64.exe"

# Download the installer
Write-Host "Downloading from: $pythonUrl" -ForegroundColor Yellow
Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing

Write-Host "Download complete. Starting installation..." -ForegroundColor Green
Write-Host "Installing with options:" -ForegroundColor Yellow
Write-Host "  - Add Python to PATH" -ForegroundColor Yellow
Write-Host "  - Install for all users" -ForegroundColor Yellow
Write-Host "  - Include pip" -ForegroundColor Yellow
Write-Host "  - Include py launcher" -ForegroundColor Yellow

# Install Python silently with all features
# /quiet - silent install
# InstallAllUsers=1 - install for all users
# PrependPath=1 - add to PATH
# Include_pip=1 - include pip
# Include_launcher=1 - include py launcher
Start-Process -FilePath $installerPath -ArgumentList @(
    "/quiet",
    "InstallAllUsers=1",
    "PrependPath=1", 
    "Include_pip=1",
    "Include_launcher=1",
    "Include_test=0",
    "Include_doc=0"
) -Wait

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Cleaning up installer..." -ForegroundColor Cyan
Remove-Item $installerPath -Force

Write-Host "`nPython 3.12 has been installed!" -ForegroundColor Green
Write-Host "You may need to restart your terminal for PATH changes to take effect." -ForegroundColor Yellow