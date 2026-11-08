"""Seats, baggage and meals: configuration, seat maps and the money ledger.

Seat maps are derived, not stored: the layout comes from the aircraft type (or the cabin's seat
capacity when the type is unknown) in config/ancillaries.yaml, and a seat is taken when an active
`booking_extras` row holds it. Only seats sold through TripMind are known, and the map says so.

The ledger helpers are used wherever a flight item stops being flown as booked (cancel, change,
disruption), so extras are always refunded and closed together with their flight.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingExtra, ExtraStatus

ExtraKind = Literal["seat", "baggage", "meal"]
SeatZone = Literal["extra_legroom", "front", "window_or_aisle", "middle", "included"]
PREMIUM_CABINS = frozenset({"premium_economy", "business", "first"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Layout(_Strict):
    name: str
    match: list[str] = Field(default_factory=list)
    economy: str = Field(pattern=r"^[A-Z]+( [A-Z]+)*$")
    premium: str = Field(pattern=r"^[A-Z]+( [A-Z]+)*$")


class SeatPrices(_Strict):
    extra_legroom: int = Field(ge=0)
    front: int = Field(ge=0)
    window_or_aisle: int = Field(ge=0)
    middle: int = Field(ge=0)


class SeatMapRules(_Strict):
    widebody_min_seats: int = Field(ge=1)
    turboprop_max_seats: int = Field(ge=1)
    layouts: list[Layout] = Field(min_length=1)
    exit_row_fraction: float = Field(gt=0, lt=1)
    front_rows: int = Field(ge=0)
    prices: SeatPrices


class Option(_Strict):
    code: str = Field(pattern=r"^[A-Z0-9]{2,16}$")
    label: str
    price: int = Field(ge=0)


class Baggage(_Strict):
    domestic: list[Option]
    international: list[Option]


class Meals(_Strict):
    premium_included: bool = True
    options: list[Option]


class AncillaryRules(_Strict):
    cutoff_hours_before_departure: int = Field(ge=0)
    seat_maps: SeatMapRules
    baggage: Baggage
    meals: Meals


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> AncillaryRules:
    return AncillaryRules.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def load_ancillary_rules(config_dir: Path) -> AncillaryRules:
    path = config_dir / "ancillaries.yaml"
    return _load(str(path), path.stat().st_mtime)


# ------------------------------------------------------------------------------ seat maps


@dataclass(frozen=True)
class Seat:
    code: str  # "12A"
    row: int
    letter: str
    zone: SeatZone
    position: Literal["window", "aisle", "middle"]
    price: int  # display currency, whole units


@dataclass(frozen=True)
class Cabin:
    layout: str
    groups: list[str]  # letters per block between aisles, e.g. ["ABC", "DEF"]
    rows: list[list[Seat]]

    def seat(self, code: str) -> Seat | None:
        return next((s for row in self.rows for s in row if s.code == code), None)


def _layout(rules: SeatMapRules, aircraft: str | None, capacity: int) -> Layout:
    text = (aircraft or "").lower()
    by_name = {layout.name: layout for layout in rules.layouts}
    for layout in rules.layouts:
        if any(token.lower() in text for token in layout.match if token):
            return layout
    if capacity >= rules.widebody_min_seats and "widebody" in by_name:
        return by_name["widebody"]
    if capacity <= rules.turboprop_max_seats and "turboprop" in by_name:
        return by_name["turboprop"]
    return by_name.get("narrowbody", rules.layouts[-1])


def build_cabin(
    rules: SeatMapRules, aircraft: str | None, cabin_class: str, capacity: int
) -> Cabin:
    """The seats of one cabin. Rows fill from the front; the last row may be partly empty."""
    layout = _layout(rules, aircraft, capacity)
    premium = cabin_class in PREMIUM_CABINS
    groups = (layout.premium if premium else layout.economy).split()
    letters = "".join(groups)
    edges = {g[0] for g in groups} | {g[-1] for g in groups}
    windows = {letters[0], letters[-1]}
    row_count = math.ceil(capacity / len(letters)) if capacity > 0 else 0
    exit_rows: set[int] = set()
    if not premium and row_count >= 10:
        first_exit = max(1, round(row_count * rules.exit_row_fraction))
        exit_rows = {first_exit, first_exit + 1}
    rows: list[list[Seat]] = []
    remaining = capacity
    for row in range(1, row_count + 1):
        seats: list[Seat] = []
        for letter in letters[: min(len(letters), remaining)]:
            position: Literal["window", "aisle", "middle"] = (
                "window" if letter in windows else "aisle" if letter in edges else "middle"
            )
            zone: SeatZone
            if premium:
                zone = "included"
            elif row in exit_rows:
                zone = "extra_legroom"
            elif row <= rules.front_rows:
                zone = "front"
            elif position != "middle":
                zone = "window_or_aisle"
            else:
                zone = "middle"
            price = 0 if zone == "included" else getattr(rules.prices, zone)
            seats.append(Seat(f"{row}{letter}", row, letter, zone, position, price))
        remaining -= len(seats)
        rows.append(seats)
    return Cabin(layout=layout.name, groups=groups, rows=rows)


def taken_seats(session: Session, flight_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Seat code -> traveller ID for every seat held on this flight."""
    rows = session.execute(
        select(BookingExtra.code, BookingExtra.traveller_id).where(
            BookingExtra.flight_id == flight_id,
            BookingExtra.kind == "seat",
            BookingExtra.status == ExtraStatus.ACTIVE,
        )
    )
    return {code: traveller for code, traveller in rows}


# ------------------------------------------------------------------------------ ledger


def paid_for_extras(session: Session, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """What the traveller has paid for extras on each item that are not yet closed."""
    totals: dict[uuid.UUID, int] = defaultdict(int)
    if not item_ids:
        return totals
    rows = session.execute(
        select(BookingExtra.booking_item_id, BookingExtra.paid_minor).where(
            BookingExtra.booking_item_id.in_(item_ids),
            BookingExtra.status != ExtraStatus.CLOSED,
        )
    )
    for item_id, paid in rows:
        totals[item_id] += paid
    return totals


def close_extras(session: Session, item_ids: list[uuid.UUID]) -> None:
    """Free the seats and close every extra on these items (refunds are recorded by the caller)."""
    if item_ids:
        session.execute(
            update(BookingExtra)
            .where(
                BookingExtra.booking_item_id.in_(item_ids),
                BookingExtra.status != ExtraStatus.CLOSED,
            )
            .values(status=ExtraStatus.CLOSED)
        )
