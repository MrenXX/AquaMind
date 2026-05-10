# Load OPENROUTER_API_KEY from WaterSec .env (if present), then start the gateway.
# Keep this window open while testing WhatsApp.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $kv = $_ -split '=', 2
    if ($kv.Length -eq 2) {
      $k = $kv[0].Trim()
      $v = $kv[1].Trim().Trim('"')
      Set-Item -Path "Env:$k" -Value $v
    }
  }
}
Import-DotEnvFile (Join-Path $repoRoot ".env")
Import-DotEnvFile (Join-Path $repoRoot "env")
Write-Host "Starting OpenClaw gateway (Ctrl+C to stop). Ensure WhatsApp linked via: openclaw channels login --channel whatsapp"
openclaw gateway run
