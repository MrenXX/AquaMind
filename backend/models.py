from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    ok: bool = True
    answer_summary: str = ""
    computed_values: dict[str, Any] = Field(default_factory=dict)
    sql_or_method: str = ""
    evidence_rows: list[dict[str, Any]] = Field(default_factory=list)
    chart_spec: dict[str, Any] | None = None
    confidence_notes: str = ""


class QueryMetricsBody(BaseModel):
    use_trusted: bool = True
    customer_profile: str | None = None
    device_ids: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    group_by: Literal["none", "device", "day", "profile", "sub_category"] = "device"
    limit: int = Field(default=50, ge=1, le=500)


class CompareSlice(BaseModel):
    label: str
    customer_profile: str | None = None
    device_ids: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None


class CompareSourcesBody(BaseModel):
    slice_a: CompareSlice
    slice_b: CompareSlice
    use_trusted: bool = True


class FindMotifsBody(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class DetectAnomaliesBody(BaseModel):
    customer_profile: str | None = None
    device_id: str | None = None
    anomaly_type: str | None = None
    min_severity: float | None = None
    limit: int = Field(default=30, ge=1, le=200)


class RunSqlReadonlyBody(BaseModel):
    sql: str
    max_rows: int = Field(default=200, ge=1, le=500)


class DashboardSummary(BaseModel):
    total_events: int
    trusted_events: int
    hard_flagged_events: int
    profiles: list[str]
    device_count: int
    motif_top: list[dict[str, Any]]
    anomaly_count: int
    db_path: str
    db_mtime_iso: str | None = None
