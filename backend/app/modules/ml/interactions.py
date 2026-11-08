"""What signed-in travellers do with stays: viewed, saved, booked.

The log is the training signal for the preference model (`ml/preferences.py`). It holds no
personal details beyond the user ID, and rows are deleted with the account.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

InteractionKind = Literal["view", "save", "book"]


class HotelInteraction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "hotel_interactions"
    __table_args__ = (
        CheckConstraint("kind IN ('view', 'save', 'book')", name="kind_valid"),
        Index("ix_hotel_interactions_user_time", "user_id", "occurred_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def record_interaction(
    session: Session, user_id: uuid.UUID, hotel_id: uuid.UUID, kind: InteractionKind, at: datetime
) -> None:
    """Adds the row to the caller's transaction; the caller commits."""
    session.add(HotelInteraction(user_id=user_id, hotel_id=hotel_id, kind=kind, occurred_at=at))
