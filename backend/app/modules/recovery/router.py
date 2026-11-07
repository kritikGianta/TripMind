"""Disruption (operators) and recovery (travellers) endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_request_meta, get_settings_dep, require_feature
from app.core.errors import ErrorEnvelope
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.auth.models import User, UserRole
from app.modules.recovery.schemas import (
    AcceptIn,
    BookedFlightListOut,
    DisruptionIn,
    DisruptionListOut,
    DisruptionOut,
    RecoveryCaseListOut,
    RecoveryCaseOut,
)
from app.modules.recovery.service import RecoveryService

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}

admin_router = APIRouter(
    prefix="/admin/operations",
    tags=["admin: operations"],
    dependencies=[Depends(require_feature("recovery"))],
)
router = APIRouter(
    prefix="/recovery", tags=["recovery"], dependencies=[Depends(require_feature("recovery"))]
)


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> RecoveryService:
    return RecoveryService(session, settings, clock)


@admin_router.get(
    "/booked-flights",
    response_model=BookedFlightListOut,
    responses=_ERRORS,
    summary="Upcoming flights with seats sold",
)
def booked_flights(
    _: User = Depends(require_role(UserRole.ADMIN)), service: RecoveryService = Depends(_service)
) -> BookedFlightListOut:
    return service.booked_flights()


@admin_router.get(
    "/disruptions",
    response_model=DisruptionListOut,
    responses=_ERRORS,
    summary="Recorded disruptions",
)
def disruptions(
    _: User = Depends(require_role(UserRole.ADMIN)), service: RecoveryService = Depends(_service)
) -> DisruptionListOut:
    return service.disruptions()


@admin_router.post(
    "/disruptions",
    response_model=DisruptionOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Record a cancellation, delay or room outage and open recovery cases",
)
def disrupt(
    body: DisruptionIn,
    operator: User = Depends(require_role(UserRole.ADMIN)),
    service: RecoveryService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> DisruptionOut:
    return service.disrupt(operator, body, meta)


@router.get(
    "/cases",
    response_model=RecoveryCaseListOut,
    responses=_ERRORS,
    summary="My recovery cases, open first",
)
def cases(
    booking_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    service: RecoveryService = Depends(_service),
) -> RecoveryCaseListOut:
    return service.cases(user, booking_id)


@router.get(
    "/cases/{case_id}",
    response_model=RecoveryCaseOut,
    responses=_ERRORS,
    summary="One recovery case with its options",
)
def case(
    case_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: RecoveryService = Depends(_service),
) -> RecoveryCaseOut:
    return service.case(user, case_id)


@router.post(
    "/cases/{case_id}/accept",
    response_model=RecoveryCaseOut,
    responses=_ERRORS,
    summary="Choose an option; only the affected item changes",
)
def accept(
    case_id: uuid.UUID,
    body: AcceptIn,
    user: User = Depends(get_current_user),
    service: RecoveryService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> RecoveryCaseOut:
    return service.accept(user, case_id, body.option_id, meta)
