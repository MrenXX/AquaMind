# Start AquaMind FastAPI (analytics + POST /run chat SSE). Loads repo .env like the gateway script.
# Requires: pip install -r requirements-backend.txt
# Uses: OPENROUTER_API_KEY, DAYTONA_API_KEY, optional AQUAMIND_CORS_ORIGINS, AQUAMIND_DB_PATH

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $kv = $_ -split '=', 2
    if ($kv.Length -eq 2) {
      $k = $kv[0].Trim()
      $v = $kv[1].Trim().Trim('"')
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Error "Missing .venv. Create venv and install requirements-backend.txt"
}

& ".\.venv\Scripts\python.exe" -m pip install -q -r requirements-backend.txt
Write-Host "Starting backend on http://127.0.0.1:8765 (health: /health, chat SSE: POST /run). Ctrl+C to stop."
& ".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
