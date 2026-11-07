from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class ImportStatus(enum.StrEnum):
    RUNNING = "running"
    PUBLISHED = "published"  # data is live in the catalog
    VALIDATED = "validated"  # dry run passed; nothing was written to the catalog
    BLOCKED = "blocked"  # too many rejected rows; nothing was written (likely a wrong mapping)
    FAILED = "failed"  # unexpected error; nothing was written


class ImportRun(UUIDPrimaryKeyMixin, Base):
    """One attempt to load a dataset. The row is the import report."""

    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'published', 'validated', 'blocked', 'failed')",
            name="status_valid",
        ),
        # At most one import runs at a time: a second start fails on this index.
        Index(
            "uq_import_runs_single_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
    )

    dataset: Mapped[str] = mapped_column(String(120), nullable=False)
    mapping_name: Mapped[str] = mapped_column(String(120), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    triggered_via: Mapped[str] = mapped_column(String(16), nullable=False)  # cli | api
    # Per entity: read, accepted, rejected, inserted, updated, unchanged, retired.
    entity_counts: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Normalisations applied instead of rejecting (defaults filled, fuzzy city matches, ...).
    adjustments: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reject_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    profile: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class ImportReject(UUIDPrimaryKeyMixin, Base):
    """A quarantined source row: what was wrong, where, and the original values."""

    __tablename__ = "import_rejects"
    __table_args__ = (Index("ix_import_rejects_run_entity", "import_run_id", "entity"),)

    import_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False
    )
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    field: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)
