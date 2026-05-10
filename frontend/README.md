# AquaMind Dashboard

WaterSec React dashboard for the live agent pipeline. The UI is chat-first and renders real backend output: model text (optional Expert view), generated Python, sandbox stdout, chart metadata, and PNG artifacts. Top tabs add **Pipeline** (run evidence), **Model routing** (OpenRouter roles from `/health`), **Insights** (SQLite KPIs via FastAPI), and **Docs** (in-app reference).

## Backend contract

The dashboard expects a chat service that exposes:

- `POST /run` with body `{ "prompt": string }`
- Server-Sent Events on the response body
- Event names: `status`, `model_output`, `code`, `sandbox_result`, `repair`, `done`
- `GET /health` may include `openrouter_roles` for the Model routing tab

The app uses `fetch` plus `ReadableStream` because `EventSource` cannot send a POST body.

The backend may emit `status` with `step: "intent"` and `intent: "conversational" | "data"`. Special `sandbox_result.sandbox_id` values: `intent:conversational`, `sqlite:local` (stdout is ToolResponse JSON), or Daytona-style results.

**Insights** calls `GET /dashboard/summary` and `POST /tools/query_metrics`, `find_motifs`, `detect_anomalies` (same as documented in `openclaw/workspace-templates/TOOLS.md`).

### Optional: LFM tier router

The parent repo resolves **fast / balanced / heavy** tiers in `backend/router_gate.py` and heuristic intent in `backend/intent.py`. The FastAPI `/health` response includes `tier_slugs` for the dashboard. To try tier selection locally: `python -m backend.router_gate "your prompt"` from the repo root (with `.venv` and `PYTHONPATH` set so `backend` is importable, e.g. run from root after `pip install -r requirements-backend.txt`).

## Environment

- `VITE_CHAT_API`: SSE base URL. Use **`/api`** in local dev (`vite.config.ts` proxies to `127.0.0.1:8765`) so the browser stays same-origin.
- `VITE_API_BASE`: fallback if `VITE_CHAT_API` is unset
- `VITE_ANALYTICS_API`: optional; defaults to the same base as chat

Secrets stay on the server; restart FastAPI after changing model env vars so `/health` matches.

## Development

From this folder:

```powershell
npm install
npm run dev
```

Start the analytics API from the **repository root**: `.\scripts\start-aquamind-backend.ps1`

Use `npm run build` and `npm run lint` before shipping frontend changes.
