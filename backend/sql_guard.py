from __future__ import annotations

import re
import sqlite3

_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|create|alter|attach|detach|pragma|replace|"
    r"truncate|vacuum|analyze|rollback|savepoint|release|begin|commit|"
    r"grant|revoke|reindex|detach"
    r")\b",
    re.IGNORECASE,
)


def _strip_trailing_semicolon(sql: str) -> str:
    s = sql.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    return s


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Empty SQL"
    if len(sql) > 8000:
        return False, "SQL exceeds maximum length (8000)"

    body = _strip_trailing_semicolon(sql)
    if ";" in body:
        return False, "Multiple SQL statements are not allowed"

    lowered = body.lstrip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Only SELECT or WITH queries are allowed"

    if _FORBIDDEN.search(body):
        return False, "Query contains forbidden keyword"

    return True, ""


def load_allowed_relations(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}
