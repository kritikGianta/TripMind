"""Trips, bookings and everything attached to them.

A trip is what the traveller sees in My Trips. It holds one or more bookings, so a trip can
start with a flight and gain a stay later (add-on booking). A booking is one checkout: it holds
items (a flight offer, a room), its travellers, payments, refunds and a timeline of events.

States
------
Booking: held -> confirmed -> cancelled;  held -> expired;  held -> payment_failed -> confirmed
         (retry within the hold) or expired.
Item:    held -> confirmed -> cancelled | replaced (recovery);  held -> released.
Every price is a snapshot: later catalog changes or re-imports never change a booking.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BookingStatus(enum.StrEnum):
    HELD = "held"
    PAYMENT_FAILED = "payment_failed"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ItemStatus(enum.StrEnum):
    HELD = "held"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    RELEASED = "released"
    REPLACED = "replaced"


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trips"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_city_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('held', 'payment_failed', 'confirmed', 'cancelled', 'expired')",
            name="status_valid",
        ),
        # A retried checkout with the same key returns the first booking (plan v2, G18).
        UniqueConstraint("user_id", "idempotency_key", name="uq_bookings_user_idempotency"),
        Index("ix_bookings_status_hold", "status", "hold_expires_at"),
    )

    reference: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hold_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Charged amount, in the display currency (items keep their own supplier currency).
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    promo_code: Mapped[str | None] = mapped_column(String(24))
    discount_minor: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class BookingItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "booking_items"
    __table_args__ = (
        CheckConstraint("kind IN ('flight', 'hotel')", name="kind_valid"),
        CheckConstraint(
            "status IN ('held', 'confirmed', 'cancelled', 'released', 'replaced')",
            name="status_valid",
        ),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Flight: offer ID ("leg~leg"), adults. Hotel: room type and stay dates.
    offer_id: Mapped[str | None] = mapped_column(String(80))
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    hotel_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # seats or rooms
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    refundable: Mapped[bool | None] = mapped_column()
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    replaced_by_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("booking_items.id", ondelete="SET NULL")
    )


class BookingTraveller(UUIDPrimaryKeyMixin, Base):
    """Travellers as entered at checkout (a snapshot; editing a profile never changes this)."""

    __tablename__ = "booking_travellers"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)


class Payment(UUIDPrimaryKeyMixin, Base):
    """A simulated card payment. Only the brand and last four digits are ever stored."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("status IN ('succeeded', 'failed')", name="status_valid"),
        UniqueConstraint("booking_id", "idempotency_key", name="uq_payments_booking_idempotency"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    card_brand: Mapped[str] = mapped_column(String(16), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(32))
    provider_reference: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class Refund(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refunds"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("booking_items.id", ondelete="CASCADE"), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class BookingEvent(UUIDPrimaryKeyMixin, Base):
    """The booking's timeline, shown to the traveller and used for support."""

    __tablename__ = "booking_events"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
