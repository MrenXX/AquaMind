WaterSec — OpenClaw + WhatsApp setup bundle
============================================

This archive contains repo files needed to reproduce the WhatsApp + OpenClaw + MiniMax (OpenRouter)
+ Daytona runner workflow. It does NOT include secrets or machine-local state.

Included
--------
- openclaw/           Patches, workspace templates, README-WHATSAPP.md
- scripts/            Gateway + patch scripts, Daytona runner CLI, optional OpenRouter/Daytona proof script
- .env.example        Template for OPENROUTER_API_KEY, DAYTONA_API_KEY, WHATSAPP_SELF_E164

Excluded on purpose
-------------------
- .env (secrets)
- whatsapp-allowlist.generated.json5 (run patch-whatsapp-allowlist.ps1 to regenerate)
- %USERPROFILE%\.openclaw\ (create via OpenClaw onboard / login)

Quick restore (outline)
-----------------------
1. Unzip preserving folders; place under your WaterSec repo root (or merge paths).
2. Copy .env.example to .env and fill keys.
3. Follow openclaw/README-WHATSAPP.md bootstrap steps.
