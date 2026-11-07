"""Connected-trip planner endpoints. Plans belong to the signed-in traveller."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_settings_dep, rate_limit, require_feature
from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.planner.schemas import OptionStateIn, PlanListOut, PlanOut, PlanRequest
from app.modules.planner.service import PlannerService

router = APIRouter(
    prefix="/plans", tags=["planner"], dependencies=[Depends(require_feature("trip_planner"))]
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> PlannerService:
    return PlannerService(session, settings, clock)


@router.post(
    "",
    response_model=PlanOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("plans.create", limit=20, window_seconds=60))],
    summary="Plan a connected trip: ranked flight + stay bundles with confidence checks",
)
def create_plan(
    body: PlanRequest,
    user: User = Depends(get_current_user),
    service: PlannerService = Depends(_service),
) -> PlanOut:
    return service.generate(user, body)


@router.get("", response_model=PlanListOut, responses=_ERRORS, summary="My saved plans")
def list_plans(
    user: User = Depends(get_current_user), service: PlannerService = Depends(_service)
) -> PlanListOut:
    return service.plans(user)


@router.get("/{plan_id}", response_model=PlanOut, responses=_ERRORS, summary="One plan")
def get_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: PlannerService = Depends(_service),
) -> PlanOut:
    return service.get(user, plan_id)


@router.put(
    "/{plan_id}/options/{option_id}",
    response_model=PlanOut,
    responses=_ERRORS,
    summary="Save or dismiss an option; the decision is remembered",
)
def set_option_state(
    plan_id: uuid.UUID,
    option_id: str,
    body: OptionStateIn,
    user: User = Depends(get_current_user),
    service: PlannerService = Depends(_service),
) -> PlanOut:
    return service.set_state(user, plan_id, option_id, body.state)
