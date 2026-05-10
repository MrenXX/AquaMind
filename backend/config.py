from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return _REPO_ROOT


def db_path() -> Path:
    raw = os.environ.get("AQUAMIND_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _REPO_ROOT / "data" / "aquamind.sqlite"
