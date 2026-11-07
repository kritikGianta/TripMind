"""Ingestion API contract."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ingestion.models import ImportRun


class EntityCountsOut(BaseModel):
    read: int = 0
    accepted: int = 0
    rejected: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    retired: int = 0


class TravelWindowOut(BaseModel):
    first_departure: date
    last_departure: date


class ImportRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset: str
    mapping_name: str
    origin: Literal["provided", "synthetic"]
    source_name: str
    source_sha256: str
    dry_run: bool
    status: Literal["running", "published", "validated", "blocked", "failed"]
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    triggered_via: str
    entity_counts: dict[str, EntityCountsOut] = Field(default_factory=dict)
    adjustments: dict[str, int] = Field(
        default_factory=dict, description="Normalisations applied instead of rejecting rows"
    )
    adjustment_examples: dict[str, list[str]] = Field(default_factory=dict)
    reject_summary: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Rejected rows per entity and reason code"
    )
    rejects_total: int = 0
    travel_window: TravelWindowOut | None = None
    error: str | None = None

    @classmethod
    def from_run(cls, run: ImportRun) -> ImportRunOut:
        adjustments = run.adjustments or {}
        profile = run.profile or {}
        return cls(
            id=run.id,
            dataset=run.dataset,
            mapping_name=run.mapping_name,
            origin=run.origin,
            source_name=run.source_name,
            source_sha256=run.source_sha256,
            dry_run=run.dry_run,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=run.duration_ms,
            triggered_via=run.triggered_via,
            entity_counts={k: EntityCountsOut(**v) for k, v in (run.entity_counts or {}).items()},
            adjustments=adjustments.get("counts", {}),
            adjustment_examples=adjustments.get("examples", {}),
            reject_summary=run.reject_summary or {},
            rejects_total=int(profile.get("rejects_total", 0)),
            travel_window=profile.get("travel_window"),
            error=run.error,
        )


class ColumnProfileOut(BaseModel):
    name: str
    kind: str
    format: str | None
    non_null: int
    null_pct: float
    distinct: int
    samples: list[str]


class FileProfileOut(BaseModel):
    file: str
    rows: int
    encoding: str | None
    entity: str | None = None
    columns: list[ColumnProfileOut]


class ImportRunDetailOut(ImportRunOut):
    files: list[FileProfileOut] = Field(default_factory=list)
    error_details: dict[str, Any] | None = None

    @classmethod
    def from_run(cls, run: ImportRun) -> ImportRunDetailOut:
        base = ImportRunOut.from_run(run).model_dump()
        profile = run.profile or {}
        return cls(
            **base, files=profile.get("files", []), error_details=profile.get("error_details")
        )


class ImportRunPage(BaseModel):
    items: list[ImportRunOut]
    total: int
    limit: int
    offset: int


class RejectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity: str
    source_file: str
    row_number: int
    code: str
    field: str | None
    message: str
    raw: dict[str, Any] | None


class RejectPage(BaseModel):
    items: list[RejectOut]
    total: int
    limit: int
    offset: int


class MappingListOut(BaseModel):
    mappings: list[str]


class ProfileOut(BaseModel):
    files: list[FileProfileOut]
    suggested_mapping: str = Field(description="Draft mapping YAML; review before saving")


class DatasetSummaryOut(BaseModel):
    status: Literal["empty", "loaded"]
    dataset: str | None = None
    origin: Literal["provided", "synthetic"] | None = None
    published_at: datetime | None = None
    is_demo_data: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    by_origin: dict[str, int] = Field(
        default_factory=dict, description="Active flights, hotels and room types by provenance"
    )
    travel_window: TravelWindowOut | None = None
