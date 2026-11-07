"""Publish: write a prepared dataset into the catalog inside the caller's transaction.

For each table the new snapshot is compared with what is stored, by deterministic ID and row
hash: new rows are inserted, changed rows updated, identical rows left alone, and rows that are no
longer supplied are retired (never deleted, plan v2 G15). Retiring an airport or hotel also
retires the flights or room types that depend on it.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.orm import Session

from app.modules.catalog.models import Airport, City, Flight, Hotel, HotelAmenity, RoomType

_CHUNK = 2000

CITY_COLUMNS = ("name", "country", "latitude", "longitude", "timezone")
AIRPORT_COLUMNS = (
    "code",
    "name",
    "city_id",
    "city_name",
    "country",
    "latitude",
    "longitude",
    "timezone",
    "timezone_assumed",
)
FLIGHT_COLUMNS = (
    "flight_number",
    "airline_code",
    "airline_name",
    "origin_airport_id",
    "destination_airport_id",
    "departure_local",
    "arrival_local",
    "departure_at",
    "arrival_at",
    "duration_minutes",
    "stops",
    "cabin_class",
    "fare_minor",
    "currency",
    "seat_capacity",
    "aircraft",
)
HOTEL_COLUMNS = (
    "name",
    "city_id",
    "city_name",
    "country",
    "address",
    "latitude",
    "longitude",
    "star_rating",
    "guest_rating",
    "review_count",
    "description",
    "check_in_time",
    "check_out_time",
)
ROOM_COLUMNS = (
    "hotel_id",
    "name",
    "max_occupancy",
    "bed_type",
    "board",
    "refundable",
    "nightly_rate_minor",
    "currency",
    "total_rooms",
)


@dataclass
class TableCounts:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    retired: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "retired": self.retired,
        }


def py(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain Python values the database driver accepts."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if math.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _hash(record: dict[str, Any], extra: Iterable[str] = ()) -> str:
    def encode(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    payload = {k: encode(v) for k, v in sorted(record.items())}
    if extra:
        payload["__extra__"] = list(extra)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def records(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    *,
    origin_column: str = "origin",
    import_run_id: uuid.UUID,
    extras: dict[Any, list[str]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame[["id", "source_key", origin_column, *columns]].to_dict("records"):
        business = {c: py(raw[c]) for c in columns}
        for key in ("city_id", "hotel_id", "origin_airport_id", "destination_airport_id"):
            if key in business and business[key] is not None:
                business[key] = uuid.UUID(str(business[key]))
        row_id = uuid.UUID(str(raw["id"]))
        rows.append(
            {
                "id": row_id,
                "source_key": str(raw["source_key"])[:160],
                "origin": raw[origin_column],
                "row_hash": _hash(
                    {**business, "origin": raw[origin_column]}, (extras or {}).get(row_id, ())
                ),
                "import_run_id": import_run_id,
                **business,
            }
        )
    return rows


def _chunks(items: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(items), _CHUNK):
        yield items[start : start + _CHUNK]


class CatalogPublisher:
    def __init__(self, session: Session, now: datetime) -> None:
        self._session = session
        self._now = now

    def sync(
        self,
        model: type[City | Airport | Flight | Hotel | RoomType],
        rows: list[dict[str, Any]],
        *,
        retire_missing: bool = True,
    ) -> tuple[TableCounts, set[uuid.UUID]]:
        """Bring `model`'s table in line with `rows`. Returns counts and the IDs written.

        With `retire_missing=False` the rows are upserted only; used when the import is not a
        complete snapshot of the table (for example cities when only hotels are imported).
        """
        counts = TableCounts()
        existing = {
            row.id: (row.row_hash, row.is_active)
            for row in self._session.execute(select(model.id, model.row_hash, model.is_active))
        }
        to_insert, to_update = [], []
        for row in rows:
            current = existing.get(row["id"])
            if current is None:
                to_insert.append(row)
            elif current[0] != row["row_hash"] or not current[1]:
                to_update.append({**row, "is_active": True, "retired_at": None})
            else:
                counts.unchanged += 1
        for chunk in _chunks(to_insert):
            self._session.execute(insert(model), chunk)
        for chunk in _chunks(to_update):
            self._session.execute(update(model), chunk)
        counts.inserted, counts.updated = len(to_insert), len(to_update)

        supplied = {row["id"] for row in rows}
        if retire_missing:
            stale = [i for i, (_, active) in existing.items() if active and i not in supplied]
            counts.retired = self._retire(model, stale)
        written = {r["id"] for r in to_insert} | {r["id"] for r in to_update}
        return counts, written

    def _retire(
        self, model: type[City | Airport | Flight | Hotel | RoomType], ids: list[uuid.UUID]
    ) -> int:
        for start in range(0, len(ids), _CHUNK):
            self._session.execute(
                update(model)
                .where(model.id.in_(ids[start : start + _CHUNK]))
                .values(is_active=False, retired_at=self._now)
            )
        return len(ids)

    def replace_amenities(
        self, hotel_ids: set[uuid.UUID], amenities: dict[uuid.UUID, list[str]]
    ) -> None:
        ids = list(hotel_ids)
        for start in range(0, len(ids), _CHUNK):
            self._session.execute(
                delete(HotelAmenity).where(HotelAmenity.hotel_id.in_(ids[start : start + _CHUNK]))
            )
        rows = [{"hotel_id": h, "amenity": a} for h in ids for a in amenities.get(h, [])]
        for chunk in _chunks(rows):
            self._session.execute(insert(HotelAmenity), chunk)

    def cascade_retirements(self) -> dict[str, int]:
        """Retire dependants of retired parents, so nothing bookable points at a retired row."""
        inactive_airports = select(Airport.id).where(Airport.is_active.is_(False))
        flights = self._session.execute(
            update(Flight)
            .where(Flight.is_active.is_(True))
            .where(
                or_(
                    Flight.origin_airport_id.in_(inactive_airports),
                    Flight.destination_airport_id.in_(inactive_airports),
                )
            )
            .values(is_active=False, retired_at=self._now)
        )
        inactive_hotels = select(Hotel.id).where(Hotel.is_active.is_(False))
        rooms = self._session.execute(
            update(RoomType)
            .where(RoomType.is_active.is_(True), RoomType.hotel_id.in_(inactive_hotels))
            .values(is_active=False, retired_at=self._now)
        )
        return {
            "flights": int(flights.rowcount or 0),  # type: ignore[attr-defined]
            "room_types": int(rooms.rowcount or 0),  # type: ignore[attr-defined]
        }
