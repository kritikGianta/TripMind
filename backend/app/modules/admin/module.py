"""Admin console: analytics, the audit log, model status and account management. Admins only."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.deps import get_clock, get_request_meta
from app.core.errors import Conflict, ErrorEnvelope, NotFound
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditService
from app.modules.auth.dependencies import require_role
from app.modules.auth.models import User, UserRole
from app.modules.auth.repository import RefreshTokenRepository
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
        session.execute(select(Booking.status, func.count()).group_by(Booking.status)).all()
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
        ).all()
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
    destinations = session.execute(
        select(City.name, func.count())
        .join(Trip, Trip.destination_city_id == City.id)
        .join(Booking, Booking.trip_id == Trip.id)
        .where(Booking.confirmed_at.is_not(None))
        .group_by(City.name)
        .order_by(func.count().desc())
        .limit(5)
    ).all()
    recovery = dict(
        session.execute(
            select(
                func.coalesce(RecoveryCase.resolution, RecoveryCase.status), func.count()
            ).group_by(func.coalesce(RecoveryCase.resolution, RecoveryCase.status))
        ).all()
    )
    since = clock.now() - timedelta(days=30)
    days = session.execute(
        select(func.date(Booking.confirmed_at), func.count(), func.sum(Booking.total_minor))
        .where(Booking.confirmed_at >= since)
        .group_by(func.date(Booking.confirmed_at))
        .order_by(func.date(Booking.confirmed_at))
    ).all()
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
    rows = session.execute(
        query.order_by(AuditLog.occurred_at.desc()).limit(limit).offset(offset)
    ).all()
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


# ------------------------------------------------------------------------------ users


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    bookings: int


class AdminUserPageOut(BaseModel):
    items: list[AdminUserOut]
    total: int


class UserStatusIn(BaseModel):
    active: bool


def _user_out(session: Session, user: User) -> AdminUserOut:
    bookings = session.scalar(
        select(func.count()).select_from(Booking).where(Booking.user_id == user.id)
    )
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        bookings=int(bookings or 0),
    )


@router.get("/users", response_model=AdminUserPageOut, summary="Find accounts")
def list_users(
    _: Admin,
    session: Session = Depends(get_session),
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserPageOut:
    query = select(User)
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.where(
            func.lower(User.email).like(needle) | func.lower(User.full_name).like(needle)
        )
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    users = session.scalars(query.order_by(User.created_at.desc()).limit(limit).offset(offset))
    return AdminUserPageOut(items=[_user_out(session, u) for u in users], total=int(total or 0))


@router.post(
    "/users/{user_id}/status",
    response_model=AdminUserOut,
    responses={404: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
    summary="Disable or re-enable an account (audited; disabling ends its sessions)",
)
def set_user_status(
    user_id: uuid.UUID,
    body: UserStatusIn,
    admin: Admin,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    meta: RequestMeta = Depends(get_request_meta),
) -> AdminUserOut:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound("Account not found.", code="USER_NOT_FOUND")
    if user.id == admin.id:
        raise Conflict("You cannot change your own account status.", code="CANNOT_CHANGE_SELF")
    user.is_active = body.active
    if not body.active:
        RefreshTokenRepository(session).revoke_all_for_user(user.id, clock.now())
    AuditService(session).record(
        action="admin.user_status",
        outcome="success",
        meta=meta,
        actor_user_id=admin.id,
        details={"user_id": str(user.id), "active": body.active},
    )
    session.commit()
    return _user_out(session, user)
