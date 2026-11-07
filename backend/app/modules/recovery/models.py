from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class RecoveryCase(UUIDPrimaryKeyMixin, Base):
    """One disrupted booking item and the ways out offered to its traveller (plan v2, G6).

    Options are a snapshot taken when the disruption happened; accepting one re-checks price
    and availability before anything changes.
    """

    __tablename__ = "recovery_cases"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved', 'closed')", name="status_valid"),
    )

    disruption_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("disruptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("booking_items.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(String(16))  # rebooked | refunded | kept
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    impact: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    chosen_option_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
