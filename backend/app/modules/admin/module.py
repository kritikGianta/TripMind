"""Admin console reads: business analytics and the audit log. Read-only; admins only."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.deps import get_clock
from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.modules.audit.models import AuditLog
from app.modules.auth.dependencies import require_role
from app.modules.auth.models import User, UserRole
from app.modules.bookings.models import Booking, BookingItem, BookingStatus, Refund, Trip
from app.modules.catalog.models import City
from app.modules.planner.models import TripPlan
from app.modules.recovery.models import RecoveryCase
from app.modules.search.pricing import MoneyOut

router = APIRouter(
    prefix="/admin",
    tags=["admin: console"],
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


class CountOut(BaseModel):
    label: str
    value: int


class DayOut(BaseModel):
    day: date
    bookings: int
    value: MoneyOut


class AnalyticsOut(BaseModel):
    currency: str
    travellers: int
    bookings_by_status: list[CountOut]
    confirmed_value: MoneyOut
    refunded_value: MoneyOut
    net_value: MoneyOut
    average_booking_value: MoneyOut | None
    hold_conversion_percent: float | None
    items_by_kind: list[CountOut]
    connected_trips: int
    plans_generated: int
    promo_bookings: int
    top_destinations: list[CountOut]
    recovery_by_status: list[CountOut]
    last_30_days: list[DayOut]
    note: str


class AuditOut(BaseModel):
    occurred_at: datetime
    action: str
    outcome: str
    actor_email: str | None
    request_id: str | None
    ip_address: str | None
    details: dict[str, Any] | None


class AuditPageOut(BaseModel):
    items: list[AuditOut]
    total: int
    actions: list[str]


@router.get(
    "/analytics", response_model=AnalyticsOut, summary="Business overview from the database"
)
def analytics(
    _: Admin, session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> AnalyticsOut:
    currency = session.scalar(select(Booking.currency).limit(1)) or "INR"

    def money(value: int | None) -> MoneyOut:
        return MoneyOut(amount_minor=int(value or 0), currency=currency)

    by_status = dict(
        session.execute(select(Booking.status, func.count()).group_by(Booking.status))
        .tuples()
        .all()
    )
    confirmed_value = int(
        session.scalar(
            select(func.coalesce(func.sum(Booking.total_minor), 0)).where(
                Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CANCELLED]),
                Booking.confirmed_at.is_not(None),
            )
        )
        or 0
    )
    refunded = int(session.scalar(select(func.coalesce(func.sum(Refund.amount_minor), 0))) or 0)
    paid_count = int(
        session.scalar(
            select(func.count()).select_from(Booking).where(Booking.confirmed_at.is_not(None))
        )
        or 0
    )
    holds = sum(by_status.values())
    kinds = dict(
        session.execute(
            select(BookingItem.kind, func.count())
            .where(BookingItem.status == "confirmed")
            .group_by(BookingItem.kind)
        )
        .tuples()
        .all()
    )
    connected = int(
        session.scalar(
            select(func.count()).select_from(
                select(Booking.trip_id)
                .join(BookingItem, BookingItem.booking_id == Booking.id)
                .where(BookingItem.status == "confirmed")
                .group_by(Booking.trip_id)
                .having(func.count(func.distinct(BookingItem.kind)) == 2)
                .subquery()
            )
        )
        or 0
    )
    destinations = (
        session.execute(
            select(City.name, func.count())
            .join(Trip, Trip.destination_city_id == City.id)
            .join(Booking, Booking.trip_id == Trip.id)
            .where(Booking.confirmed_at.is_not(None))
            .group_by(City.name)
            .order_by(func.count().desc())
            .limit(5)
        )
        .tuples()
        .all()
    )
    recovery = dict(
        session.execute(
            select(
                func.coalesce(RecoveryCase.resolution, RecoveryCase.status), func.count()
            ).group_by(func.coalesce(RecoveryCase.resolution, RecoveryCase.status))
        )
        .tuples()
        .all()
    )
    since = clock.now() - timedelta(days=30)
    days = (
        session.execute(
            select(func.date(Booking.confirmed_at), func.count(), func.sum(Booking.total_minor))
            .where(Booking.confirmed_at >= since)
            .group_by(func.date(Booking.confirmed_at))
            .order_by(func.date(Booking.confirmed_at))
        )
        .tuples()
        .all()
    )
    return AnalyticsOut(
        currency=currency,
        travellers=int(
            session.scalar(
                select(func.count()).select_from(User).where(User.role == UserRole.TRAVELER)
            )
            or 0
        ),
        bookings_by_status=[CountOut(label=k, value=v) for k, v in sorted(by_status.items())],
        confirmed_value=money(confirmed_value),
        refunded_value=money(refunded),
        net_value=money(confirmed_value - refunded),
        average_booking_value=money(confirmed_value // paid_count) if paid_count else None,
        hold_conversion_percent=round(100 * paid_count / holds, 1) if holds else None,
        items_by_kind=[CountOut(label=k, value=v) for k, v in sorted(kinds.items())],
        connected_trips=connected,
        plans_generated=int(session.scalar(select(func.count()).select_from(TripPlan)) or 0),
        promo_bookings=int(
            session.scalar(
                select(func.count())
                .select_from(Booking)
                .where(Booking.promo_code.is_not(None), Booking.confirmed_at.is_not(None))
            )
            or 0
        ),
        top_destinations=[CountOut(label=name, value=n) for name, n in destinations],
        recovery_by_status=[CountOut(label=k, value=v) for k, v in sorted(recovery.items())],
        last_30_days=[
            DayOut(
                day=d if isinstance(d, date) else date.fromisoformat(str(d)),
                bookings=n,
                value=money(v),
            )
            for d, n, v in days
            if d is not None
        ],
        note="Simulated payments on demo data; not real revenue.",
    )


@router.get("/audit", response_model=AuditPageOut, summary="Audit log, newest first")
def audit(
    _: Admin,
    action: str | None = None,
    outcome: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
) -> AuditPageOut:
    query = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_user_id)
    count = select(func.count()).select_from(AuditLog)
    if action:
        query, count = (
            query.where(AuditLog.action == action),
            count.where(AuditLog.action == action),
        )
    if outcome:
        query = query.where(AuditLog.outcome == outcome)
        count = count.where(AuditLog.outcome == outcome)
    rows = (
        session.execute(query.order_by(AuditLog.occurred_at.desc()).limit(limit).offset(offset))
        .tuples()
        .all()
    )
    actions = list(session.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)))
    return AuditPageOut(
        items=[
            AuditOut(
                occurred_at=log.occurred_at,
                action=log.action,
                outcome=log.outcome,
                actor_email=email,
                request_id=log.request_id,
                ip_address=log.ip_address,
                details=log.details,
            )
            for log, email in rows
        ],
        total=int(session.scalar(count) or 0),
        actions=actions,
    )
