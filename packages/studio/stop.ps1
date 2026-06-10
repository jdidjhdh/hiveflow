# HiveFlow Studio Stop Script

Write-Host "Stopping HiveFlow Studio services..." -ForegroundColor Yellow

# Stop uvicorn
$uvicorn = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*app.main*" }
if ($uvicorn) {
    $uvicorn | Stop-Process -Force
    Write-Host "  Backend stopped" -ForegroundColor Cyan
} else {
    Write-Host "  Backend not running" -ForegroundColor Gray
}

# Stop vite/node
$vite = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" }
if ($vite) {
    $vite | Stop-Process -Force
    Write-Host "  Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "  Frontend not running" -ForegroundColor Gray
}

Write-Host "Done" -ForegroundColor Yellow