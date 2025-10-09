# Script to fix Cursor tab settings
# This will modify Cursor's settings to enable proper tab behavior

Write-Host "🔧 FIXING CURSOR TAB SETTINGS" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# Get Cursor settings directory
$cursorSettingsPath = "$env:APPDATA\Cursor\User\settings.json"

Write-Host "`n📁 Cursor settings location: $cursorSettingsPath" -ForegroundColor Yellow

# Check if settings file exists
if (Test-Path $cursorSettingsPath) {
    Write-Host "✅ Found Cursor settings file" -ForegroundColor Green
    
    # Read current settings
    $settings = Get-Content $cursorSettingsPath -Raw | ConvertFrom-Json
    
    Write-Host "`n🔧 Current tab-related settings:" -ForegroundColor Yellow
    if ($settings.'workbench.editor.enablePreview') {
        Write-Host "  • Preview mode: $($settings.'workbench.editor.enablePreview')" -ForegroundColor Red
    }
    if ($settings.'workbench.editor.showTabs') {
        Write-Host "  • Show tabs: $($settings.'workbench.editor.showTabs')" -ForegroundColor $(if ($settings.'workbench.editor.showTabs') { "Green" } else { "Red" })
    }
} else {
    Write-Host "❌ Cursor settings file not found. Creating new one..." -ForegroundColor Yellow
    $settings = @{}
}

# Set the correct tab settings
Write-Host "`n🔧 Applying tab fixes..." -ForegroundColor Cyan

$settings | Add-Member -MemberType NoteProperty -Name 'workbench.editor.enablePreview' -Value $false -Force
$settings | Add-Member -MemberType NoteProperty -Name 'workbench.editor.enablePreviewFromQuickOpen' -Value $false -Force
$settings | Add-Member -MemberType NoteProperty -Name 'workbench.editor.showTabs' -Value $true -Force
$settings | Add-Member -MemberType NoteProperty -Name 'workbench.editor.tabCloseButton' -Value 'right' -Force
$settings | Add-Member -MemberType NoteProperty -Name 'workbench.editor.openPositioning' -Value 'right' -Force

# Save the settings
try {
    $settings | ConvertTo-Json -Depth 10 | Set-Content $cursorSettingsPath -Encoding UTF8
    Write-Host "✅ Settings updated successfully!" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to update settings: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n🎯 RESTART CURSOR NOW for changes to take effect!" -ForegroundColor Red
Write-Host "After restart, try opening multiple files with Ctrl+P" -ForegroundColor Cyan
