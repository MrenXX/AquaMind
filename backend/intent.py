"""Heuristic user intent + routing tier (regex + prompt length). No extra LLM calls."""

from __future__ import annotations

import os
import re
from typing import Literal

UserIntent = Literal["conversational", "data"]

# Strong signals the user wants DB / analytics / sandbox work.
_DATA_HINT = re.compile(
    r"\b("
    r"consumption|telemetry|metric|metrics|sqlite|sql|select|query|"
    r"gym|customer\s*[abc]|customera|customerb|customerc|"
    r"device|devices|anomaly|anomalies|motif|motifs|"
    r"chart|plot|matplotlib|graph|histogram|"
    r"trusted_events|consumption_events|database|db\b|warehouse|"
    r"total|average|avg|sum|count|group\s*by|liters|l\/day|"
    r"compare|slice|flag|severity|csv|export|"
    r"daytona|sandbox|python\s*code|run\s*sql"
    r")\b",
    re.IGNORECASE,
)

# Short social / meta questions without numbers pipeline.
_CHAT_GREETING = re.compile(
    r"^\s*("
    r"hi\b|hello\b|hey\b|hiya\b|yo\b|sup\b|"
    r"good\s+(morning|afternoon|evening)|"
    r"thanks?\b|thank\s+you|thx\b|ty\b|"
    r"ok(ay)?\s*[!.]?$|yes\b|no\b"
    r")[\s!.?]*$",
    re.IGNORECASE,
)

_CHAT_META = re.compile(
    r"\b("
    r"what\s+can\s+you\s+do|who\s+are\s+you|capabilities|"
    r"how\s+do(es)?\s+this\s+work|help\s+me\s+understand|"
    r"explain\s+(the\s+)?(app|dashboard|aquamind|watersec)"
    r")\b",
    re.IGNORECASE,
)

# User wants matplotlib / image output — skip SQLite-only planner and use Daytona codegen.
_SANDBOX_VIZ = re.compile(
    r"(?:"
    r"\b(?:"
    r"chart|charts|plot|plots|matplotlib|pyplot|seaborn|ggplot|"
    r"histogram|heatmap|scatter(?:\s+plot)?|bar\s+chart|line\s+chart|pie\s+chart|"
    r"visuali[sz]e|visuali[sz]ation|figure|savefig|"
    r"render\s+(?:a\s+)?(?:chart|plot|graph)|"
    r"draw\s+(?:me\s+)?(?:a\s+)?(?:chart|plot|graph)|"
    r"graphs?\b|graph\s+of|plot\s+of|image\s+of|"
    r"trend\s*-?\s*lines?\b|trendlines?\b|"
    r"time\s+series(?:\s+(?:chart|plot|graph))?\b|"
    r"usage\s+over\s+time\b|"
    r"over\s+time\s+(?:chart|plot|graph|trend)\b"
    r")\b|\.png\b|📊)",
    re.IGNORECASE,
)


def force_daytona_codegen(prompt: str) -> bool:
    """True when the prompt asks for charts/code figures — bypass SQLite-first short path."""
    text = (prompt or "").strip()
    if not text:
        return False
    return bool(_SANDBOX_VIZ.search(text))


def classify_user_intent(prompt: str) -> UserIntent:
    """Fast local classifier: default *data* when unsure."""
    text = (prompt or "").strip()
    if not text:
        return "conversational"
    if _DATA_HINT.search(text):
        return "data"
    low = text.lower()
    if len(text) > 360:
        return "data"
    if _CHAT_GREETING.match(low) or _CHAT_META.search(low):
        return "conversational"
    # Short lines without data vocabulary → chat (e.g. "how are you", "tell me a joke").
    if len(text) < 140 and not any(ch.isdigit() for ch in text):
        if re.match(r"^[\w\s'’?!.,\-–—]+$", text) and not _DATA_HINT.search(low):
            return "conversational"
    return "data"


def _routing_int() -> tuple[int, int]:
    """(heavy_chars, heavy_lines) from env with safe defaults."""
    try:
        heavy_chars = int(os.environ.get("AQUAMIND_ROUTING_HEAVY_CHARS", "800"))
    except ValueError:
        heavy_chars = 800
    try:
        heavy_lines = int(os.environ.get("AQUAMIND_ROUTING_HEAVY_LINES", "20"))
    except ValueError:
        heavy_lines = 20
    return max(200, heavy_chars), max(4, heavy_lines)


def routing_tier(prompt: str) -> Literal["fast", "balanced", "heavy"]:
    """Map prompt → fast | balanced | heavy using regex + length (no OpenRouter router call).

    - *fast*: conversational-only (LFM / chat role) — no Daytona codegen.
    - *balanced*: typical telemetry / medium prompts (Qwen-first chain).
    - *heavy*: chart/code viz hints or long / multi-line prompts (MiniMax-first chain).
    """
    text = (prompt or "").strip()
    if not text:
        return "fast"  # type: ignore[return-value]

    if force_daytona_codegen(text):
        return "heavy"  # type: ignore[return-value]

    if classify_user_intent(text) == "conversational":
        return "fast"  # type: ignore[return-value]

    heavy_chars, heavy_lines = _routing_int()
    lines = text.count("\n") + 1
    if len(text) >= heavy_chars or lines >= heavy_lines:
        return "heavy"  # type: ignore[return-value]

    return "balanced"  # type: ignore[return-value]


def routing_health() -> dict[str, object]:
    """Static + threshold info for GET /health (no per-request state)."""
    hc, hl = _routing_int()
    return {
        "kind": "regex_length",
        "heavy_chars_threshold": hc,
        "heavy_lines_threshold": hl,
        "notes": (
            "conversational → tier fast (plain text, no sandbox); "
            "viz/chart regex or long prompt → heavy; else balanced."
        ),
    }
