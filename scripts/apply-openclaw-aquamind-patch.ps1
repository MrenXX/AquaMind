# Applies AquaMind OpenRouter/MiniMax + WhatsApp defaults into active ~/.openclaw/openclaw.json
# Usage (repo root):  .\scripts\apply-openclaw-aquamind-patch.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $PSScriptRoot
$patch = Join-Path $here "openclaw\aquamind.patch.json5"
if (-not (Test-Path $patch)) {
  Write-Error "Missing patch file: $patch"
}
Write-Host "Patch file: $patch"
openclaw config patch --file $patch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
openclaw config validate
