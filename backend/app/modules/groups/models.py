"""Group trip planning: a plan shared with friends who vote on its options."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class TripGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "trip_groups"
    __table_args__ = (CheckConstraint("status IN ('open', 'decided')", name="status_valid"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("trip_plans.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invite_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    decided_option_id: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class GroupMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_members_member"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(8), nullable=False)  # owner | member
    # Most this member wants to pay for their share, in the display currency (major units).
    max_budget_per_person: Mapped[int | None] = mapped_column(Integer)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GroupVote(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "group_votes"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "option_id", name="uq_group_votes_ballot"),
        CheckConstraint("value IN (-2, 1, 2)", name="value_valid"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("trip_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)  # love 2, ok 1, no -2 (veto)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
