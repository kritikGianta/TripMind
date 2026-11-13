"""The holiday engine: catalog snapshot, prices, the travel rules (checker) and the builder.

Everything here works on plain Python objects loaded once per request from the catalog (the pack
is small: 469 flights, 49 hotels, 125 room types, 66 transfers, 56 attractions), so the rules read
like the handout. All times are local times of the place; prices are whole rupees (INR).

Package items follow the shared trip format (handout section 6) with one extra field, `details`,
that keeps what the rules need (airports, rooms, pickup and arrival times).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import select
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
)
from app.modules.inventory.models import RoomNightInventory
from app.modules.inventory.service import InventoryService

# The data window and trip limits (destinations.json `rules`).
# Used only when the catalog is empty; the real window is computed from the data.
FIRST_NIGHT = date(2027, 4, 1)
LAST_DEPARTURE = date(2027, 4, 20)
MIN_NIGHTS, MAX_NIGHTS, MIN_NIGHTS_PER_CITY = 3, 10, 2
PICKUP_AFTER_LANDING = 60  # minutes
AT_AIRPORT_BEFORE = 180  # minutes
DAY_START = time(9, 0)  # attractions start from 09:00
CITY_MOVE_AT = time(10, 0)  # preferred departure time on a city-change day
GAP_MINUTES = 30  # between two visits on the same day
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
Strategy = Literal["cheapest", "fastest", "best_rated"]


def minutes(clock: str) -> int:
    """'06:30' -> 390; '24:00' -> 1440 (midnight at the end of the day)."""
    h, m = clock.split(":")
    return int(h) * 60 + int(m)


def at(day: date, clock: str) -> datetime:
    return datetime.combine(day, time()) + timedelta(minutes=minutes(clock))


def window(day: date, start: str, end: str) -> tuple[datetime, datetime]:
    """A service or opening window on a day; one like 06:00-00:30 runs past midnight."""
    a, b = at(day, start), at(day, end)
    return (a, b + timedelta(days=1)) if b < a else (a, b)


def in_window(moment: datetime, start: str, end: str) -> bool:
    """True when a moment is inside the window that opens on its day or the day before."""
    for day in (moment.date(), moment.date() - timedelta(days=1)):
        a, b = window(day, start, end)
        if a <= moment <= b:
            return True
    return False


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ── Catalog snapshot ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FlightRow:
    key: str
    db_id: Any
    number: str
    airline: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    stops: int
    duration: int
    price: int  # per seat
    seats: int  # seats still free


@dataclass(frozen=True)
class HotelRow:
    key: str
    name: str
    city: str
    area: str | None
    stars: float
    rating: float
    family_friendly: bool
    image: str | None
    check_in: str | None
    check_out: str | None


@dataclass(frozen=True)
class RoomRow:
    key: str
    db_id: Any
    hotel: str
    name: str
    kind: str
    max_adults: int
    max_children: int
    price: int  # per room per night


@dataclass(frozen=True)
class TransferRow:
    key: str
    kind: str
    name: str
    airport: str | None
    city: str | None
    area: str | None
    from_city: str | None
    to_city: str | None
    max_passengers: int
    service_from: str
    service_until: str
    frequency: int | None
    duration: int
    pricing: str
    price: int
    child_price: int | None


@dataclass(frozen=True)
class AttractionRow:
    key: str
    name: str
    city: str
    category: str | None
    open_days: tuple[str, ...]
    open_from: str
    open_until: str
    closed: frozenset[str]
    visit: int
    child_friendly: bool
    price: int
    child_price: int | None
    image: str | None


@dataclass
class Catalog:
    departures: dict[str, str]  # airport code -> city
    countries: dict[str, list[str]]  # country name -> cities that have hotels
    links: dict[tuple[str, str], list[str]]  # (from city, to city) -> transfer keys
    serves: dict[str, set[str]]  # airport code -> cities it serves
    flights: dict[str, FlightRow]
    hotels: dict[str, HotelRow]
    rooms: dict[str, RoomRow]
    rooms_by_hotel: dict[str, list[RoomRow]]
    free: dict[tuple[str, date], int]  # (room key, night) -> rooms still free
    transfers: dict[str, TransferRow]
    attractions: dict[str, AttractionRow]

    @property
    def first_night(self) -> date:
        """First night any room is listed (the data window comes from the data)."""
        return min((night for _, night in self.free), default=FIRST_NIGHT)

    @property
    def last_departure(self) -> date:
        return max((f.departure.date() for f in self.flights.values()), default=LAST_DEPARTURE)

    def rooms_free(self, room: str, nights: list[date]) -> int:
        return min((self.free.get((room, n), 0) for n in nights), default=0)


def _rupees(minor: int | None) -> int | None:
    return None if minor is None else round(minor / 100)


def load_catalog(session: Session) -> Catalog:
    provided = DataOrigin.PROVIDED.value
    airports = {a.id: a.code for a in session.scalars(select(Airport))}
    cities = {c.id: c for c in session.scalars(select(City).where(City.origin == provided))}
    departures = {
        a.code: a.city_name
        for a in session.scalars(select(Airport).where(Airport.is_active.is_(True)))
        if cities.get(a.city_id) is not None and cities[a.city_id].is_departure
    }
    serves: dict[str, set[str]] = defaultdict(set)
    for airport_id, city_id in session.execute(
        select(AirportServedCity.airport_id, AirportServedCity.city_id)
    ):
        serves[airports[airport_id]].add(cities[city_id].name)
    transfers_by_id: dict[Any, str] = {}
    transfers: dict[str, TransferRow] = {}
    for t in session.scalars(select(Transfer).where(Transfer.is_active.is_(True))):
        transfers_by_id[t.id] = t.source_key
        transfers[t.source_key] = TransferRow(
            t.source_key,
            t.kind,
            t.name,
            t.airport_code,
            t.city_name,
            t.area,
            t.from_city_name,
            t.to_city_name,
            t.max_passengers,
            t.service_from,
            t.service_until,
            t.frequency_minutes,
            t.duration_minutes,
            t.pricing,
            _rupees(t.price_minor) or 0,
            _rupees(t.child_price_minor),
        )
    links: dict[tuple[str, str], list[str]] = defaultdict(list)
    for a, b, t_id in session.execute(
        select(CityLink.from_city_id, CityLink.to_city_id, CityLink.transfer_id)
    ):
        links[(cities[a].name, cities[b].name)].append(transfers_by_id[t_id])
    flight_rows = list(
        session.scalars(select(Flight).where(Flight.is_active.is_(True), Flight.origin == provided))
    )
    seats = InventoryService(session).availability([f.id for f in flight_rows])
    flights = {
        f.source_key: FlightRow(
            f.source_key,
            f.id,
            f.flight_number,
            f.airline_name or "",
            airports[f.origin_airport_id],
            airports[f.destination_airport_id],
            f.departure_local,
            f.arrival_local,
            f.stops,
            f.duration_minutes,
            _rupees(f.fare_minor) or 0,
            seats.get(f.id, 0),
        )
        for f in flight_rows
    }
    hotel_rows = list(
        session.scalars(select(Hotel).where(Hotel.is_active.is_(True), Hotel.origin == provided))
    )
    hotels = {
        h.source_key: HotelRow(
            h.source_key,
            h.name,
            h.city_name,
            h.area,
            h.star_rating or 0,
            h.guest_rating or 0,
            bool(h.family_friendly),
            h.image,
            h.check_in_time,
            h.check_out_time,
        )
        for h in hotel_rows
    }
    hotel_keys = {h.id: h.source_key for h in hotel_rows}
    rooms: dict[str, RoomRow] = {}
    by_hotel: dict[str, list[RoomRow]] = defaultdict(list)
    for r in session.scalars(select(RoomType).where(RoomType.is_active.is_(True))):
        if r.hotel_id not in hotel_keys:
            continue
        row = RoomRow(
            r.source_key,
            r.id,
            hotel_keys[r.hotel_id],
            r.name,
            r.room_kind or "",
            r.max_adults or r.max_occupancy,
            r.max_children or 0,
            _rupees(r.nightly_rate_minor) or 0,
        )
        rooms[row.key] = row
        by_hotel[row.hotel].append(row)
    room_keys = {r.db_id: r.key for r in rooms.values()}
    free = {
        (room_keys[room_id], night): capacity - reserved
        for room_id, night, capacity, reserved in session.execute(
            select(
                RoomNightInventory.room_type_id,
                RoomNightInventory.night,
                RoomNightInventory.capacity,
                RoomNightInventory.reserved,
            )
        )
        if room_id in room_keys
    }
    countries: dict[str, list[str]] = {}
    hotel_cities = {h.city for h in hotels.values()}
    for c in session.scalars(select(Country)):
        countries[c.name] = sorted(
            city.name
            for city in cities.values()
            if city.country_code == c.code and city.name in hotel_cities
        )
    attractions = {
        a.source_key: AttractionRow(
            a.source_key,
            a.name,
            a.city_name,
            a.category,
            tuple(a.open_days),
            a.open_from,
            a.open_until,
            frozenset(a.closed_dates or []),
            a.visit_minutes,
            bool(a.child_friendly),
            _rupees(a.price_minor) or 0,
            _rupees(a.child_price_minor),
            a.image,
        )
        for a in session.scalars(select(Attraction).where(Attraction.is_active.is_(True)))
    }
    return Catalog(
        departures,
        countries,
        dict(links),
        dict(serves),
        flights,
        hotels,
        rooms,
        dict(by_hotel),
        free,
        transfers,
        attractions,
    )


# ── The request ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Request:
    home: str  # departure airport code (BLR, DEL, BOM, MAA)
    country: str  # destination country name
    start: date  # holiday start date: the arrival flight lands that day
    nights: int
    adults: int
    child_ages: tuple[int, ...]
    budget: int  # INR

    @property
    def children(self) -> int:
        return len(self.child_ages)

    @property
    def travellers(self) -> int:
        return self.adults + self.children

    @property
    def end(self) -> date:
        return self.start + timedelta(days=self.nights)


def request_problems(req: Request, cat: Catalog) -> list[str]:
    """Why a request cannot be valid (M1). Empty when it is fine."""
    out = []
    if req.home not in cat.departures:
        out.append(f"Departure city must be one of {', '.join(sorted(cat.departures.values()))}.")
    if req.country not in cat.countries:
        out.append(f"Destination country must be one of {', '.join(sorted(cat.countries))}.")
    if not MIN_NIGHTS <= req.nights <= MAX_NIGHTS:
        out.append(f"A trip is {MIN_NIGHTS} to {MAX_NIGHTS} nights.")
    if req.adults < 1:
        out.append("At least one adult must travel.")
    if any(not 0 <= age <= 17 for age in req.child_ages):
        out.append("A child is aged 0 to 17.")
    if req.budget <= 0:
        out.append("The budget must be more than zero.")
    if req.start < cat.first_night or req.end > cat.last_departure:
        out.append(
            f"Flights and rooms exist from {cat.first_night:%d %b %Y} to "
            f"{cat.last_departure:%d %b %Y}: the first night must be on or after the first date "
            "and the flight home on or before the last."
        )
    return out


# ── Prices (handout section 4) ───────────────────────────────────────────────────────────────


def rooms_needed(room: RoomRow, adults: int, children: int) -> int | None:
    """Smallest k rooms that fit: adults <= k*max_adults, everyone <= k*(max_adults+max_children),
    and adults >= k (each room has an adult). None when no k fits."""
    for k in range(1, adults + 1):
        if adults <= k * room.max_adults and adults + children <= k * (
            room.max_adults + room.max_children
        ):
            return k
    return None


def transfer_price(t: TransferRow, adults: int, children: int) -> tuple[int, int]:
    """(price, quantity): per person, or per vehicle with vehicles rounded up."""
    if t.pricing == "PER_PERSON":
        child = t.child_price if t.child_price is not None else t.price
        return adults * t.price + children * child, adults + children
    vehicles = math.ceil((adults + children) / t.max_passengers)
    return t.price * vehicles, vehicles


def attraction_price(a: AttractionRow, adults: int, children: int) -> int:
    child = a.child_price if a.child_price is not None else a.price
    return adults * a.price + children * child


# ── Items ────────────────────────────────────────────────────────────────────────────────────


def _item(
    kind: str,
    name: str,
    city: str,
    catalog_id: str,
    start: str,
    end: str | None,
    quantity: int,
    price: int,
    details: dict[str, Any],
    room_id: str | None = None,
) -> dict[str, Any]:
    return {
        "item_id": "",
        "type": kind,
        "name": name,
        "city": city,
        "status": "PLANNED",
        "catalog_id": catalog_id,
        "room_id": room_id,
        "start": start,
        "end": end,
        "quantity": quantity,
        "price_inr": price,
        "booking": None,
        "sources": [],
        "warnings": [],
        "details": details,
    }


def flight_item(f: FlightRow, cat: Catalog, req: Request, leg: str, city: str) -> dict[str, Any]:
    return _item(
        "flight",
        f"{f.number} {f.origin} to {f.destination}",
        city,
        f.key,
        iso(f.departure),
        iso(f.arrival),
        req.travellers,
        f.price * req.travellers,
        {
            "leg": leg,
            "from": f.origin,
            "to": f.destination,
            "airline": f.airline,
            "stops": f.stops,
            "duration_minutes": f.duration,
        },
    )


def hotel_item(h: HotelRow, r: RoomRow, k: int, check_in: date, check_out: date) -> dict[str, Any]:
    n = (check_out - check_in).days
    return _item(
        "hotel",
        h.name,
        h.city,
        h.key,
        check_in.isoformat(),
        check_out.isoformat(),
        k,
        r.price * k * n,
        {
            "room_name": r.name,
            "room_type": r.kind,
            "nights": n,
            "stars": h.stars,
            "area": h.area,
            "rating": h.rating,
            "image": h.image,
        },
        room_id=r.key,
    )


def transfer_item(
    t: TransferRow, req: Request, leg: str, pickup: datetime, city: str
) -> dict[str, Any]:
    price, qty = transfer_price(t, req.adults, req.children)
    return _item(
        "transfer",
        t.name,
        city,
        t.key,
        iso(pickup),
        iso(pickup + timedelta(minutes=t.duration)),
        qty,
        price,
        {
            "leg": leg,
            "kind": t.kind,
            "duration_minutes": t.duration,
            "from_city": t.from_city,
            "to_city": t.to_city,
            "airport": t.airport,
        },
    )


def attraction_item(a: AttractionRow, req: Request, start: datetime) -> dict[str, Any]:
    return _item(
        "attraction",
        a.name,
        a.city,
        a.key,
        iso(start),
        iso(start + timedelta(minutes=a.visit)),
        req.travellers,
        attraction_price(a, req.adults, req.children),
        {"category": a.category, "image": a.image},
    )


def number_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Time order for the day-by-day plan; a hotel check-in comes last on its day."""

    def when(item: dict[str, Any]) -> str:
        start = str(item["start"])
        return start + "T23:59" if item["type"] == "hotel" else start

    items.sort(key=when)
    for n, item in enumerate(items, start=1):
        item["item_id"] = f"i{n}"
    return items


# ── Timing helpers for transfers and visits ──────────────────────────────────────────────────


def earliest_pickup(t: TransferRow, earliest: datetime) -> datetime | None:
    """First pickup at or after `earliest` inside the service window."""
    best = None
    for day in (
        earliest.date() - timedelta(days=1),
        earliest.date(),
        earliest.date() + timedelta(1),
    ):
        a, b = window(day, t.service_from, t.service_until)
        pickup = max(earliest, a)
        if pickup <= b and (best is None or pickup < best):
            best = pickup
    return best


def latest_pickup(t: TransferRow, latest: datetime) -> datetime | None:
    """Last pickup at or before `latest` inside the service window."""
    best = None
    for day in (latest.date() - timedelta(days=1), latest.date()):
        a, b = window(day, t.service_from, t.service_until)
        pickup = min(latest, b)
        if pickup >= a and (best is None or pickup > best):
            best = pickup
    return best


def city_move_departure(t: TransferRow, day: date) -> datetime | None:
    """Departure of a transfer between cities on `day`: the first one from 10:00 (trains and
    buses leave every `frequency` minutes), else the first of the day."""
    a, b = window(day, t.service_from, t.service_until)
    target = max(a, datetime.combine(day, CITY_MOVE_AT))
    if t.frequency:
        steps = math.ceil((target - a).total_seconds() / 60 / t.frequency)
        target = a + timedelta(minutes=steps * t.frequency)
    if target > b:
        target = a
    return target if target.date() == day else None


def airport_transfers(cat: Catalog, airport: str, hotel: HotelRow) -> list[TransferRow]:
    return [
        t
        for t in cat.transfers.values()
        if t.kind.startswith("AIRPORT")
        and t.airport == airport
        and t.city == hotel.city
        and (t.area is None or t.area == hotel.area)
    ]


def attraction_open(a: AttractionRow, start: datetime) -> bool:
    end = start + timedelta(minutes=a.visit)
    if WEEKDAYS[start.weekday()] not in a.open_days or start.date().isoformat() in a.closed:
        return False
    lo, hi = window(start.date(), a.open_from, a.open_until)
    return lo <= start and end <= hi


def fit_visit(a: AttractionRow, day: date, earliest: datetime) -> datetime | None:
    if WEEKDAYS[day.weekday()] not in a.open_days or day.isoformat() in a.closed:
        return None
    lo, hi = window(day, a.open_from, a.open_until)
    start = max(lo, earliest)
    return start if start + timedelta(minutes=a.visit) <= hi else None


# ── The rule checker (M3): every rule in handout section 4 ────────────────────────────────────


def check(items: list[dict[str, Any]], req: Request, cat: Catalog, *, first: bool) -> list[str]:
    """Every broken rule, in plain words. Empty list = the package is correct.

    `first` adds the rule that only the first package must meet: 1-2 attractions on every full day.
    """
    problems: list[str] = []
    bad = problems.append
    flights = [i for i in items if i["type"] == "flight"]
    hotels = sorted((i for i in items if i["type"] == "hotel"), key=lambda i: i["start"])
    transfers = [i for i in items if i["type"] == "transfer"]
    visits = [i for i in items if i["type"] == "attraction"]

    # Dates and cities
    problems += request_problems(req, cat)
    arrival = [f for f in flights if f["details"].get("leg") == "arrival"]
    ret = [f for f in flights if f["details"].get("leg") == "return"]
    if len(arrival) != 1 or len(ret) != 1 or len(flights) != 2:
        bad("A package has exactly one arrival flight and one return flight.")
        return problems
    if not hotels:
        bad("A package has a hotel for every night.")
        return problems
    plan = [
        (h["city"], date.fromisoformat(h["start"]), date.fromisoformat(h["end"])) for h in hotels
    ]
    cities_in_country = set(cat.countries.get(req.country, []))
    seen: set[str] = set()
    cursor = req.start
    for n, (city, check_in, check_out) in enumerate(plan):
        if check_in != cursor:
            bad(f"Hotel nights must follow each other from {req.start} (gap or overlap at {city}).")
        if city not in cities_in_country:
            bad(f"{city} is not in {req.country}.")
        if city in seen:
            bad(f"{city} appears more than once in the plan.")
        seen.add(city)
        if (check_out - check_in).days < MIN_NIGHTS_PER_CITY:
            bad(f"Each city has at least {MIN_NIGHTS_PER_CITY} nights in a row ({city}).")
        if n and (plan[n - 1][0], city) not in cat.links:
            bad(f"There is no transfer from {plan[n - 1][0]} to {city}.")
        cursor = check_out
    if cursor != req.end:
        bad(f"Hotels must cover every night up to {req.end}, with no hotel night on the last day.")
    first_city, last_city = plan[0][0], plan[-1][0]

    # Flights
    a_row = cat.flights.get(arrival[0]["catalog_id"])
    r_row = cat.flights.get(ret[0]["catalog_id"])
    if a_row is None or r_row is None:
        bad("A flight in the package is not in the catalog.")
        return problems
    if a_row.origin != req.home:
        bad(f"The arrival flight must leave from {req.home}.")
    if a_row.arrival.date() != req.start:
        bad(f"The arrival flight must land on {req.start} (local time).")
    if first_city not in cat.serves.get(a_row.destination, set()):
        bad(f"{a_row.destination} does not serve {first_city}, the first city.")
    if r_row.destination != req.home:
        bad(f"The return flight must fly to {req.home}.")
    if r_row.departure.date() != req.end:
        bad(f"The return flight must leave on {req.end} (local time).")
    if last_city not in cat.serves.get(r_row.origin, set()):
        bad(f"{r_row.origin} does not serve {last_city}, the last city.")
    for row in (a_row, r_row):
        if row.seats < req.travellers:
            bad(f"{row.number} has {row.seats} seats left for {req.travellers} travellers.")

    # Hotels
    for h in hotels:
        room = cat.rooms.get(h["room_id"] or "")
        hotel = cat.hotels.get(h["catalog_id"])
        if room is None or hotel is None or room.hotel != hotel.key:
            bad(f"{h['name']}: the room type is not a room of this hotel.")
            continue
        k = h["quantity"]
        fits = (
            req.adults <= k * room.max_adults
            and req.travellers <= k * (room.max_adults + room.max_children)
            and req.adults >= k
        )
        if not fits:
            bad(f"{k} x {room.name} at {hotel.name} does not fit the travellers.")
        stay = [
            date.fromisoformat(h["start"]) + timedelta(days=d)
            for d in range(h["details"]["nights"])
        ]
        if cat.rooms_free(room.key, stay) < k:
            bad(f"{hotel.name} has fewer than {k} free {room.name} rooms on a night of the stay.")

    # Airport transfers
    def airport_leg(leg: str) -> dict[str, Any] | None:
        found = [t for t in transfers if t["details"].get("leg") == leg]
        if len(found) != 1:
            bad(f"A package has exactly one {leg.replace('_', ' ')} transfer.")
            return None
        return found[0]

    hotel_in = cat.hotels.get(hotels[0]["catalog_id"])
    hotel_out = cat.hotels.get(hotels[-1]["catalog_id"])
    leg_in, leg_out = airport_leg("airport_in"), airport_leg("airport_out")
    if leg_in and hotel_in:
        t = cat.transfers.get(leg_in["catalog_id"])
        pickup = parse(leg_in["start"])
        if t is None or t not in airport_transfers(cat, a_row.destination, hotel_in):
            bad("The airport transfer must serve the arrival airport and the first hotel's area.")
        elif pickup < a_row.arrival + timedelta(minutes=PICKUP_AFTER_LANDING):
            bad("The airport pickup is at least 60 minutes after landing.")
        elif not in_window(pickup, t.service_from, t.service_until):
            bad(f"The airport pickup at {pickup:%H:%M} is outside {t.name}'s service hours.")
    if leg_out and hotel_out:
        t = cat.transfers.get(leg_out["catalog_id"])
        pickup = parse(leg_out["start"])
        if t is None or t not in airport_transfers(cat, r_row.origin, hotel_out):
            bad("The transfer to the airport must serve the last hotel's area and that airport.")
        elif pickup + timedelta(minutes=t.duration) > r_row.departure - timedelta(
            minutes=AT_AIRPORT_BEFORE
        ):
            bad("The traveller must reach the airport at least 180 minutes before departure.")
        elif not in_window(pickup, t.service_from, t.service_until):
            bad(f"The hotel pickup at {pickup:%H:%M} is outside {t.name}'s service hours.")

    # Transfers between cities
    moves = [t for t in transfers if t["details"].get("leg") == "city_move"]
    for n in range(1, len(plan)):
        a, b, day = plan[n - 1][0], plan[n][0], plan[n][1]
        found = [
            t
            for t in moves
            if t["start"][:10] == day.isoformat()
            and t["details"].get("from_city") == a
            and t["details"].get("to_city") == b
        ]
        if len(found) != 1:
            bad(f"On {day} the package needs one transfer from {a} to {b}.")
            continue
        t = cat.transfers.get(found[0]["catalog_id"])
        if t is None or t.key not in cat.links.get((a, b), []):
            bad(f"{found[0]['name']} is not a transfer from {a} to {b}.")
        elif not in_window(parse(found[0]["start"]), t.service_from, t.service_until):
            bad(f"{t.name} does not run at {found[0]['start'][11:]}.")
    if len(moves) != len(plan) - 1:
        bad("There must be exactly one transfer between cities on each city-change day.")

    # Attractions
    def city_on(day: date) -> str | None:
        for city, check_in, check_out in plan:
            if check_in <= day < check_out:
                return str(city)
        return None

    busy: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    for ti in transfers:
        busy[ti["start"][:10]].append((parse(ti["start"]), parse(ti["end"])))
    used: set[str] = set()
    for v in visits:
        a = cat.attractions.get(v["catalog_id"])
        start, end = parse(v["start"]), parse(v["end"])
        day = start.date()
        if a is None:
            bad(f"{v['name']} is not in the catalog.")
            continue
        if a.key in used:
            bad(f"{a.name} is in the package more than once.")
        used.add(a.key)
        if day >= req.end:
            bad(f"No attractions on the last day ({a.name}).")
        if a.city != city_on(day):
            bad(f"{a.name} is not in the city of that night's hotel ({day}).")
        if not attraction_open(a, start):
            bad(f"{a.name} is not open for the whole visit on {day} at {start:%H:%M}.")
        if end - start != timedelta(minutes=a.visit):
            bad(f"A visit to {a.name} takes {a.visit} minutes.")
        if day == req.start and start < parse(leg_in["end"]) if leg_in else False:
            bad(f"{a.name} starts before the traveller reaches {a.city}.")
        for other_start, other_end in busy[day.isoformat()]:
            if start < other_end and other_start < end:
                bad(f"{a.name} on {day} overlaps another visit or a transfer.")
        busy[day.isoformat()].append((start, end))
    if first:
        change_days = {c[1] for c in plan[1:]}
        day = req.start + timedelta(days=1)
        while day < req.end:
            if day not in change_days:
                n = sum(1 for v in visits if v["start"][:10] == day.isoformat())
                if not 1 <= n <= 2:
                    bad(f"The first package has 1-2 attractions on every full day ({day}: {n}).")
            day += timedelta(days=1)

    # Prices
    for i in items:
        expected = expected_price(i, req, cat)
        if expected is not None and abs(expected - i["price_inr"]) > max(1, expected * 0.01):
            bad(f"{i['name']}: price should be {expected} INR, not {i['price_inr']}.")
    return problems


def expected_price(i: dict[str, Any], req: Request, cat: Catalog) -> int | None:
    if i["type"] == "flight" and (f := cat.flights.get(i["catalog_id"])):
        return f.price * req.travellers
    if i["type"] == "hotel" and (r := cat.rooms.get(i["room_id"] or "")):
        return int(r.price * i["quantity"] * i["details"]["nights"])
    if i["type"] == "transfer" and (t := cat.transfers.get(i["catalog_id"])):
        return transfer_price(t, req.adults, req.children)[0]
    if i["type"] == "attraction" and (a := cat.attractions.get(i["catalog_id"])):
        return attraction_price(a, req.adults, req.children)
    return None


def total(items: list[dict[str, Any]]) -> int:
    return sum(int(i["price_inr"]) for i in items)


def travel_minutes(items: list[dict[str, Any]]) -> int:
    """'Fastest' (G4): both flights + transfers between cities (airport transfers do not count)."""
    return sum(
        i["details"]["duration_minutes"]
        for i in items
        if i["type"] == "flight" or (i["type"] == "transfer" and i["details"]["leg"] == "city_move")
    )


def average_stars(items: list[dict[str, Any]]) -> float:
    """'Best rated' (G4): hotel stars averaged over the nights."""
    hotels = [i for i in items if i["type"] == "hotel"]
    nights = sum(h["details"]["nights"] for h in hotels)
    return float(
        sum(h["details"]["stars"] * h["details"]["nights"] for h in hotels) / max(nights, 1)
    )


# ── The builder (M2, G4) ─────────────────────────────────────────────────────────────────────


def city_plans(req: Request, cat: Catalog) -> Iterator[list[tuple[str, int]]]:
    """Every valid city plan: which cities, in what order, how many nights each (at least 2).

    Our city rule: all orders are tried; plans with more cities come first (a fuller holiday),
    and the cheapest, fastest and best-rated packages are then picked across all of them."""
    cities = cat.countries.get(req.country, [])

    def grow(plan: list[tuple[str, int]], left: int) -> Iterator[list[tuple[str, int]]]:
        for city in cities:
            if any(c == city for c, _ in plan) or (plan and (plan[-1][0], city) not in cat.links):
                continue
            for n in range(MIN_NIGHTS_PER_CITY, left + 1):
                rest = left - n
                if rest == 0:
                    yield [*plan, (city, n)]
                elif rest >= MIN_NIGHTS_PER_CITY:
                    yield from grow([*plan, (city, n)], rest)

    yield from sorted(grow([], req.nights), key=lambda p: -len(p))


@dataclass
class Failure:
    reasons: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, reason: str) -> None:
        self.reasons[reason] += 1

    def summary(self) -> list[str]:
        return [r for r, _ in sorted(self.reasons.items(), key=lambda kv: -kv[1])][:4]


def _hotel_options(
    cat: Catalog, req: Request, city: str, check_in: date, nights: int, strategy: Strategy
) -> list[tuple[HotelRow, RoomRow, int, int]]:
    """(hotel, room, rooms needed, price) that fit the party and are free every night."""
    stay = [check_in + timedelta(days=d) for d in range(nights)]
    out = []
    for hotel in (h for h in cat.hotels.values() if h.city == city):
        for room in cat.rooms_by_hotel.get(hotel.key, []):
            k = rooms_needed(room, req.adults, req.children)
            if k is not None and cat.rooms_free(room.key, stay) >= k:
                out.append((hotel, room, k, room.price * k * nights))
    family = req.children > 0
    if strategy == "best_rated":
        out.sort(key=lambda o: (-o[0].stars, o[3]))
    else:
        out.sort(key=lambda o: (o[3], not (family and o[0].family_friendly)))
    return out


def _flights(
    cat: Catalog, req: Request, leg: str, city: str, strategy: Strategy
) -> list[FlightRow]:
    if leg == "arrival":
        rows = [
            f
            for f in cat.flights.values()
            if f.origin == req.home
            and f.arrival.date() == req.start
            and city in cat.serves.get(f.destination, set())
            and f.seats >= req.travellers
        ]
    else:
        rows = [
            f
            for f in cat.flights.values()
            if f.destination == req.home
            and f.departure.date() == req.end
            and city in cat.serves.get(f.origin, set())
            and f.seats >= req.travellers
        ]
    key = (
        (lambda f: (f.duration, f.price))
        if strategy == "fastest"
        else (lambda f: (f.price, f.duration))
    )
    return sorted(rows, key=key)


def _pick_airport_in(
    cat: Catalog, req: Request, flight: FlightRow, hotel: HotelRow, strategy: Strategy
) -> tuple[TransferRow, datetime] | None:
    best = None
    for t in airport_transfers(cat, flight.destination, hotel):
        pickup = earliest_pickup(t, flight.arrival + timedelta(minutes=PICKUP_AFTER_LANDING))
        if pickup is None:
            continue
        cost = transfer_price(t, req.adults, req.children)[0]
        # Never leave a family waiting overnight when another transfer runs: a pickup within two
        # hours of the earliest possible one comes first, then price (or time for 'fastest').
        long_wait = pickup - flight.arrival > timedelta(minutes=PICKUP_AFTER_LANDING + 120)
        key = (long_wait, pickup, cost) if strategy == "fastest" else (long_wait, cost, pickup)
        if best is None or key < best[0]:
            best = (key, t, pickup)
    return None if best is None else (best[1], best[2])


def _pick_airport_out(
    cat: Catalog, req: Request, flight: FlightRow, hotel: HotelRow
) -> tuple[TransferRow, datetime] | None:
    best = None
    for t in airport_transfers(cat, flight.origin, hotel):
        latest = flight.departure - timedelta(minutes=AT_AIRPORT_BEFORE + t.duration)
        pickup = latest_pickup(t, latest)
        if pickup is None:
            continue
        key = (transfer_price(t, req.adults, req.children)[0], -pickup.timestamp())
        if best is None or key < best[0]:
            best = (key, t, pickup)
    return None if best is None else (best[1], best[2])


def _plan_attractions(
    cat: Catalog, req: Request, city: str, days: list[date], used: set[str], strategy: Strategy
) -> list[dict[str, Any]] | None:
    """1-2 attractions on each full day in a city (1 for the cheapest package)."""
    out: list[dict[str, Any]] = []
    per_day = 1 if strategy == "cheapest" else 2
    family = req.children > 0
    candidates = sorted(
        (a for a in cat.attractions.values() if a.city == city),
        key=lambda a: (
            not (family and a.child_friendly),
            attraction_price(a, req.adults, req.children) if strategy == "cheapest" else -0,
            a.key,
        ),
    )
    for day in days:
        cursor = datetime.combine(day, DAY_START)
        placed = 0
        categories: set[str | None] = set()
        for a in candidates:
            if placed >= per_day:
                break
            if a.key in used or (placed and a.category in categories):
                continue
            start = fit_visit(a, day, cursor)
            if start is None:
                continue
            out.append(attraction_item(a, req, start))
            used.add(a.key)
            categories.add(a.category)
            cursor = start + timedelta(minutes=a.visit + GAP_MINUTES)
            placed += 1
        if placed == 0:
            return None
    return out


def build_one(
    req: Request, cat: Catalog, plan: list[tuple[str, int]], strategy: Strategy, why: Failure
) -> list[dict[str, Any]] | None:
    """One complete package for a city plan, or None (the reason is recorded in `why`)."""
    first_city, last_city = plan[0][0], plan[-1][0]
    arrivals = _flights(cat, req, "arrival", first_city, strategy)
    if not arrivals:
        why.add(
            f"No flight from {req.home} with {req.travellers} free seats lands on {req.start} "
            f"at an airport serving {first_city}."
        )
        return None
    returns = _flights(cat, req, "return", last_city, strategy)
    if not returns:
        why.add(
            f"No flight to {req.home} with {req.travellers} free seats leaves {last_city}'s "
            f"airport on {req.end}."
        )
        return None
    # Check-in dates of each city.
    starts, day = [], req.start
    for _, n in plan:
        starts.append(day)
        day += timedelta(days=n)
    options = [
        _hotel_options(cat, req, city, check_in, n, strategy)
        for (city, n), check_in in zip(plan, starts, strict=True)
    ]
    for (city, _), opts in zip(plan, options, strict=True):
        if not opts:
            why.add(f"No hotel in {city} has free rooms for the travellers on every night.")
            return None
    chosen: list[tuple[HotelRow, RoomRow, int, int] | None] = [o[0] for o in options]
    # First and last hotels must be reachable by an airport transfer from the chosen flights.
    pick_in = pick_out = None
    for flight in arrivals[:8]:
        for option in options[0]:
            got = _pick_airport_in(cat, req, flight, option[0], strategy)
            if got:
                pick_in, chosen[0] = (flight, *got), option
                break
        if pick_in:
            break
    if pick_in is None:
        why.add(
            f"No airport transfer reaches a free hotel in {first_city} after the arrival flight."
        )
        return None
    last_options: list[tuple[HotelRow, RoomRow, int, int] | None] = (
        [chosen[0]] if len(plan) == 1 else list(options[-1])
    )
    for flight in returns[:8]:
        for last in last_options:
            if last is None:
                continue
            got = _pick_airport_out(cat, req, flight, last[0])
            if got:
                pick_out, chosen[-1] = (flight, *got), last
                break
        if pick_out:
            break
    if pick_out is None:
        why.add(f"No transfer reaches {last_city}'s airport 180 minutes before a flight home.")
        return None
    items = [
        flight_item(pick_in[0], cat, req, "arrival", first_city),
        flight_item(pick_out[0], cat, req, "return", last_city),
        transfer_item(pick_in[1], req, "airport_in", pick_in[2], first_city),
        transfer_item(pick_out[1], req, "airport_out", pick_out[2], last_city),
    ]
    used: set[str] = set()
    for idx, ((city, n), check_in) in enumerate(zip(plan, starts, strict=True)):
        hotel, room, k, _ = chosen[idx]  # type: ignore[misc]
        items.append(hotel_item(hotel, room, k, check_in, check_in + timedelta(days=n)))
        if idx:
            prev = plan[idx - 1][0]
            moves = [cat.transfers[k_] for k_ in cat.links.get((prev, city), [])]
            moves.sort(
                key=(lambda t: (t.duration, t.price))
                if strategy == "fastest"
                else (lambda t: (transfer_price(t, req.adults, req.children)[0], t.duration))
            )
            move = next(((t, d) for t in moves if (d := city_move_departure(t, check_in))), None)
            if move is None:
                why.add(f"No transfer from {prev} to {city} runs on {check_in}.")
                return None
            items.append(transfer_item(move[0], req, "city_move", move[1], city))
        full_days = [check_in + timedelta(days=d) for d in range(1, n)]
        visits = _plan_attractions(cat, req, city, full_days, used, strategy)
        if visits is None:
            why.add(f"Not enough attractions are open in {city} for every full day.")
            return None
        items += visits
    items = number_items(items)
    if check(items, req, cat, first=True):
        why.add("A built package broke a rule and was dropped.")
        return None
    return items


def build(req: Request, cat: Catalog) -> tuple[dict[str, list[dict[str, Any]]], Failure]:
    """Cheapest, fastest and best rated packages (G4), searched over every city plan."""
    why = Failure()
    built: list[tuple[Strategy, list[dict[str, Any]]]] = []
    for plan in city_plans(req, cat):
        for strategy in ("cheapest", "fastest", "best_rated"):
            items = build_one(req, cat, plan, strategy, why)
            if items:
                built.append((strategy, items))
    if not built:
        return {}, why
    everything = [items for _, items in built]
    cheapest = min(everything, key=total)
    fastest = min(everything, key=lambda i: (travel_minutes(i), total(i)))
    affordable = [i for i in everything if total(i) <= req.budget]
    best = max(affordable or everything, key=lambda i: (average_stars(i), -total(i)))
    return {"cheapest": cheapest, "fastest": fastest, "best_rated": best}, why
