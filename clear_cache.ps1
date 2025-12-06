# Clear NodeRAG Cache
# Use this after a failed or interrupted build to start fresh

Write-Host "🗑️  Clearing NodeRAG Cache..." -ForegroundColor Cyan
Write-Host ""

$cacheFolder = "POC_Data\documents\cache"
$infoFolder = "POC_Data\documents\info"
$docHashFile = "POC_Data\document_hash.json"

# Clear cache folder
if (Test-Path $cacheFolder) {
    Write-Host "Removing cache files..." -ForegroundColor Yellow
    Remove-Item -Path "$cacheFolder\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Cache folder cleared" -ForegroundColor Green
} else {
    Write-Host "⚠️  Cache folder not found" -ForegroundColor Yellow
}

# Clear info folder (build state)
if (Test-Path $infoFolder) {
    Write-Host "Removing build state files..." -ForegroundColor Yellow
    Remove-Item -Path "$infoFolder\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Info folder cleared" -ForegroundColor Green
} else {
    Write-Host "⚠️  Info folder not found" -ForegroundColor Yellow
}

# Clear document hash
if (Test-Path $docHashFile) {
    Write-Host "Removing document hash..." -ForegroundColor Yellow
    Remove-Item -Path $docHashFile -Force
    Write-Host "✅ Document hash removed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Document hash not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Cache cleared successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now rebuild by:" -ForegroundColor Cyan
Write-Host "  1. Start WebUI: python -m NodeRAG.WebUI -f 'POC_Data\documents'" -ForegroundColor White
Write-Host "  2. Click 'Build/Update' button" -ForegroundColor White
Write-Host ""
