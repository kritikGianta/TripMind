"""Saved stays and price alerts, owned by one traveller each."""

from __future__ import annotations

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

from app.db.base import Base, UUIDPrimaryKeyMixin


class SavedHotel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saved_hotels"
    __table_args__ = (UniqueConstraint("user_id", "hotel_id", name="uq_saved_hotels_user_hotel"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PriceAlert(UUIDPrimaryKeyMixin, Base):
    """Watch one flight search or one stay for a price drop. One-shot: it fires once."""

    __tablename__ = "price_alerts"
    __table_args__ = (
        CheckConstraint("kind IN ('flight', 'hotel')", name="kind_valid"),
        CheckConstraint(
            "status IN ('active', 'triggered', 'expired', 'cancelled')", name="status_valid"
        ),
        Index("ix_price_alerts_status_travel", "status", "travel_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_minor: Mapped[int | None] = mapped_column(Integer)
    baseline_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    last_price_minor: Mapped[int | None] = mapped_column(Integer)
    lowest_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
