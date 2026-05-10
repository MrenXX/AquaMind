"""
Execute Python in a Daytona sandbox and return JSON for OpenClaw / WhatsApp agents.

Reads Python source from stdin (recommended) or --code argument.
Environment: load .env from repo root — DAYTONA_API_KEY required.

Chart workflow: model-generated code should save PNG to /home/daytona/aquamind_chart.png
If present, starts a short-lived HTTP server and returns signed_chart_url (sandbox kept alive).

Usage (OpenClaw exec from gateway host):
  cd D:\\jects\\WaterSec
  .\\.venv\\Scripts\\python.exe scripts\\aquamind_daytona_runner_cli.py < snippet.py

Output: single JSON object on stdout (stderr has logs).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

REMOTE_PNG = "/home/daytona/aquamind_chart.png"
PREVIEW_PORT = 8899


def _daytona_client():
    from daytona import Daytona, DaytonaConfig

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        raise RuntimeError("DAYTONA_API_KEY missing (set in WaterSec .env)")
    cfg_kwargs: dict = {
        "api_key": api_key,
        "api_url": os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
    }
    if os.environ.get("DAYTONA_TARGET"):
        cfg_kwargs["target"] = os.environ["DAYTONA_TARGET"]
    return Daytona(DaytonaConfig(**cfg_kwargs))


def _maybe_chart_url(sandbox) -> tuple[str | None, str | None]:
    """If PNG exists on sandbox, serve it and return signed URL; else (None, None)."""
    from daytona.common.process import SessionExecuteRequest

    try:
        png = sandbox.fs.download_file(REMOTE_PNG)
    except Exception:
        return None, None
    if not png or len(png) < 64:
        return None, None

    # Serve folder so URL path /aquamind_chart.png works
    sandbox.process.exec("mkdir -p /home/daytona/www && cp /home/daytona/aquamind_chart.png /home/daytona/www/aquamind_chart.png 2>/dev/null || cp /home/daytona/aquamind_chart.png /home/daytona/www/chart.png")

    session_id = "chart-http"
    sandbox.process.create_session(session_id)
    req = SessionExecuteRequest(
        command=f"cd /home/daytona/www && python3 -m http.server {PREVIEW_PORT}",
        run_async=True,
    )
    sandbox.process.execute_session_command(session_id, req)
    time.sleep(2)
    signed = sandbox.create_signed_preview_url(PREVIEW_PORT, expires_in_seconds=3600)
    base = signed.url.rstrip("/")
    full_url = f"{base}/aquamind_chart.png"
    # Fallback path if copy used chart.png
    alt_note = f"If 404, try {base}/chart.png"
    return full_url, alt_note


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Python in Daytona; print JSON result.")
    parser.add_argument("--code", default=None, help="Python source (else read stdin)")
    parser.add_argument("--delete-sandbox", action="store_true", help="Always delete sandbox (breaks chart URLs)")
    args = parser.parse_args()

    if args.code is not None:
        code = args.code
    else:
        code = sys.stdin.read()

    code = (code or "").strip()
    if not code:
        print(json.dumps({"ok": False, "error": "no_code", "detail": "Provide stdin or --code"}))
        return 1

    result: dict = {"ok": False}
    try:
        daytona = _daytona_client()
        sandbox = daytona.create()
        sid = sandbox.id
        result["sandbox_id"] = sid

        resp = sandbox.process.code_run(code, timeout=180)
        out = resp.result or ""
        ec = resp.exit_code if resp.exit_code is not None else -1
        result["ok"] = ec == 0
        result["exit_code"] = ec
        result["stdout"] = out

        chart_url = None
        alt = None
        try:
            chart_url, alt = _maybe_chart_url(sandbox)
        except Exception as ex:
            result["chart_error"] = str(ex)

        if chart_url:
            result["signed_chart_url"] = chart_url
            result["chart_open_note"] = "Open this URL in a browser (Daytona preview). " + (alt or "")
            result["sandbox_kept_for_chart_url"] = not args.delete_sandbox
            if not args.delete_sandbox:
                print(json.dumps(result, ensure_ascii=False), flush=True)
                print(
                    f"aquamind_daytona_runner: sandbox {sid} left running for chart URL; "
                    f"delete in Daytona dashboard when done.",
                    file=sys.stderr,
                )
                return 0 if ec == 0 else 1

        try:
            raw = sandbox.fs.download_file(REMOTE_PNG)
            if raw and len(raw) < 350_000:
                result["chart_base64"] = base64.standard_b64encode(raw).decode("ascii")
        except Exception:
            pass

        sandbox.delete()
        result["sandbox_deleted"] = True

    except Exception as e:
        result["ok"] = False
        result["error"] = type(e).__name__
        result["detail"] = str(e)

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
