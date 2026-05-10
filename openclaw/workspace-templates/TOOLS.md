# AquaMind tools contract

End-to-end integration (agent, OpenClaw, FastAPI, SQLite, Daytona, Gmail): **[`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)**.

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

PowerShell exec example (from repo root):

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
$report | & ".\.venv\Scripts\python.exe" ".\scripts\aquamind_gmail_report_cli.py"
```

If a virtualenv is not available, use `python scripts\aquamind_gmail_report_cli.py` from the repo root after installing `requirements-gmail.txt`.

## FastAPI analytics service (live)

Local HTTP API over `data/aquamind.sqlite` (build with `python scripts\etl\build_database.py`). Start from repo root:

```powershell
.\scripts\start-aquamind-backend.ps1
```

Default URL: `http://127.0.0.1:8765`. Set `AQUAMIND_API_BASE` in `.env` if you bind another host/port. Optional `AQUAMIND_DB_PATH` points at a non-default SQLite file.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | API up, DB file exists, Gmail env hints |
| `GET` | `/schema` | Allowed table/view names and doc pointers for agents |
| `GET` | `/dashboard/summary` | Compact counts for a future dashboard |
| `GET` | `/events/latest` | Last tool call trace (in-process MVP) |
| `POST` | `/tools/query_metrics` | Aggregates on `trusted_events` or `consumption_events` |
| `POST` | `/tools/compare_sources` | Two filtered slices side by side |
| `POST` | `/tools/find_motifs` | Rows from `motif_patterns` |
| `POST` | `/tools/detect_anomalies` | Rows from `anomaly_candidates` |
| `POST` | `/tools/run_sql_readonly` | Guarded `SELECT` / `WITH`, row cap |

PowerShell example (metrics):

```text
$body = @{ use_trusted = $true; customer_profile = "gym"; group_by = "day"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8765/tools/query_metrics" -Method Post -Body $body -ContentType "application/json"
```

Read-only SQL example:

```text
$body = @{ sql = "SELECT COUNT(*) AS n FROM trusted_events WHERE customer_profile = 'gym'"; max_rows = 50 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8765/tools/run_sql_readonly" -Method Post -Body $body -ContentType "application/json"
```

### Future: CSV → DB ingest tool

Planned endpoint (not implemented yet): `POST /tools/ingest_csv` — accept validated CSV payload + profile (`customerA` / `customerB` / `customerC` / `gym`), append to the appropriate `raw_*` table, then re-run or incrementally refresh normalized tables so MiniMax can refresh telemetry without shell access. Will be documented here when shipped; gate behind auth for non-demo use.

## Planned FastAPI extras

| Endpoint | Purpose |
|----------|---------|
| `POST /ask` | Optional natural-language orchestration layer |

Natural-language `/ask` is optional; until then the agent calls the `/tools/*` routes directly.
