from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import analytics
from backend.chat import router as chat_router
from backend.config import db_path
from backend.db import get_connection
from backend.openrouter_client import describe_model_config
from backend.intent import routing_health
from backend.router_gate import tier_slugs_health
from backend.models import (
    CompareSourcesBody,
    DetectAnomaliesBody,
    FindMotifsBody,
    QueryMetricsBody,
    RunSqlReadonlyBody,
    ToolResponse,
)
from backend.sql_guard import validate_readonly_sql

app = FastAPI(title="AquaMind Analytics API", version="0.1.0")

_DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def _cors_origins_and_credentials() -> tuple[list[str], bool]:
    """Starlette forbids allow_credentials=True with allow_origins=['*']."""
    raw = os.environ.get("AQUAMIND_CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if origins == ["*"]:
            return ["*"], False
        return origins, True
    return list(_DEFAULT_DEV_ORIGINS), True


_cors_origins, _cors_credentials = _cors_origins_and_credentials()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


def _gmail_ready() -> dict[str, bool | str]:
    sender = os.environ.get("GMAIL_SENDER", "").strip()
    to = os.environ.get("GMAIL_TO", "").strip()
    return {
        "gmail_sender_set": bool(sender),
        "gmail_to_set": bool(to),
        "note": "OAuth files are outside the repo; see aquamind_gmail_report_cli.py",
    }


@app.get("/health")
def health() -> dict:
    p = db_path()
    exists = p.is_file()
    out: dict = {
        "ok": exists,
        "db_path": str(p),
        "db_exists": exists,
        "gmail": _gmail_ready(),
        "openrouter_roles": describe_model_config(),
        "routing": routing_health(),
        "tier_slugs": tier_slugs_health(),
    }
    if not exists:
        out["hint"] = "Run: python scripts\\etl\\build_database.py"
    return out


@app.get("/schema")
def schema() -> dict:
    return analytics.schema_doc()


@app.get("/dashboard/summary")
def dashboard_summary() -> dict:
    p = db_path()
    if not p.is_file():
        raise HTTPException(status_code=503, detail="Database missing; run ETL build_database.py")
    with get_connection() as conn:
        return analytics.dashboard_summary(conn).model_dump()


@app.get("/events/latest")
def events_latest() -> dict:
    trace = analytics.get_latest_trace()
    return {"last_interaction": trace}


@app.post("/tools/query_metrics", response_model=ToolResponse)
def tools_query_metrics(body: QueryMetricsBody) -> ToolResponse:
    p = db_path()
    if not p.is_file():
        raise HTTPException(status_code=503, detail="Database missing")
    with get_connection() as conn:
        resp = analytics.query_metrics(conn, body)
        analytics.record_tool_trace("query_metrics", body.model_dump(), resp)
        return resp


@app.post("/tools/compare_sources", response_model=ToolResponse)
def tools_compare_sources(body: CompareSourcesBody) -> ToolResponse:
    if not db_path().is_file():
        raise HTTPException(status_code=503, detail="Database missing")
    with get_connection() as conn:
        resp = analytics.compare_sources(conn, body)
        analytics.record_tool_trace("compare_sources", body.model_dump(), resp)
        return resp


@app.post("/tools/find_motifs", response_model=ToolResponse)
def tools_find_motifs(body: FindMotifsBody) -> ToolResponse:
    if not db_path().is_file():
        raise HTTPException(status_code=503, detail="Database missing")
    with get_connection() as conn:
        resp = analytics.find_motifs(conn, body)
        analytics.record_tool_trace("find_motifs", body.model_dump(), resp)
        return resp


@app.post("/tools/detect_anomalies", response_model=ToolResponse)
def tools_detect_anomalies(body: DetectAnomaliesBody) -> ToolResponse:
    if not db_path().is_file():
        raise HTTPException(status_code=503, detail="Database missing")
    with get_connection() as conn:
        resp = analytics.detect_anomalies(conn, body)
        analytics.record_tool_trace("detect_anomalies", body.model_dump(), resp)
        return resp


@app.post("/tools/run_sql_readonly", response_model=ToolResponse)
def tools_run_sql_readonly(body: RunSqlReadonlyBody) -> ToolResponse:
    ok, reason = validate_readonly_sql(body.sql)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if not db_path().is_file():
        raise HTTPException(status_code=503, detail="Database missing")
    with get_connection() as conn:
        try:
            resp = analytics.run_sql_readonly(conn, body.sql.strip().rstrip(";"), body.max_rows)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        analytics.record_tool_trace("run_sql_readonly", {"sql": body.sql, "max_rows": body.max_rows}, resp)
        return resp


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "aquamind-analytics", "docs": "/docs"}
