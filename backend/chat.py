from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Iterator

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import repo_root
from backend.intent import routing_tier
from backend.openrouter_client import (
    codegen_chain_for_tier,
    openrouter_completion,
    openrouter_completion_chain,
)
from backend.router_gate import Tier, tier_to_primary_slug

REMOTE_PNG = "/home/daytona/aquamind_chart.png"
# Models sometimes pick a different path; try these after a successful run.
_FALLBACK_PNG_PATHS = (
    "/home/daytona/aquamind_chart.png",
    "/home/daytona/aquamind_proof.png",
    "/home/daytona/chart.png",
)
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


def _conversational_system() -> str:
    return (
        "You are AquaMind, the WaterSec operations copilot. Reply in clear, friendly plain text. "
        "Do not output Python, SQL, or JSON unless the user explicitly asks for it. "
        "Do not invent telemetry numbers; suggest they ask a concrete data question if they need metrics."
    )


def _messages_for_conversational(prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _conversational_system()},
        {"role": "user", "content": prompt},
    ]


def _stream_conversational_fast(openrouter_key: str, prompt: str) -> Iterator[str]:
    """Tier fast: plain text only, no Daytona."""
    tier: Tier = "fast"
    slug_preview = tier_to_primary_slug(tier)
    yield _sse(
        "status",
        {
            "step": "routing",
            "tier": tier,
            "intent": "conversational",
            "tier_primary_model": slug_preview,
            "message": "Heuristic routing: conversational (plain text, no sandbox).",
        },
    )
    yield _sse("status", {"step": "model", "message": "Generating reply…", "tier": tier})
    try:
        raw, used_slug = openrouter_completion(
            openrouter_key,
            _messages_for_conversational(prompt),
            role="chat",
            x_title="AquaMind WaterSec Chat",
        )
    except (RuntimeError, httpx.HTTPStatusError) as exc:
        yield _sse("status", {"step": "model", "message": str(exc), "error": True, "tier": tier})
        yield _sse("done", {"success": False, "attempts": 0, "error": type(exc).__name__, "tier": tier})
        return
    yield _sse(
        "status",
        {
            "step": "model",
            "message": f"Reply ready ({used_slug}).",
            "openrouter_model": used_slug,
            "tier": tier,
        },
    )
    yield _sse("model_output", {"raw": raw, "openrouter_model": used_slug, "tier": tier})
    yield _sse(
        "code",
        {"source": "# heuristic: conversational — no Python executed.\n"},
    )
    yield _sse("status", {"step": "sandbox", "message": "Skipped sandbox (conversational).", "tier": tier})
    yield _sse(
        "sandbox_result",
        {
            "sandbox_id": "intent:conversational",
            "exit_code": 0,
            "stdout": json.dumps({"intent": "conversational", "tier": tier}, ensure_ascii=False),
            "chart_artifacts": [],
            "png_base64": None,
        },
    )
    yield _sse(
        "done",
        {"success": True, "attempts": 1, "openrouter_model": used_slug, "tier": tier, "intent": "conversational"},
    )


def _openrouter_chat_code(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    tier: Tier,
) -> tuple[str, str]:
    """Codegen: tier primary (LFM / Qwen / MiniMax via env), then standard code-role fallbacks."""
    chain = codegen_chain_for_tier(tier)
    return openrouter_completion_chain(
        api_key,
        messages,
        model_chain=chain,
        x_title="AquaMind WaterSec Dashboard",
    )


def _system_prompt() -> str:
    return (
        "You generate Python 3 code for the AquaMind WaterSec dashboard. "
        "Return ONLY executable Python source code, with no markdown fences and no commentary. "
        "Do not write any preamble, explanation, or 'Here is the code' — the first character must start the program. "
        "Print useful progress or results to stdout. "
        "If the user asks for any chart, plot, or image: use matplotlib, call "
        f"plt.savefig('{REMOTE_PNG}', dpi=120, bbox_inches='tight') before plt.close(), "
        "and ensure that exact path string appears in the code. "
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


def _chart_artifacts(resp) -> list[dict]:
    artifacts = getattr(resp, "artifacts", None)
    charts = getattr(artifacts, "charts", None) if artifacts else None
    if not charts:
        return []
    out: list[dict] = []
    for chart in charts:
        chart_type = getattr(chart, "type", None) or getattr(chart, "chart_type", None) or "chart"
        title = getattr(chart, "title", None) or "Untitled chart"
        row: dict = {"type": str(chart_type), "title": str(title)}
        for attr in (
            "labels",
            "values",
            "data",
            "series",
            "x",
            "y",
            "categories",
        ):
            v = getattr(chart, attr, None)
            if v is None:
                continue
            if hasattr(v, "tolist"):
                try:
                    v = v.tolist()
                except Exception:
                    continue
            if isinstance(v, (list, tuple)):
                row[attr] = list(v)
        out.append(row)
    return out


def _first_png_bytes(sandbox) -> bytes | None:
    for path in _FALLBACK_PNG_PATHS:
        try:
            png = sandbox.fs.download_file(path)
            if png and len(png) > 200:
                return png
        except Exception:
            continue
    return None


def _run_daytona(code: str) -> dict:
    daytona = _daytona_client()
    sandbox = daytona.create()
    try:
        resp = sandbox.process.code_run(code, timeout=180)
        exit_code = resp.exit_code if resp.exit_code is not None else -1
        png_raw = _first_png_bytes(sandbox)
        png_base64 = (
            base64.standard_b64encode(png_raw).decode("ascii") if png_raw else None
        )
        return {
            "sandbox_id": sandbox.id,
            "exit_code": exit_code,
            "stdout": resp.result or "",
            "chart_artifacts": _chart_artifacts(resp),
            "png_base64": png_base64,
        }
    finally:
        sandbox.delete()


def _model_output_for_daytona_codegen(
    raw: str,
    *,
    openrouter_model: str,
    tier: Tier,
    attempt: int,
) -> dict:
    """Chat must not show raw Python; full draft lives in ``model_generation_full`` for Expert UI."""
    body = _strip_code_fence(raw)
    n = len(body)
    summary = (
        f"Python for this run is ready ({n} characters). "
        "Open the **Script** card to view or copy code; **Run output** shows stdout, tables, and exports."
    )
    return {
        "raw": summary,
        "model_generation_full": raw,
        "surface": "run_panels",
        "openrouter_model": openrouter_model,
        "tier": tier,
        "attempt": attempt,
        "code_char_count": n,
    }


def _stream_run(prompt: str) -> Iterator[str]:
    load_dotenv(repo_root() / ".env")

    openrouter_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not openrouter_key:
        yield _sse(
            "status",
            {
                "step": "model",
                "message": "Server misconfiguration: set OPENROUTER_API_KEY in WaterSec-OpenClaw-.env",
            },
        )
        yield _sse("done", {"success": False, "attempts": 0})
        return

    tier: Tier = routing_tier(prompt)
    if tier == "fast":
        yield from _stream_conversational_fast(openrouter_key, prompt)
        return

    tier_slug = tier_to_primary_slug(tier)
    codegen_preview = codegen_chain_for_tier(tier)
    yield _sse(
        "status",
        {
            "step": "routing",
            "tier": tier,
            "intent": "data",
            "tier_primary_model": tier_slug,
            "codegen_chain": codegen_preview[:6],
            "message": (
                f"Heuristic routing: tier={tier}, primary={tier_slug} "
                f"(regex + length → model chain + Daytona)."
            ),
        },
    )

    messages = _messages_for_prompt(prompt)
    last_code = ""
    last_error = ""

    for attempt in range(1, MAX_REPAIRS + 1):
        yield _sse(
            "status",
            {
                "step": "model",
                "message": f"Codegen (tier={tier}); model chain …",
                "tier": tier,
            },
        )

        try:
            raw, used_slug = _openrouter_chat_code(openrouter_key, messages, tier=tier)
        except (RuntimeError, httpx.HTTPStatusError) as exc:
            yield _sse(
                "status",
                {"step": "model", "message": str(exc), "error": True},
            )
            yield _sse(
                "done",
                {"success": False, "attempts": attempt, "error": type(exc).__name__, "tier": tier},
            )
            return
        yield _sse(
            "status",
            {
                "step": "model",
                "message": f"Generation complete ({used_slug}).",
                "openrouter_model": used_slug,
                "tier": tier,
            },
        )
        yield _sse(
            "model_output",
            _model_output_for_daytona_codegen(raw, openrouter_model=used_slug, tier=tier, attempt=attempt),
        )

        last_code = _strip_code_fence(raw)
        yield _sse(
            "code",
            {"source": last_code, "surface": "run_panels", "for_chat": False},
        )

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
            yield _sse(
                "done",
                {"success": True, "attempts": attempt, "openrouter_model": used_slug, "tier": tier},
            )
            return

        last_error = result.get("stdout") or f"exit_code={result['exit_code']}"
        if attempt < MAX_REPAIRS:
            yield _sse("repair", {"attempt": attempt, "max": MAX_REPAIRS, "error": last_error})
            messages = _messages_for_repair(prompt, last_code, last_error)

    yield _sse("done", {"success": False, "attempts": MAX_REPAIRS, "tier": tier})


@router.post("/run")
def run(body: RunBody) -> StreamingResponse:
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")
    return StreamingResponse(_stream_run(prompt), media_type="text/event-stream")
