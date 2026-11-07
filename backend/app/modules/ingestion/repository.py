from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.ingestion.models import ImportReject, ImportRun, ImportStatus


class ImportRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: ImportRun) -> ImportRun:
        self._session.add(run)
        self._session.flush()
        return run

    def get(self, run_id: uuid.UUID) -> ImportRun | None:
        return self._session.get(ImportRun, run_id)

    def page(self, *, limit: int, offset: int) -> tuple[Sequence[ImportRun], int]:
        total = int(self._session.scalar(select(func.count()).select_from(ImportRun)) or 0)
        rows = self._session.scalars(
            select(ImportRun).order_by(ImportRun.started_at.desc()).limit(limit).offset(offset)
        ).all()
        return rows, total

    def latest_published(self) -> ImportRun | None:
        return self._session.scalar(
            select(ImportRun)
            .where(ImportRun.status == ImportStatus.PUBLISHED)
            .order_by(ImportRun.finished_at.desc())
            .limit(1)
        )

    def fail_stale_running(self, *, started_before: datetime, now: datetime) -> int:
        """A run left 'running' by a crashed process would block imports forever."""
        result = self._session.execute(
            update(ImportRun)
            .where(ImportRun.status == ImportStatus.RUNNING, ImportRun.started_at < started_before)
            .values(
                status=ImportStatus.FAILED,
                finished_at=now,
                error="Abandoned: the process stopped before the import finished.",
            )
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def add_rejects(self, rejects: list[ImportReject]) -> None:
        self._session.add_all(rejects)

    def rejects(
        self,
        run_id: uuid.UUID,
        *,
        entity: str | None,
        code: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[ImportReject], int]:
        query = select(ImportReject).where(ImportReject.import_run_id == run_id)
        if entity:
            query = query.where(ImportReject.entity == entity)
        if code:
            query = query.where(ImportReject.code == code)
        total = int(self._session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        rows = self._session.scalars(
            query.order_by(ImportReject.entity, ImportReject.row_number).limit(limit).offset(offset)
        ).all()
        return rows, total
