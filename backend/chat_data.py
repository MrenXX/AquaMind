"""SQLite-first chat turn: OpenRouter plans a tool call; server executes on real WaterSec DB."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any

import httpx
from backend import analytics, models
from backend.config import db_path
from backend.sql_guard import validate_readonly_sql

MODEL = os.environ.get("AQUAMIND_OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _planner_system() -> str:
    return """You are the AquaMind WaterSec telemetry planner. The user question must be answered ONLY from the real SQLite warehouse (no invented numbers).

Reply with a single JSON object and nothing else (no markdown fences). Shape:
{"route":"<route>","...fields for that route..."}

Routes and fields:

1) "query_metrics" — aggregates from trusted_events or consumption_events.
   Fields: use_trusted (boolean, default true), customer_profile (optional string: customerA|customerB|customerC|gym),
   device_ids (optional string[]), date_from, date_to (optional YYYY-MM-DD), group_by: none|device|day|profile|sub_category, limit (1-500, default 50).

2) "compare_sources" — two slices side by side.
   Fields: use_trusted (boolean), slice_a and slice_b each { "label": string, "customer_profile"?, "device_ids"?, "date_from"?, "date_to"? }.

3) "find_motifs" — motif_patterns table.
   Fields: limit (1-100, default 20).

4) "detect_anomalies" — anomaly_candidates.
   Fields: customer_profile?, device_id?, anomaly_type?, min_severity?, limit (1-200, default 30).

5) "run_sql" — read-only SELECT or WITH only.
   Fields: sql (string), max_rows (1-500, default 200).

6) "daytona" — only if the user explicitly needs arbitrary Python charts/code that cannot be expressed as the routes above (e.g. custom matplotlib not covered by SQL).
   Fields: reason (short string).

Prefer routes 1–5. Use customer_profile "gym" for gym data, "customerC" for residential motifs, etc.
If the user is vague, pick reasonable defaults: use_trusted true, group_by device, limit 20."""


def planner_messages(user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _planner_system()},
        {"role": "user", "content": user_prompt},
    ]


def openrouter_chat(api_key: str, messages: list[dict[str, str]]) -> str:
    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "AquaMind WaterSec SQLite planner",
        },
        json={"model": MODEL, "messages": messages},
        timeout=120.0,
    )
    response.raise_for_status()
    payload = response.json()
    message = payload["choices"][0]["message"]
    return (message.get("content") or "").strip()


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def parse_plan_json(text: str) -> dict[str, Any] | None:
    text = _strip_code_fence(text).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def execute_plan(conn: sqlite3.Connection, plan: dict[str, Any]) -> models.ToolResponse:
    route = plan.get("route")
    if not isinstance(route, str):
        raise ValueError("missing route")

    body = {k: v for k, v in plan.items() if k != "route"}

    if route == "query_metrics":
        return analytics.query_metrics(conn, models.QueryMetricsBody.model_validate(body))
    if route == "compare_sources":
        return analytics.compare_sources(conn, models.CompareSourcesBody.model_validate(body))
    if route == "find_motifs":
        return analytics.find_motifs(conn, models.FindMotifsBody.model_validate(body))
    if route == "detect_anomalies":
        return analytics.detect_anomalies(conn, models.DetectAnomaliesBody.model_validate(body))
    if route == "run_sql":
        sql = body.get("sql", "")
        max_rows = int(body.get("max_rows", 200))
        ok, reason = validate_readonly_sql(str(sql))
        if not ok:
            raise ValueError(reason)
        return analytics.run_sql_readonly(conn, str(sql).strip().rstrip(";"), max_rows)
    if route == "daytona":
        raise ValueError("daytona route — caller should fall back")

    raise ValueError(f"unknown route: {route}")


def sqlite_first_enabled() -> bool:
    raw = os.environ.get("AQUAMIND_CHAT_SQLITE_FIRST", "true").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    return db_path().is_file()
