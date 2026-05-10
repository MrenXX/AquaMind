# AquaMind tools contract

## Daytona Python runner (live)

- **CLI:** `scripts/aquamind_daytona_runner_cli.py` (stdin = Python source).
- **Chart path:** `/home/daytona/aquamind_chart.png`
- **Output:** JSON on stdout (`stdout`, `exit_code`, optional `signed_chart_url`).

## Planned FastAPI (analytics)

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | API + SQLite + Gmail readiness |
| `POST /ask` | Natural-language orchestration |
| `POST /tools/query_metrics` | Deterministic metrics |

Until deployed, use runner + domain knowledge only.
