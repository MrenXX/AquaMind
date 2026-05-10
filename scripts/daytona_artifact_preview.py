"""
Minimal AquaMind spike: upload static HTML to a Daytona sandbox, serve it, create a signed preview URL.

Requires: pip install daytona python-dotenv (see project .venv)
Env: DAYTONA_API_KEY (see .env.example). OpenRouter is not used here.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from daytona import Daytona, DaytonaConfig
from daytona.common.process import SessionExecuteRequest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "aquamind_artifact_test.html"
PREVIEW_PORT = 8080
MAX_ATTEMPTS = 3


def load_html() -> bytes:
    return ARTIFACT.read_bytes()


def simpler_fallback_html() -> bytes:
    """Tiny fallback if primary artifact fails validation."""
    return (
        b'<!DOCTYPE html><html><head><meta charset="utf-8"><title>AquaMind Artifact Test</title></head>'
        b"<body><h1>AquaMind Artifact Test</h1>"
        b"<table border=1><tr><th>date</th><th>consumption</th></tr>"
        b"<tr><td>2026-05-01</td><td>1200</td></tr>"
        b"<tr><td>2026-05-02</td><td>1800</td></tr></table></body></html>"
    )


def verify_preview(url: str) -> tuple[bool, str]:
    try:
        r = httpx.get(
            url,
            timeout=60.0,
            follow_redirects=True,
            headers={"X-Daytona-Skip-Preview-Warning": "true"},
        )
        body = r.text
        ok = r.status_code == 200 and "AquaMind Artifact Test" in body and "2026-05-01" in body
        return ok, f"status={r.status_code} len={len(body)}"
    except Exception as e:
        return False, repr(e)


def main() -> int:
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        print("DAYTONA_API_KEY missing. Copy .env.example to .env and set the key.", file=sys.stderr)
        return 2

    if not ARTIFACT.is_file():
        print(f"Missing artifact: {ARTIFACT}", file=sys.stderr)
        return 2

    api_url = os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api")
    target = os.environ.get("DAYTONA_TARGET")
    cfg_kwargs: dict = {"api_key": api_key, "api_url": api_url}
    if target:
        cfg_kwargs["target"] = target
    config = DaytonaConfig(**cfg_kwargs)
    daytona = Daytona(config)

    remote_dir = "/home/daytona/aquamind-artifact"
    remote_file = f"{remote_dir}/index.html"

    last_logs: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        html_bytes = load_html() if attempt == 1 else simpler_fallback_html()
        sandbox = daytona.create()
        sid = sandbox.id
        print(f"attempt {attempt}/{MAX_ATTEMPTS} sandbox={sid}")

        try:
            sandbox.process.exec(f"mkdir -p {remote_dir}")
            sandbox.fs.upload_file(html_bytes, remote_file)

            session_id = "http-srv"
            sandbox.process.create_session(session_id)
            req = SessionExecuteRequest(
                command=f"cd {remote_dir} && python3 -m http.server {PREVIEW_PORT}",
                run_async=True,
            )
            sandbox.process.execute_session_command(session_id, req)
            time.sleep(3)

            signed = sandbox.create_signed_preview_url(PREVIEW_PORT, expires_in_seconds=3600)
            url = signed.url
            print(f"signed_preview_url={url}")

            ok, info = verify_preview(url)
            last_logs.append(f"verify: ok={ok} {info}")
            print(last_logs[-1])

            if ok:
                print("SUCCESS")
                return 0

            logs = sandbox.process.exec(f"ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true")
            last_logs.append(f"ports: {logs.result[:500]}")
            print(last_logs[-1])
        except Exception as e:
            last_logs.append(repr(e))
            print(f"error: {e}")
        finally:
            try:
                sandbox.delete()
            except Exception:
                pass

        print("retry with fallback HTML..." if attempt < MAX_ATTEMPTS else "giving up.")

    print("FAILED after retries:", file=sys.stderr)
    for line in last_logs:
        print(line, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
