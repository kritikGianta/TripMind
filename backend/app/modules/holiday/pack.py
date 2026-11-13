"""Load the official finale data pack into TripMind's catalog.

The pack is read-only (`data/catalog/*.json`). Loading maps every record onto the one catalog that
every part of TripMind uses (flight search, stay search, the holiday builder, recovery, alerts):

    destinations.json   countries, departure cities, destination cities, city links
    airports.json       airports and the cities each one serves
    flights.json        flights (the dataset's flight_id is kept as `source_key`)
    hotels.json         hotels, with area, family_friendly and photo
    rooms.json          room types, with max_adults / max_children
    availability.json   room_night_inventory: rooms_left per room type per night
    transfers.json      airport, city-to-city and city transfers
    attractions.json    attractions

Rules of the load:
- IDs are stable (UUIDv5 of the dataset ID), so loading twice changes nothing and bookings keep
  pointing at the same rows.
- Prices in the pack are whole rupees; TripMind stores minor units (paise), so x 100.
- Seats: a flight's capacity is its `seats_left`. Rooms: each night's capacity is `rooms_left`, and
  a room type has no rooms on nights the pack does not list. Seats and rooms reserved by
  TripMind bookings are counted separately and kept across reloads (reserved is never reset).
- Catalog rows that are not in the pack are retired (hidden, never deleted), so only official data
  is offered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.catalog.models import (
    Airport,
    AirportServedCity,
    Attraction,
    City,
    CityLink,
    Country,
    DataOrigin,
    Flight,
    Hotel,
    RoomType,
    Transfer,
    catalog_id,
)
from app.modules.inventory.models import RoomNightInventory

log = structlog.get_logger(__name__)

PACK_FILES = (
    "destinations",
    "airports",
    "flights",
    "hotels",
    "rooms",
    "availability",
    "transfers",
    "attractions",
)
INDIA = ("IN", "India", "Asia/Kolkata")


class PackError(ValueError):
    """The data pack is missing a file or a record does not fit the documented format."""


@dataclass
class LoadReport:
    counts: dict[str, int] = field(default_factory=dict)
    retired: dict[str, int] = field(default_factory=dict)


def _minor(price: dict[str, Any] | None) -> int | None:
    """{"amount": 6440, "currency": "INR"} -> 644000 (paise)."""
    if price is None:
        return None
    return round(float(price["amount"]) * 100)


def _hash(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def _utc(local: datetime, tz: str) -> datetime:
    return local.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC)


def read_pack(pack_dir: Path, extra_dir: Path | None = None) -> dict[str, Any]:
    """Read the 8 catalog files (UTF-8: they hold Japanese names).

    `extra_dir` holds more rows in the same schema (TripMind's own extension, see extend.py);
    any file it has is appended to the official one.
    """
    folder = pack_dir / "data" / "catalog"
    out: dict[str, Any] = {}
    for name in PACK_FILES:
        path = folder / f"{name}.json"
        if not path.exists():
            raise PackError(f"The data pack has no {path.name} (looked in {folder}).")
        out[name] = json.loads(path.read_text(encoding="utf-8"))
        extra = extra_dir / "data" / "catalog" / f"{name}.json" if extra_dir else None
        if extra is not None and extra.exists():
            more = json.loads(extra.read_text(encoding="utf-8"))
            if isinstance(out[name], list):
                out[name] += more
            else:  # destinations.json: add the extra countries
                out[name]["countries"] += more.get("countries", [])
    return out


class PackLoader:
    def __init__(self, session: Session, now: datetime) -> None:
        self._session = session
        self._now = now
        self.report = LoadReport()
        self._by_key: dict[type[Any], dict[str, Any]] = {}

    # ------------------------------------------------------------------ helpers

    def _upsert(self, model: type[Any], row_id: Any, values: dict[str, Any]) -> Any:
        """Insert the row, or update it in place.

        Catalog rows are found by their dataset key first: an earlier dataset may already hold
        the same airport (BLR) under another ID, and that row is reused, keeping its ID, so
        nothing that points at it breaks.
        """
        row = None
        if "source_key" in values:
            if model not in self._by_key:  # one query per table, not one per row
                self._by_key[model] = {
                    r.source_key: r for r in self._session.scalars(select(model))
                }
            row = self._by_key[model].get(values["source_key"])
        if row is None:
            row = self._session.get(model, row_id)
        if row is None:
            row = model(**values)
            self._session.add(row)
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(row, key, value)
        return row

    def _catalog_values(self, source_key: str, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_key": source_key,
            "origin": DataOrigin.PROVIDED.value,
            "row_hash": _hash(record),
            "is_active": True,
            "retired_at": None,
            "import_run_id": None,
        }

    def _count(self, name: str, n: int) -> None:
        self.report.counts[name] = n

    # ------------------------------------------------------------------ load

    def load(self, pack: dict[str, Any]) -> LoadReport:
        destinations = pack["destinations"]
        country_names = self._countries(destinations)
        cities = self._cities(destinations, pack["airports"], country_names)
        airports = self._airports(pack["airports"], cities, country_names)
        self._flights(pack["flights"], airports)
        hotels = self._hotels(pack["hotels"], cities)
        self._rooms(pack["rooms"], hotels)
        self._availability(pack["availability"])
        transfers = self._transfers(pack["transfers"])
        self._links(destinations, cities, transfers)
        self._attractions(pack["attractions"])
        self._session.flush()
        self._retire_others()
        return self.report

    def _countries(self, destinations: dict[str, Any]) -> dict[str, str]:
        names = {INDIA[0]: INDIA[1]}
        for c in destinations["countries"]:
            self._upsert(
                Country,
                c["code"],
                {"code": c["code"], "name": c["name"], "timezone": c["timezone"]},
            )
            names[c["code"]] = c["name"]
        self._count("countries", len(destinations["countries"]))
        return names

    def _cities(
        self, destinations: dict[str, Any], airports: list[dict[str, Any]], names: dict[str, str]
    ) -> dict[str, City]:
        """Departure cities (India), destination cities, and any other city an airport names."""
        wanted: dict[str, dict[str, Any]] = {}
        for d in destinations["departure_cities"]:
            wanted[d["city"]] = {"code": INDIA[0], "tz": INDIA[2], "departure": True}
        for c in destinations["countries"]:
            for city in c["cities"]:
                wanted[city["name"]] = {"code": c["code"], "tz": c["timezone"], "departure": False}
        for a in airports:
            wanted.setdefault(
                a["city"], {"code": a["country"], "tz": a["timezone"], "departure": False}
            )
        out: dict[str, City] = {}
        for name, info in wanted.items():
            key = f"city:{name}"
            out[name] = self._upsert(
                City,
                catalog_id("cities", key),
                {
                    "id": catalog_id("cities", key),
                    **self._catalog_values(key, {"name": name, **info}),
                    "name": name,
                    "country": names.get(info["code"], info["code"]),
                    "country_code": info["code"],
                    "timezone": info["tz"],
                    "is_departure": info["departure"],
                },
            )
        self._count("cities", len(out))
        return out

    def _airports(
        self, records: list[dict[str, Any]], cities: dict[str, City], names: dict[str, str]
    ) -> dict[str, Airport]:
        out: dict[str, Airport] = {}
        served = 0
        self._session.flush()
        for a in records:
            row_id = catalog_id("airports", a["code"])
            out[a["code"]] = self._upsert(
                Airport,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(a["code"], a),
                    "code": a["code"],
                    "name": a["name"],
                    "city_id": cities[a["city"]].id,
                    "city_name": a["city"],
                    "country": names.get(a["country"], a["country"]),
                    "latitude": a.get("lat"),
                    "longitude": a.get("lng"),
                    "timezone": a["timezone"],
                    "timezone_assumed": False,
                },
            )
        self._session.flush()
        self._session.execute(delete(AirportServedCity))
        for a in records:
            for city in a.get("serves_cities") or []:
                if city not in cities:
                    raise PackError(f"Airport {a['code']} serves an unknown city: {city}.")
                self._session.add(
                    AirportServedCity(airport_id=out[a["code"]].id, city_id=cities[city].id)
                )
                served += 1
        self._count("airports", len(out))
        self._count("airport_served_cities", served)
        return out

    def _flights(self, records: list[dict[str, Any]], airports: dict[str, Airport]) -> None:
        for f in records:
            origin, destination = airports[f["from"]], airports[f["to"]]
            departure = datetime.fromisoformat(f["departure_local"])
            arrival = datetime.fromisoformat(f["arrival_local"])
            row_id = catalog_id("flights", f["flight_id"])
            self._upsert(
                Flight,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(f["flight_id"], f),
                    "flight_number": f["flight_number"],
                    "airline_code": f["flight_number"].split()[0],
                    "airline_name": f["airline"],
                    "origin_airport_id": origin.id,
                    "destination_airport_id": destination.id,
                    "departure_local": departure,
                    "arrival_local": arrival,
                    "departure_at": _utc(departure, origin.timezone),
                    "arrival_at": _utc(arrival, destination.timezone),
                    "duration_minutes": int(f["duration_minutes"]),
                    "stops": int(f["stops"]),
                    "cabin_class": str(f["cabin"]).lower(),
                    "fare_minor": _minor(f["price_per_seat"]),
                    "currency": f["price_per_seat"]["currency"],
                    "seat_capacity": int(f["seats_left"]),
                    "aircraft": None,
                },
            )
        self._count("flights", len(records))

    def _hotels(self, records: list[dict[str, Any]], cities: dict[str, City]) -> dict[str, Hotel]:
        out: dict[str, Hotel] = {}
        for h in records:
            city = cities[h["city"]]
            row_id = catalog_id("hotels", h["hotel_id"])
            out[h["hotel_id"]] = self._upsert(
                Hotel,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(h["hotel_id"], h),
                    "name": h["name"],
                    "city_id": city.id,
                    "city_name": h["city"],
                    "country": city.country,
                    "address": f"{h['area']}, {h['city']}" if h.get("area") else None,
                    "latitude": h.get("lat"),
                    "longitude": h.get("lng"),
                    "star_rating": float(h["stars"]),
                    "guest_rating": float(h["rating"]),
                    "review_count": None,
                    "description": None,
                    "check_in_time": h.get("check_in_from"),
                    "check_out_time": h.get("check_out_until"),
                    "area": h.get("area"),
                    "family_friendly": h.get("family_friendly"),
                    "image": h.get("image"),
                },
            )
        self._count("hotels", len(out))
        return out

    def _rooms(self, records: list[dict[str, Any]], hotels: dict[str, Hotel]) -> None:
        for r in records:
            row_id = catalog_id("room_types", r["room_id"])
            self._upsert(
                RoomType,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(r["room_id"], r),
                    "hotel_id": hotels[r["hotel_id"]].id,
                    "name": r["name"],
                    "max_occupancy": int(r["max_adults"]) + int(r["max_children"]),
                    "max_adults": int(r["max_adults"]),
                    "max_children": int(r["max_children"]),
                    "room_kind": r["room_type"],
                    "bed_type": None,
                    "board": None,
                    "refundable": r.get("refundable"),
                    "nightly_rate_minor": _minor(r["price_per_night"]),
                    "currency": r["price_per_night"]["currency"],
                    # Rooms exist only on the nights availability.json lists (seeded below).
                    "total_rooms": 0,
                },
            )
        self._count("room_types", len(records))

    def _availability(self, records: list[dict[str, Any]]) -> None:
        self._session.flush()
        existing = {
            (r.room_type_id, r.night): r for r in self._session.scalars(select(RoomNightInventory))
        }
        for a in records:
            room_type_id = catalog_id("room_types", a["room_id"])
            night = date.fromisoformat(a["date"])
            row = existing.get((room_type_id, night))
            capacity = int(a["rooms_left"])
            if row is None:
                self._session.add(
                    RoomNightInventory(
                        room_type_id=room_type_id, night=night, capacity=capacity, reserved=0
                    )
                )
            else:
                # Keep what TripMind has already reserved; never let capacity drop below it.
                row.capacity = max(capacity, row.reserved)
        self._count("room_nights", len(records))

    def _transfers(self, records: list[dict[str, Any]]) -> dict[str, Transfer]:
        out: dict[str, Transfer] = {}
        for t in records:
            row_id = catalog_id("transfers", t["transfer_id"])
            out[t["transfer_id"]] = self._upsert(
                Transfer,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(t["transfer_id"], t),
                    "kind": t["type"],
                    "name": t["name"],
                    "airport_code": t.get("airport"),
                    "city_name": t.get("city"),
                    "area": t.get("area"),
                    "from_city_name": t.get("from_city"),
                    "to_city_name": t.get("to_city"),
                    "from_point": t.get("from_point"),
                    "to_point": t.get("to_point"),
                    "door_to_door": t.get("door_to_door"),
                    "max_passengers": int(t["max_passengers"]),
                    "service_from": t["service_from"],
                    "service_until": t["service_until"],
                    "frequency_minutes": t.get("frequency_minutes"),
                    "duration_minutes": int(t["duration_minutes"]),
                    "pricing": t["pricing"],
                    "price_minor": _minor(t["price"]),
                    "child_price_minor": _minor(t.get("child_price")),
                    "currency": t["price"]["currency"],
                },
            )
        self._count("transfers", len(out))
        return out

    def _links(
        self,
        destinations: dict[str, Any],
        cities: dict[str, City],
        transfers: dict[str, Transfer],
    ) -> None:
        self._session.flush()
        self._session.execute(delete(CityLink))
        n = 0
        for country in destinations["countries"]:
            for link in country["links"]:
                for transfer_id in link["transfer_ids"]:
                    if transfer_id not in transfers:
                        raise PackError(f"City link uses an unknown transfer: {transfer_id}.")
                    self._session.add(
                        CityLink(
                            from_city_id=cities[link["from_city"]].id,
                            to_city_id=cities[link["to_city"]].id,
                            transfer_id=transfers[transfer_id].id,
                        )
                    )
                    n += 1
        self._count("city_links", n)

    def _attractions(self, records: list[dict[str, Any]]) -> None:
        for a in records:
            row_id = catalog_id("attractions", a["attraction_id"])
            self._upsert(
                Attraction,
                row_id,
                {
                    "id": row_id,
                    **self._catalog_values(a["attraction_id"], a),
                    "name": a["name"],
                    "name_local": a.get("name_ja"),
                    "city_name": a["city"],
                    "category": a.get("category"),
                    "latitude": a.get("lat"),
                    "longitude": a.get("lng"),
                    "open_days": list(a["open_days"]),
                    "open_from": a["open_from"],
                    "open_until": a["open_until"],
                    "closed_dates": list(a.get("closed_dates") or []),
                    "visit_minutes": int(a["visit_minutes"]),
                    "aliases": list(a.get("aliases") or []),
                    "child_friendly": a.get("child_friendly"),
                    "accessible": a.get("accessible"),
                    "price_minor": _minor(a["price_per_person"]),
                    "child_price_minor": _minor(a.get("child_price")),
                    "currency": a["price_per_person"]["currency"],
                    "image": a.get("image"),
                },
            )
        self._count("attractions", len(records))

    def _retire_others(self) -> None:
        """Hide catalog rows from any earlier dataset, so only the official pack is offered."""
        for model in (Flight, RoomType, Hotel, Airport, City):
            result = self._session.execute(
                update(model)
                .where(model.origin != DataOrigin.PROVIDED.value, model.is_active.is_(True))
                .values(is_active=False, retired_at=self._now)
            )
            self.report.retired[model.__tablename__] = int(result.rowcount or 0)  # type: ignore[attr-defined]


def load_pack(
    session: Session, pack_dir: Path, now: datetime, extra_dir: Path | None = None
) -> LoadReport:
    """Read the pack (and its extension) and load it in one transaction (all of it, or nothing)."""
    pack = read_pack(pack_dir, extra_dir)
    try:
        report = PackLoader(session, now).load(pack)
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info("holiday_pack_loaded", counts=report.counts, retired=report.retired)
    return report


def pack_loaded(session: Session) -> bool:
    """True once the official pack is in the catalog (any provided flight row exists)."""
    return (
        session.scalar(select(Flight.id).where(Flight.origin == DataOrigin.PROVIDED.value).limit(1))
        is not None
    )
