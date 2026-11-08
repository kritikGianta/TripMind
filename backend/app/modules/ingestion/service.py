"""Import use cases: run an import, profile a dataset, report the live dataset.

Transaction design:
1. The run row is committed as `running` first. A partial unique index allows only one running
   import, so a concurrent start fails fast with IMPORT_IN_PROGRESS.
2. Catalog changes, the final run status, the quarantined rows and the audit record are committed
   together in one transaction: the catalog is never left half-imported.
3. On any error the transaction is rolled back and the run is marked `failed` with the reason.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, DomainError
from app.core.request_context import RequestMeta
from app.modules.audit.service import AuditService
from app.modules.catalog.models import Airport, City, Flight, Hotel, HotelReview, RoomType
from app.modules.catalog.repository import CatalogRepository
from app.modules.ingestion import metrics
from app.modules.ingestion.mapping import DatasetMapping, load_mapping
from app.modules.ingestion.models import ImportReject, ImportRun, ImportStatus
from app.modules.ingestion.pipeline import PreparedDataset, prepare
from app.modules.ingestion.profiler import profile_source, suggest_mapping
from app.modules.ingestion.publish import (
    AIRPORT_COLUMNS,
    CITY_COLUMNS,
    FLIGHT_COLUMNS,
    HOTEL_COLUMNS,
    REVIEW_COLUMNS,
    ROOM_COLUMNS,
    CatalogPublisher,
    TableCounts,
    records,
)
from app.modules.ingestion.repository import ImportRunRepository
from app.modules.ingestion.resolve import AirportRef
from app.modules.ingestion.rules import IngestionRules, Vocabulary, load_rules, load_vocabulary
from app.modules.ingestion.sources import DatasetSource

log = structlog.get_logger(__name__)

_STALE_AFTER = timedelta(hours=1)


@dataclass(frozen=True)
class Actor:
    user_id: uuid.UUID | None
    via: str  # "api" | "cli"
    meta: RequestMeta


class ImportService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        self._runs = ImportRunRepository(session)

    # ------------------------------------------------------------------ configuration

    def rules(self) -> IngestionRules:
        return load_rules(self._settings.config_dir)

    def vocabulary(self) -> Vocabulary:
        return load_vocabulary(self._settings.config_dir)

    def mapping(self, name: str) -> DatasetMapping:
        return load_mapping(self._settings.config_dir, name)

    # ------------------------------------------------------------------ use cases

    def run_import(
        self,
        source: DatasetSource,
        *,
        mapping_name: str,
        dry_run: bool,
        actor: Actor,
    ) -> ImportRun:
        mapping = self.mapping(mapping_name)
        rules, vocabulary = self.rules(), self.vocabulary()
        run = self._start(source, mapping, mapping_name, dry_run, actor)
        started = time.perf_counter()
        try:
            prepared = prepare(
                source,
                mapping,
                rules,
                vocabulary,
                catalog_airports=self._catalog_airports,
                catalog_hotels=self._catalog_hotels,
                today=self._clock.now().date(),
            )
            self._finish(run, prepared, rules, dry_run, actor)
        except Exception as exc:
            self._session.rollback()
            self._fail(run.id, exc, actor)
            raise
        finally:
            metrics.IMPORT_DURATION.observe(time.perf_counter() - started)
        return run

    def profile(self, source: DatasetSource, dataset: str) -> tuple[list[dict[str, Any]], str]:
        profiles = [p for _, p in profile_source(source)]
        return profiles, suggest_mapping(profiles, dataset)

    # ------------------------------------------------------------------ steps

    def _start(
        self,
        source: DatasetSource,
        mapping: DatasetMapping,
        mapping_name: str,
        dry_run: bool,
        actor: Actor,
    ) -> ImportRun:
        now = self._clock.now()
        self._runs.fail_stale_running(started_before=now - _STALE_AFTER, now=now)
        run = ImportRun(
            dataset=mapping.dataset,
            mapping_name=mapping_name,
            origin=mapping.origin,
            source_name=source.name[:255],
            source_sha256=source.sha256,
            dry_run=dry_run,
            status=ImportStatus.RUNNING,
            started_at=now,
            triggered_by_user_id=actor.user_id,
            triggered_via=actor.via,
        )
        try:
            self._runs.add(run)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise Conflict("Another import is already running.", code="IMPORT_IN_PROGRESS") from exc
        log.info("import_started", run_id=str(run.id), dataset=mapping.dataset, dry_run=dry_run)
        return run

    def _finish(
        self,
        run: ImportRun,
        prepared: PreparedDataset,
        rules: IngestionRules,
        dry_run: bool,
        actor: Actor,
    ) -> None:
        counts: dict[str, dict[str, int]] = prepared.entity_counts()
        blocked = prepared.reject_ratio_exceeded(rules.max_reject_ratio)

        if blocked:
            status = ImportStatus.BLOCKED
            run.error = (
                "Too many rows were rejected, so nothing was published: "
                + ", ".join(f"{e} {r:.0%}" for e, r in blocked.items())
                + f" (limit {rules.max_reject_ratio:.0%}). Check the mapping."
            )
        elif dry_run:
            status = ImportStatus.VALIDATED
        else:
            status = ImportStatus.PUBLISHED
            for entity, table_counts in self._publish(run.id, prepared).items():
                counts.setdefault(entity, {}).update(table_counts)

        now = self._clock.now()
        stored = prepared.log.rejects[: rules.max_stored_rejects]
        self._runs.add_rejects(
            [
                ImportReject(
                    import_run_id=run.id,
                    entity=r.entity,
                    source_file=r.source_file[:255],
                    row_number=r.row_number,
                    code=r.code,
                    field=r.field,
                    message=r.message,
                    raw=r.raw,
                )
                for r in stored
            ]
        )
        run.status = status
        run.finished_at = now
        run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
        run.entity_counts = counts
        run.adjustments = {
            "counts": dict(prepared.log.adjustments),
            "examples": prepared.log.examples,
        }
        run.reject_summary = prepared.log.summary()
        run.profile = {
            "files": prepared.profile,
            "travel_window": prepared.travel_window(),
            "rejects_stored": len(stored),
            "rejects_total": len(prepared.log.rejects),
        }
        AuditService(self._session).record(
            action="data.import",
            outcome=status.value,
            meta=actor.meta,
            actor_user_id=actor.user_id,
            details={"run_id": str(run.id), "dataset": run.dataset, "dry_run": dry_run},
        )
        self._session.commit()

        metrics.IMPORT_RUNS.labels(status=status.value, dry_run=str(dry_run).lower()).inc()
        for entity, c in counts.items():
            metrics.IMPORT_ROWS.labels(entity=entity, outcome="accepted").inc(c.get("accepted", 0))
            metrics.IMPORT_ROWS.labels(entity=entity, outcome="rejected").inc(c.get("rejected", 0))
        log.info(
            "import_finished",
            run_id=str(run.id),
            status=status.value,
            rejected=len(prepared.log.rejects),
        )

    def _publish(self, run_id: uuid.UUID, prepared: PreparedDataset) -> dict[str, dict[str, int]]:
        publisher = CatalogPublisher(self._session, self._clock.now())
        result: dict[str, TableCounts] = {}
        full_snapshot = prepared.airports is not None and prepared.hotels is not None

        if prepared.cities is not None:
            result["cities"], _ = publisher.sync(
                City,
                records(prepared.cities, CITY_COLUMNS, import_run_id=run_id),
                retire_missing=full_snapshot,
            )
        if prepared.airports is not None:
            result["airports"], _ = publisher.sync(
                Airport, records(prepared.airports, AIRPORT_COLUMNS, import_run_id=run_id)
            )
        if prepared.flights is not None:
            result["flights"], _ = publisher.sync(
                Flight, records(prepared.flights, FLIGHT_COLUMNS, import_run_id=run_id)
            )
        if prepared.hotels is not None:
            amenities = {
                uuid.UUID(str(i)): codes
                for i, codes in zip(
                    prepared.hotels["id"], prepared.hotels["amenity_codes"], strict=True
                )
            }
            result["hotels"], written = publisher.sync(
                Hotel,
                records(prepared.hotels, HOTEL_COLUMNS, import_run_id=run_id, extras=amenities),
            )
            publisher.replace_amenities(written, amenities)
        if prepared.room_types is not None and not prepared.room_types.empty:
            result["room_types"], _ = publisher.sync(
                RoomType, records(prepared.room_types, ROOM_COLUMNS, import_run_id=run_id)
            )
        if prepared.reviews is not None:
            result["reviews"], _ = publisher.sync(
                HotelReview, records(prepared.reviews, REVIEW_COLUMNS, import_run_id=run_id)
            )
        for entity, retired in publisher.cascade_retirements().items():
            result.setdefault(entity, TableCounts()).retired += retired
        return {entity: counts.as_dict() for entity, counts in result.items()}

    def _fail(self, run_id: uuid.UUID, exc: Exception, actor: Actor) -> None:
        run = self._runs.get(run_id)
        if run is None:
            return
        now = self._clock.now()
        run.status = ImportStatus.FAILED
        run.finished_at = now
        started = (
            run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=now.tzinfo)
        )
        run.duration_ms = int((now - started).total_seconds() * 1000)
        run.error = (
            exc.message
            if isinstance(exc, DomainError)
            else f"Unexpected error ({type(exc).__name__}). See the API logs."
        )
        if isinstance(exc, DomainError) and exc.details:
            run.profile = {"error_details": exc.details}
        AuditService(self._session).record(
            action="data.import",
            outcome="failed",
            meta=actor.meta,
            actor_user_id=actor.user_id,
            details={"run_id": str(run_id), "error": run.error},
        )
        self._session.commit()
        metrics.IMPORT_RUNS.labels(status="failed", dry_run=str(run.dry_run).lower()).inc()
        log.warning(
            "import_failed", run_id=str(run_id), error=run.error, error_type=type(exc).__name__
        )

    def _catalog_hotels(self) -> dict[str, str]:
        rows = self._session.execute(
            select(Hotel.source_key, Hotel.id).where(Hotel.is_active.is_(True))
        )
        return {key: str(hotel_id) for key, hotel_id in rows}

    def _catalog_airports(self) -> list[AirportRef]:
        return [
            AirportRef(
                id=str(a.id), code=a.code, name=a.name, city_key=city_key, timezone=a.timezone
            )
            for a, city_key in CatalogRepository(self._session).active_airports()
        ]
