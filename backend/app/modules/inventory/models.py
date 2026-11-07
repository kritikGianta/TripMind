"""Inventory: how many seats and rooms are taken, kept separate from the catalog.

Rows are created lazily, the first time something is reserved (plan v2, G10): pre-creating one row
per hotel room per night would be enormous and mostly unused. Capacity is copied from the catalog
when the row is created.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class FlightInventory(Base):
    __tablename__ = "flight_inventory"
    __table_args__ = (
        CheckConstraint("reserved >= 0 AND reserved <= capacity", name="within_capacity"),
    )

    flight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("flights.id", ondelete="RESTRICT"), primary_key=True
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RoomNightInventory(Base):
    __tablename__ = "room_night_inventory"
    __table_args__ = (
        CheckConstraint("reserved >= 0 AND reserved <= capacity", name="within_capacity"),
    )

    room_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("room_types.id", ondelete="RESTRICT"), primary_key=True
    )
    night: Mapped[date] = mapped_column(Date, primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InventoryClaim(UUIDPrimaryKeyMixin, Base):
    """Exactly what one booking item took, so releasing it gives back exactly that."""

    __tablename__ = "inventory_claims"
    __table_args__ = (
        CheckConstraint("resource IN ('flight', 'room_night')", name="resource_valid"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_inventory_claims_open", "booking_item_id", "released_at"),
    )

    booking_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource: Mapped[str] = mapped_column(String(16), nullable=False)
    flight_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    night: Mapped[date | None] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
