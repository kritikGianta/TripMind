"""Discovery: the fare calendar ("which day is cheapest?") and Explore ("where can I go for this?").

Both use direct flights and published rates only, so every figure is a real starting price from
the catalog. Taxes that the data lacks are not included, as everywhere else; the exact price comes
from search and checkout.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import ValidationFailed
from app.modules.catalog.models import Airport, City, Flight, Hotel, RoomType
from app.modules.search.flights import FlightSearchService
from app.modules.search.locations import LocationService
from app.modules.search.pricing import MoneyOut
from app.modules.search.schemas import CabinClass

NOTE = "Starting prices from direct flights and published rates; taxes the data lacks are excluded."


class CalendarDayOut(BaseModel):
    date: date
    cheapest: MoneyOut | None = Field(
        description="Lowest direct fare for the party; None: no flight"
    )
    flights: int
    level: Literal["low", "typical", "high"] | None = Field(
        description="Compared with the other days shown"
    )


class FareCalendarOut(BaseModel):
    origin: str
    destination: str
    adults: int
    cabin_class: str
    days: list[CalendarDayOut]
    cheapest_day: date | None
    note: str


class ExploreStayOut(BaseModel):
    hotel_id: uuid.UUID
    name: str
    star_rating: float | None
    guest_rating: float | None


class ExploreOptionOut(BaseModel):
    city_id: uuid.UUID
    city: str
    country: str | None
    airport_code: str
    flights: MoneyOut = Field(description="Return fares for the party")
    stay: MoneyOut = Field(description="Cheapest well-rated stay for all nights and rooms")
    total: MoneyOut
    per_person: MoneyOut
    stay_option: ExploreStayOut


class ExploreOut(BaseModel):
    origin: str
    departure_date: date
    return_date: date
    nights: int
    adults: int
    budget: MoneyOut | None
    options: list[ExploreOptionOut] = Field(description="Cheapest first")
    over_budget: int = Field(description="Destinations reachable but above the budget")
    note: str


class DiscoverService(FlightSearchService):
    def _display_minor(self, amount_minor: int, currency: str) -> int | None:
        shown = self._converter.to_display(amount_minor, currency)
        return shown.amount_minor if shown else None

    def _money(self, minor: int) -> MoneyOut:
        return MoneyOut(amount_minor=minor, currency=self._converter.display_currency)

    def _cheapest_by_destination(
        self, origin_ids: list[uuid.UUID], day: date, cabin: str
    ) -> dict[uuid.UUID, int]:
        cheapest: dict[uuid.UUID, int] = {}
        for flight in self._day_flights(Flight.origin_airport_id.in_(origin_ids), day, day, cabin):
            minor = self._display_minor(flight.fare_minor or 0, flight.currency)
            if minor is not None:
                key = flight.destination_airport_id
                cheapest[key] = min(cheapest.get(key, minor), minor)
        return cheapest

    def _day_flights(self, condition: object, first: date, last: date, cabin: str) -> list[Flight]:
        return self._flights(
            condition,
            Flight.cabin_class == cabin,
            Flight.fare_minor.is_not(None),
            Flight.stops == 0,
            Flight.departure_local >= first,
            Flight.departure_local < last + timedelta(days=1),
        )

    def calendar(
        self, origin: str, destination: str, start: date, days: int, adults: int, cabin: CabinClass
    ) -> FareCalendarOut:
        if start < self._today:
            raise ValidationFailed("The start date is in the past.", code="DATE_IN_PAST")
        locations = LocationService(self._session)
        origins = {a.id for a in locations.airports_for(origin)}
        destinations = {a.id for a in locations.airports_for(destination)}
        if origins & destinations:
            raise ValidationFailed(
                "Origin and destination must be different.", code="SAME_ORIGIN_DESTINATION"
            )
        last = start + timedelta(days=days - 1)
        prices: dict[date, list[int]] = defaultdict(list)
        flights = self._day_flights(Flight.origin_airport_id.in_(origins), start, last, cabin)
        for flight in flights:
            if flight.destination_airport_id in destinations:
                minor = self._display_minor(flight.fare_minor or 0, flight.currency)
                if minor is not None:
                    prices[flight.departure_local.date()].append(minor * adults)
        lows = sorted(min(v) for v in prices.values())
        low_line = lows[len(lows) // 4] if lows else 0
        high_line = lows[len(lows) * 3 // 4] if lows else 0

        def level(minor: int) -> Literal["low", "typical", "high"]:
            if len(lows) < 4 or low_line == high_line:
                return "typical"
            return "low" if minor <= low_line else "high" if minor >= high_line else "typical"

        out = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            fares = prices.get(day)
            out.append(
                CalendarDayOut(
                    date=day,
                    cheapest=self._money(min(fares)) if fares else None,
                    flights=len(fares or ()),
                    level=level(min(fares)) if fares else None,
                )
            )
        priced = [(min(prices[d.date]), d.date) for d in out if d.cheapest is not None]
        return FareCalendarOut(
            origin=origin,
            destination=destination,
            adults=adults,
            cabin_class=cabin,
            days=out,
            cheapest_day=min(priced)[1] if priced else None,
            note=NOTE,
        )

    def _cheapest_stays(
        self, city_ids: set[uuid.UUID], min_rating: float
    ) -> dict[uuid.UUID, tuple[int, Hotel]]:
        """Cheapest nightly rate per city among stays rated at least `min_rating`."""
        best: dict[uuid.UUID, tuple[int, Hotel]] = {}
        rows = self._session.execute(
            select(RoomType, Hotel)
            .join(Hotel, Hotel.id == RoomType.hotel_id)
            .where(
                Hotel.city_id.in_(city_ids),
                Hotel.is_active.is_(True),
                RoomType.is_active.is_(True),
                RoomType.nightly_rate_minor.is_not(None),
                Hotel.guest_rating >= min_rating,
            )
        )
        for room, hotel in rows:
            minor = self._display_minor(room.nightly_rate_minor or 0, room.currency)
            if minor is not None and (hotel.city_id not in best or minor < best[hotel.city_id][0]):
                best[hotel.city_id] = (minor, hotel)
        return best

    def explore(
        self,
        origin: str,
        departure: date,
        nights: int,
        adults: int,
        budget: int | None,
        min_rating: float,
    ) -> ExploreOut:
        if departure < self._today:
            raise ValidationFailed("The departure date is in the past.", code="DATE_IN_PAST")
        origins = LocationService(self._session).airports_for(origin)
        origin_ids = [a.id for a in origins]
        back = departure + timedelta(days=nights)
        outbound = self._cheapest_by_destination(origin_ids, departure, "economy")
        airports = {
            a.id: a
            for a in self._session.scalars(select(Airport).where(Airport.id.in_(list(outbound))))
        }
        city_airports: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for airport in airports.values():
            city_airports[airport.city_id].append(airport.id)
        stays = self._cheapest_stays(set(city_airports), min_rating)
        cities = {
            c.id: c
            for c in self._session.scalars(select(City).where(City.id.in_(list(city_airports))))
        }
        rooms = math.ceil(adults / 2)
        options: list[ExploreOptionOut] = []
        for city_id, airport_ids in city_airports.items():
            if city_id not in stays or city_id in {a.city_id for a in origins}:
                continue
            returning = self._cheapest_by_destination(airport_ids, back, "economy")
            home = [returning[i] for i in origin_ids if i in returning]
            there = min(airport_ids, key=lambda i: outbound[i])
            if not home:
                continue
            flights = (outbound[there] + min(home)) * adults
            nightly, hotel = stays[city_id]
            stay = nightly * nights * rooms
            total = flights + stay
            options.append(
                ExploreOptionOut(
                    city_id=city_id,
                    city=cities[city_id].name,
                    country=cities[city_id].country,
                    airport_code=airports[there].code,
                    flights=self._money(flights),
                    stay=self._money(stay),
                    total=self._money(total),
                    per_person=self._money(total // adults),
                    stay_option=ExploreStayOut(
                        hotel_id=hotel.id,
                        name=hotel.name,
                        star_rating=hotel.star_rating,
                        guest_rating=hotel.guest_rating,
                    ),
                )
            )
        options.sort(key=lambda o: o.total.amount_minor)
        limit = budget * 100 if budget is not None else None
        within = [o for o in options if limit is None or o.total.amount_minor <= limit]
        return ExploreOut(
            origin=origin,
            departure_date=departure,
            return_date=back,
            nights=nights,
            adults=adults,
            budget=self._money(limit) if limit is not None else None,
            options=within,
            over_budget=len(options) - len(within),
            note=NOTE,
        )
