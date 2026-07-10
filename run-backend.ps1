# 启动后端（FastAPI / uvicorn，热重载）
Push-Location backend
if (-not (Test-Path ".venv")) {
  Write-Host "请先运行 .\setup.ps1" -ForegroundColor Red
  exit 1
}
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Pop-Location
