from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Iterator

import httpx

from backend import analytics
from backend.chat_data import (
    execute_plan,
    openrouter_chat as openrouter_chat_planner,
    parse_plan_json,
    planner_messages,
    sqlite_first_enabled,
)
from backend.config import db_path
from backend.db import get_connection
from backend.env_load import load_repo_env
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


MODEL = os.environ.get("AQUAMIND_OPENROUTER_MODEL", "minimax/minimax-m2.5:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REMOTE_PNG = "/home/daytona/aquamind_chart.png"
MAX_REPAIRS = 3

router = APIRouter()


class RunBody(BaseModel):
    prompt: str = Field(min_length=1)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def _openrouter_chat(api_key: str, messages: list[dict[str, str]]) -> str:
    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "AquaMind WaterSec Dashboard",
        },
        json={"model": MODEL, "messages": messages},
        timeout=120.0,
    )
    response.raise_for_status()
    payload = response.json()
    message = payload["choices"][0]["message"]
    return (message.get("content") or "").strip()


def _system_prompt() -> str:
    return (
        "You generate Python 3 code for the AquaMind WaterSec dashboard. "
        "Return ONLY executable Python source code, with no markdown fences and no commentary. "
        "Print useful progress or results to stdout. "
        f"If the user asks for a chart or visual artifact, save a PNG to {REMOTE_PNG}. "
        "Do not require stdin, local private files, network access, or credentials."
    )


def _messages_for_prompt(prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": prompt},
    ]


def _messages_for_repair(prompt: str, code: str, error: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _system_prompt()},
        {
            "role": "user",
            "content": (
                "Repair this Python code for the same user request. "
                "Return ONLY the corrected Python source code.\n\n"
                f"User request:\n{prompt}\n\n"
                f"Failed code:\n{code}\n\n"
                f"Sandbox output/error:\n{error}"
            ),
        },
    ]


def _daytona_client():
    from daytona import Daytona, DaytonaConfig

    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        raise RuntimeError("DAYTONA_API_KEY missing")
    kwargs: dict[str, str] = {
        "api_key": api_key,
        "api_url": os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
    }
    if os.environ.get("DAYTONA_TARGET"):
        kwargs["target"] = os.environ["DAYTONA_TARGET"]
    return Daytona(DaytonaConfig(**kwargs))


def _chart_artifacts(resp) -> list[dict[str, str]]:
    artifacts = getattr(resp, "artifacts", None)
    charts = getattr(artifacts, "charts", None) if artifacts else None
    if not charts:
        return []
    out: list[dict[str, str]] = []
    for chart in charts:
        chart_type = getattr(chart, "type", None) or getattr(chart, "chart_type", None) or "chart"
        title = getattr(chart, "title", None) or "Untitled chart"
        out.append({"type": str(chart_type), "title": str(title)})
    return out


def _run_daytona(code: str) -> dict:
    daytona = _daytona_client()
    sandbox = daytona.create()
    try:
        resp = sandbox.process.code_run(code, timeout=180)
        exit_code = resp.exit_code if resp.exit_code is not None else -1
        png_base64 = None
        try:
            png = sandbox.fs.download_file(REMOTE_PNG)
            if png:
                png_base64 = base64.standard_b64encode(png).decode("ascii")
        except Exception:
            png_base64 = None
        return {
            "sandbox_id": sandbox.id,
            "exit_code": exit_code,
            "stdout": resp.result or "",
            "chart_artifacts": _chart_artifacts(resp),
            "png_base64": png_base64,
        }
    finally:
        sandbox.delete()


def _stream_run(prompt: str) -> Iterator[str]:
    load_repo_env()

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not openrouter_key:
        yield _sse(
            "status",
            {
                "step": "model",
                "message": "Server misconfiguration: set OPENROUTER_API_KEY in repo `.env` or `env` file, then restart the backend.",
            },
        )
        yield _sse("done", {"success": False, "attempts": 0})
        return

    if sqlite_first_enabled():
        yield _sse(
            "status",
            {"step": "sqlite", "message": "Planning query against WaterSec SQLite (real telemetry)..."},
        )
        try:
            plan_raw = openrouter_chat_planner(openrouter_key, planner_messages(prompt))
            yield _sse("model_output", {"raw": plan_raw})
            plan = parse_plan_json(plan_raw)
            if plan and plan.get("route") == "daytona":
                raise RuntimeError("planner chose daytona")
            if not plan or "route" not in plan:
                raise RuntimeError("planner did not return valid JSON with route")

            yield _sse("code", {"source": json.dumps(plan, indent=2, ensure_ascii=False)})
            yield _sse(
                "status",
                {"step": "sandbox", "message": "Running on WaterSec SQLite (server, trusted analytics)..."},
            )

            with get_connection() as conn:
                tool_resp = execute_plan(conn, plan)
            analytics.record_tool_trace(f"chat_sqlite:{plan['route']}", plan, tool_resp)

            out_text = json.dumps(tool_resp.model_dump(), indent=2, ensure_ascii=False)
            yield _sse(
                "sandbox_result",
                {
                    "sandbox_id": "sqlite:local",
                    "exit_code": 0,
                    "stdout": out_text,
                    "chart_artifacts": [],
                    "png_base64": None,
                },
            )
            yield _sse("done", {"success": True, "attempts": 1})
            return
        except Exception as exc:  # noqa: BLE001
            if not db_path().is_file():
                yield _sse(
                    "status",
                    {
                        "step": "sqlite",
                        "message": f"SQLite path skipped (no database at {db_path()}). Build with: python scripts\\etl\\build_database.py",
                    },
                )
            else:
                yield _sse(
                    "status",
                    {
                        "step": "sqlite",
                        "message": f"SQLite planner/execute failed ({type(exc).__name__}: {exc}). Falling back to Daytona code generation.",
                    },
                )

    messages = _messages_for_prompt(prompt)
    last_code = ""
    last_error = ""

    for attempt in range(1, MAX_REPAIRS + 1):
        yield _sse("status", {"step": "model", "message": "Prompting MiniMax via OpenRouter..."})

        raw = _openrouter_chat(openrouter_key, messages)
        yield _sse("model_output", {"raw": raw})

        last_code = _strip_code_fence(raw)
        yield _sse("code", {"source": last_code})

        yield _sse("status", {"step": "sandbox", "message": "Running in Daytona sandbox..."})

        try:
            result = _run_daytona(last_code)
        except Exception as exc:  # noqa: BLE001
            result = {
                "sandbox_id": "",
                "exit_code": 1,
                "stdout": f"{type(exc).__name__}: {exc}",
                "chart_artifacts": [],
                "png_base64": None,
            }

        yield _sse("sandbox_result", result)

        if result["exit_code"] == 0:
            yield _sse("done", {"success": True, "attempts": attempt})
            return

        last_error = result.get("stdout") or f"exit_code={result['exit_code']}"
        if attempt < MAX_REPAIRS:
            yield _sse("repair", {"attempt": attempt, "max": MAX_REPAIRS, "error": last_error})
            messages = _messages_for_repair(prompt, last_code, last_error)

    yield _sse("done", {"success": False, "attempts": MAX_REPAIRS})


@router.post("/run")
def run(body: RunBody) -> StreamingResponse:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")
    return StreamingResponse(_stream_run(prompt), media_type="text/event-stream")
