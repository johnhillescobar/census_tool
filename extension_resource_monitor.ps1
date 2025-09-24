# Extension Resource Monitor for Cursor
# This script identifies which extensions are consuming the most resources

Write-Host "🔍 CURSOR EXTENSION RESOURCE MONITOR" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Function to identify extension from command line
function Get-ExtensionName {
    param($CommandLine)
    
    if ($CommandLine -like "*cursorpyright*") { return "CursorPyright (Python)" }
    elseif ($CommandLine -like "*github*") { return "GitHub Actions" }
    elseif ($CommandLine -like "*yaml*") { return "YAML Language Server" }
    elseif ($CommandLine -like "*markdown*") { return "Markdown Language Features" }
    elseif ($CommandLine -like "*typescript*") { return "TypeScript Language Server" }
    elseif ($CommandLine -like "*json*") { return "JSON Language Server" }
    elseif ($CommandLine -like "*html*") { return "HTML Language Server" }
    elseif ($CommandLine -like "*css*") { return "CSS Language Server" }
    elseif ($CommandLine -like "*eslint*") { return "ESLint" }
    elseif ($CommandLine -like "*prettier*") { return "Prettier" }
    elseif ($CommandLine -like "*renderer*") { return "Main Renderer Process" }
    elseif ($CommandLine -like "*gpu-process*") { return "GPU Process" }
    elseif ($CommandLine -like "*utility*") { return "Utility Process" }
    elseif ($CommandLine -like "*crashpad*") { return "Crash Handler" }
    else { return "Unknown Extension" }
}

# Function to categorize process type
function Get-ProcessType {
    param($CommandLine)
    
    if ($CommandLine -like "*server.js*" -or $CommandLine -like "*languageserver*") { return "Language Server" }
    elseif ($CommandLine -like "*renderer*") { return "Main Process" }
    elseif ($CommandLine -like "*gpu-process*") { return "GPU Process" }
    elseif ($CommandLine -like "*utility*") { return "Utility Process" }
    elseif ($CommandLine -like "*crashpad*") { return "System Process" }
    else { return "Extension Process" }
}

# Get all Cursor processes with detailed analysis
Write-Host "`n📊 EXTENSION RESOURCE USAGE:" -ForegroundColor Yellow
Write-Host "=============================" -ForegroundColor Yellow

$cursorProcesses = Get-WmiObject -Class Win32_Process | Where-Object { $_.Name -eq "Cursor.exe" }

$extensionData = @()
foreach ($process in $cursorProcesses) {
    $extensionName = Get-ExtensionName $process.CommandLine
    $processType = Get-ProcessType $process.CommandLine
    $memoryMB = [math]::Round($process.WorkingSetSize / 1MB, 2)
    
    $extensionData += [PSCustomObject]@{
        ProcessId   = $process.ProcessId
        Extension   = $extensionName
        Type        = $processType
        MemoryMB    = $memoryMB
        CommandLine = $process.CommandLine
    }
}

# Sort by memory usage and display
$extensionData | Sort-Object MemoryMB -Descending | Format-Table ProcessId, Extension, Type, @{Name = "Memory(MB)"; Expression = { $_.MemoryMB } } -AutoSize

# Calculate totals by extension
Write-Host "`n📈 MEMORY USAGE BY EXTENSION:" -ForegroundColor Yellow
Write-Host "===============================" -ForegroundColor Yellow

$extensionTotals = $extensionData | Group-Object Extension | ForEach-Object {
    $totalMemory = ($_.Group | Measure-Object MemoryMB -Sum).Sum
    [PSCustomObject]@{
        Extension     = $_.Name
        TotalMemoryMB = [math]::Round($totalMemory, 2)
        ProcessCount  = $_.Count
    }
} | Sort-Object TotalMemoryMB -Descending

$extensionTotals | Format-Table Extension, @{Name = "Total Memory(MB)"; Expression = { $_.TotalMemoryMB } }, ProcessCount -AutoSize

# Calculate grand total
$grandTotal = ($extensionData | Measure-Object MemoryMB -Sum).Sum
Write-Host "`n🎯 SUMMARY:" -ForegroundColor Green
Write-Host "Total Cursor Memory Usage: $([math]::Round($grandTotal, 2)) MB" -ForegroundColor $(if ($grandTotal -gt 2000) { "Red" } elseif ($grandTotal -gt 1000) { "Yellow" } else { "Green" })

# Identify top resource consumers
Write-Host "`n🚨 TOP RESOURCE CONSUMERS:" -ForegroundColor Red
$topConsumers = $extensionTotals | Where-Object { $_.TotalMemoryMB -gt 100 }
if ($topConsumers) {
    foreach ($consumer in $topConsumers) {
        Write-Host "• $($consumer.Extension): $($consumer.TotalMemoryMB) MB" -ForegroundColor Red
    }
}
else {
    Write-Host "✅ No extensions consuming excessive memory" -ForegroundColor Green
}

# Recommendations
Write-Host "`n💡 RECOMMENDATIONS:" -ForegroundColor Cyan
if ($grandTotal -gt 2000) {
    Write-Host "🚨 CRITICAL: Cursor using >2GB RAM" -ForegroundColor Red
    Write-Host "   → Restart Cursor immediately" -ForegroundColor Red
    Write-Host "   → Consider disabling heavy extensions" -ForegroundColor Red
}
elseif ($grandTotal -gt 1000) {
    Write-Host "⚠️  WARNING: Cursor using >1GB RAM" -ForegroundColor Yellow
    Write-Host "   → Monitor extension usage" -ForegroundColor Yellow
    Write-Host "   → Consider disabling unused extensions" -ForegroundColor Yellow
}
else {
    Write-Host "✅ GOOD: Cursor memory usage is acceptable" -ForegroundColor Green
}

# Extension-specific recommendations
Write-Host "`n🔧 EXTENSION-SPECIFIC RECOMMENDATIONS:" -ForegroundColor Cyan
foreach ($extension in $extensionTotals | Where-Object { $_.TotalMemoryMB -gt 50 }) {
    switch ($extension.Extension) {
        "CursorPyright (Python)" {
            Write-Host "• Python Extension: Consider disabling if not actively coding Python" -ForegroundColor Yellow
        }
        "GitHub Actions" {
            Write-Host "• GitHub Actions: Disable if not using GitHub workflows" -ForegroundColor Yellow
        }
        "YAML Language Server" {
            Write-Host "• YAML Extension: Disable if not editing YAML files" -ForegroundColor Yellow
        }
        "Markdown Language Features" {
            Write-Host "• Markdown Extension: Disable if not writing documentation" -ForegroundColor Yellow
        }
        "Main Renderer Process" {
            Write-Host "• Main Process: This is normal - restart Cursor if >500MB" -ForegroundColor White
        }
    }
}

Write-Host "`n📋 HOW TO DISABLE EXTENSIONS:" -ForegroundColor Cyan
Write-Host "1. Press Ctrl+Shift+X (Extensions)" -ForegroundColor White
Write-Host "2. Search for the extension name" -ForegroundColor White
Write-Host "3. Click 'Disable' on the extension" -ForegroundColor White
Write-Host "4. Restart Cursor" -ForegroundColor White

Write-Host "`n✨ Run this script regularly to monitor extension resource usage!" -ForegroundColor Green
