"""Saved traveller profiles: people a user books for often, used to prefill checkout.

Bookings copy the details at checkout (booking_travellers), so editing or deleting a profile
never changes a past booking.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.errors import Conflict, ErrorEnvelope, NotFound
from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

MAX_PROFILES = 10
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class TravellerProfile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "traveller_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class TravellerProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    date_of_birth: date | None = None


class TravellerProfileOut(TravellerProfileIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: uuid.UUID


class TravellerProfileListOut(BaseModel):
    items: list[TravellerProfileOut]


router = APIRouter(
    prefix="/me/travellers",
    tags=["account"],
    responses={
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
    },
)


@router.get("", response_model=TravellerProfileListOut, summary="My saved travellers")
def list_profiles(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> TravellerProfileListOut:
    rows = session.scalars(
        select(TravellerProfile)
        .where(TravellerProfile.user_id == user.id)
        .order_by(TravellerProfile.created_at)
    )
    return TravellerProfileListOut(items=[TravellerProfileOut.model_validate(r) for r in rows])


@router.post(
    "",
    response_model=TravellerProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save a traveller",
)
def add_profile(
    body: TravellerProfileIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TravellerProfileOut:
    count = (
        session.scalar(
            select(func.count())
            .select_from(TravellerProfile)
            .where(TravellerProfile.user_id == user.id)
        )
        or 0
    )
    if count >= MAX_PROFILES:
        raise Conflict(f"You can save up to {MAX_PROFILES} travellers.", code="PROFILE_LIMIT")
    profile = TravellerProfile(user_id=user.id, **body.model_dump())
    session.add(profile)
    session.commit()
    return TravellerProfileOut.model_validate(profile)


@router.delete(
    "/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a saved traveller"
)
def delete_profile(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    profile = session.get(TravellerProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise NotFound("Traveller not found.", code="PROFILE_NOT_FOUND")
    session.delete(profile)
    session.commit()
