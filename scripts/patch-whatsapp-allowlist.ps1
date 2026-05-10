$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

$envFile = Join-Path $repoRoot ".env"
$self = $null
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $kv = $_ -split '=', 2
    if ($kv.Length -eq 2 -and $kv[0].Trim() -eq "WHATSAPP_SELF_E164") {
      $self = $kv[1].Trim().Trim('"')
    }
  }
}

$allow = [System.Collections.ArrayList]@("+21658526779", "+21693779303")
if ($self -and $self -notmatch "REPLACE|XXXX|YOUR") {
  [void]$allow.Add($self.Trim())
}

$unique = $allow | Select-Object -Unique

$patchPath = Join-Path $repoRoot "openclaw\whatsapp-allowlist.generated.json5"
$lines = @(
  "{",
  "  channels: {",
  "    whatsapp: {",
  "      dmPolicy: `"allowlist`",",
  "      allowFrom: ["
)
$i = 0
foreach ($n in $unique) {
  $comma = if ($i -lt $unique.Count - 1) { "," } else { "" }
  $lines += "        `"$n`"$comma"
  $i++
}
$lines += "      ],"
$lines += "      groupPolicy: `"allowlist`","
$lines += "      groups: {"
$lines += "        `"*`": {"
$lines += "          requireMention: true"
$lines += "        }"
$lines += "      }"
$lines += "    }"
$lines += "  }"
$lines += "}"

$lines | Set-Content -Path $patchPath -Encoding UTF8
Write-Host "Writing $patchPath"
Write-Host ("allowFrom: " + ($unique -join ", "))
openclaw config patch --file $patchPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
openclaw config validate
Write-Host "Restart gateway: openclaw gateway stop  then  .\scripts\start-watersec-openclaw-gateway.ps1"
