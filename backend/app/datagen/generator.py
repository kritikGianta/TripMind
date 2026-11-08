"""Synthetic demo dataset.

Produces a ZIP shaped like a supplier export (airports.csv, flights.csv, hotels.csv, rooms.csv),
with column names that deliberately differ from TripMind's own, so it goes through the same
mapping, validation and quarantine as the real finale data. No catalog row is ever seeded
directly into the database.

The output is deterministic for a given seed and start date. A small, configurable share of rows
is corrupted in realistic ways (unknown airports, impossible times, misspelt cities, duplicates)
so the import report and quarantine have something real to show.
"""

from __future__ import annotations

import csv
import io
import math
import random
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.datagen.reference import (
    AIRLINES,
    AIRPORTS,
    CITIES,
    HUBS,
    SYNTHETIC_INR_TO_LOCAL,
    AirportRef,
    CityRef,
)

AIRPORT_COLUMNS = ("iata", "airport_name", "city", "country", "lat", "lon", "tz")
SCHEDULE_COLUMNS = (
    "airline",
    "airline_code",
    "flight_no",
    "from",
    "to",
    "dep",
    "arr",
    "duration",
    "days",
    "valid_from",
    "valid_to",
    "cabin",
    "fare",
    "currency",
    "aircraft",
    "seats",
)
FLIGHT_COLUMNS = (
    "airline",
    "airline_code",
    "flight_no",
    "from",
    "to",
    "departure",
    "arrival",
    "duration",
    "cabin",
    "fare",
    "currency",
    "aircraft",
    "seats",
)
HOTEL_COLUMNS = (
    "hotel_id",
    "name",
    "city",
    "country",
    "address",
    "lat",
    "lng",
    "stars",
    "rating",
    "reviews",
    "amenities",
    "checkin",
    "checkout",
    "price_per_night",
    "currency",
    "total_rooms",
    "description",
)
ROOM_COLUMNS = (
    "room_id",
    "hotel_id",
    "room_name",
    "max_guests",
    "bed",
    "price",
    "currency",
    "rooms_count",
    "refundable",
    "meal_plan",
)

INTERNATIONAL_ROUTES: dict[str, tuple[str, ...]] = {
    "DXB": ("DEL", "BOM", "BLR", "COK", "HYD", "MAA"),
    "DOH": ("DEL", "BOM", "COK"),
    "SIN": ("DEL", "BOM", "BLR", "MAA"),
    "BKK": ("DEL", "BOM", "CCU"),
    "LHR": ("DEL", "BOM", "BLR"),
    "CMB": ("MAA", "BLR", "DEL"),
    "KTM": ("DEL", "BOM"),
}

PREFIXES = (
    "Banyan",
    "Peepal",
    "Jasmine",
    "Teak",
    "Sandstone",
    "Riverstone",
    "Palm Grove",
    "Coral",
    "Marigold",
    "Cedar",
    "Kesar",
    "Neem",
    "Bodhi",
    "Chandni",
    "Amber",
    "Mist",
    "Saffron Court",
    "Lotus",
    "Monsoon",
    "Silver Oak",
    "Jade",
    "Indus",
    "Kaveri",
    "Tamarind",
    "Banjara",
    "Gulmohar",
    "Mango Tree",
    "Sapphire",
    "Horizon",
    "Ivory",
)
SUFFIXES: dict[str, tuple[str, ...]] = {
    "metro": ("Residency", "Suites", "Grand", "Business Hotel", "Inn", "Plaza", "Executive Stay"),
    "heritage": ("Haveli", "Heritage Hotel", "Palace Stay", "Mahal Retreat", "Inn"),
    "beach": ("Beach Resort", "Bay Resort", "Sands", "Lagoon Retreat", "Shore Inn"),
    "hill": ("Valley Lodge", "Lake View", "Houseboats", "Cottages", "Retreat"),
    "spiritual": ("Guest House", "Inn", "Residency", "Retreat"),
    "international": ("Hotel", "Suites", "Tower", "City Hotel", "Residences"),
}
STREETS = (
    "Station Road",
    "Lake Road",
    "Market Street",
    "Garden Lane",
    "Temple Road",
    "Hill View Road",
    "Harbour Road",
    "Park Avenue",
    "College Road",
    "Canal Street",
)
AMENITY_LABELS = {
    "wifi": "Free WiFi",
    "air_conditioning": "Air conditioning",
    "restaurant": "Restaurant",
    "pool": "Swimming pool",
    "gym": "Fitness centre",
    "spa": "Spa",
    "bar": "Bar",
    "room_service": "Room service",
    "parking": "Free parking",
    "airport_shuttle": "Airport shuttle",
    "wheelchair_accessible": "Wheelchair access",
    "pet_friendly": "Pets allowed",
    "family_rooms": "Family rooms",
    "beach_access": "Beachfront",
    "ev_charging": "EV charger",
    "business_centre": "Business centre",
    "laundry": "Laundry service",
}
MISSPELLINGS = {
    "Bengaluru": "Banglore",
    "Jaipur": "Jaipurr",
    "Hyderabad": "Hyderbad",
    "Thiruvananthapuram": "Thiruvanantapuram",
    "Kolkata": "Calcutta",
}


Defect = Callable[[dict[str, Any]], None] | Literal["duplicate"]


@dataclass(frozen=True)
class GeneratorOptions:
    seed: int = 7
    start: date = date(2026, 11, 13)
    days: int = 45
    dirty_rate: float = 0.004
    hotels_scale: float = 1.0
    # "schedules" writes repeating schedule rows (flight_schedules.csv) instead of dated flights.
    flight_format: str = "dated"


@dataclass(frozen=True)
class GeneratedDataset:
    path: Path
    counts: dict[str, int]
    corrupted: dict[str, int]


def _distance_km(a: AirportRef, b: AirportRef) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class _Schedule:
    airline: str
    code: str
    number: int
    origin: AirportRef
    destination: AirportRef
    departure_minute: int
    duration: int
    aircraft: str
    seats: int
    business_seats: int
    weekdays: frozenset[int]
    base_fare_inr: float


class _Generator:
    def __init__(self, options: GeneratorOptions) -> None:
        self.o = options
        self.rng = random.Random(options.seed)
        self.airports = {a.code: a for a in AIRPORTS}

    # ------------------------------------------------------------------ flights

    def _routes(self) -> list[tuple[str, str, int]]:
        """(origin, destination, departures per day)."""
        routes: list[tuple[str, str, int]] = []
        for a in HUBS:
            for b in HUBS:
                if a != b:
                    routes.append((a, b, self.rng.randint(4, 6)))
        domestic = [c for c in self.airports if self.airports[c].country == "IN"]
        for spoke in (c for c in domestic if c not in HUBS):
            near = sorted(HUBS, key=lambda h: _distance_km(self.airports[spoke], self.airports[h]))[
                :2
            ]
            for hub in dict.fromkeys([*near, "DEL", "BOM"]):
                per_day = self.rng.randint(1, 3)
                routes += [(spoke, hub, per_day), (hub, spoke, per_day)]
        for foreign, gateways in INTERNATIONAL_ROUTES.items():
            for gateway in gateways:
                per_day = self.rng.randint(1, 2)
                routes += [(gateway, foreign, per_day), (foreign, gateway, per_day)]
        return routes

    def _schedules(self) -> list[_Schedule]:
        numbers = {code: 100 for _, code in AIRLINES}
        schedules = []
        for origin_code, destination_code, per_day in self._routes():
            origin, destination = self.airports[origin_code], self.airports[destination_code]
            km = _distance_km(origin, destination)
            international = origin.country != destination.country
            minutes = km / 760 * 60 + 35
            duration = int(round(minutes * (1.08 if international else 1.0) / 5) * 5)
            if km > 3500:
                aircraft, seats, business = "Boeing 787-9", 296, 28
            elif km < 500 and not international:
                aircraft, seats, business = "ATR 72-600", 70, 0
            elif (origin_code in HUBS and destination_code in HUBS) or international:
                aircraft, seats, business = "Airbus A321neo", 222, 12
            else:
                aircraft, seats, business = "Airbus A320neo", 186, 0
            base = (4000 + 6.5 * km) if international else (1800 + 4.2 * km)
            slots = sorted(self.rng.sample(range(5 * 60, 23 * 60, 25), per_day))
            for slot in slots:
                airline, code = self.rng.choice(AIRLINES)
                numbers[code] += self.rng.randint(1, 7)
                weekdays = (
                    frozenset(range(7))
                    if self.rng.random() < 0.8
                    else frozenset(self.rng.sample(range(7), 5))
                )
                schedules.append(
                    _Schedule(
                        airline=airline,
                        code=code,
                        number=numbers[code],
                        origin=origin,
                        destination=destination,
                        departure_minute=slot,
                        duration=duration,
                        aircraft=aircraft,
                        seats=seats - business,
                        business_seats=business,
                        weekdays=weekdays,
                        base_fare_inr=base * (1.08 if code == "SF" else 0.95),
                    )
                )
        return schedules

    def _fare(self, schedule: _Schedule, day: date) -> float:
        hour = schedule.departure_minute // 60
        time_factor = (
            1.15
            if 6 <= hour < 9
            else 1.12
            if 17 <= hour < 21
            else (0.88 if hour >= 22 or hour < 6 else 1.0)
        )
        weekday_factor = {4: 1.12, 6: 1.12, 1: 0.92, 2: 0.92}.get(day.weekday(), 1.0)
        days_out = (day - self.o.start).days
        urgency = 1 + 0.6 * math.exp(-days_out / 7)
        noise = self.rng.lognormvariate(0, 0.08)
        return schedule.base_fare_inr * time_factor * weekday_factor * urgency * noise

    def schedule_rows(self) -> list[dict[str, Any]]:
        """The same flights as airline schedules: one row per flight number and cabin."""
        rows = []
        end = self.o.start + timedelta(days=self.o.days - 1)
        for schedule in self._schedules():
            currency = next(c.currency for c in CITIES if schedule.origin.code in c.airports)
            rate = SYNTHETIC_INR_TO_LOCAL[currency]
            departure = datetime.combine(self.o.start, datetime.min.time()) + timedelta(
                minutes=schedule.departure_minute
            )
            arrival = (
                departure.replace(tzinfo=ZoneInfo(schedule.origin.timezone))
                + timedelta(minutes=schedule.duration)
            ).astimezone(ZoneInfo(schedule.destination.timezone))
            cabins = [("Economy", schedule.base_fare_inr, schedule.seats)]
            if schedule.business_seats:
                cabins.append(("Business", schedule.base_fare_inr * 3.3, schedule.business_seats))
            for cabin, amount, seats in cabins:
                local = amount * rate
                rows.append(
                    {
                        "airline": schedule.airline,
                        "airline_code": schedule.code,
                        "flight_no": f"{schedule.code} {schedule.number}",
                        "from": schedule.origin.code,
                        "to": schedule.destination.code,
                        "dep": departure.strftime("%H:%M"),
                        "arr": arrival.strftime("%H:%M"),
                        "duration": f"{schedule.duration // 60}h {schedule.duration % 60}m",
                        "days": "".join(str(d + 1) for d in sorted(schedule.weekdays)),
                        "valid_from": self.o.start.isoformat(),
                        "valid_to": end.isoformat(),
                        "cabin": cabin,
                        "fare": f"{round(local):.2f}" if currency != "INR" else f"{round(local)}",
                        "currency": currency,
                        "aircraft": schedule.aircraft,
                        "seats": seats,
                    }
                )
        return rows

    def flights(self) -> list[dict[str, Any]]:
        rows = []
        for schedule in self._schedules():
            currency = next(c.currency for c in CITIES if schedule.origin.code in c.airports)
            rate = SYNTHETIC_INR_TO_LOCAL[currency]
            origin_tz = ZoneInfo(schedule.origin.timezone)
            destination_tz = ZoneInfo(schedule.destination.timezone)
            for offset in range(self.o.days):
                day = self.o.start + timedelta(days=offset)
                if day.weekday() not in schedule.weekdays:
                    continue
                departure = datetime.combine(day, datetime.min.time()) + timedelta(
                    minutes=schedule.departure_minute
                )
                arrival = (
                    departure.replace(tzinfo=origin_tz) + timedelta(minutes=schedule.duration)
                ).astimezone(destination_tz)
                fare = self._fare(schedule, day)
                cabins = [("Economy", fare, schedule.seats)]
                if schedule.business_seats:
                    cabins.append(("Business", fare * 3.3, schedule.business_seats))
                for cabin, amount, seats in cabins:
                    local = amount * rate
                    rows.append(
                        {
                            "airline": schedule.airline,
                            "airline_code": schedule.code,
                            "flight_no": f"{schedule.code} {schedule.number}",
                            "from": schedule.origin.code,
                            "to": schedule.destination.code,
                            "departure": departure.strftime("%Y-%m-%d %H:%M"),
                            "arrival": arrival.strftime("%Y-%m-%d %H:%M"),
                            "duration": f"{schedule.duration // 60}h {schedule.duration % 60}m",
                            "cabin": cabin,
                            "fare": f"{round(local):.2f}"
                            if currency != "INR"
                            else f"{round(local)}",
                            "currency": currency,
                            "aircraft": schedule.aircraft,
                            "seats": seats,
                        }
                    )
        return rows

    # ------------------------------------------------------------------ hotels

    def hotels(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        hotels: list[dict[str, Any]] = []
        rooms: list[dict[str, Any]] = []
        room_counter = 0
        for city in CITIES:
            count = max(3, round({1: 16, 2: 11, 3: 7}[city.tier] * self.o.hotels_scale))
            names: set[str] = set()
            for _ in range(count):
                hotel, hotel_rooms = self._hotel(city, len(hotels) + 1, names)
                hotels.append(hotel)
                for room in hotel_rooms:
                    room_counter += 1
                    rooms.append({"room_id": f"R{room_counter:06d}", **room})
        return hotels, rooms

    def _hotel(
        self, city: CityRef, index: int, names: set[str]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rng = self.rng
        while True:
            name = f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES[city.kind])}"
            if name not in names:
                names.add(name)
                break
        stars = rng.choices((2, 3, 4, 5), weights=(10, 35, 35, 20))[0]
        rating = min(5.0, max(2.0, rng.gauss(3.4 + 0.25 * stars, 0.3)))
        radius = 7 * math.sqrt(rng.random())
        angle = rng.random() * 2 * math.pi
        lat = city.latitude + radius / 111 * math.cos(angle)
        lon = city.longitude + radius / (111 * math.cos(math.radians(city.latitude))) * math.sin(
            angle
        )
        amenities = self._amenities(city, stars)
        price_inr = (
            {2: 1800, 3: 3200, 4: 6500, 5: 12500}[stars]
            * {1: 1.25, 2: 1.0, 3: 0.85}[city.tier]
            * (1.6 if city.kind == "international" else 1.0)
            * (1.15 if city.kind == "beach" else 1.0)
            * rng.lognormvariate(0, 0.15)
        )
        rate = SYNTHETIC_INR_TO_LOCAL[city.currency]
        hotel_id = f"H{index:05d}"
        total_rooms = rng.randint(18, 60) * (2 if stars >= 4 else 1)

        room_plans = [("Standard Room", 2, "Queen", 1.0, "Room only")]
        room_plans.append(("Deluxe Room", 2, "King", 1.3, "Breakfast included"))
        if "family_rooms" in amenities:
            room_plans.append(("Family Room", 4, "2 Queens", 1.6, "Breakfast included"))
        if stars >= 4:
            room_plans.append(("Suite", 3, "King", 2.2, "Breakfast included"))
        shares = [0.5, 0.3, 0.12, 0.08][: len(room_plans)]
        rooms = []
        for (room_name, guests, bed, multiplier, board), share in zip(
            room_plans, shares, strict=True
        ):
            local = price_inr * multiplier * rate
            rooms.append(
                {
                    "hotel_id": hotel_id,
                    "room_name": room_name,
                    "max_guests": guests,
                    "bed": bed,
                    "price": f"{local:.2f}" if city.currency != "INR" else f"{round(local)}",
                    "currency": city.currency,
                    "rooms_count": max(1, round(total_rooms * share / sum(shares))),
                    "refundable": "N"
                    if room_name == "Standard Room" and rng.random() < 0.35
                    else "Y",
                    "meal_plan": board,
                }
            )
        distance = radius
        kind_label = {"international": "city", "spiritual": "pilgrimage-town"}.get(
            city.kind, city.kind
        )
        hotel = {
            "hotel_id": hotel_id,
            "name": name,
            "city": city.name,
            "country": city.country,
            "address": f"{rng.randint(1, 240)} {rng.choice(STREETS)}, {city.name}",
            "lat": f"{lat:.5f}",
            "lng": f"{lon:.5f}",
            "stars": stars,
            "rating": f"{rating:.1f}",
            "reviews": int(rng.lognormvariate(math.log(120 * stars), 0.6)),
            "amenities": "|".join(AMENITY_LABELS[a] for a in amenities),
            "checkin": "14:00",
            "checkout": rng.choice(("11:00", "12:00")),
            "price_per_night": rooms[0]["price"],
            "currency": city.currency,
            "total_rooms": total_rooms,
            "description": (
                f"{stars}-star {kind_label} hotel in {city.name}, about {distance:.1f} km from "
                f"the city centre."
            ),
        }
        return hotel, rooms

    def _amenities(self, city: CityRef, stars: int) -> list[str]:
        rng = self.rng
        chosen = ["wifi"]
        if city.name != "London":
            chosen.append("air_conditioning")
        maybe = {
            "restaurant": 1.0 if stars >= 3 else 0.4,
            "pool": 0.7 if stars >= 4 else 0.15,
            "gym": 0.85 if stars >= 4 else 0.2,
            "spa": 0.8 if stars == 5 else 0.25 if stars == 4 else 0.0,
            "bar": 0.8 if stars >= 4 else 0.15,
            "room_service": 0.9 if stars >= 4 else 0.3,
            "parking": 0.6,
            "airport_shuttle": 0.3,
            "wheelchair_accessible": {2: 0.1, 3: 0.35, 4: 0.7, 5: 0.8}[stars],
            "pet_friendly": 0.1,
            "family_rooms": 0.4,
            "beach_access": 0.6 if city.kind == "beach" else 0.0,
            "ev_charging": 0.15 if stars >= 4 else 0.0,
            "business_centre": 0.6 if city.kind == "metro" and stars >= 4 else 0.0,
            "laundry": 0.7,
        }
        chosen += [a for a, p in maybe.items() if rng.random() < p]
        return chosen

    # ------------------------------------------------------------------ data quality

    def corrupt(self, name: str, rows: list[dict[str, Any]]) -> int:
        """Apply realistic defects to a small share of rows. Returns how many were changed."""
        if self.o.dirty_rate <= 0 or not rows:
            return 0
        catalogue: dict[str, list[Defect]] = {
            "airports": [lambda r: r.update(tz="Mars/Olympus_Mons")],
            "flights": [
                lambda r: r.update(to="XYZ"),
                lambda r: r.update(
                    arrival=r["departure"].replace(r["departure"][-5:], "00:01")
                    if r["departure"][-5:] > "00:01"
                    else "2000-01-01 00:00"
                ),
                lambda r: r.update(fare="-1200"),
                lambda r: r.update(flight_no=""),
                lambda r: r.update(departure="2026-13-45 10:00"),
                lambda r: r.update(fare=""),
                # A plausible-looking but wrong price (8x): valid data, caught as an anomaly.
                lambda r: r.update(fare=f"{float(r['fare']) * 8:.0f}" if r["fare"] else r["fare"]),
                "duplicate",
            ],
            "hotels": [
                lambda r: r.update(city=MISSPELLINGS.get(r["city"], r["city"])),
                lambda r: r.update(lat="123.4"),
                lambda r: r.update(name=""),
                lambda r: r.update(stars="seven"),
                "duplicate",
            ],
            "rooms": [
                lambda r: r.update(hotel_id="H99999"),
                lambda r: r.update(price="on request"),
            ],
        }
        defects = catalogue[name]
        count = max(len(defects), round(len(rows) * self.o.dirty_rate))
        targets = self.rng.sample(range(len(rows)), min(count, len(rows)))
        for i, index in enumerate(targets):
            defect = defects[i % len(defects)]
            if isinstance(defect, str):  # "duplicate"
                rows.append(dict(rows[index]))
            else:
                defect(rows[index])
        return len(targets)


def _csv(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


README = """TripMind synthetic demo dataset
==============================

Generated by `python -m app.cli data generate` (seed {seed}, start {start}, {days} days).

Airport codes, names, coordinates and timezones are public reference data. Airlines, schedules,
fares, hotels, rooms and prices are SYNTHETIC and do not describe real services or properties.
About {dirty:.1%} of rows are deliberately corrupted to exercise validation and quarantine.

Files: airports.csv, flights.csv (one row per flight, date and cabin; local times),
hotels.csv (rating on a 0-5 scale), rooms.csv (room types per hotel).
Import with the mapping config/mappings/synthetic-v1.yaml.
"""


def generate(output: Path, options: GeneratorOptions | None = None) -> GeneratedDataset:
    options = options or GeneratorOptions()
    gen = _Generator(options)
    airports = [
        {
            "iata": a.code,
            "airport_name": a.name,
            "city": a.city,
            "country": a.country,
            "lat": a.latitude,
            "lon": a.longitude,
            "tz": a.timezone,
        }
        for a in AIRPORTS
    ]
    schedules = options.flight_format == "schedules"
    flights = gen.schedule_rows() if schedules else gen.flights()
    hotels, rooms = gen.hotels()
    corrupted = {
        "airports": gen.corrupt("airports", airports),
        "flights": 0 if schedules else gen.corrupt("flights", flights),
        "hotels": gen.corrupt("hotels", hotels),
        "rooms": gen.corrupt("rooms", rooms),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("airports.csv", _csv(airports, AIRPORT_COLUMNS))
        if schedules:
            archive.writestr("flight_schedules.csv", _csv(flights, SCHEDULE_COLUMNS))
        else:
            archive.writestr("flights.csv", _csv(flights, FLIGHT_COLUMNS))
        archive.writestr("hotels.csv", _csv(hotels, HOTEL_COLUMNS))
        archive.writestr("rooms.csv", _csv(rooms, ROOM_COLUMNS))
        archive.writestr(
            "README.md",
            README.format(
                seed=options.seed, start=options.start, days=options.days, dirty=options.dirty_rate
            ),
        )
    return GeneratedDataset(
        path=output,
        counts={
            "airports": len(airports),
            "flights": len(flights),
            "hotels": len(hotels),
            "rooms": len(rooms),
        },
        corrupted=corrupted,
    )
