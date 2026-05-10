"""OpenRouter completions with role-based models and fallback chains."""

from __future__ import annotations

import os
import time
from typing import Literal, Sequence

import httpx

from backend.router_gate import Tier, tier_to_primary_slug

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter page slugs (free tier defaults)
DEFAULT_MODEL_CHAT = "liquid/lfm-2.5-1.2b-instruct:free"
DEFAULT_MODEL_PLANNER = "qwen/qwen3-next-80b-a3b-instruct:free"
DEFAULT_MODEL_CODE = "minimax/minimax-m2.5:free"

_MAX_RETRIES = max(1, int(os.environ.get("AQUAMIND_OPENROUTER_MAX_RETRIES", "5")))
_RETRY_BASE_SEC = float(os.environ.get("AQUAMIND_OPENROUTER_RETRY_BASE_SEC", "2.5"))

Role = Literal["chat", "planner", "code"]


def _legacy_fallback() -> str:
    """Single-model override used when per-role vars are unset."""
    return (os.environ.get("AQUAMIND_OPENROUTER_MODEL") or "").strip()


def _model_for_role(role: Role) -> tuple[str, str]:
    """(primary_slug, fallback_slug). Fallback used when primary is down / rate limited."""
    leg = _legacy_fallback()

    if role == "chat":
        pri = (
            (os.environ.get("AQUAMIND_MODEL_CHAT") or "").strip()
            or leg
            or DEFAULT_MODEL_CHAT
        )
        fb = (os.environ.get("AQUAMIND_MODEL_CHAT_FALLBACK") or "").strip() or DEFAULT_MODEL_CODE
    elif role == "planner":
        pri = (
            (os.environ.get("AQUAMIND_MODEL_PLANNER") or "").strip()
            or leg
            or DEFAULT_MODEL_PLANNER
        )
        fb = (os.environ.get("AQUAMIND_MODEL_PLANNER_FALLBACK") or "").strip() or DEFAULT_MODEL_CODE
    else:
        pri = (
            (os.environ.get("AQUAMIND_MODEL_CODE") or "").strip()
            or leg
            or DEFAULT_MODEL_CODE
        )
        fb = (os.environ.get("AQUAMIND_MODEL_CODE_FALLBACK") or "").strip() or DEFAULT_MODEL_PLANNER

    if fb == pri and pri == DEFAULT_MODEL_CODE:
        fb = DEFAULT_MODEL_PLANNER
    elif fb == pri and pri == DEFAULT_MODEL_PLANNER:
        fb = DEFAULT_MODEL_CODE
    elif fb == pri:
        fb = DEFAULT_MODEL_CODE if pri != DEFAULT_MODEL_CODE else DEFAULT_MODEL_PLANNER

    return pri, fb


def _ordered_models(role: Role) -> list[str]:
    pri, fb = _model_for_role(role)
    chain = [pri]
    if fb and fb not in chain:
        chain.append(fb)
    return chain


def _retry_delay_sec(response: httpx.Response | None, attempt_index: int) -> float:
    if response is not None:
        ra = response.headers.get("Retry-After")
        if ra:
            try:
                return min(float(ra), 90.0)
            except ValueError:
                pass
    return min(_RETRY_BASE_SEC * (2**attempt_index), 45.0)


def _single_model_completion(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    x_title: str,
) -> str:
    """One model: retry 429 / 503 only; raise on exhaustion."""
    last: httpx.Response | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            last = httpx.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": x_title,
                },
                json={"model": model, "messages": messages},
                timeout=120.0,
            )
        except httpx.RequestError:
            raise
        if last.is_success:
            payload = last.json()
            message = payload["choices"][0]["message"]
            return (message.get("content") or "").strip()
        if last.status_code in (429, 503) and attempt + 1 < _MAX_RETRIES:
            time.sleep(_retry_delay_sec(last, attempt))
            continue
        last.raise_for_status()

    if last is not None:
        last.raise_for_status()
    raise RuntimeError("OpenRouter request did not complete")


def openrouter_completion_chain(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    model_chain: Sequence[str],
    x_title: str = "AquaMind",
) -> tuple[str, str]:
    """Try models in order; same backoff/fallback semantics as ``openrouter_completion``."""
    slugs = [str(s).strip() for s in model_chain if s and str(s).strip()]
    if not slugs:
        raise ValueError("openrouter_completion_chain: empty model_chain")
    errors: list[str] = []
    for slug in slugs:
        for net_try in range(2):
            try:
                text = _single_model_completion(api_key, slug, messages, x_title=x_title)
                return text, slug
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if code == 401:
                    raise
                try:
                    snippet = (exc.response.text or "")[:300] if exc.response else ""
                except Exception:
                    snippet = ""
                errors.append(f"{slug} HTTP {code}: {snippet or str(exc)}")
                break
            except httpx.RequestError as exc:
                errors.append(f"{slug} ({net_try}): {type(exc).__name__}: {exc}")
                if net_try == 0:
                    time.sleep(min(_retry_delay_sec(None, 0), 8.0))
                    continue
                break

    detail = "; ".join(errors[-8:]) if errors else "Unknown error"
    raise RuntimeError(f"OpenRouter: all models in chain failed: {detail}") from None


def codegen_chain_for_tier(tier: Tier) -> list[str]:
    """Tier primary plus code-role reliability fallbacks (deduped)."""
    primary = tier_to_primary_slug(tier)
    chain = [primary]
    for m in _ordered_models("code"):
        if m not in chain:
            chain.append(m)
    return chain


def planner_chain_for_tier(tier: Tier) -> list[str]:
    """Tier primary plus planner-role fallbacks (deduped)."""
    primary = tier_to_primary_slug(tier)
    chain = [primary]
    for m in _ordered_models("planner"):
        if m not in chain:
            chain.append(m)
    return chain


def openrouter_completion(
    api_key: str,
    messages: list[dict[str, str]],
    *,
    role: Role,
    x_title: str = "AquaMind",
) -> tuple[str, str]:
    """Call OpenRouter; try primary then fallback on transient/provider errors.

    Returns (assistant_text, model_slug_that_succeeded).

    Qwen (planner) can be flaky: the second model in the chain (default MiniMax)
    is used when the first returns 5xx, is rate-limited after retries, or raises
    HTTP transport errors.
    """
    errors: list[str] = []
    for slug in _ordered_models(role):
        for net_try in range(2):
            try:
                text = _single_model_completion(api_key, slug, messages, x_title=x_title)
                return text, slug
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code if exc.response is not None else 0
                if code == 401:
                    raise
                try:
                    snippet = (exc.response.text or "")[:300] if exc.response else ""
                except Exception:
                    snippet = ""
                errors.append(f"{slug} HTTP {code}: {snippet or str(exc)}")
                break  # next model in chain
            except httpx.RequestError as exc:
                errors.append(f"{slug} ({net_try}): {type(exc).__name__}: {exc}")
                if net_try == 0:
                    time.sleep(min(_retry_delay_sec(None, 0), 8.0))
                    continue
                break  # next model

    detail = "; ".join(errors[-8:]) if errors else "Unknown error"
    raise RuntimeError(f"OpenRouter: all models failed for role={role}: {detail}") from None


def describe_model_config() -> dict[str, list[str]]:
    """For /health diagnostics (no secrets)."""
    out: dict[str, list[str]] = {}
    for role in ("chat", "planner", "code"):
        out[role] = _ordered_models(role)  # type: ignore[arg-type]
    return out
