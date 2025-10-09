# Force restart Cursor to fix multiple tab issue
Write-Host "🚨 FORCE RESTARTING CURSOR" -ForegroundColor Red

# Kill all Cursor processes forcefully
Write-Host "Killing all Cursor processes..." -ForegroundColor Yellow
Get-Process -Name "Cursor" -ErrorAction SilentlyContinue | Stop-Process -Force

# Wait for processes to fully terminate
Write-Host "Waiting 5 seconds for cleanup..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Verify all processes are gone
$remaining = Get-Process -Name "Cursor" -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "Force killing remaining processes..." -ForegroundColor Red
    $remaining | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Get current directory to restore workspace
$currentDir = Get-Location

# Start Cursor fresh
Write-Host "Starting fresh Cursor instance..." -ForegroundColor Green
Start-Process "cursor" -ArgumentList $currentDir

Write-Host "✅ Cursor restarted! Try opening multiple tabs now." -ForegroundColor Green
