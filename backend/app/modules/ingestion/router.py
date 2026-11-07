"""Dataset endpoints.

Admin (role `admin`, feature `data_import`): profile an upload, import it (or dry-run it), and read
import reports and quarantined rows. Public: a summary of the live dataset, which the web app uses
for its "demo data" label and the valid travel window.

Uploads are multipart, so they also require the `X-Requested-With: tripmind` header. Browsers only
send custom headers cross-site after a CORS preflight, which the API never grants, so a forged
cross-site form cannot start an import even if a cookie were sent.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_request_meta,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import DomainError, ErrorEnvelope, Forbidden, NotFound
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.dependencies import require_role
from app.modules.auth.models import User, UserRole
from app.modules.catalog.repository import CatalogRepository
from app.modules.ingestion.mapping import list_mappings
from app.modules.ingestion.repository import ImportRunRepository
from app.modules.ingestion.schemas import (
    DatasetSummaryOut,
    ImportRunDetailOut,
    ImportRunOut,
    ImportRunPage,
    MappingListOut,
    ProfileOut,
    RejectOut,
    RejectPage,
    TravelWindowOut,
)
from app.modules.ingestion.service import Actor, ImportService
from app.modules.ingestion.sources import ZipSource

public_router = APIRouter(tags=["datasets"])
admin_router = APIRouter(
    prefix="/admin/imports",
    tags=["admin: imports"],
    dependencies=[Depends(require_feature("data_import"))],
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    413: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}

AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


class PayloadTooLarge(DomainError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "The upload is too large."


def _require_client_header(
    x_requested_with: Annotated[str | None, Header()] = None,
) -> None:
    if (x_requested_with or "").lower() != "tripmind":
        raise Forbidden(
            "Uploads must be sent by the TripMind client.", code="CLIENT_HEADER_MISSING"
        )


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> ImportService:
    return ImportService(session, settings, clock)


def _read_upload(upload: UploadFile, service: ImportService) -> ZipSource:
    rules = service.rules()
    limit = rules.max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLarge(f"The upload is larger than {rules.max_upload_mb} MB.")
    return ZipSource(
        data,
        name=(upload.filename or "upload.zip")[:255],
        max_members=rules.max_archive_members,
        max_uncompressed_mb=rules.max_uncompressed_mb,
    )


# ---------------------------------------------------------------------------------- public


@public_router.get(
    "/datasets/current",
    response_model=DatasetSummaryOut,
    summary="The dataset currently live in the catalog",
)
def current_dataset(session: Session = Depends(get_session)) -> DatasetSummaryOut:
    run = ImportRunRepository(session).latest_published()
    catalog = CatalogRepository(session)
    counts = catalog.active_counts()
    if run is None and not any(counts.values()):
        return DatasetSummaryOut(status="empty")
    by_origin = catalog.origin_counts()
    window = catalog.flight_window()
    return DatasetSummaryOut(
        status="loaded",
        dataset=run.dataset if run else None,
        origin=run.origin if run else None,
        published_at=run.finished_at if run else None,
        is_demo_data=by_origin.get("synthetic", 0) > 0,
        counts=counts,
        by_origin=by_origin,
        travel_window=TravelWindowOut(
            first_departure=window[0].date(), last_departure=window[1].date()
        )
        if window
        else None,
    )


# ---------------------------------------------------------------------------------- admin


@admin_router.get(
    "/mappings",
    response_model=MappingListOut,
    responses=_ERRORS,
    summary="Dataset mappings available in config/mappings",
)
def mappings(_: AdminUser, settings: Settings = Depends(get_settings_dep)) -> MappingListOut:
    return MappingListOut(mappings=list_mappings(settings.config_dir))


@admin_router.post(
    "/profile",
    response_model=ProfileOut,
    responses=_ERRORS,
    dependencies=[
        Depends(_require_client_header),
        Depends(rate_limit("imports.profile", limit=20, window_seconds=60)),
    ],
    summary="Profile a dataset ZIP and draft a mapping (nothing is stored)",
)
def profile(
    _: AdminUser,
    file: Annotated[UploadFile, File(description="Dataset ZIP")],
    dataset: Annotated[str, Form(max_length=64, pattern=r"^[a-z0-9][a-z0-9_.-]*$")] = "finale",
    service: ImportService = Depends(_service),
) -> ProfileOut:
    files, suggestion = service.profile(_read_upload(file, service), dataset)
    return ProfileOut.model_validate({"files": files, "suggested_mapping": suggestion})


@admin_router.post(
    "",
    response_model=ImportRunOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[
        Depends(_require_client_header),
        Depends(rate_limit("imports.run", limit=10, window_seconds=60)),
    ],
    summary="Import a dataset ZIP with a named mapping (dry_run validates without publishing)",
)
def run_import(
    user: AdminUser,
    file: Annotated[UploadFile, File(description="Dataset ZIP")],
    mapping: Annotated[str, Form(max_length=64)],
    dry_run: Annotated[bool, Form()] = False,
    service: ImportService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> ImportRunOut:
    source = _read_upload(file, service)
    run = service.run_import(
        source,
        mapping_name=mapping,
        dry_run=dry_run,
        actor=Actor(user_id=user.id, via="api", meta=meta),
    )
    return ImportRunOut.from_run(run)


@admin_router.get(
    "", response_model=ImportRunPage, responses=_ERRORS, summary="Import history, newest first"
)
def list_runs(
    _: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> ImportRunPage:
    rows, total = ImportRunRepository(session).page(limit=limit, offset=offset)
    return ImportRunPage(
        items=[ImportRunOut.from_run(r) for r in rows], total=total, limit=limit, offset=offset
    )


@admin_router.get(
    "/{run_id}",
    response_model=ImportRunDetailOut,
    responses=_ERRORS,
    summary="One import report, including the file profiles",
)
def get_run(
    run_id: uuid.UUID, _: AdminUser, session: Session = Depends(get_session)
) -> ImportRunDetailOut:
    run = ImportRunRepository(session).get(run_id)
    if run is None:
        raise NotFound("Import run not found.")
    return ImportRunDetailOut.from_run(run)


@admin_router.get(
    "/{run_id}/rejects",
    response_model=RejectPage,
    responses=_ERRORS,
    summary="Quarantined rows of one import",
)
def get_rejects(
    run_id: uuid.UUID,
    _: AdminUser,
    entity: str | None = None,
    code: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> RejectPage:
    repo = ImportRunRepository(session)
    if repo.get(run_id) is None:
        raise NotFound("Import run not found.")
    rows, total = repo.rejects(run_id, entity=entity, code=code, limit=limit, offset=offset)
    return RejectPage(
        items=[RejectOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )
