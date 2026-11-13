"""A built holiday package, saved so it survives a refresh and a backend restart (M7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HolidayPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One package: the request it answers, its items (shared trip format) and its status.

    `reference` is the 10-digit reservation number, set only when the traveller confirms.
    """

    __tablename__ = "holiday_packages"
    __table_args__ = (
        CheckConstraint("status IN ('PLANNED', 'BOOKED')", name="status_valid"),
        CheckConstraint("total_inr >= 0", name="total_non_negative"),
    )

    # The traveller (often a guest) who built it, so it shows in their My Trips.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    label: Mapped[str] = mapped_column(String(16), nullable=False)  # cheapest, fastest, ...
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="PLANNED")
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    total_inr: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
