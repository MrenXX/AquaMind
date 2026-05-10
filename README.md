# AquaMind (WaterSec)

AquaMind is a **WaterSec operations assistant** that employees reach on **WhatsApp**. It runs on **OpenClaw** and uses **OpenRouter** with **multiple coordinated models**, **latency-prioritized provider selection**, and **fallback chains**—not a single fixed model. It runs **Python in Daytona** for charts and proofs, and can send **Gmail** incident reports when a situation should be escalated.

This repository holds **config patches**, **PowerShell helpers**, **CLI tools**, **OpenClaw workspace prompts**, a **FastAPI backend** (chat + SQLite analytics), an optional **React dashboard**, and **sample telemetry CSVs** for demos—**not** secrets or your live `%USERPROFILE%\.openclaw\` state.

**Full stack onboarding (agent → OpenClaw → FastAPI → SQLite → web UI, plus Daytona/Gmail):** see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). On **`main`**, treat that file as the integration map (the `feature/sqlite-fastapi-backend` branch tracks the same stack when you need a long-lived integration branch).

---

## What you get

| Area | What’s in the repo |
|------|---------------------|
| **WhatsApp** | OpenClaw channel setup, QR linking, DM/group allowlist script, `@clanker` group wake word (see patch + docs). |
| **Models** | `openclaw/aquamind.patch.json5`: **primary** Qwen 3 Next, **fallbacks** MiniMax M2.5 and Liquid LFM 2.5, **`provider.sort: "latency"`**, shared timeouts; FastAPI **`/health`** exposes per-tier slugs via `AQUAMIND_MODEL_*` (see `backend/router_gate.py`). |
| **Daytona** | `scripts/aquamind_daytona_runner_cli.py` — stdin Python → sandbox → **JSON** (`stdout`, `exit_code`, optional **`signed_chart_url`** for PNG previews). |
| **Gmail** | `scripts/aquamind_gmail_report_cli.py` — stdin **JSON report** → Gmail API (OAuth) → **JSON** result + **SQLite** send log under `%USERPROFILE%\.openclaw\gmail\`. |
| **Gateway** | `scripts/start-watersec-openclaw-gateway.ps1` — loads repo `.env`, runs `openclaw gateway run`. |
| **Agent prompts** | `openclaw/workspace-templates/` → copy into `%USERPROFILE%\.openclaw\workspace\` (`AGENTS.md`, `SOUL.md`, `TOOLS.md`). |
| **Data / demo** | Sample consumption CSVs, `requirements-spike.txt`, `scripts/proof_openrouter_daytona.py`, artifacts and hackathon PDF (see repo root). |
| **SQLite data layer** (`sqlite-backend`) | `scripts/etl/` — builds `data/aquamind.sqlite` from the CSVs; **normalization**, **quality flags**, **trusted metrics**, motifs, anomalies. See [`docs/SQLITE_BACKEND.md`](docs/SQLITE_BACKEND.md). |
| **FastAPI (chat + analytics)** | `backend/` + `scripts/start-aquamind-backend.ps1` — **`POST /run`** streams **SSE** for the dashboard and tools (intent classification, optional SQLite-first planner, Daytona codegen fallback); **`GET /health`** reports DB status, Gmail env hints, **`openrouter_roles`**, **routing** metadata, and **tier** slug health from `router_gate` / `intent`. **REST tools:** `/dashboard/summary`, `/tools/query_metrics`, `/tools/compare_sources`, `/tools/find_motifs`, `/tools/detect_anomalies`, `/tools/run_sql_readonly` (see [`openclaw/workspace-templates/TOOLS.md`](openclaw/workspace-templates/TOOLS.md)). |
| **Heuristic routing** | `backend/router_gate.py` and `backend/intent.py` — tier choice mapped to `AQUAMIND_MODEL_*` slugs; summarized on `/health` as `tier_slugs`. |
| **React dashboard** | `frontend/` — Vite + React: **Overview** (chat), **Pipeline** (steps, expert transcript/code, charts), **Model routing** (planned OpenRouter chains from `/health`), **Insights** (charts + KPIs from SQLite API), **Docs** (in-app setup summary). Uses `fetchAnalytics` for the same tool routes the agent uses. |

---

## Architecture (high level)

```mermaid
flowchart LR
  subgraph channels [Channels]
    WA[WhatsApp user]
  end
  subgraph clients [Other clients]
    FE[React dashboard]
  end
  subgraph runtime [Gateway host]
    OC[OpenClaw gateway]
    DR[Daytona runner CLI]
    GM[Gmail report CLI]
    API[FastAPI chat plus analytics]
  end
  subgraph cloud [External APIs]
    OR[OpenRouter]
    DT[Daytona]
    GMAIL[Gmail API]
  end
  WA --> OC
  FE --> API
  OC --> OR
  OC --> DR
  DR --> DT
  OC --> GM
  GM --> GMAIL
  OC --> API
  API --> OR
```

---

## Prerequisites

- **Windows** (paths and scripts assume PowerShell). OpenClaw also documents [Windows / WSL2](https://docs.openclaw.ai/windows) if you hit native Windows edge cases.
- **Node.js** (OpenClaw recommends current LTS-style versions; WhatsApp plugin is pinned in [`openclaw/README-WHATSAPP.md`](openclaw/README-WHATSAPP.md)).
- **OpenClaw CLI** — install globally, e.g. `npm install -g openclaw@latest` (see [OpenClaw install](https://docs.openclaw.ai/install/)).
- **Python 3.12+** recommended for local CLIs and venvs.

---

## Quick start

1. **Clone** this repo and open a terminal at the repo root.

2. **Environment**

   ```powershell
   Copy-Item .\.env.example .\.env
   ```

   Fill at least:

   - `OPENROUTER_API_KEY` — for the agent model via OpenClaw.
   - `DAYTONA_API_KEY` — for the Daytona runner (and spike scripts).
   - `WHATSAPP_SELF_E164` — your number in E.164 for the allowlist script.
   - For Gmail reports: `GMAIL_SENDER`, `GMAIL_TO`, plus OAuth files (see below).

3. **Python dependencies** (for CLIs)

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-gmail.txt
   # Optional spike / proof stack:
   .\.venv\Scripts\python.exe -m pip install -r requirements-spike.txt
   # Analytics API (FastAPI over SQLite):
   .\.venv\Scripts\python.exe -m pip install -r requirements-backend.txt
   ```

4. **OpenClaw bootstrap and patches** — follow the step-by-step guide:

   **[`openclaw/README-WHATSAPP.md`](openclaw/README-WHATSAPP.md)**

   Summary of repo scripts you will run from the repo root:

   - `.\scripts\apply-openclaw-aquamind-patch.ps1` — merges model, timeouts, fallbacks, latency sort, group chat mention config, and plugin allowlist into `~\.openclaw\openclaw.json`.
   - `.\scripts\patch-whatsapp-allowlist.ps1` — regenerates allowlist patch from built-in numbers + `WHATSAPP_SELF_E164`.

5. **WhatsApp linking** (interactive QR)

   ```powershell
   openclaw channels login --channel whatsapp
   ```

6. **Copy workspace templates** (after editing templates in git, refresh the live workspace)

   ```powershell
   Copy-Item -Path .\openclaw\workspace-templates\* -Destination "$env:USERPROFILE\.openclaw\workspace" -Force
   ```

7. **Start the gateway**

   ```powershell
   .\scripts\start-watersec-openclaw-gateway.ps1
   ```

8. **(Optional) Telemetry DB + analytics API** — after CSVs are in the repo root:

   ```powershell
   .\.venv\Scripts\python.exe scripts\etl\build_database.py
   .\.venv\Scripts\python.exe scripts\validate_db.py
   .\scripts\start-aquamind-backend.ps1
   ```

   Open `http://127.0.0.1:8765/docs` for interactive API testing.

9. **(Optional) React dashboard** — in a second terminal:

   ```powershell
   cd frontend
   npm install
   copy ..\.env.example .env.local   # optional; set VITE_CHAT_API=/api for Vite proxy to step 8
   npm run dev
   ```

   Use `VITE_CHAT_API=/api` so the dev server proxies `http://127.0.0.1:8765` (avoids CORS). See [`frontend/README.md`](frontend/README.md) for the chat/analytics contract.

---

## Gmail incident reports (summary)

- Install deps: `requirements-gmail.txt`.
- Default OAuth client JSON: `%USERPROFILE%\.openclaw\gmail\client_secret.json` (Desktop OAuth client from Google Cloud; enable Gmail API; add test users if app is in **Testing**).
- After first consent, token is stored (default `%USERPROFILE%\.openclaw\gmail\token.json`).
- **Dry run** (no send): `scripts/aquamind_gmail_report_cli.py --dry-run`
- Full details and env vars: [`openclaw/README-WHATSAPP.md`](openclaw/README-WHATSAPP.md) and [`openclaw/workspace-templates/TOOLS.md`](openclaw/workspace-templates/TOOLS.md).

---

## Useful scripts (reference)

| Script | Role |
|--------|------|
| `scripts/start-watersec-openclaw-gateway.ps1` | Load `.env`, run `openclaw gateway run`. |
| `scripts/apply-openclaw-aquamind-patch.ps1` | Apply `openclaw/aquamind.patch.json5`. |
| `scripts/patch-whatsapp-allowlist.ps1` | Build and apply WhatsApp allowlist patch. |
| `scripts/aquamind_daytona_runner_cli.py` | Python in Daytona → JSON (charts → `signed_chart_url`). |
| `scripts/aquamind_gmail_report_cli.py` | JSON report → Gmail API → JSON + SQLite log. |
| `scripts/proof_openrouter_daytona.py` | End-to-end OpenRouter → generated code → Daytona smoke test. |
| `scripts/daytona_artifact_preview.py` | Helper around Daytona artifacts (see script docstring). |
| `scripts/start-aquamind-backend.ps1` | Install `requirements-backend.txt` if needed, run **FastAPI** on `127.0.0.1:8765` (`/run`, `/health`, `/dashboard/*`, `/tools/*`). |
| `backend/router_gate.py` | Tier smoke test from repo root: `python -m backend.router_gate "your prompt"` (uses `backend.intent` heuristics + `AQUAMIND_MODEL_*` env slugs). |

---

## Security and hygiene

- **Never commit** `.env`, OAuth `client_secret.json`, or `token.json`. They are listed in `.gitignore` for env and generated files; keep Gmail secrets under `%USERPROFILE%\.openclaw\gmail\`.
- **Rotate keys** if they ever appeared in chat logs or were committed by mistake.
- WhatsApp linking ties the gateway to a real device session—treat the host like production credentials.

---

## SQLite data layer

WaterSec telemetry arrives as **four inconsistent CSV exports**. This branch adds an ETL pipeline that loads them into **SQLite**, normalizes to one event schema, flags bad sensor rows, and builds **derived datasets** (daily profiles, device baselines, Customer C **motifs**, anomaly candidates, cautious gym pairing). Optional enrichment: seeded holidays, placeholders for water-stress benchmarks, and [`scripts/fetch_open_meteo.py`](scripts/fetch_open_meteo.py) for **`climate_context`** (network).

**Build locally (Python 3.10+):**

```powershell
python scripts\etl\build_database.py
python scripts\validate_db.py
```

Output: `data\aquamind.sqlite` (ignored by git — regenerate after clone).

**Docs:** [`docs/SQLITE_BACKEND.md`](docs/SQLITE_BACKEND.md) — normalization purpose, cleaning rules, enhancement data. Pitch-oriented summary: [`docs/PITCH_DATA_RESUME.md`](docs/PITCH_DATA_RESUME.md).

---

## Documentation links

- OpenClaw: [https://docs.openclaw.ai/](https://docs.openclaw.ai/)
- OpenClaw WhatsApp: [https://docs.openclaw.ai/channels/whatsapp](https://docs.openclaw.ai/channels/whatsapp)
- OpenRouter + OpenClaw cookbook: [https://openrouter.ai/docs/cookbook/coding-agents/openclaw-integration](https://openrouter.ai/docs/cookbook/coding-agents/openclaw-integration)
- **Full bootstrap & troubleshooting:** [`openclaw/README-WHATSAPP.md`](openclaw/README-WHATSAPP.md)

---

## Repository layout (short)

- `openclaw/` — JSON5 merge patches and workspace templates for the agent.
- `frontend/` — Vite + React WaterSec dashboard (chat, pipeline, model routing, SQLite insights).
- `backend/` — FastAPI analytics service over `data/aquamind.sqlite`.
- `scripts/` — gateway, patches, Daytona runner, Gmail CLI, proofs, **SQLite ETL** (`scripts/etl/`).
- `docs/` — SQLite backend, data inventory, pitch resume, agent data rules, **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** (end-to-end integration for agents).
- `data/` — optional local folder for generated `aquamind.sqlite` (see `.gitignore`).
- `artifacts/` — demo outputs (e.g. charts, HTML) when generated.
- Root CSVs / PDF — WaterSec hackathon and sample consumption data for analytics demos.
