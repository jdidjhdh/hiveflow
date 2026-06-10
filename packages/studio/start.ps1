﻿﻿﻿﻿﻿﻿﻿﻿﻿# HiveFlow Studio Start Script
# Usage: .\\start.ps1              # Start both frontend and backend
#        .\\start.ps1 -Frontend    # Frontend only
#        .\\start.ps1 -Backend     # Backend only

param(
    [switch]$Frontend,
    [switch]$Backend
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (!$Frontend -and !$Backend) {
    $Frontend = $true
    $Backend = $true
}

if ($Backend) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Starting Backend FastAPI (http://127.0.0.1:8000)" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$root\backend'; .\venv\Scripts\activate; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    )
}

if ($Frontend) {
    Write-Host "`n========================================"  -ForegroundColor Green
    Write-Host "  Starting Frontend Vite (http://localhost:3000)" -ForegroundColor Green
    Write-Host "========================================`n" -ForegroundColor Green
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$root\frontend'; npm run dev"
    )
}

Write-Host "`nHiveFlow Studio starting..." -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "  Backend: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "  API Docs: http://127.0.0.1:8000/docs`n" -ForegroundColor Yellow