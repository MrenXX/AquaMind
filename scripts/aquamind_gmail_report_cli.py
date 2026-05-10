"""
Send AquaMind incident reports through Gmail API and return JSON for OpenClaw.

Reads a JSON report from stdin (recommended) or --json.
Environment: loads .env from repo root. Required for real sends:
  GMAIL_SENDER, GMAIL_TO, GMAIL_CLIENT_SECRET_FILE

OAuth files default outside the repo:
  %USERPROFILE%\\.openclaw\\gmail\\client_secret.json
  %USERPROFILE%\\.openclaw\\gmail\\token.json

Usage (OpenClaw exec from gateway host):
  Get-Content .\\gmail_report.json -Raw | python scripts\\aquamind_gmail_report_cli.py

Output: single JSON object on stdout.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback keeps config usable before deps install.
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
GMAIL_DIR = Path.home() / ".openclaw" / "gmail"
DEFAULT_CLIENT_SECRET = GMAIL_DIR / "client_secret.json"
DEFAULT_TOKEN = GMAIL_DIR / "token.json"
DEFAULT_DB = GMAIL_DIR / "gmail_reports.sqlite3"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class ConfigError(RuntimeError):
    pass


def _load_env() -> None:
    env_path = ROOT / ".env"
    if load_dotenv:
        load_dotenv(env_path)
        return

    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _split_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(os.path.expandvars(value)).expanduser() if value else default


def _read_report(args: argparse.Namespace) -> dict[str, Any]:
    raw = args.json if args.json is not None else sys.stdin.read()
    raw = (raw or "").strip()
    if not raw:
        raise ConfigError("Provide a JSON report on stdin or with --json.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON report: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ConfigError("JSON report must be an object.")
    return data


def _string_field(data: dict[str, Any], name: str, *, required: bool = True) -> str:
    value = data.get(name)
    if value is None:
        if required:
            raise ConfigError(f"Missing required field: {name}")
        return ""
    if not isinstance(value, str):
        raise ConfigError(f"Field {name} must be a string.")
    value = value.strip()
    if required and not value:
        raise ConfigError(f"Field {name} cannot be empty.")
    return value


def _list_field(data: dict[str, Any], name: str) -> list[Any]:
    value = data.get(name, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"Field {name} must be a list.")
    return value


def _resolve_recipients(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    to_value = data.get("to")
    cc_value = data.get("cc")

    if isinstance(to_value, list):
        to_addresses = [str(item).strip() for item in to_value if str(item).strip()]
    elif isinstance(to_value, str):
        to_addresses = _split_addresses(to_value)
    elif to_value is None:
        to_addresses = _split_addresses(os.environ.get("GMAIL_TO"))
    else:
        raise ConfigError("Field to must be a string or list of strings.")

    if isinstance(cc_value, list):
        cc_addresses = [str(item).strip() for item in cc_value if str(item).strip()]
    elif isinstance(cc_value, str):
        cc_addresses = _split_addresses(cc_value)
    elif cc_value is None:
        cc_addresses = _split_addresses(os.environ.get("GMAIL_CC"))
    else:
        raise ConfigError("Field cc must be a string or list of strings.")

    if not to_addresses:
        raise ConfigError("No Gmail recipients configured. Set GMAIL_TO or include to in the report JSON.")
    return to_addresses, cc_addresses


def _format_evidence_rows(rows: list[Any]) -> str:
    if not rows:
        return "- No structured evidence rows were provided."

    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            parts = [f"{key}: {value}" for key, value in row.items()]
            lines.append(f"{index}. " + "; ".join(parts))
        else:
            lines.append(f"{index}. {row}")
    return "\n".join(lines)


def _build_body(data: dict[str, Any]) -> str:
    report_type = _string_field(data, "report_type", required=False) or "incident"
    incident_id = _string_field(data, "incident_id")
    summary = _string_field(data, "summary")
    recommended_action = _string_field(data, "recommended_action")
    caveats = _string_field(data, "caveats", required=False) or "None stated."
    evidence_rows = _list_field(data, "evidence_rows")

    return "\n\n".join(
        [
            "AquaMind WaterSec Report",
            f"Report type: {report_type}",
            f"Incident ID: {incident_id}",
            "Executive summary:\n" + summary,
            "Evidence:\n" + _format_evidence_rows(evidence_rows),
            "Recommended inspection/action:\n" + recommended_action,
            "Caveats:\n" + caveats,
            "Generated by AquaMind via OpenClaw.",
        ]
    )


def _build_message(data: dict[str, Any], sender: str, to_addresses: list[str], cc_addresses: list[str]) -> EmailMessage:
    subject = _string_field(data, "subject")
    body = _build_body(data)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to_addresses)
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Subject"] = subject
    message.set_content(body)
    return message


def _connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gmail_reports (
          report_id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          recipient TEXT NOT NULL,
          subject TEXT NOT NULL,
          incident_id TEXT NOT NULL,
          status TEXT NOT NULL,
          message_id TEXT,
          error TEXT
        )
        """
    )
    return conn


def _log_report(
    db_path: Path,
    *,
    recipient: str,
    subject: str,
    incident_id: str,
    status: str,
    message_id: str | None = None,
    error: str | None = None,
) -> int:
    with _connect_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO gmail_reports
              (timestamp, recipient, subject, incident_id, status, message_id, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                recipient,
                subject,
                incident_id,
                status,
                message_id,
                error,
            ),
        )
        return int(cursor.lastrowid)


def _gmail_service(client_secret: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ConfigError(
            "Missing Gmail dependencies. Install with: pip install -r requirements-gmail.txt"
        ) from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret.exists():
                raise ConfigError(f"Missing Gmail OAuth client secret file: {client_secret}")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def _send_message(service: Any, message: EmailMessage) -> str:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    message_id = response.get("id")
    if not message_id:
        raise RuntimeError("Gmail API response did not include a message id.")
    return str(message_id)


def _safe_error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": type(exc).__name__,
        "detail": str(exc),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a WaterSec Gmail report and print JSON.")
    parser.add_argument("--json", default=None, help="Report JSON object (else read stdin).")
    parser.add_argument("--dry-run", action="store_true", help="Validate and render without Gmail send or SQLite log.")
    args = parser.parse_args()

    _load_env()
    result: dict[str, Any] = {"ok": False}

    try:
        data = _read_report(args)
        sender = (data.get("sender") or os.environ.get("GMAIL_SENDER") or "").strip()
        if not sender:
            raise ConfigError("Missing GMAIL_SENDER or sender in report JSON.")

        to_addresses, cc_addresses = _resolve_recipients(data)
        message = _build_message(data, sender, to_addresses, cc_addresses)
        subject = _string_field(data, "subject")
        incident_id = _string_field(data, "incident_id")
        db_path = _env_path("GMAIL_DB_PATH", DEFAULT_DB)

        if args.dry_run:
            result.update(
                {
                    "ok": True,
                    "status": "dry_run",
                    "recipient": ", ".join(to_addresses),
                    "cc": ", ".join(cc_addresses),
                    "subject": subject,
                    "incident_id": incident_id,
                    "body_preview": message.get_content(),
                }
            )
        else:
            client_secret = _env_path("GMAIL_CLIENT_SECRET_FILE", DEFAULT_CLIENT_SECRET)
            token_path = _env_path("GMAIL_TOKEN_FILE", DEFAULT_TOKEN)
            service = _gmail_service(client_secret, token_path)
            message_id = _send_message(service, message)
            sqlite_report_id = _log_report(
                db_path,
                recipient=", ".join(to_addresses),
                subject=subject,
                incident_id=incident_id,
                status="sent",
                message_id=message_id,
            )
            result.update(
                {
                    "ok": True,
                    "status": "sent",
                    "message_id": message_id,
                    "recipient": ", ".join(to_addresses),
                    "cc": ", ".join(cc_addresses),
                    "subject": subject,
                    "incident_id": incident_id,
                    "sqlite_report_id": sqlite_report_id,
                }
            )
    except Exception as exc:
        result.update(_safe_error(exc))
        try:
            data_for_log = locals().get("data")
            if isinstance(data_for_log, dict) and not args.dry_run:
                db_path = _env_path("GMAIL_DB_PATH", DEFAULT_DB)
                _log_report(
                    db_path,
                    recipient=", ".join(locals().get("to_addresses", [])) or "unknown",
                    subject=str(data_for_log.get("subject") or "unknown"),
                    incident_id=str(data_for_log.get("incident_id") or "unknown"),
                    status="failed",
                    error=result["detail"],
                )
        except Exception:
            pass

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
