from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TripPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A connected-trip plan (plan v2, G7): the request, the ranked bundles as generated
    (a snapshot, so the explanation stays true to what was shown), and the traveller's
    saved or dismissed decisions, which survive reloads and devices."""

    __tablename__ = "trip_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    option_states: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    notices: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
