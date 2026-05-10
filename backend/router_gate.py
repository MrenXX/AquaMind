"""
OpenRouter model tier slugs (fast / balanced / heavy) for AquaMind.

Maps env ``AQUAMIND_MODEL_FAST|BALANCED|HEAVY`` and legacy ``AQUAMIND_OPENROUTER_MODEL``.
Heuristic routing lives in ``backend.intent.routing_tier`` (regex + length).
"""

from __future__ import annotations

import os
import sys
from typing import Literal

Tier = Literal["fast", "balanced", "heavy"]

_DEFAULT_FAST = "liquid/lfm-2.5-1.2b-instruct:free"
_DEFAULT_BALANCED = "qwen/qwen3-next-80b-a3b-instruct:free"
_DEFAULT_HEAVY = "minimax/minimax-m2.5:free"

_DEFAULTS: dict[Tier, str] = {
    "fast": _DEFAULT_FAST,
    "balanced": _DEFAULT_BALANCED,
    "heavy": _DEFAULT_HEAVY,
}

_TIER_ENV_KEYS: dict[Tier, str] = {
    "fast": "AQUAMIND_MODEL_FAST",
    "balanced": "AQUAMIND_MODEL_BALANCED",
    "heavy": "AQUAMIND_MODEL_HEAVY",
}


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, "").strip()
    return v if v else default


def tier_to_primary_slug(tier: Tier) -> str:
    """Primary OpenRouter slug for this tier (env overrides tier defaults)."""
    key = _TIER_ENV_KEYS[tier]
    slug = (_env(key) or "").strip()
    if slug:
        return slug
    legacy = (_env("AQUAMIND_OPENROUTER_MODEL") or "").strip()
    if legacy:
        return legacy
    return _DEFAULTS[tier]


def tier_slugs_health() -> dict[str, object]:
    """For GET /health: resolved primary slug per tier (no secrets)."""
    return {
        "kind": "env_tier_slugs",
        "tier_primary_slugs": {
            "fast": tier_to_primary_slug("fast"),
            "balanced": tier_to_primary_slug("balanced"),
            "heavy": tier_to_primary_slug("heavy"),
        },
    }


if __name__ == "__main__":
    from backend.intent import routing_tier

    q = " ".join(sys.argv[1:]).strip() or "hello"
    t = routing_tier(q)
    print(f"tier={t} primary={tier_to_primary_slug(t)}")
