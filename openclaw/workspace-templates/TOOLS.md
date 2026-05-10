# AquaMind tools contract

## Daytona Python runner (live)

- **CLI:** `scripts/aquamind_daytona_runner_cli.py` (stdin = Python source).
- **Chart path:** `/home/daytona/aquamind_chart.png`
- **Output:** JSON on stdout (`stdout`, `exit_code`, optional `signed_chart_url`).

## Gmail report sender (live)

- **CLI:** `scripts/aquamind_gmail_report_cli.py` (stdin = JSON report object).
- **Install deps:** `pip install -r requirements-gmail.txt`
- **OAuth client secret:** `%USERPROFILE%\.openclaw\gmail\client_secret.json` by default.
- **OAuth token:** `%USERPROFILE%\.openclaw\gmail\token.json` by default; first real send may open browser consent.
- **SQLite log:** `%USERPROFILE%\.openclaw\gmail\gmail_reports.sqlite3` by default.
- **Output:** one JSON object on stdout (`ok`, `status`, `message_id`, `recipient`, `subject`, `incident_id`, `sqlite_report_id`, or `error`).

Required report JSON:

```json
{
  "report_type": "incident",
  "incident_id": "AQM-2026-0001",
  "subject": "WaterSec incident report: suspected night leak",
  "summary": "Short executive summary with exact tool-computed values.",
  "evidence_rows": [
    {
      "timestamp": "2026-05-10T01:00:00",
      "device_id": "device-12",
      "observation": "Abnormal night usage above baseline"
    }
  ],
  "recommended_action": "Inspect the affected fixture and confirm whether flow continues while the building is closed.",
  "caveats": "Candidate anomaly based on available telemetry; field verification required."
}
```

PowerShell exec example:

```text
$report = @'
{
  "report_type": "incident",
  "incident_id": "AQM-2026-0001",
  "subject": "WaterSec incident report: suspected night leak",
  "summary": "Tool-computed anomaly summary goes here.",
  "evidence_rows": [{"device_id":"device-12","metric":"night_usage_liters","value":1840}],
  "recommended_action": "Dispatch a technician to inspect the toilet block and check for stuck flush valves.",
  "caveats": "Correlation is not causation; sensor faults remain possible."
}
'@
$report | & "C:\Users\Dell\WaterSec-OpenClaw-\.venv\Scripts\python.exe" "C:\Users\Dell\WaterSec-OpenClaw-\scripts\aquamind_gmail_report_cli.py"
```

If a virtualenv is not available, use `python scripts\aquamind_gmail_report_cli.py` from the repo root after installing `requirements-gmail.txt`.

## Planned FastAPI (analytics)

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | API + SQLite + Gmail readiness |
| `POST /ask` | Natural-language orchestration |
| `POST /tools/query_metrics` | Deterministic metrics |

Until deployed, use runner + domain knowledge only.
