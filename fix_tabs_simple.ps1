# Simple script to fix Cursor tab settings
$cursorSettingsPath = "$env:APPDATA\Cursor\User\settings.json"

Write-Host "Fixing Cursor tab settings..." -ForegroundColor Green

# Create backup
if (Test-Path $cursorSettingsPath) {
    Copy-Item $cursorSettingsPath "$cursorSettingsPath.backup"
    Write-Host "Created backup of settings" -ForegroundColor Yellow
}

# Create new settings with proper tab configuration
$newSettings = @{
    "workbench.editor.enablePreview" = $false
    "workbench.editor.enablePreviewFromQuickOpen" = $false
    "workbench.editor.showTabs" = $true
    "workbench.editor.tabCloseButton" = "right"
    "workbench.editor.openPositioning" = "right"
} | ConvertTo-Json -Depth 10

# Write new settings
$newSettings | Set-Content $cursorSettingsPath -Encoding UTF8

Write-Host "Settings updated! RESTART CURSOR NOW!" -ForegroundColor Red


