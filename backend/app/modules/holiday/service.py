"""Holiday use cases: build packages, change one, confirm it, open a reservation, export it."""

from __future__ import annotations

import copy
import secrets
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.catalog.models import Flight, RoomType
from app.modules.holiday import engine as e
from app.modules.holiday.models import HolidayPackage
from app.modules.inventory.service import InventoryService, SoldOut

# ── API shapes ───────────────────────────────────────────────────────────────────────────────


class HolidayRequestIn(BaseModel):
    departure_airport: str = Field(description="BLR, DEL, BOM or MAA", min_length=3, max_length=3)
    country: str = Field(min_length=2, max_length=80)
    start_date: date = Field(description="The day the arrival flight lands")
    nights: int = Field(ge=1, le=30)
    adults: int = Field(ge=0, le=9)
    child_ages: list[int] = Field(default_factory=list, max_length=8)
    budget_inr: int = Field(ge=0)

    def to_request(self) -> e.Request:
        return e.Request(
            home=self.departure_airport.upper(),
            country=self.country,
            start=self.start_date,
            nights=self.nights,
            adults=self.adults,
            child_ages=tuple(self.child_ages),
            budget=self.budget_inr,
        )


class PackageOut(BaseModel):
    id: uuid.UUID
    label: str
    status: str
    reference: str | None
    request: dict[str, Any]
    items: list[dict[str, Any]]
    total_inr: int
    budget_inr: int
    left_inr: int = Field(description="Budget minus total; negative = over budget")
    travel_minutes: int
    average_stars: float
    cities: list[dict[str, Any]]
    problems: list[str] = Field(description="Broken rules; empty for a correct package")


class BuildOut(BaseModel):
    ok: bool
    packages: list[PackageOut]
    message: str | None = None
    reasons: list[str] = Field(default_factory=list)
    cheapest_total_inr: int | None = None
    suggestion: str | None = None


class OptionsOut(BaseModel):
    departure_cities: list[dict[str, str]]
    countries: list[dict[str, Any]]
    first_night: date
    last_departure: date
    min_nights: int
    max_nights: int


class ChangeIn(BaseModel):
    action: Literal["hotel", "flight", "add_attraction", "remove_attraction"]
    city: str | None = Field(default=None, description="hotel: the city whose hotel changes")
    hotel_id: str | None = None
    room_id: str | None = None
    leg: Literal["arrival", "return"] | None = None
    flight_id: str | None = None
    attraction_id: str | None = None
    day: date | None = Field(default=None, description="add_attraction: the visit day")
    item_id: str | None = Field(default=None, description="remove_attraction: the item")


class AlternativeOut(BaseModel):
    kind: str
    catalog_id: str
    room_id: str | None = None
    name: str
    detail: str
    price_inr: int
    difference_inr: int = Field(description="Against the current choice (G2)")
    valid: bool
    reason: str | None = None


# ── Service ──────────────────────────────────────────────────────────────────────────────────


def _request_of(row: HolidayPackage) -> e.Request:
    r = row.request
    return e.Request(
        r["departure_airport"],
        r["country"],
        date.fromisoformat(r["start_date"]),
        r["nights"],
        r["adults"],
        tuple(r["child_ages"]),
        r["budget_inr"],
    )


def _cities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "city": h["city"],
            "check_in": h["start"],
            "check_out": h["end"],
            "nights": h["details"]["nights"],
        }
        for h in sorted((i for i in items if i["type"] == "hotel"), key=lambda i: i["start"])
    ]


class HolidayService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._cat: e.Catalog | None = None

    @property
    def cat(self) -> e.Catalog:
        if self._cat is None:
            self._cat = e.load_catalog(self._session)
        return self._cat

    def options(self) -> OptionsOut:
        return OptionsOut(
            departure_cities=[
                {"airport": code, "city": city}
                for code, city in sorted(self.cat.departures.items())
            ],
            countries=[{"name": n, "cities": c} for n, c in sorted(self.cat.countries.items())],
            first_night=self.cat.first_night,
            last_departure=self.cat.last_departure,
            min_nights=e.MIN_NIGHTS,
            max_nights=e.MAX_NIGHTS,
        )

    def out(self, row: HolidayPackage, *, first: bool = False) -> PackageOut:
        req = _request_of(row)
        problems = e.check(row.items, req, self.cat, first=first) if row.status == "PLANNED" else []
        return PackageOut(
            id=row.id,
            label=row.label,
            status=row.status,
            reference=row.reference,
            request=row.request,
            items=row.items,
            total_inr=row.total_inr,
            budget_inr=req.budget,
            left_inr=req.budget - row.total_inr,
            travel_minutes=e.travel_minutes(row.items),
            average_stars=round(e.average_stars(row.items), 2),
            cities=_cities(row.items),
            problems=problems,
        )

    # M1, M2, M5, M8, G4
    def build(self, body: HolidayRequestIn, user_id: uuid.UUID | None = None) -> BuildOut:
        req = body.to_request()
        problems = e.request_problems(req, self.cat)
        if problems:
            raise ValidationFailed(" ".join(problems), code="INVALID_REQUEST")
        packages, why = e.build(req, self.cat)
        if not packages:
            return BuildOut(
                ok=False,
                packages=[],
                message="No holiday package is possible for this request.",
                reasons=why.summary() or ["No valid city plan exists for these dates."],
                suggestion="Try other dates, fewer travellers, or the other country.",
            )
        cheapest = e.total(packages["cheapest"])
        saved = []
        for label, items in packages.items():
            row = HolidayPackage(
                user_id=user_id,
                label=label,
                status="PLANNED",
                request=body.model_dump(mode="json"),
                items=items,
                total_inr=e.total(items),
            )
            self._session.add(row)
            saved.append(row)
        self._session.commit()
        if cheapest > req.budget:
            return BuildOut(
                ok=False,
                packages=[self.out(r, first=True) for r in saved],
                message=f"No package fits the budget of {req.budget:,} INR.",
                cheapest_total_inr=cheapest,
                suggestion=self._suggest(req, cheapest),
            )
        return BuildOut(ok=True, packages=[self.out(r, first=True) for r in saved])

    def _suggest(self, req: e.Request, cheapest: int) -> str:
        """M8: a concrete change that would help."""
        tips = [f"Raise the budget by {cheapest - req.budget:,} INR to {cheapest:,} INR"]
        if req.nights > e.MIN_NIGHTS:
            shorter = e.Request(
                req.home,
                req.country,
                req.start,
                req.nights - 1,
                req.adults,
                req.child_ages,
                req.budget,
            )
            found, _ = e.build(shorter, self.cat)
            if found and e.total(found["cheapest"]) <= req.budget:
                tips.append(
                    f"or travel {req.nights - 1} nights ({e.total(found['cheapest']):,} INR)"
                )
        other = [c for c in self.cat.countries if c != req.country]
        if other:
            tips.append(f"or try {other[0]}")
        return ", ".join(tips) + "."

    def get(self, package_id: uuid.UUID) -> HolidayPackage:
        row = self._session.get(HolidayPackage, package_id)
        if row is None:
            raise NotFound("Package not found.", code="PACKAGE_NOT_FOUND")
        return row

    # M6, G1, G2
    def change(self, package_id: uuid.UUID, body: ChangeIn) -> PackageOut:
        row = self.get(package_id)
        if row.status == "BOOKED":
            raise Conflict("A confirmed package cannot be changed.", code="PACKAGE_BOOKED")
        req = _request_of(row)
        items, notes = self._apply(copy.deepcopy(row.items), req, body)
        problems = e.check(items, req, self.cat, first=False)
        if problems:
            raise Conflict(
                "This change breaks a rule, so it was not made: " + " ".join(problems[:3]),
                code="CHANGE_REFUSED",
                details={"problems": problems},
            )
        for item in items:
            item["warnings"] = [n for n in notes if n.startswith(item["item_id"] + ":")]
            item["warnings"] = [w.split(":", 1)[1].strip() for w in item["warnings"]]
        row.items = e.number_items(items)
        row.total_inr = e.total(row.items)
        self._session.commit()
        return self.out(row)

    def _apply(
        self, items: list[dict[str, Any]], req: e.Request, body: ChangeIn
    ) -> tuple[list[dict[str, Any]], list[str]]:
        cat, notes = self.cat, list[str]()
        if body.action == "hotel":
            hotel = cat.hotels.get(body.hotel_id or "")
            old = next((i for i in items if i["type"] == "hotel" and i["city"] == body.city), None)
            if hotel is None or old is None or hotel.city != old["city"]:
                raise ValidationFailed("Choose a hotel in one of the package's cities.")
            check_in, check_out = date.fromisoformat(old["start"]), date.fromisoformat(old["end"])
            stay = [check_in + timedelta(days=d) for d in range((check_out - check_in).days)]
            rooms = [
                (r, k)
                for r in cat.rooms_by_hotel.get(hotel.key, [])
                if (body.room_id in (None, r.key))
                and (k := e.rooms_needed(r, req.adults, req.children)) is not None
                and cat.rooms_free(r.key, stay) >= k
            ]
            if not rooms:
                raise Conflict(
                    f"{hotel.name} has no room that fits and is free.", code="CHANGE_REFUSED"
                )
            room, k = min(rooms, key=lambda rk: rk[0].price * rk[1])
            items[items.index(old)] = e.hotel_item(hotel, room, k, check_in, check_out)
            items = self._refresh_airport_transfers(items, req, notes)
        elif body.action == "flight":
            flight = cat.flights.get(body.flight_id or "")
            old = next(
                (i for i in items if i["type"] == "flight" and i["details"]["leg"] == body.leg),
                None,
            )
            if flight is None or old is None:
                raise ValidationFailed("Choose an arrival or return flight.")
            items[items.index(old)] = e.flight_item(flight, cat, req, body.leg or "", old["city"])
            items = self._refresh_airport_transfers(items, req, notes)
        elif body.action == "add_attraction":
            a = cat.attractions.get(body.attraction_id or "")
            if a is None or body.day is None:
                raise ValidationFailed("Choose an attraction and a day.")
            busy = sorted(
                (e.parse(i["start"]), e.parse(i["end"]))
                for i in items
                if i["type"] in ("attraction", "transfer")
                and i["start"][:10] == body.day.isoformat()
            )
            cursor = datetime.combine(body.day, e.DAY_START)
            for s, en in busy:  # first gap long enough, after anything already planned
                start = e.fit_visit(a, body.day, cursor)
                if start and start + timedelta(minutes=a.visit) <= s:
                    break
                cursor = max(cursor, en + timedelta(minutes=e.GAP_MINUTES))
            start = e.fit_visit(a, body.day, cursor)
            if start is None:
                raise Conflict(f"{a.name} has no free time on {body.day}.", code="CHANGE_REFUSED")
            items.append(e.attraction_item(a, req, start))
        else:
            if not any(i["item_id"] == body.item_id and i["type"] == "attraction" for i in items):
                raise ValidationFailed("Choose an attraction in the package to remove.")
            items = [i for i in items if i["item_id"] != body.item_id]
        return e.number_items(items), notes

    def _refresh_airport_transfers(
        self, items: list[dict[str, Any]], req: e.Request, notes: list[str]
    ) -> list[dict[str, Any]]:
        """G1: a new flight or first/last hotel moves the airport transfers with it."""
        cat = self.cat
        hotels = sorted((i for i in items if i["type"] == "hotel"), key=lambda i: i["start"])
        arrival = next(
            i for i in items if i["type"] == "flight" and i["details"]["leg"] == "arrival"
        )
        ret = next(i for i in items if i["type"] == "flight" and i["details"]["leg"] == "return")
        items = [i for i in items if i["details"].get("leg") not in ("airport_in", "airport_out")]
        a_row, r_row = cat.flights[arrival["catalog_id"]], cat.flights[ret["catalog_id"]]
        first, last = cat.hotels[hotels[0]["catalog_id"]], cat.hotels[hotels[-1]["catalog_id"]]
        got_in = e._pick_airport_in(cat, req, a_row, first, "cheapest")
        got_out = e._pick_airport_out(cat, req, r_row, last)
        if got_in is None:
            raise Conflict(
                f"No airport transfer from {a_row.destination} reaches {first.name}.",
                code="CHANGE_REFUSED",
            )
        if got_out is None:
            raise Conflict(
                f"No transfer gets from {last.name} to {r_row.origin} 180 minutes before the flight.",
                code="CHANGE_REFUSED",
            )
        items.append(e.transfer_item(got_in[0], req, "airport_in", got_in[1], first.city))
        items.append(e.transfer_item(got_out[0], req, "airport_out", got_out[1], last.city))
        landing = a_row.arrival
        check_in_from = first.check_in
        if check_in_from and landing.date() == date.fromisoformat(hotels[0]["start"]):
            arrive = got_in[1] + timedelta(minutes=got_in[0].duration)
            if arrive < e.at(arrive.date(), check_in_from):
                notes.append(
                    f"{hotels[0]['item_id']}: You reach the hotel at {arrive:%H:%M}, before "
                    f"check-in from {check_in_from}."
                )
        return items

    def alternatives(
        self, package_id: uuid.UUID, kind: str, key: str | None
    ) -> list[AlternativeOut]:
        """G2: change options with the price difference against the current choice."""
        row = self.get(package_id)
        req, cat, out = _request_of(row), self.cat, []
        if kind == "hotel":
            current = next(i for i in row.items if i["type"] == "hotel" and i["city"] == key)
            check_in = date.fromisoformat(current["start"])
            nights = current["details"]["nights"]
            for hotel, room, k, price in e._hotel_options(
                cat, req, key or "", check_in, nights, "cheapest"
            ):
                out.append(
                    AlternativeOut(
                        kind="hotel",
                        catalog_id=hotel.key,
                        room_id=room.key,
                        name=hotel.name,
                        detail=f"{hotel.stars:.0f} stars, {hotel.area}, {k} x {room.name}",
                        price_inr=price,
                        difference_inr=price - current["price_inr"],
                        valid=True,
                    )
                )
        elif kind == "flight":
            current = next(
                i for i in row.items if i["type"] == "flight" and i["details"]["leg"] == key
            )
            city = current["city"]
            for f in e._flights(cat, req, key or "arrival", city, "cheapest"):
                price = f.price * req.travellers
                out.append(
                    AlternativeOut(
                        kind="flight",
                        catalog_id=f.key,
                        name=f"{f.number} {f.origin} to {f.destination}",
                        detail=f"{f.departure:%d %b %H:%M} to {f.arrival:%d %b %H:%M}, "
                        f"{'direct' if f.stops == 0 else f'{f.stops} stop'}, {f.seats} seats left",
                        price_inr=price,
                        difference_inr=price - current["price_inr"],
                        valid=True,
                    )
                )
        elif kind == "attraction":
            used = {i["catalog_id"] for i in row.items if i["type"] == "attraction"}
            hotels = [i for i in row.items if i["type"] == "hotel"]
            for a in cat.attractions.values():
                if a.key in used or a.city not in {h["city"] for h in hotels}:
                    continue
                price = e.attraction_price(a, req.adults, req.children)
                out.append(
                    AlternativeOut(
                        kind="attraction",
                        catalog_id=a.key,
                        name=a.name,
                        detail=f"{a.city}, {a.category}, {a.visit} min, open {a.open_from}-{a.open_until}",
                        price_inr=price,
                        difference_inr=price,
                        valid=True,
                    )
                )
        return sorted(out, key=lambda o: o.difference_inr)

    # M7, S2
    def mine(self, user_id: uuid.UUID) -> list[PackageOut]:
        """The traveller's confirmed holidays, newest first (shown in My Trips)."""
        rows = self._session.scalars(
            select(HolidayPackage)
            .where(HolidayPackage.user_id == user_id, HolidayPackage.status == "BOOKED")
            .order_by(HolidayPackage.booked_at.desc())
        )
        return [self.out(r) for r in rows]

    def confirm(self, package_id: uuid.UUID, user_id: uuid.UUID | None = None) -> PackageOut:
        row = self.get(package_id)
        if row.user_id is None:
            row.user_id = user_id
        if row.status == "BOOKED":
            return self.out(row)  # confirming twice gives the same reservation
        req = _request_of(row)
        problems = e.check(row.items, req, self.cat, first=False)
        if problems:
            raise Conflict(
                "The package no longer passes every rule: " + " ".join(problems[:3]),
                code="PACKAGE_INVALID",
                details={"problems": problems},
            )
        inventory = InventoryService(self._session)
        try:
            for item in row.items:
                claim = uuid.uuid5(row.id, item["item_id"])
                if item["type"] == "flight":
                    flight = self._session.get(Flight, self.cat.flights[item["catalog_id"]].db_id)
                    inventory.reserve_seats(claim, flight, req.travellers)  # type: ignore[arg-type]
                elif item["type"] == "hotel":
                    room = self._session.get(RoomType, self.cat.rooms[item["room_id"]].db_id)
                    inventory.reserve_rooms(
                        claim,
                        room,  # type: ignore[arg-type]
                        date.fromisoformat(item["start"]),
                        date.fromisoformat(item["end"]),
                        item["quantity"],
                    )
        except SoldOut as exc:
            self._session.rollback()
            raise Conflict(
                f"{exc.message} Someone booked the last seats or rooms first; change that part.",
                code="SOLD_OUT",
            ) from exc
        row.reference = self._new_reference()
        row.status = "BOOKED"
        row.booked_at = self._clock.now()
        items = copy.deepcopy(row.items)
        for item in items:
            item["status"] = "BOOKED"
            item["booking"] = {"reference": row.reference}
        row.items = items
        try:
            self._session.commit()
        except IntegrityError as exc:  # a reference collision, astronomically rare
            self._session.rollback()
            raise Conflict("Please confirm again.", code="RETRY") from exc
        return self.out(row)

    def _new_reference(self) -> str:
        while True:
            ref = str(secrets.randbelow(9 * 10**9) + 10**9)  # 10 digits, never a leading 0
            taken = self._session.scalar(
                select(HolidayPackage.id).where(HolidayPackage.reference == ref)
            )
            if taken is None:
                return ref

    def reservation(self, reference: str) -> PackageOut:
        row = self._session.scalar(
            select(HolidayPackage).where(HolidayPackage.reference == reference)
        )
        if row is None:
            raise NotFound("Reservation not found.", code="RESERVATION_NOT_FOUND")
        return self.out(row)

    def export(self, package_id: uuid.UUID) -> dict[str, Any]:
        """The shared trip format (handout section 6)."""
        row = self.get(package_id)
        req = _request_of(row)
        return {
            "trip_id": str(row.id),
            "traveler": {
                "name": "TripMind traveller",
                "home_airport": req.home,
                "adults": req.adults,
                "children": req.children,
                "child_ages": list(req.child_ages),
            },
            "start_date": req.start.isoformat(),
            "end_date": req.end.isoformat(),
            "country": req.country,
            "budget_inr": req.budget,
            "total_inr": row.total_inr,
            "status": row.status,
            "booking": {"reference": row.reference} if row.reference else None,
            "items": row.items,
        }
