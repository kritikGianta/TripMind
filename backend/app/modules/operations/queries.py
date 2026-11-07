"""Read-side helpers other modules use to stop selling disrupted inventory."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.operations.models import Disruption, DisruptionKind


def cancelled_flights() -> Select[Any]:
    """Subquery of cancelled flight IDs, for `Flight.id.not_in(...)`."""
    return select(Disruption.flight_id).where(Disruption.kind == DisruptionKind.FLIGHT_CANCELLED)


def unavailable_rooms(session: Session, check_in: date, check_out: date) -> set[uuid.UUID]:
    """Room types out of service for any night of the stay."""
    rows = session.scalars(
        select(Disruption.room_type_id).where(
            Disruption.kind == DisruptionKind.ROOM_UNAVAILABLE,
            Disruption.starts_on < check_out,
            Disruption.ends_on > check_in,
        )
    )
    return {r for r in rows if r is not None}


def flight_delays(session: Session, flight_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    rows = session.execute(
        select(Disruption.flight_id, Disruption.delay_minutes).where(
            Disruption.kind == DisruptionKind.FLIGHT_DELAYED, Disruption.flight_id.in_(flight_ids)
        )
    ).tuples()
    delays: dict[uuid.UUID, int] = {}
    for flight_id, minutes in rows:
        if flight_id is not None and minutes:
            delays[flight_id] = max(delays.get(flight_id, 0), minutes)
    return delays
