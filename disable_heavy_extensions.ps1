# Disable Heavy Cursor Extensions
# This script disables extensions that are consuming too much memory

Write-Host "🔧 DISABLING HEAVY CURSOR EXTENSIONS" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Extensions known to consume high memory
$heavyExtensions = @(
    "github.vscode-github-actions",
    "redhat.vscode-yaml", 
    "ms-vscode.vscode-markdown",
    "ms-python.vscode-pylance"
)

Write-Host "`n📋 Extensions to disable:" -ForegroundColor Yellow
foreach ($ext in $heavyExtensions) {
    Write-Host "  • $ext" -ForegroundColor Red
}

Write-Host "`n🎯 MANUAL STEPS TO DISABLE EXTENSIONS:" -ForegroundColor Green
Write-Host "1. Press Ctrl+Shift+X to open Extensions panel" -ForegroundColor White
Write-Host "2. Search for each extension above" -ForegroundColor White
Write-Host "3. Click the gear icon next to each extension" -ForegroundColor White
Write-Host "4. Select 'Disable'" -ForegroundColor White
Write-Host "5. Restart Cursor after disabling all" -ForegroundColor White

Write-Host "`n💡 ALTERNATIVE: Use Command Palette" -ForegroundColor Cyan
Write-Host "1. Press Ctrl+Shift+P" -ForegroundColor White
Write-Host "2. Type 'Extensions: Disable' and select it" -ForegroundColor White
Write-Host "3. Type the extension name and disable it" -ForegroundColor White

Write-Host "`n🚨 CRITICAL: After disabling extensions, restart Cursor!" -ForegroundColor Red


