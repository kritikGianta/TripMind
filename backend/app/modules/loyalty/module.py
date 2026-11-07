"""Loyalty points: an append-only ledger. Paying earns points; refunds take back the points the
refunded amount had earned, so the balance always matches what the traveller actually paid."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.core.errors import ErrorEnvelope
from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.search.pricing import rules_section


class LoyaltyEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "loyalty_ledger"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("bookings.id", ondelete="SET NULL")
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LoyaltyRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points_per_100: int = Field(default=1, ge=0)
    tiers: dict[str, int] = Field(default_factory=lambda: {"Explorer": 0})


def load_loyalty_rules(config_dir: Path) -> LoyaltyRules:
    return LoyaltyRules.model_validate(rules_section(config_dir, "loyalty"))


class LoyaltyService:
    """Called inside booking and recovery transactions; never commits on its own."""

    def __init__(self, session: Session, rules: LoyaltyRules) -> None:
        self._session = session
        self._rules = rules

    def points_for(self, amount_minor: int) -> int:
        return amount_minor // 100 // 100 * self._rules.points_per_100

    def earn(
        self,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        amount_minor: int,
        reference: str,
        now: datetime,
    ) -> int:
        points = self.points_for(amount_minor)
        if points:
            self._session.add(
                LoyaltyEntry(
                    user_id=user_id,
                    booking_id=booking_id,
                    points=points,
                    reason=f"Booking {reference}",
                    created_at=now,
                )
            )
        return points

    def reverse(
        self,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        refund_minor: int,
        reference: str,
        now: datetime,
    ) -> int:
        points = self.points_for(refund_minor)
        earned = int(
            self._session.scalar(
                select(func.coalesce(func.sum(LoyaltyEntry.points), 0)).where(
                    LoyaltyEntry.booking_id == booking_id
                )
            )
            or 0
        )
        points = min(points, max(earned, 0))  # never take back more than this booking earned
        if points:
            self._session.add(
                LoyaltyEntry(
                    user_id=user_id,
                    booking_id=booking_id,
                    points=-points,
                    reason=f"Refund on {reference}",
                    created_at=now,
                )
            )
        return points


class LoyaltyEntryOut(BaseModel):
    points: int
    reason: str
    created_at: datetime


class LoyaltyOut(BaseModel):
    balance: int
    tier: str
    next_tier: str | None
    points_to_next_tier: int | None
    points_per_100: int
    history: list[LoyaltyEntryOut]


router = APIRouter(
    prefix="/me/loyalty", tags=["account"], responses={401: {"model": ErrorEnvelope}}
)


@router.get("", response_model=LoyaltyOut, summary="My loyalty points and tier")
def my_loyalty(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> LoyaltyOut:
    rules = load_loyalty_rules(settings.config_dir)
    entries = list(
        session.scalars(
            select(LoyaltyEntry)
            .where(LoyaltyEntry.user_id == user.id)
            .order_by(LoyaltyEntry.created_at.desc())
        )
    )
    balance = sum(e.points for e in entries)
    tiers = sorted(rules.tiers.items(), key=lambda t: t[1])
    tier = next((name for name, floor in reversed(tiers) if balance >= floor), tiers[0][0])
    upcoming = next(((name, floor) for name, floor in tiers if floor > balance), None)
    return LoyaltyOut(
        balance=balance,
        tier=tier,
        next_tier=upcoming[0] if upcoming else None,
        points_to_next_tier=upcoming[1] - balance if upcoming else None,
        points_per_100=rules.points_per_100,
        history=[
            LoyaltyEntryOut(points=e.points, reason=e.reason, created_at=e.created_at)
            for e in entries[:20]
        ],
    )
