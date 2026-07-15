# PowerShell script to fix Python installation

Write-Host "Attempting to fix Python installation..." -ForegroundColor Yellow

# Test basic Python
Write-Host "`nTest 1: Python with -S (no site packages)" -ForegroundColor Cyan
& python -S -c "print('Works with -S')"

# Find and rename problematic files
$sitePackages = "C:\Users\mirok\AppData\Local\Programs\Python\Python310\Lib\site-packages"

# Look for pywin32 related files
Write-Host "`nSearching for pywin32 files..." -ForegroundColor Cyan
$pywin32Files = Get-ChildItem -Path $sitePackages -Filter "*pywin32*" -ErrorAction SilentlyContinue
if ($pywin32Files) {
    Write-Host "Found pywin32 files:" -ForegroundColor Yellow
    $pywin32Files | ForEach-Object { Write-Host "  $_" }
}

# Look for customization files
Write-Host "`nSearching for sitecustomize/usercustomize files..." -ForegroundColor Cyan
$customFiles = Get-ChildItem -Path $sitePackages -Filter "*customize.py" -ErrorAction SilentlyContinue
if ($customFiles) {
    Write-Host "Found customization files:" -ForegroundColor Yellow
    $customFiles | ForEach-Object { Write-Host "  $_" }
}

Write-Host "`nDone!" -ForegroundColor Green