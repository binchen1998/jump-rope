# First-time setup: backend venv + deps + migrate, frontend deps
# Usage: .\setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> Backend: create venv and install deps" -ForegroundColor Cyan
Push-Location backend
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "==> Create tables" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m migrations.0001_init
Pop-Location

Write-Host "==> Frontend: npm install" -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location

Write-Host "Done!" -ForegroundColor Green
Write-Host "Dev: .\run-backend.ps1  .\run-frontend.ps1  .\run-worker.ps1" -ForegroundColor Green
