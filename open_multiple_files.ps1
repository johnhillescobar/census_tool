# Script to force open multiple files in Cursor
# This bypasses the memory issue by opening files programmatically

Write-Host "🔧 FORCE OPENING MULTIPLE FILES" -ForegroundColor Cyan
Write-Host "===============================" -ForegroundColor Cyan

# Get current directory
$currentDir = Get-Location

# Files to open
$filesToOpen = @("config.py", "app.py", "routing.py")

Write-Host "`n📁 Opening files in current directory: $currentDir" -ForegroundColor Yellow

foreach ($file in $filesToOpen) {
    if (Test-Path $file) {
        Write-Host "• Opening: $file" -ForegroundColor Green
        # Open file with Cursor
        Start-Process "cursor" -ArgumentList $file
        Start-Sleep -Milliseconds 500  # Small delay between files
    } else {
        Write-Host "• File not found: $file" -ForegroundColor Red
    }
}

Write-Host "`n✅ Attempted to open multiple files!" -ForegroundColor Green
Write-Host "Check if multiple Cursor windows opened with different files." -ForegroundColor Cyan

