"""Support requests: travellers open and follow tickets; admins work the queue."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_request_meta, get_settings_dep, rate_limit, require_feature
from app.core.errors import ErrorEnvelope
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.auth.models import User, UserRole
from app.modules.support.service import (
    AgentReplyIn,
    Category,
    MessageIn,
    Status,
    SupportService,
    TicketIn,
    TicketListOut,
    TicketOut,
    TicketUpdateIn,
)

router = APIRouter(tags=["support"], dependencies=[Depends(require_feature("support"))])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}
Traveller = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> SupportService:
    return SupportService(session, settings, clock)


Service = Annotated[SupportService, Depends(_service)]


@router.post(
    "/support/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("support.create", limit=10, window_seconds=300))],
    summary="Open a support request (filed by category automatically)",
)
def create_ticket(body: TicketIn, user: Traveller, service: Service, meta: Meta) -> TicketOut:
    return service.create(user, body, meta)


@router.get(
    "/support/tickets",
    response_model=TicketListOut,
    responses=_ERRORS,
    summary="My support requests",
)
def my_tickets(user: Traveller, service: Service) -> TicketListOut:
    return service.mine(user)


@router.get(
    "/support/tickets/{ticket_id}",
    response_model=TicketOut,
    responses=_ERRORS,
    summary="One of my requests",
)
def my_ticket(ticket_id: uuid.UUID, user: Traveller, service: Service) -> TicketOut:
    return service.get(user, ticket_id)


@router.post(
    "/support/tickets/{ticket_id}/messages",
    response_model=TicketOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("support.reply", limit=30, window_seconds=300))],
    summary="Add a message to my request (reopens it if resolved)",
)
def reply(ticket_id: uuid.UUID, body: MessageIn, user: Traveller, service: Service) -> TicketOut:
    return service.reply(user, ticket_id, body)


@router.post(
    "/support/tickets/{ticket_id}/close",
    response_model=TicketOut,
    responses=_ERRORS,
    summary="Close my request",
)
def close(ticket_id: uuid.UUID, user: Traveller, service: Service) -> TicketOut:
    return service.close(user, ticket_id)


@router.get(
    "/admin/support/tickets",
    response_model=TicketListOut,
    responses=_ERRORS,
    summary="Support queue: urgent first, then oldest (open and waiting by default)",
)
def queue(
    _: Admin, service: Service, status: Status | None = None, category: Category | None = None
) -> TicketListOut:
    return service.queue(status, category)


@router.get(
    "/admin/support/tickets/{ticket_id}",
    response_model=TicketOut,
    responses=_ERRORS,
    summary="One request",
)
def agent_view(ticket_id: uuid.UUID, _: Admin, service: Service) -> TicketOut:
    return service.agent_view(ticket_id)


@router.post(
    "/admin/support/tickets/{ticket_id}/messages",
    response_model=TicketOut,
    responses=_ERRORS,
    summary="Reply as an agent (the traveller is notified)",
)
def agent_reply(
    ticket_id: uuid.UUID, body: AgentReplyIn, agent: Admin, service: Service, meta: Meta
) -> TicketOut:
    return service.agent_reply(agent, ticket_id, body, meta)


@router.patch(
    "/admin/support/tickets/{ticket_id}",
    response_model=TicketOut,
    responses=_ERRORS,
    summary="Re-file, re-prioritise or change the status of a request (audited)",
)
def update(
    ticket_id: uuid.UUID, body: TicketUpdateIn, agent: Admin, service: Service, meta: Meta
) -> TicketOut:
    return service.update(agent, ticket_id, body, meta)
