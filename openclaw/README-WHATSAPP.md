# OpenClaw + WhatsApp (WaterSec / AquaMind)

OpenClaw stores live config in `%USERPROFILE%\.openclaw\openclaw.json`. This repo carries **merge patches only** (no secrets committed).

## One-time bootstrap

1. **OpenClaw base setup** (creates config + workspace):

   ```powershell
   openclaw onboard --non-interactive --accept-risk --mode local --auth-choice skip --skip-channels --skip-daemon --skip-skills --skip-search --skip-ui --skip-health
   ```

2. **WhatsApp plugin on Windows** — `openclaw plugins install @openclaw/whatsapp` can hit npm bugs. Reliable fallback:

   ```powershell
   npm install -g @openclaw/whatsapp@2026.5.7
   npm install @openclaw/whatsapp@2026.5.7 --prefix "$env:USERPROFILE\.openclaw\npm"
   ```

3. **Merge AquaMind defaults** (MiniMax via OpenRouter + `plugins.allow` + agent timeouts):

   ```powershell
   cd <your-repo-root>
   .\scripts\apply-openclaw-aquamind-patch.ps1
   ```

   **If PowerShell refuses the script** (“not digitally signed” / `PSSecurityException`), either run once with bypass:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\apply-openclaw-aquamind-patch.ps1
   ```

   Or allow signed-remote + local scripts for your user (persists; answer `Y` when prompted):

   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

   Use the same bypass or policy for `patch-whatsapp-allowlist.ps1` and `start-watersec-openclaw-gateway.ps1`.

   This sets **`agents.defaults.timeoutSeconds`** (whole agent turn), **`agents.defaults.model.timeoutMs`** (per provider HTTP completion), **`agents.defaults.model.fallbacks`** (free-model chain if MiniMax fails), and **`agents.defaults.params.extra_body.provider.sort: "latency"`** so OpenRouter prefers low-latency endpoints. **`agents.list`** enables **`fastModeDefault`** on `main`. Restart the gateway after patching.

4. **WhatsApp allowlist** (team numbers + your own):

   - Add **`WHATSAPP_SELF_E164=+216…`** to `.env` (your WhatsApp number in **E.164**, no spaces).
   - Run:

   ```powershell
   .\scripts\patch-whatsapp-allowlist.ps1
   ```

   This merges **+21658628797**, **+21693779303**, **+21651377789**, and optional `WHATSAPP_SELF_E164` into `channels.whatsapp.allowFrom` with **`dmPolicy: allowlist`**. It also sets **`groupPolicy: allowlist`**, **`groups["*"].requireMention: true`**, and uses your DM allowlist as the group sender allowlist (OpenClaw falls back from `groupAllowFrom` to **`allowFrom`** when `groupAllowFrom` is omitted).

5. **API keys** — set `OPENROUTER_API_KEY` and `DAYTONA_API_KEY` in `.env`; start the gateway via `scripts\start-watersec-openclaw-gateway.ps1` so keys load without printing the file.

### Group chats (`@clanker`)

- **`aquamind.patch.json5`** adds **`messages.groupChat`**: **`mentionPatterns: ["@clanker\\b"]`** (case-insensitive) and **`historyLimit: 50`**. Only messages containing **`@clanker`** as a wake word match this setup—no extra patterns or phone-number shortcuts in config.
- In groups, people should write **`@clanker …`** with their prompt. OpenClaw still considers **native WhatsApp @** of the linked account as a mention for replies (platform behavior); there is no repo toggle to disable that from here.
- Pending group messages (up to the history limit) can be injected as context when someone pings—see [WhatsApp group messages](https://docs.openclaw.ai/channels/group-messages).

### Changing OpenClaw config safely

1. **Stop** the gateway: **`Ctrl+C`** in its window, or **`openclaw gateway stop`** elsewhere.
2. Apply patches from the repo root:
   - **`.\scripts\apply-openclaw-aquamind-patch.ps1`** (model + timeouts + **`messages.groupChat`** + **`plugins.allow`**),
   - **`.\scripts\patch-whatsapp-allowlist.ps1`** (DM allowlist + WhatsApp **`groups`** map).
3. **`openclaw config validate`** (the scripts run this).
4. Start again: **`.\scripts\start-watersec-openclaw-gateway.ps1`**.

Avoid editing **`openclaw.json`** while the gateway is running if hot reload previously cleared WhatsApp Web credentials; prefer **stop → patch → start**.

## Link WhatsApp (QR — interactive)

```powershell
openclaw channels login --channel whatsapp
```

Scan the QR with the WhatsApp phone that should host the linked session.

## Run the gateway

```powershell
cd D:\jects\WaterSec
.\scripts\start-watersec-openclaw-gateway.ps1
```

Restart after **any** `openclaw config patch`: **`openclaw gateway stop`**, then **`.\scripts\start-watersec-openclaw-gateway.ps1`** (or run patches **before** starting the gateway).

## Troubleshooting

### Trace stops at `attempt-dispatch` / gateway “frozen” for many minutes

Usually the **model request** (OpenRouter → MiniMax free, or whichever primary you set in **`aquamind.patch.json5`**) never completes—slow queue, rate limits, or a stalled HTTP connection. The AquaMind patch caps **`agents.defaults.model.timeoutMs`** (per request) and **`agents.defaults.timeoutSeconds`** (full turn including tools) and sets **`fastModeDefault`** on the `main` agent. **If stalls exceed those limits**, check OpenClaw gateway logs—some builds do not surface timeouts the same on every path. After merging the patch, **restart the gateway**. If replies still fail often, try another model or check **`OPENROUTER_API_KEY`** and OpenRouter status.

### `openclaw gateway stop` says “Gateway service missing”

That applies when no **background service** is registered. If you started the gateway with **`openclaw gateway run`** or **`start-watersec-openclaw-gateway.ps1`**, stop it from that window (**`Ctrl+C`**) or kill the process (below).

### Ctrl+C does not stop the gateway (Windows)

Foreground Node sometimes ignores Ctrl+C. Options:

1. **Close the terminal tab** (ends the process tree for that session).
2. **Task Manager** → **Node.js** → **End task** (may affect other Node apps; prefer closing that terminal).
3. From **another** PowerShell: find the listener on your gateway port (default **18789**) and stop that PID, for example:

   ```powershell
   Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```

## Daytona code execution (WhatsApp agent)

The agent is instructed in **`AGENTS.md`** to run Python via:

- **`scripts/aquamind_daytona_runner_cli.py`** — reads Python from stdin; returns **JSON** (`stdout`, `exit_code`, optional **`signed_chart_url`**).
- Charts must save to **`/home/daytona/aquamind_chart.png`**.

WhatsApp cannot reliably embed PNG bytes from the model; when the runner returns **`signed_chart_url`**, the agent should send that **link** so you open the chart in a browser (Daytona preview, ~1h signed).

If a chart URL was created, the runner may **leave the sandbox running** so the link stays valid — delete orphaned sandboxes in the Daytona dashboard when done.

## Gmail incident reports (WhatsApp agent)

The agent can send real Gmail reports through:

- **`scripts/aquamind_gmail_report_cli.py`** — reads report JSON from stdin; returns one JSON object with send status, Gmail `message_id`, and SQLite `sqlite_report_id`.
- **`requirements-gmail.txt`** — install Gmail dependencies with `pip install -r requirements-gmail.txt`.
- OAuth client secret default: **`%USERPROFILE%\.openclaw\gmail\client_secret.json`**.
- OAuth token default: **`%USERPROFILE%\.openclaw\gmail\token.json`**.
- SQLite send log default: **`%USERPROFILE%\.openclaw\gmail\gmail_reports.sqlite3`**.

Required `.env` values:

```powershell
GMAIL_SENDER=your-sender@gmail.com
GMAIL_TO=ops.manager@example.com
```

Optional `.env` values: `GMAIL_CC`, `GMAIL_CLIENT_SECRET_FILE`, `GMAIL_TOKEN_FILE`, and `GMAIL_DB_PATH`.

First real send may open Google OAuth consent in the browser. After consent, the stored token is reused for later WhatsApp-triggered sends.

## Workspace prompts

Templates: [`openclaw/workspace-templates/`](workspace-templates/). Live copies: `%USERPROFILE%\.openclaw\workspace\` (`AGENTS.md`, `SOUL.md`, `TOOLS.md`).

## References

- OpenClaw WhatsApp: https://docs.openclaw.ai/channels/whatsapp  
- OpenClaw WhatsApp group messages: https://docs.openclaw.ai/channels/group-messages  
- OpenRouter + OpenClaw: https://openrouter.ai/docs/cookbook/coding-agents/openclaw-integration  
