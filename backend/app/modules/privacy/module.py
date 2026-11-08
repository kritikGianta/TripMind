"""Personal data rights and retention.

Export: everything TripMind holds about the signed-in traveller, as JSON.
Delete: the account is anonymised and personal activity removed. Booking and payment records stay
for accounting, with names and contact details scrubbed. Refused while a trip is still ahead, so
nobody loses a live booking by accident.
Retention: a daily worker job removes data past the periods in `config/rules.yaml`.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.core.deps import get_clock, get_request_meta, get_settings_dep, rate_limit
from app.core.errors import Conflict, ErrorEnvelope, ValidationFailed
from app.core.request_context import RequestMeta
from app.core.security import hash_password, verify_password
from app.db.session import get_session, get_session_factory
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditService
from app.modules.auth.cookies import clear_session_cookies
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import PasswordResetToken, RefreshToken, User
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.bookings.models import (
    Booking,
    BookingItem,
    BookingTraveller,
    ItemStatus,
    Payment,
    Refund,
)
from app.modules.loyalty.module import LoyaltyEntry
from app.modules.ml.interactions import HotelInteraction
from app.modules.ml.preferences import UserPreference
from app.modules.notifications.models import Notification
from app.modules.profiles.module import TravellerProfile
from app.modules.reviews.models import StayReview
from app.modules.search.history import SearchHistory
from app.modules.search.pricing import rules_section
from app.modules.support.models import SupportTicket, TicketMessage
from app.modules.watchlist.models import PriceAlert, SavedHotel

log = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/me",
    tags=["privacy"],
    responses={401: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
Traveller = Annotated[User, Depends(get_current_user)]


class RetentionRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token_days: int = Field(default=30, ge=1)
    notification_days: int = Field(default=180, ge=1)
    search_history_days: int = Field(default=180, ge=1)
    interaction_days: int = Field(default=365, ge=1)
    audit_days: int = Field(default=730, ge=30)


class DeleteAccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: Annotated[str, Field(min_length=1, max_length=128)]


def _rows(session: Session, model: Any, *where: Any) -> list[dict[str, Any]]:
    columns = [c.name for c in model.__table__.columns]
    return [
        {c: getattr(row, c) for c in columns if c not in {"password_hash", "token_hash"}}
        for row in session.scalars(select(model).where(*where))
    ]


@router.get(
    "/export",
    dependencies=[Depends(rate_limit("privacy.export", limit=5, window_seconds=300))],
    summary="Download everything TripMind holds about me",
)
def export_my_data(
    user: Traveller,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    meta: RequestMeta = Depends(get_request_meta),
) -> dict[str, Any]:
    uid = user.id
    bookings = select(Booking.id).where(Booking.user_id == uid)
    tickets = select(SupportTicket.id).where(SupportTicket.user_id == uid)
    data: dict[str, Any] = {
        "exported_at": clock.now(),
        "account": _rows(session, User, User.id == uid)[0],
        "saved_travellers": _rows(session, TravellerProfile, TravellerProfile.user_id == uid),
        "bookings": _rows(session, Booking, Booking.user_id == uid),
        "booking_items": _rows(session, BookingItem, BookingItem.booking_id.in_(bookings)),
        "booking_travellers": _rows(
            session, BookingTraveller, BookingTraveller.booking_id.in_(bookings)
        ),
        "payments": _rows(session, Payment, Payment.booking_id.in_(bookings)),
        "refunds": _rows(session, Refund, Refund.booking_id.in_(bookings)),
        "loyalty": _rows(session, LoyaltyEntry, LoyaltyEntry.user_id == uid),
        "notifications": _rows(session, Notification, Notification.user_id == uid),
        "recent_searches": _rows(session, SearchHistory, SearchHistory.user_id == uid),
        "saved_stays": _rows(session, SavedHotel, SavedHotel.user_id == uid),
        "price_alerts": _rows(session, PriceAlert, PriceAlert.user_id == uid),
        "reviews": _rows(session, StayReview, StayReview.user_id == uid),
        "support_tickets": _rows(session, SupportTicket, SupportTicket.user_id == uid),
        "support_messages": _rows(session, TicketMessage, TicketMessage.ticket_id.in_(tickets)),
        "stay_activity": _rows(session, HotelInteraction, HotelInteraction.user_id == uid),
        "learned_preferences": _rows(session, UserPreference, UserPreference.user_id == uid),
    }
    AuditService(session).record(
        action="privacy.export", outcome="success", meta=meta, actor_user_id=uid
    )
    session.commit()
    return data


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("privacy.delete", limit=5, window_seconds=300))],
    responses={422: {"model": ErrorEnvelope}},
    summary="Delete my account (bookings kept for accounting, without personal details)",
)
def delete_my_account(
    body: DeleteAccountIn,
    user: Traveller,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings_dep),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    valid, _ = verify_password(body.password, user.password_hash)
    if not valid:
        raise ValidationFailed("Your password is incorrect.", code="WRONG_PASSWORD")
    if user.email in (settings.demo_traveler_email, settings.demo_admin_email):
        raise Conflict("Demo accounts cannot be deleted.", code="DEMO_ACCOUNT")
    now = clock.now()
    upcoming = session.scalar(
        select(BookingItem.id)
        .join(Booking, Booking.id == BookingItem.booking_id)
        .where(
            Booking.user_id == user.id,
            BookingItem.status == ItemStatus.CONFIRMED,
            BookingItem.ends_at > now,
        )
        .limit(1)
    )
    if upcoming is not None:
        raise Conflict(
            "You have a trip ahead. Cancel it or wait until it ends first.",
            code="ACCOUNT_HAS_UPCOMING_TRIPS",
        )
    uid = user.id
    bookings = select(Booking.id).where(Booking.user_id == uid)
    session.execute(
        update(BookingTraveller)
        .where(BookingTraveller.booking_id.in_(bookings))
        .values(first_name="Removed", last_name="Removed", date_of_birth=None)
    )
    session.execute(
        update(Booking)
        .where(Booking.user_id == uid)
        .values(contact_email="removed@deleted.invalid", contact_phone=None)
    )
    for model in (
        TravellerProfile,
        Notification,
        SearchHistory,
        SavedHotel,
        PriceAlert,
        SupportTicket,
        HotelInteraction,
        UserPreference,
        PasswordResetToken,
    ):
        session.execute(delete(model).where(model.user_id == uid))
    RefreshTokenRepository(session).revoke_all_for_user(uid, now)
    user.email = f"deleted-{uid}@deleted.invalid"
    user.full_name = "Deleted traveller"
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.is_active = False
    AuditService(session).record(
        action="privacy.account_deleted", outcome="success", meta=meta, actor_user_id=uid
    )
    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response


def purge_expired(session: Session, rules: RetentionRules, now: datetime) -> dict[str, int]:
    """Delete data past its retention period. Safe to run repeatedly."""

    def older(days: int) -> datetime:
        return now - timedelta(days=days)

    targets: tuple[tuple[str, Any, Any], ...] = (
        ("refresh_tokens", RefreshToken, RefreshToken.expires_at < older(rules.refresh_token_days)),
        (
            "password_resets",
            PasswordResetToken,
            PasswordResetToken.expires_at < older(rules.refresh_token_days),
        ),
        ("notifications", Notification, Notification.created_at < older(rules.notification_days)),
        (
            "search_history",
            SearchHistory,
            SearchHistory.searched_at < older(rules.search_history_days),
        ),
        (
            "stay_activity",
            HotelInteraction,
            HotelInteraction.occurred_at < older(rules.interaction_days),
        ),
        ("audit_log", AuditLog, AuditLog.occurred_at < older(rules.audit_days)),
    )
    removed = {
        name: int(session.execute(delete(model).where(condition)).rowcount or 0)  # type: ignore[attr-defined]
        for name, model, condition in targets
    }
    session.commit()
    return removed


def purge_once(settings: Settings) -> int:
    """Worker job."""
    rules = RetentionRules.model_validate(rules_section(settings.config_dir, "retention"))
    with get_session_factory()() as session:
        removed = purge_expired(session, rules, SystemClock().now())
    if any(removed.values()):
        log.info("retention_purged", **removed)
    return sum(removed.values())
