# Start AquaMind FastAPI analytics (from repo root).
# Requires: pip install -r requirements-backend.txt
# Optional: $env:AQUAMIND_DB_PATH = "C:\path\to\aquamind.sqlite"

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Error "Missing .venv. Create venv and install requirements-backend.txt"
}

& ".\.venv\Scripts\python.exe" -m pip install -q -r requirements-backend.txt
& ".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
