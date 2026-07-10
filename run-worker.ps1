# 启动后台 Worker：转码 / AI 分析 / 比赛结算 / DB 备份
Push-Location backend
if (-not (Test-Path ".venv")) {
  Write-Host "请先运行 .\setup.ps1" -ForegroundColor Red
  exit 1
}
.\.venv\Scripts\python.exe -m run_background_workers
Pop-Location
