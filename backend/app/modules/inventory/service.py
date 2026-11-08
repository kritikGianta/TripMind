"""Reserving and releasing seats and room-nights.

Concurrency is handled by the database, not by application locks (plan v2, section 2):

    UPDATE flight_inventory SET reserved = reserved + :n
    WHERE flight_id = :id AND reserved + :n <= capacity

Two travellers racing for the last seat both run this statement; the database serialises the row
update, exactly one sees one affected row, the other sees zero and gets SOLD_OUT. A stay updates
every night in one statement and requires the affected-row count to equal the number of nights,
otherwise the caller's transaction is rolled back, so a stay is never half-held.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.modules.catalog.models import Flight, RoomType
from app.modules.inventory.models import FlightInventory, InventoryClaim, RoomNightInventory


class SoldOut(Conflict):
    code = "SOLD_OUT"
    message = "Sorry, this is no longer available for your party."


def _insert_ignore(
    session: Session,
    model: type[FlightInventory | RoomNightInventory],
    rows: list[dict[str, object]],
) -> None:
    """INSERT ... ON CONFLICT DO NOTHING on both PostgreSQL and SQLite (plan v2, G5)."""
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
    session.execute(insert(model).values(rows).on_conflict_do_nothing())


def nights(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]


class InventoryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def availability(self, flight_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Seats left per flight (catalog capacity where nothing is reserved yet)."""
        capacity = dict(
            self._session.execute(
                select(Flight.id, Flight.seat_capacity).where(Flight.id.in_(flight_ids))
            ).all()
        )
        reserved = dict(
            self._session.execute(
                select(FlightInventory.flight_id, FlightInventory.reserved).where(
                    FlightInventory.flight_id.in_(flight_ids)
                )
            ).all()
        )
        return {fid: cap - reserved.get(fid, 0) for fid, cap in capacity.items()}

    def reserve_seats(self, item_id: uuid.UUID, flight: Flight, quantity: int) -> None:
        _insert_ignore(
            self._session,
            FlightInventory,
            [{"flight_id": flight.id, "capacity": flight.seat_capacity, "reserved": 0}],
        )
        result = self._session.execute(
            update(FlightInventory)
            .where(
                FlightInventory.flight_id == flight.id,
                FlightInventory.reserved + quantity <= FlightInventory.capacity,
            )
            .values(reserved=FlightInventory.reserved + quantity)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise SoldOut(f"Flight {flight.flight_number} has no seats left for your party.")
        self._session.add(
            InventoryClaim(
                booking_item_id=item_id, resource="flight", flight_id=flight.id, quantity=quantity
            )
        )

    def reserve_rooms(
        self, item_id: uuid.UUID, room: RoomType, check_in: date, check_out: date, quantity: int
    ) -> None:
        stay = nights(check_in, check_out)
        _insert_ignore(
            self._session,
            RoomNightInventory,
            [
                {"room_type_id": room.id, "night": n, "capacity": room.total_rooms, "reserved": 0}
                for n in stay
            ],
        )
        result = self._session.execute(
            update(RoomNightInventory)
            .where(
                RoomNightInventory.room_type_id == room.id,
                RoomNightInventory.night.in_(stay),
                RoomNightInventory.reserved + quantity <= RoomNightInventory.capacity,
            )
            .values(reserved=RoomNightInventory.reserved + quantity)
        )
        if result.rowcount != len(stay):  # type: ignore[attr-defined]
            raise SoldOut(f"{room.name} is not available for every night of your stay.")
        self._session.add_all(
            [
                InventoryClaim(
                    booking_item_id=item_id,
                    resource="room_night",
                    room_type_id=room.id,
                    night=n,
                    quantity=quantity,
                )
                for n in stay
            ]
        )

    def release(self, item_ids: list[uuid.UUID], at: datetime) -> int:
        """Give back everything still claimed by these items. Safe to call twice."""
        claims = list(
            self._session.scalars(
                select(InventoryClaim)
                .where(
                    InventoryClaim.booking_item_id.in_(item_ids),
                    InventoryClaim.released_at.is_(None),
                )
                .with_for_update()
            )
        )
        for claim in claims:
            if claim.resource == "flight":
                self._session.execute(
                    update(FlightInventory)
                    .where(FlightInventory.flight_id == claim.flight_id)
                    .values(reserved=FlightInventory.reserved - claim.quantity)
                )
            else:
                self._session.execute(
                    update(RoomNightInventory)
                    .where(
                        RoomNightInventory.room_type_id == claim.room_type_id,
                        RoomNightInventory.night == claim.night,
                    )
                    .values(reserved=RoomNightInventory.reserved - claim.quantity)
                )
            claim.released_at = at
        return len(claims)
