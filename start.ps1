# Starts Sarthi: FastAPI backend (port 8000) + Vite frontend (port 5173).
# Usage:  .\start.ps1
# Stop:   close the backend window, and Ctrl+C in this one.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- backend: its own window so `app.*` imports resolve from backend/ ---
$backend = Join-Path $root "backend"
$python  = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv not found at $python -- create it and pip install -r requirements.txt -r backend\requirements.txt" }

Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$backend'; & '$python' -m uvicorn app.main:app --reload --port 8000"
)

# --- frontend: runs in this window ---
$frontend = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "Installing frontend deps (first run) ..." -ForegroundColor Cyan
  npm install --prefix $frontend
}

Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
Set-Location $frontend
npm run dev
