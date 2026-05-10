from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable

from backend.config import db_path


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path()
    conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_connection(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params or ())
    return rows_to_dicts(cur.fetchall())


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    cur = conn.execute(sql, params or ())
    row = cur.fetchone()
    return dict(row) if row else None
