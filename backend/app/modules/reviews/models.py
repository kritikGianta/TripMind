"""Reviews written in TripMind by travellers who completed a stay."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class StayReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "stay_reviews"
    __table_args__ = (
        UniqueConstraint("booking_item_id", name="uq_stay_reviews_item"),
        CheckConstraint("rating >= 1 AND rating <= 10", name="rating_range"),
        CheckConstraint("status IN ('published', 'removed')", name="status_valid"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("booking_items.id", ondelete="CASCADE"), nullable=False
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    title: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    traveller_type: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
