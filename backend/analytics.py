from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend import models
from backend.config import db_path
from backend.db import fetch_all, fetch_one, get_connection


def _events_table(use_trusted: bool) -> str:
    return "trusted_events" if use_trusted else "consumption_events"


def _filters_sql(
    customer_profile: str | None,
    device_ids: list[str] | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if customer_profile:
        clauses.append("customer_profile = ?")
        params.append(customer_profile)
    if device_ids:
        placeholders = ",".join("?" * len(device_ids))
        clauses.append(f"device_id IN ({placeholders})")
        params.extend(device_ids)
    if date_from:
        clauses.append("event_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("event_date <= ?")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def query_metrics(conn: sqlite3.Connection, body: models.QueryMetricsBody) -> models.ToolResponse:
    table = _events_table(body.use_trusted)
    where, params = _filters_sql(body.customer_profile, body.device_ids, body.date_from, body.date_to)

    if body.group_by == "none":
        sql = f"""
        SELECT COUNT(*) AS event_count,
               SUM(consumption_raw) AS total_consumption,
               AVG(consumption_raw) AS avg_consumption
        FROM {table}{where}
        """
        row = fetch_one(conn, sql, tuple(params))
        summary = (
            f"Aggregated {table}: {row['event_count']} events, "
            f"total consumption_raw={row['total_consumption']}, avg={row['avg_consumption']}."
        )
        return models.ToolResponse(
            answer_summary=summary,
            computed_values=dict(row) if row else {},
            sql_or_method=sql.strip(),
            evidence_rows=[dict(row)] if row else [],
            confidence_notes="Values are consumption_raw as stored; confirm units with WaterSec.",
        )

    group_col = {
        "device": "device_id",
        "day": "event_date",
        "profile": "customer_profile",
        "sub_category": "COALESCE(sub_category, '')",
    }[body.group_by]

    sql = f"""
    SELECT {group_col} AS group_key,
           COUNT(*) AS event_count,
           SUM(consumption_raw) AS total_consumption,
           AVG(consumption_raw) AS avg_consumption
    FROM {table}{where}
    GROUP BY {group_col}
    ORDER BY total_consumption DESC
    LIMIT ?
    """
    rows = fetch_all(conn, sql, tuple(params + [body.limit]))
    summary = f"Top {body.group_by} groups by total consumption_raw ({table})."
    return models.ToolResponse(
        answer_summary=summary,
        computed_values={"row_count": len(rows)},
        sql_or_method=sql.strip(),
        evidence_rows=rows,
        confidence_notes="Sorted by total_consumption_raw descending.",
    )


def _slice_metrics(conn: sqlite3.Connection, table: str, sl: models.CompareSlice) -> dict[str, Any]:
    where, params = _filters_sql(sl.customer_profile, sl.device_ids, sl.date_from, sl.date_to)
    sql = f"""
    SELECT COUNT(*) AS event_count,
           SUM(consumption_raw) AS total_consumption,
           AVG(consumption_raw) AS avg_consumption
    FROM {table}{where}
    """
    row = fetch_one(conn, sql, tuple(params))
    return {"label": sl.label, **(row or {})}


def compare_sources(conn: sqlite3.Connection, body: models.CompareSourcesBody) -> models.ToolResponse:
    table = _events_table(body.use_trusted)
    a = _slice_metrics(conn, table, body.slice_a)
    b = _slice_metrics(conn, table, body.slice_b)
    diff = (a.get("total_consumption") or 0) - (b.get("total_consumption") or 0)
    summary = f"Compared totals: {a['label']} vs {b['label']}; delta total_consumption_raw={diff}."
    return models.ToolResponse(
        answer_summary=summary,
        computed_values={"slice_a": a, "slice_b": b, "delta_total_consumption_raw": diff},
        sql_or_method="compare_sources: two aggregate SELECTs on " + table,
        evidence_rows=[a, b],
        confidence_notes="Uses same filters per slice; missing dates mean all-time.",
    )


def find_motifs(conn: sqlite3.Connection, body: models.FindMotifsBody) -> models.ToolResponse:
    sql = """
    SELECT motif_name, pattern_count, median_delay_seconds, interpretation
    FROM motif_patterns
    ORDER BY pattern_count DESC
    LIMIT ?
    """
    rows = fetch_all(conn, sql, (body.limit,))
    return models.ToolResponse(
        answer_summary="Motif pattern counts from motif_patterns.",
        computed_values={"count": len(rows)},
        sql_or_method=sql.strip(),
        evidence_rows=rows,
        confidence_notes="Motifs are derived from Customer C sequences; cite as behavioral patterns.",
    )


def detect_anomalies(conn: sqlite3.Connection, body: models.DetectAnomaliesBody) -> models.ToolResponse:
    clauses: list[str] = []
    params: list[Any] = []
    if body.customer_profile:
        clauses.append("customer_profile = ?")
        params.append(body.customer_profile)
    if body.device_id:
        clauses.append("device_id = ?")
        params.append(body.device_id)
    if body.anomaly_type:
        clauses.append("anomaly_type = ?")
        params.append(body.anomaly_type)
    if body.min_severity is not None:
        clauses.append("severity_score >= ?")
        params.append(body.min_severity)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT anomaly_id, customer_profile, device_id, anomaly_type, severity_score,
           explanation, recommended_action, evidence_json
    FROM anomaly_candidates{where}
    ORDER BY severity_score DESC
    LIMIT ?
    """
    params.append(body.limit)
    rows = fetch_all(conn, sql, tuple(params))
    return models.ToolResponse(
        answer_summary=f"Returned {len(rows)} anomaly candidate rows.",
        computed_values={"row_count": len(rows)},
        sql_or_method=sql.strip(),
        evidence_rows=rows,
        confidence_notes="Treat as candidates; verify in the field and check data_quality_flags.",
    )


def run_sql_readonly(conn: sqlite3.Connection, sql: str, max_rows: int) -> models.ToolResponse:
    cur = conn.execute(sql)
    rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    dicts = [dict(r) for r in rows]
    return models.ToolResponse(
        answer_summary=f"Read {len(dicts)} rows" + (" (truncated)" if truncated else ""),
        computed_values={"row_count": len(dicts), "truncated": truncated},
        sql_or_method=sql.strip(),
        evidence_rows=dicts,
        confidence_notes="Ad-hoc SELECT; validate joins and trusted vs raw usage manually.",
    )


def dashboard_summary(conn: sqlite3.Connection) -> models.DashboardSummary:
    p = db_path()
    mtime_iso = None
    if p.is_file():
        ts = p.stat().st_mtime
        mtime_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    total_events = fetch_one(conn, "SELECT COUNT(*) AS n FROM consumption_events", ())
    trusted = fetch_one(conn, "SELECT COUNT(*) AS n FROM trusted_events", ())
    flagged = fetch_one(
        conn,
        "SELECT COUNT(DISTINCT event_id) AS n FROM data_quality_flags WHERE severity = 'hard'",
        (),
    )
    profiles = fetch_all(conn, "SELECT DISTINCT customer_profile FROM consumption_events ORDER BY 1", ())
    devices = fetch_one(conn, "SELECT COUNT(DISTINCT device_id) AS n FROM consumption_events", ())
    motifs = fetch_all(
        conn,
        "SELECT motif_name, pattern_count FROM motif_patterns ORDER BY pattern_count DESC LIMIT 5",
        (),
    )
    anomalies = fetch_one(conn, "SELECT COUNT(*) AS n FROM anomaly_candidates", ())

    return models.DashboardSummary(
        total_events=int(total_events["n"]) if total_events else 0,
        trusted_events=int(trusted["n"]) if trusted else 0,
        hard_flagged_events=int(flagged["n"]) if flagged else 0,
        profiles=[r["customer_profile"] for r in profiles],
        device_count=int(devices["n"]) if devices else 0,
        motif_top=motifs,
        anomaly_count=int(anomalies["n"]) if anomalies else 0,
        db_path=str(p),
        db_mtime_iso=mtime_iso,
    )


def schema_doc() -> dict[str, Any]:
    """Static schema hints for agents (no raw row dump)."""
    return {
        "core_tables": [
            "consumption_events",
            "trusted_events (view)",
            "data_quality_flags",
            "daily_consumption_profile",
            "device_baselines",
            "motif_patterns",
            "anomaly_candidates",
            "gym_device_inference",
            "calendar_context",
            "climate_context",
            "holiday_context",
        ],
        "docs": [
            "docs/SQLITE_BACKEND.md",
            "docs/AGENT_DATA_RULES.md",
            "docs/DATA_INVENTORY.md",
        ],
        "notes": [
            "consumption_raw units are as in telemetry; confirm with WaterSec before claiming liters.",
            "Use trusted_events for default KPIs unless investigating quality issues.",
        ],
    }


# In-process latest interaction trace for dashboard polling (MVP)
_latest_trace: dict[str, Any] | None = None


def record_tool_trace(tool: str, payload: dict[str, Any], response: models.ToolResponse) -> None:
    global _latest_trace
    _latest_trace = {
        "tool": tool,
        "request": payload,
        "answer_summary": response.answer_summary,
        "computed_values": response.computed_values,
        "confidence_notes": response.confidence_notes,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def get_latest_trace() -> dict[str, Any] | None:
    return _latest_trace
