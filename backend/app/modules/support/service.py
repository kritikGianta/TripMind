"""Support tickets: travellers write in, the request classifier files the ticket, agents reply.

Category comes from the request classifier (model when trained, keyword rules otherwise; the
ticket records which). A ticket is high priority when the traveller asks for a person or when the
linked booking starts within `support.urgent_within_hours`. Agents can re-file a ticket; that is
audited and the source becomes `admin`.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.metrics import SUPPORT_TICKETS
from app.core.request_context import RequestMeta
from app.modules.audit.service import AuditService
from app.modules.auth.models import User
from app.modules.bookings.models import Booking, BookingItem, ItemStatus
from app.modules.ml.request_classifier import CATEGORIES, LABELS, RequestClassifier
from app.modules.notifications.service import NotificationService
from app.modules.search.pricing import rules_section
from app.modules.support.models import SupportTicket, TicketMessage

Status = Literal["open", "waiting_on_traveller", "resolved", "closed"]
Category = Literal[
    "baggage_seats",
    "cancellation_refund",
    "change_booking",
    "check_in_boarding",
    "existing_booking",
    "flight_status",
    "human_agent",
    "insurance",
    "new_booking",
    "other",
]
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SupportRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urgent_within_hours: int = Field(default=72, ge=1)
    max_open_tickets: int = Field(default=10, ge=1)


class TicketIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(min_length=4, max_length=140)
    message: str = Field(min_length=10, max_length=4000)
    booking_id: uuid.UUID | None = None


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=4000)


class AgentReplyIn(MessageIn):
    status: Literal["waiting_on_traveller", "resolved"] = "waiting_on_traveller"


class TicketUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category | None = None
    priority: Literal["normal", "high"] | None = None
    status: Status | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    author_role: str
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    reference: str
    subject: str
    booking_id: uuid.UUID | None
    booking_reference: str | None
    category: str
    category_label: str
    category_source: str = Field(description="'model:<version>', 'rules' or 'admin'")
    confidence: float
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    messages: list[MessageOut]


class TicketSummaryOut(BaseModel):
    id: uuid.UUID
    reference: str
    subject: str
    category: str
    category_label: str
    priority: str
    status: str
    updated_at: datetime
    traveller_email: str | None = None


class TicketListOut(BaseModel):
    items: list[TicketSummaryOut]
    counts: dict[str, int] = Field(description="Tickets per status in this list's scope")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SupportService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._rules = SupportRules.model_validate(rules_section(settings.config_dir, "support"))
        self._classifier = RequestClassifier(settings.models_dir)
        self._notifications = NotificationService(session)
        self._audit = AuditService(session)

    # ------------------------------------------------------------------ helpers

    def _reference(self) -> str:
        while True:
            ref = "SR" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
            if (
                self._session.scalar(select(SupportTicket.id).where(SupportTicket.reference == ref))
                is None
            ):
                return ref

    def _message(
        self, ticket: SupportTicket, role: str, body: str, author: uuid.UUID | None
    ) -> None:
        self._session.flush()  # the session does not autoflush; count earlier messages
        position = self._session.scalar(
            select(func.count())
            .select_from(TicketMessage)
            .where(TicketMessage.ticket_id == ticket.id)
        )
        self._session.add(
            TicketMessage(
                ticket_id=ticket.id,
                position=int(position or 0),
                author_user_id=author,
                author_role=role,
                body=body,
                created_at=self._clock.now(),
            )
        )

    def _out(self, ticket: SupportTicket) -> TicketOut:
        messages = self._session.scalars(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket.id)
            .order_by(TicketMessage.position)
        )
        booking = self._session.get(Booking, ticket.booking_id) if ticket.booking_id else None
        return TicketOut(
            id=ticket.id,
            reference=ticket.reference,
            subject=ticket.subject,
            booking_id=ticket.booking_id,
            booking_reference=booking.reference if booking else None,
            category=ticket.category,
            category_label=LABELS.get(ticket.category, ticket.category),
            category_source=ticket.category_source,
            confidence=ticket.confidence,
            priority=ticket.priority,
            status=ticket.status,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
            messages=[
                MessageOut(id=m.id, author_role=m.author_role, body=m.body, created_at=m.created_at)
                for m in messages
            ],
        )

    def _summary(self, ticket: SupportTicket, email: str | None = None) -> TicketSummaryOut:
        return TicketSummaryOut(
            id=ticket.id,
            reference=ticket.reference,
            subject=ticket.subject,
            category=ticket.category,
            category_label=LABELS.get(ticket.category, ticket.category),
            priority=ticket.priority,
            status=ticket.status,
            updated_at=ticket.updated_at,
            traveller_email=email,
        )

    def _owned(self, user: User, ticket_id: uuid.UUID) -> SupportTicket:
        ticket = self._session.get(SupportTicket, ticket_id)
        if ticket is None or ticket.user_id != user.id:
            raise NotFound("Ticket not found.", code="TICKET_NOT_FOUND")
        return ticket

    def _counts(self, user_id: uuid.UUID | None) -> dict[str, int]:
        query = select(SupportTicket.status, func.count()).group_by(SupportTicket.status)
        if user_id is not None:
            query = query.where(SupportTicket.user_id == user_id)
        found = {status: int(n) for status, n in self._session.execute(query)}
        return {s: found.get(s, 0) for s in ("open", "waiting_on_traveller", "resolved", "closed")}

    def _urgent_booking(self, booking: Booking | None) -> bool:
        if booking is None:
            return False
        starts = self._session.scalar(
            select(func.min(BookingItem.starts_at)).where(
                BookingItem.booking_id == booking.id,
                BookingItem.status == ItemStatus.CONFIRMED,
            )
        )
        if starts is None:
            return False
        now = self._clock.now()
        return now <= _aware(starts) <= now + timedelta(hours=self._rules.urgent_within_hours)

    # ------------------------------------------------------------------ travellers

    def create(self, user: User, request: TicketIn, meta: RequestMeta) -> TicketOut:
        open_count = self._session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(
                SupportTicket.user_id == user.id,
                SupportTicket.status.in_(("open", "waiting_on_traveller")),
            )
        )
        if (open_count or 0) >= self._rules.max_open_tickets:
            raise Conflict(
                "You have several open requests; add to one of those instead.",
                code="TICKET_LIMIT",
            )
        booking = None
        if request.booking_id is not None:
            booking = self._session.get(Booking, request.booking_id)
            if booking is None or booking.user_id != user.id:
                raise NotFound("Booking not found.", code="BOOKING_NOT_FOUND")
        result = self._classifier.classify(f"{request.subject}. {request.message}")
        urgent = result.category == "human_agent" or self._urgent_booking(booking)
        now = self._clock.now()
        ticket = SupportTicket(
            reference=self._reference(),
            user_id=user.id,
            booking_id=booking.id if booking else None,
            subject=request.subject,
            category=result.category,
            category_source=result.source,
            confidence=result.confidence,
            priority="high" if urgent else "normal",
            status="open",
            created_at=now,
            updated_at=now,
        )
        self._session.add(ticket)
        self._message(ticket, "traveller", request.message, user.id)
        self._message(
            ticket,
            "system",
            f'Request {ticket.reference} received and filed under "{result.label}"'
            + (" as urgent" if urgent else "")
            + ". An agent will reply here; you will also get a notification.",
            None,
        )
        self._audit.record(
            action="support.ticket_created",
            outcome="success",
            meta=meta,
            actor_user_id=user.id,
            details={
                "ticket": ticket.reference,
                "category": result.category,
                "source": result.source,
            },
        )
        self._session.commit()
        SUPPORT_TICKETS.labels(
            category=result.category, source="model" if result.source != "rules" else "rules"
        ).inc()
        return self._out(ticket)

    def mine(self, user: User) -> TicketListOut:
        tickets = self._session.scalars(
            select(SupportTicket)
            .where(SupportTicket.user_id == user.id)
            .order_by(SupportTicket.updated_at.desc())
        )
        return TicketListOut(
            items=[self._summary(t) for t in tickets], counts=self._counts(user.id)
        )

    def get(self, user: User, ticket_id: uuid.UUID) -> TicketOut:
        return self._out(self._owned(user, ticket_id))

    def reply(self, user: User, ticket_id: uuid.UUID, request: MessageIn) -> TicketOut:
        ticket = self._owned(user, ticket_id)
        if ticket.status == "closed":
            raise Conflict("This request is closed; open a new one.", code="TICKET_CLOSED")
        self._message(ticket, "traveller", request.body, user.id)
        ticket.status, ticket.resolved_at = "open", None  # a reply reopens a resolved ticket
        ticket.updated_at = self._clock.now()
        self._session.commit()
        return self._out(ticket)

    def close(self, user: User, ticket_id: uuid.UUID) -> TicketOut:
        ticket = self._owned(user, ticket_id)
        if ticket.status != "closed":
            now = self._clock.now()
            ticket.status, ticket.updated_at = "closed", now
            ticket.resolved_at = ticket.resolved_at or now
            self._message(ticket, "system", "Closed by the traveller.", None)
            self._session.commit()
        return self._out(ticket)

    # ------------------------------------------------------------------ agents

    def queue(self, status: Status | None, category: Category | None) -> TicketListOut:
        query = (
            select(SupportTicket, User.email)
            .join(User, User.id == SupportTicket.user_id)
            .order_by(
                case((SupportTicket.priority == "high", 0), else_=1),
                SupportTicket.created_at,
            )
            .limit(200)
        )
        if status is not None:
            query = query.where(SupportTicket.status == status)
        else:
            query = query.where(SupportTicket.status.in_(("open", "waiting_on_traveller")))
        if category is not None:
            query = query.where(SupportTicket.category == category)
        rows = self._session.execute(query)
        return TicketListOut(
            items=[self._summary(t, email) for t, email in rows], counts=self._counts(None)
        )

    def agent_view(self, ticket_id: uuid.UUID) -> TicketOut:
        ticket = self._session.get(SupportTicket, ticket_id)
        if ticket is None:
            raise NotFound("Ticket not found.", code="TICKET_NOT_FOUND")
        return self._out(ticket)

    def agent_reply(
        self, agent: User, ticket_id: uuid.UUID, request: AgentReplyIn, meta: RequestMeta
    ) -> TicketOut:
        ticket = self._session.get(SupportTicket, ticket_id)
        if ticket is None:
            raise NotFound("Ticket not found.", code="TICKET_NOT_FOUND")
        if ticket.status == "closed":
            raise Conflict("This request is closed.", code="TICKET_CLOSED")
        now = self._clock.now()
        self._message(ticket, "agent", request.body, agent.id)
        ticket.status, ticket.updated_at = request.status, now
        ticket.resolved_at = now if request.status == "resolved" else None
        self._notifications.notify(
            user_id=ticket.user_id,
            kind="support_reply",
            title=f"Reply on request {ticket.reference}",
            body=request.body[:180] + ("…" if len(request.body) > 180 else ""),
            link=f"/support/{ticket.id}",
            now=now,
        )
        self._audit.record(
            action="support.agent_reply",
            outcome="success",
            meta=meta,
            actor_user_id=agent.id,
            details={"ticket": ticket.reference, "status": request.status},
        )
        self._session.commit()
        return self._out(ticket)

    def update(
        self, agent: User, ticket_id: uuid.UUID, request: TicketUpdateIn, meta: RequestMeta
    ) -> TicketOut:
        ticket = self._session.get(SupportTicket, ticket_id)
        if ticket is None:
            raise NotFound("Ticket not found.", code="TICKET_NOT_FOUND")
        changes = request.model_dump(exclude_none=True)
        if not changes:
            raise ValidationFailed("Nothing to change.", code="NOTHING_TO_CHANGE")
        if request.category is not None and request.category not in CATEGORIES:
            raise ValidationFailed("Unknown category.", code="CATEGORY_UNKNOWN")
        before = {k: getattr(ticket, k) for k in changes}
        for key, value in changes.items():
            setattr(ticket, key, value)
        if request.category is not None:
            ticket.category_source, ticket.confidence = "admin", 1.0
        if request.status in ("resolved", "closed"):
            ticket.resolved_at = ticket.resolved_at or self._clock.now()
        ticket.updated_at = self._clock.now()
        self._audit.record(
            action="support.ticket_updated",
            outcome="success",
            meta=meta,
            actor_user_id=agent.id,
            details={"ticket": ticket.reference, "before": before, "after": changes},
        )
        self._session.commit()
        return self._out(ticket)
