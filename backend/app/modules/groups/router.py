from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.deps import get_clock, rate_limit, require_feature
from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.groups.service import GroupOut, GroupService, GroupSummaryOut, Vote

router = APIRouter(tags=["groups"], dependencies=[Depends(require_feature("group_planning"))])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}
Member = Annotated[User, Depends(get_current_user)]


def _service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> GroupService:
    return GroupService(session, clock)


class JoinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite_code: str = Field(min_length=6, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")


class VoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vote: Vote


class BudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_budget_per_person: Annotated[int | None, Field(ge=1)] = None


class DecideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str = Field(min_length=1, max_length=32)


class GroupListOut(BaseModel):
    items: list[GroupSummaryOut]


@router.post(
    "/plans/{plan_id}/group",
    response_model=GroupOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Share a plan with a group (returns the existing group if already shared)",
)
def create_group(
    plan_id: uuid.UUID, user: Member, service: GroupService = Depends(_service)
) -> GroupOut:
    return service.create(user, plan_id)


@router.post(
    "/groups/join",
    response_model=GroupOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("groups.join", limit=20, window_seconds=60))],
    summary="Join a group with its invite code",
)
def join_group(body: JoinIn, user: Member, service: GroupService = Depends(_service)) -> GroupOut:
    return service.join(user, body.invite_code)


@router.get("/groups", response_model=GroupListOut, responses=_ERRORS, summary="My groups")
def my_groups(user: Member, service: GroupService = Depends(_service)) -> GroupListOut:
    return GroupListOut(items=service.mine(user))


@router.get(
    "/groups/{group_id}",
    response_model=GroupOut,
    responses=_ERRORS,
    summary="A group's options, votes and current consensus",
)
def get_group(
    group_id: uuid.UUID, user: Member, service: GroupService = Depends(_service)
) -> GroupOut:
    return service.get(user, group_id)


@router.put(
    "/groups/{group_id}/votes/{option_id}",
    response_model=GroupOut,
    responses=_ERRORS,
    summary="Vote Love, OK or No (veto) on an option; 'none' clears the vote",
)
def vote(
    group_id: uuid.UUID,
    option_id: str,
    body: VoteIn,
    user: Member,
    service: GroupService = Depends(_service),
) -> GroupOut:
    return service.vote(user, group_id, option_id, body.vote)


@router.put(
    "/groups/{group_id}/me",
    response_model=GroupOut,
    responses=_ERRORS,
    summary="Set my per-person budget for this trip",
)
def set_budget(
    group_id: uuid.UUID, body: BudgetIn, user: Member, service: GroupService = Depends(_service)
) -> GroupOut:
    return service.set_budget(user, group_id, body.max_budget_per_person)


@router.post(
    "/groups/{group_id}/decide",
    response_model=GroupOut,
    responses=_ERRORS,
    summary="Owner confirms the option the group will book",
)
def decide(
    group_id: uuid.UUID, body: DecideIn, user: Member, service: GroupService = Depends(_service)
) -> GroupOut:
    return service.decide(user, group_id, body.option_id)


@router.delete(
    "/groups/{group_id}/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Leave a group (members only)",
)
def leave(group_id: uuid.UUID, user: Member, service: GroupService = Depends(_service)) -> None:
    service.leave(user, group_id)
