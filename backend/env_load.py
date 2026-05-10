"""Load repo-root environment files for uvicorn and chat.

Supports both `.env` and `env` (no leading dot). Order: `.env` first, then `env`
with override=True so keys in `env` win on duplicates (common local layout).
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_repo_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = repo_root()
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / "env", override=True)
