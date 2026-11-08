"""The connected trip after booking: what is still missing, and the trip in your calendar.

Suggestions look at what a trip already holds. A flight with no stay gets stays at the destination
for those dates (personalised when the traveller has a preference model). A one-way flight with
an end date gets return flights. A stay with no flight gets a search link for getting there. Each
suggestion carries the item to send to checkout with this `trip_id`, so it joins the same trip.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select

from app.core.errors import NotFound
from app.modules.auth.models import User
from app.modules.bookings.models import Booking, BookingItem, ItemStatus, Trip
from app.modules.bookings.service import BookingService, _aware
from app.modules.catalog.models import Airport
from app.modules.ml.preferences import UserPreference
from app.modules.search.flights import FlightQuery
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.pricing import MoneyOut, load_search_rules

LIVE = (ItemStatus.HELD, ItemStatus.CONFIRMED)


class TripSuggestionOut(BaseModel):
    kind: Literal["stay", "return_flight", "outbound_flight"]
    title: str
    subtitle: str
    price: MoneyOut | None
    reasons: list[str]
    checkout_item: dict[str, Any] | None
    link: str


class TripSuggestionsOut(BaseModel):
    trip_id: uuid.UUID
    complete: bool
    missing: list[str]
    suggestions: list[TripSuggestionOut]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


class ConnectedTripService(BookingService):
    def _trip_items(self, user: User, trip_id: uuid.UUID) -> tuple[Trip, list[BookingItem]]:
        trip = self._session.get(Trip, trip_id)
        if trip is None or trip.user_id != user.id:
            raise NotFound("Trip not found.", code="TRIP_NOT_FOUND")
        items = list(
            self._session.scalars(
                select(BookingItem)
                .join(Booking, Booking.id == BookingItem.booking_id)
                .where(Booking.trip_id == trip.id, BookingItem.status.in_(LIVE))
                .order_by(BookingItem.starts_at)
            )
        )
        return trip, items

    def _stays(
        self, user: User, city: uuid.UUID, start: date, end: date
    ) -> list[TripSuggestionOut]:
        today = (self._clock.now() - timedelta(hours=12)).date()
        hotels = HotelSearchService(
            self._session,
            self._converter,
            load_search_rules(self._settings.config_dir),
            today,
            preference=self._session.get(UserPreference, user.id),
        )
        result = hotels.search(
            HotelQuery(city=str(city), stay=Stay(check_in=start, check_out=end, guests=2, rooms=1))
        )
        out = []
        for hotel in [r for r in result.results if r.bookable][:3]:
            room = hotel.cheapest_room
            out.append(
                TripSuggestionOut(
                    kind="stay",
                    title=hotel.name,
                    subtitle=f"{room.name}, {start:%d %b} to {end:%d %b}",
                    price=room.price.display_total if room.price else None,
                    reasons=hotel.personal_reasons,
                    checkout_item={
                        "kind": "hotel",
                        "room_type_id": str(room.room_type_id),
                        "check_in": start.isoformat(),
                        "check_out": end.isoformat(),
                        "rooms": 1,
                        "guests": 2,
                    },
                    link=f"/stays/{hotel.id}?checkIn={start}&checkOut={end}",
                )
            )
        return out

    def _flights_between(
        self, origin: str, destination: str, day: date, adults: int
    ) -> list[TripSuggestionOut]:
        result = self._flights.search(
            FlightQuery(
                origin=origin,
                destination=destination,
                departure_date=day,
                adults=adults,
                sort="cheapest",
            )
        )
        return [
            TripSuggestionOut(
                kind="return_flight",
                title=f"{origin} to {destination}",
                subtitle=f"{o.legs[0].flight_number}, {o.legs[0].departure_local:%a %d %b, %H:%M}",
                price=o.price.display_total,
                reasons=[],
                checkout_item={"kind": "flight", "offer_id": o.id, "adults": adults},
                link=f"/flights?trip=oneway&from={origin}&to={destination}&depart={day}&adults={adults}",
            )
            for o in result.outbound.offers
            if o.bookable
        ][:3]

    def suggestions(self, user: User, trip_id: uuid.UUID) -> TripSuggestionsOut:
        trip, items = self._trip_items(user, trip_id)
        flights = [i for i in items if i.kind == "flight"]
        stays = [i for i in items if i.kind == "hotel"]
        missing: list[str] = []
        out: list[TripSuggestionOut] = []
        if flights and not stays and trip.destination_city_id:
            first = _aware(flights[0].ends_at).date()
            last = _aware(flights[-1].starts_at).date() if len(flights) > 1 else first
            end = last if last > first else first + timedelta(days=2)
            missing.append("stay")
            out += self._stays(user, trip.destination_city_id, first, end)
        if len(flights) == 1:
            legs = flights[0].snapshot.get("details", {}).get("legs", [])
            leaving = stays[-1].check_out if stays else None
            if legs and leaving:
                missing.append("return_flight")
                out += self._flights_between(
                    legs[-1]["destination"]["code"],
                    legs[0]["origin"]["code"],
                    leaving,
                    flights[0].quantity,
                )
        if stays and not flights and stays[0].check_in:
            missing.append("flight")
            airport = self._session.scalar(
                select(Airport).where(
                    Airport.city_id == trip.destination_city_id, Airport.is_active.is_(True)
                )
            )
            if airport is not None:
                out.append(
                    TripSuggestionOut(
                        kind="outbound_flight",
                        title=f"Flights to {airport.city_name}",
                        subtitle=f"Arrive for check-in on {stays[0].check_in:%d %b}",
                        price=None,
                        reasons=[],
                        checkout_item=None,
                        link=f"/flights?trip=oneway&to={airport.code}&depart={stays[0].check_in}",
                    )
                )
        return TripSuggestionsOut(
            trip_id=trip.id, complete=not missing, missing=missing, suggestions=out
        )

    def calendar(self, user: User, trip_id: uuid.UUID) -> tuple[str, str]:
        """(filename, iCalendar text) for confirmed items; opens in any calendar app."""
        trip, items = self._trip_items(user, trip_id)

        def stamp(value: datetime) -> str:
            return _aware(value).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

        now = stamp(self._clock.now())
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//TripMind//Trip calendar//EN",
            "CALSCALE:GREGORIAN",
            f"X-WR-CALNAME:{_escape(trip.title)}",
        ]
        for item in (i for i in items if i.status == ItemStatus.CONFIRMED):
            lines += [
                "BEGIN:VEVENT",
                f"UID:{item.id}@tripmind",
                f"DTSTAMP:{now}",
                f"DTSTART:{stamp(item.starts_at)}",
                f"DTEND:{stamp(item.ends_at)}",
                f"SUMMARY:{_escape(item.title)}",
                f"DESCRIPTION:{_escape(str(item.snapshot.get('subtitle', '')))}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        return f"tripmind-{str(trip.id)[:8]}.ics", "\r\n".join(lines) + "\r\n"
