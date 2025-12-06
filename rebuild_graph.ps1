# Rebuild Graph Script
# This script clears the cache and rebuilds the graph from scratch

Write-Host "🔄 Rebuilding NodeRAG Graph..." -ForegroundColor Cyan

# Backup cache folder (optional)
$cacheFolder = "POC_Data\documents\cache"
$backupFolder = "POC_Data\documents\cache_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (Test-Path $cacheFolder) {
    Write-Host "📦 Backing up existing cache to $backupFolder" -ForegroundColor Yellow
    Copy-Item -Path $cacheFolder -Destination $backupFolder -Recurse
    
    Write-Host "🗑️ Clearing cache folder..." -ForegroundColor Yellow
    Remove-Item -Path "$cacheFolder\*" -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host "✅ Cache cleared" -ForegroundColor Green
}

# Clear document hash to force reprocessing
$docHashPath = "POC_Data\document_hash.json"
if (Test-Path $docHashPath) {
    Write-Host "🗑️ Removing document_hash.json" -ForegroundColor Yellow
    Remove-Item -Path $docHashPath -Force
}

Write-Host ""
Write-Host "✅ Ready to rebuild!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Start the WebUI: python -m NodeRAG.WebUI -f 'POC_Data\documents'" -ForegroundColor White
Write-Host "2. Click 'Build/Update' button in the sidebar" -ForegroundColor White
Write-Host "3. Wait for all 8 pipeline steps to complete" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Make sure you're not hitting API rate limits!" -ForegroundColor Yellow
Write-Host "   Consider waiting a few minutes before rebuilding if you hit 429 errors recently." -ForegroundColor Yellow
