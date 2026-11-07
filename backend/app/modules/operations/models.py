"""Operational events that change what can be sold: flight cancellations and delays, rooms
taken out of service. Kept apart from the catalog, which only changes through imports."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class DisruptionKind(enum.StrEnum):
    FLIGHT_CANCELLED = "flight_cancelled"
    FLIGHT_DELAYED = "flight_delayed"
    ROOM_UNAVAILABLE = "room_unavailable"


class Disruption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "disruptions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('flight_cancelled', 'flight_delayed', 'room_unavailable')", name="kind_valid"
        ),
        CheckConstraint(
            "(kind = 'room_unavailable' AND room_type_id IS NOT NULL AND starts_on IS NOT NULL "
            "AND ends_on IS NOT NULL) OR (kind <> 'room_unavailable' AND flight_id IS NOT NULL)",
            name="target_present",
        ),
    )

    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    flight_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("flights.id", ondelete="CASCADE"), index=True
    )
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("room_types.id", ondelete="CASCADE"), index=True
    )
    starts_on: Mapped[date | None] = mapped_column(Date)  # first unavailable night
    ends_on: Mapped[date | None] = mapped_column(Date)  # morning after the last unavailable night
    delay_minutes: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    affected_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
