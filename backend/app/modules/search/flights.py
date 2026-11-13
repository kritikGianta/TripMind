"""Flight search.

An offer is an ordered list of legs (plan v2, G9): one flight, or two flights joined at a
connecting airport with a legal connection time. Offers are built from the catalog, priced with a
ledger, faceted for filters, then filtered and sorted.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.modules.catalog.models import Airport, City, Flight
from app.modules.catalog.repository import CatalogRepository
from app.modules.inventory.service import seats_left
from app.modules.operations.queries import cancelled_flights
from app.modules.search.locations import LocationService
from app.modules.search.pricing import Converter, LedgerLine, MoneyOut, SearchRules
from app.modules.search.schemas import (
    AirportBrief,
    CabinClass,
    DepartureWindow,
    FacetOption,
    FlightFacets,
    FlightLegOut,
    FlightOfferOut,
    FlightResultsOut,
    FlightSearchOut,
    FlightSort,
    LayoverOut,
    PriceRange,
    TravelWindowOut,
)

WINDOWS: dict[DepartureWindow, tuple[int, int, str]] = {
    "night": (0, 6, "Night (00-06)"),
    "morning": (6, 12, "Morning (06-12)"),
    "afternoon": (12, 18, "Afternoon (12-18)"),
    "evening": (18, 24, "Evening (18-24)"),
}


@dataclass(frozen=True)
class FlightQuery:
    origin: str
    destination: str
    departure_date: date
    return_date: date | None = None
    adults: int = 1
    cabin_class: CabinClass = "economy"
    max_stops: int | None = None
    airlines: tuple[str, ...] = ()
    departure_windows: tuple[DepartureWindow, ...] = ()
    max_price: int | None = None  # display currency, major units
    sort: FlightSort = "best"


def _window(hour: int) -> DepartureWindow:
    return next(name for name, (start, end, _) in WINDOWS.items() if start <= hour < end)


class FlightSearchService:
    def __init__(
        self,
        session: Session,
        converter: Converter,
        rules: SearchRules,
        today: date,
    ) -> None:
        self._session = session
        self._converter = converter
        self._rules = rules
        self._today = today
        self._locations = LocationService(session)
        self._airports: dict[uuid.UUID, AirportBrief] = {}
        self._coords: dict[str, tuple[float, float]] = {}
        self._countries: dict[str, str | None] = {}

    # ------------------------------------------------------------------ public

    def search(self, query: FlightQuery) -> FlightSearchOut:
        if query.departure_date < self._today:
            raise ValidationFailed("The departure date is in the past.", code="DATE_IN_PAST")
        if query.return_date is not None and query.return_date < query.departure_date:
            raise ValidationFailed(
                "The return date is before the departure date.", code="RETURN_BEFORE_DEPARTURE"
            )
        origins = self._locations.airports_for(query.origin)
        destinations = self._locations.airports_for(query.destination)
        if {a.id for a in origins} & {a.id for a in destinations}:
            raise ValidationFailed("Origin and destination are the same.", code="SAME_LOCATION")
        self._load_airports()

        window = CatalogRepository(self._session).flight_window()
        notices: list[str] = []
        travel = None
        if window:
            travel = TravelWindowOut(
                first_departure=window[0].date(), last_departure=window[1].date()
            )
            for label, day in (("departure", query.departure_date), ("return", query.return_date)):
                if day and not travel.first_departure <= day <= travel.last_departure:
                    notices.append(
                        f"No flights are scheduled on the {label} date: this dataset covers "
                        f"{travel.first_departure:%d %b %Y} to {travel.last_departure:%d %b %Y}."
                    )

        outbound = self._results(origins, destinations, query.departure_date, query)
        inbound = (
            self._results(destinations, origins, query.return_date, query)
            if query.return_date
            else None
        )
        return FlightSearchOut(
            outbound=outbound,
            inbound=inbound,
            adults=query.adults,
            cabin_class=query.cabin_class,
            display_currency=self._converter.display_currency,
            travel_window=travel,
            notices=notices,
        )

    def price_offer(self, flight_ids: list[uuid.UUID], adults: int) -> FlightOfferOut:
        """Re-price an offer from the catalog (used by checkout; never trusts client prices).

        Checks that every leg still exists, is active, departs in the future, joins the previous
        leg at the same airport with a legal connection time, and has a fare.
        """
        if not 1 <= len(flight_ids) <= 2:
            raise ValidationFailed("An offer has one or two flights.", code="OFFER_INVALID")
        found = {f.id: f for f in self._flights(Flight.id.in_(flight_ids))}
        if len(found) != len(set(flight_ids)):
            raise NotFound("This flight is no longer available.", code="OFFER_UNAVAILABLE")
        flights = [found[i] for i in flight_ids]
        min_gap = timedelta(minutes=self._rules.min_connection_minutes)
        max_gap = timedelta(minutes=self._rules.max_connection_minutes)
        for first, second in pairwise(flights):
            gap = _utc(second.departure_at) - _utc(first.arrival_at)
            if first.destination_airport_id != second.origin_airport_id or not (
                min_gap <= gap <= max_gap
            ):
                raise ValidationFailed("These flights do not connect.", code="OFFER_INVALID")
        if flights[0].departure_local.date() < self._today:
            raise ValidationFailed("This flight has already departed.", code="DATE_IN_PAST")
        if any(f.fare_minor is None for f in flights):
            raise ValidationFailed(
                "This flight has no fare and cannot be booked.", code="OFFER_NOT_BOOKABLE"
            )
        self._load_airports()
        return self._offer(flights, adults)

    # ------------------------------------------------------------------ building offers

    def _load_airports(self) -> None:
        rows = self._session.execute(
            select(
                Airport.id,
                Airport.code,
                Airport.name,
                City.name,
                Airport.latitude,
                Airport.longitude,
                Airport.country,
            ).join(City, City.id == Airport.city_id)
        ).all()
        self._airports = {
            i: AirportBrief(code=code, name=name, city_name=city)
            for i, code, name, city, _, _, _ in rows
        }
        self._coords = {
            code: (lat, lon)
            for _, code, _, _, lat, lon, _ in rows
            if lat is not None and lon is not None
        }
        self._countries = {code: country for _, code, _, _, _, _, country in rows}

    def _flights(self, *conditions: object) -> list[Flight]:
        return list(
            self._session.scalars(
                select(Flight).where(
                    Flight.is_active.is_(True),
                    Flight.id.not_in(cancelled_flights()),  # cancelled by the airline: not for sale
                    *conditions,  # type: ignore[arg-type]
                )
            )
        )

    def _results(
        self, origins: list[Airport], destinations: list[Airport], day: date, query: FlightQuery
    ) -> FlightResultsOut:
        origin_ids = [a.id for a in origins]
        destination_ids = {a.id for a in destinations}
        start = datetime.combine(day, datetime.min.time())
        common = (
            Flight.cabin_class == query.cabin_class,
            seats_left() >= query.adults,
        )
        from_origin = self._flights(
            Flight.origin_airport_id.in_(origin_ids),
            Flight.departure_local >= start,
            Flight.departure_local < start + timedelta(days=1),
            *common,
        )
        offers = [
            self._offer([f], query.adults)
            for f in from_origin
            if f.destination_airport_id in destination_ids
        ]
        offers += self._connections(from_origin, destination_ids, query)

        facets = self._facets(offers)
        filtered = [o for o in offers if self._matches(o, query)]
        filtered.sort(key=self._sort_key(query.sort, filtered))
        return FlightResultsOut(
            origin=self._airports.get(origins[0].id) if len(origins) == 1 else None,
            destination=(
                self._airports.get(destinations[0].id) if len(destinations) == 1 else None
            ),
            date=day,
            offers=filtered[: self._rules.max_results],
            total=len(filtered),
            unfiltered_total=len(offers),
            facets=facets,
        )

    def _connections(
        self, first_legs: list[Flight], destination_ids: set[uuid.UUID], query: FlightQuery
    ) -> list[FlightOfferOut]:
        if query.max_stops == 0:
            return []
        candidates = [
            f
            for f in first_legs
            if f.destination_airport_id not in destination_ids
            and f.fare_minor is not None
            and f.stops == 0
        ]
        if not candidates:
            return []
        min_gap = timedelta(minutes=self._rules.min_connection_minutes)
        max_gap = timedelta(minutes=self._rules.max_connection_minutes)
        earliest = min(f.arrival_at for f in candidates) + min_gap
        latest = max(f.arrival_at for f in candidates) + max_gap
        second_legs = self._flights(
            Flight.origin_airport_id.in_({f.destination_airport_id for f in candidates}),
            Flight.destination_airport_id.in_(destination_ids),
            Flight.departure_at >= earliest,
            Flight.departure_at <= latest,
            Flight.cabin_class == query.cabin_class,
            seats_left() >= query.adults,
            Flight.fare_minor.is_not(None),
            Flight.stops == 0,
        )
        by_origin: dict[uuid.UUID, list[Flight]] = defaultdict(list)
        for leg in second_legs:
            by_origin[leg.origin_airport_id].append(leg)

        offers: list[FlightOfferOut] = []
        for first in candidates:
            options = [
                second
                for second in by_origin.get(first.destination_airport_id, [])
                if min_gap <= _utc(second.departure_at) - _utc(first.arrival_at) <= max_gap
            ]
            # The three earliest onward flights per first leg: later ones are rarely useful.
            options.sort(key=lambda f: f.departure_at)
            offers += [self._offer([first, second], query.adults) for second in options[:3]]
        return offers

    def _leg(self, flight: Flight) -> FlightLegOut:
        return FlightLegOut(
            flight_id=flight.id,
            flight_number=flight.flight_number,
            airline_code=flight.airline_code,
            airline_name=flight.airline_name,
            origin=self._airports[flight.origin_airport_id],
            destination=self._airports[flight.destination_airport_id],
            departure_local=flight.departure_local,
            arrival_local=flight.arrival_local,
            departure_at=_utc(flight.departure_at),
            arrival_at=_utc(flight.arrival_at),
            duration_minutes=flight.duration_minutes,
            stops=flight.stops,
            cabin_class=flight.cabin_class,
            aircraft=flight.aircraft,
            fare=(
                MoneyOut(amount_minor=flight.fare_minor, currency=flight.currency)
                if flight.fare_minor is not None
                else None
            ),
        )

    def _offer(self, flights: list[Flight], adults: int) -> FlightOfferOut:
        legs = [self._leg(f) for f in flights]
        layovers = [
            LayoverOut(
                airport=legs[i].destination,
                minutes=int((legs[i + 1].departure_at - legs[i].arrival_at).total_seconds() // 60),
            )
            for i in range(len(legs) - 1)
        ]
        lines = [
            LedgerLine(
                label=f"{leg.flight_number} {leg.origin.code}-{leg.destination.code} fare"
                + (f" x {adults} adults" if adults > 1 else ""),
                kind="fare",
                amount=(
                    MoneyOut(
                        amount_minor=leg.fare.amount_minor * adults, currency=leg.fare.currency
                    )
                    if leg.fare
                    else None
                ),
                note=None if leg.fare else "No fare in the supplied data",
            )
            for leg in legs
        ]
        airlines = {leg.airline_code or leg.airline_name for leg in legs}
        notices = []
        if len(airlines) > 1:
            notices.append("Different airlines: you may need to collect and re-check bags.")
        if any(leg.fare is None for leg in legs):
            notices.append("Browse only: the supplied data has no fare for this flight.")
        return FlightOfferOut(
            id="~".join(str(f.id) for f in flights),
            legs=legs,
            stops=sum(leg.stops for leg in legs) + len(legs) - 1,
            layovers=layovers,
            duration_minutes=int(
                (legs[-1].arrival_at - legs[0].departure_at).total_seconds() // 60
            ),
            self_transfer=len(airlines) > 1,
            bookable=all(leg.fare is not None for leg in legs),
            price=self._converter.ledger(lines),
            notices=notices,
        )

    # ------------------------------------------------------------------ filters, facets, sort

    @staticmethod
    def _display_price(offer: FlightOfferOut) -> int | None:
        total = offer.price.display_total
        return total.amount_minor if total else None

    def _matches(self, offer: FlightOfferOut, query: FlightQuery) -> bool:
        if query.max_stops is not None and offer.stops > query.max_stops:
            return False
        if query.airlines and not all(
            (leg.airline_code or "") in query.airlines for leg in offer.legs
        ):
            return False
        if (
            query.departure_windows
            and _window(offer.legs[0].departure_local.hour) not in query.departure_windows
        ):
            return False
        if query.max_price is not None:
            price = self._display_price(offer)
            if price is None or price > query.max_price * 100:
                return False
        return True

    def _facets(self, offers: list[FlightOfferOut]) -> FlightFacets:
        currency = self._converter.display_currency

        def facet(
            groups: dict[str, list[FlightOfferOut]], labels: dict[str, str]
        ) -> list[FacetOption]:
            options = []
            for value, members in groups.items():
                prices = [p for p in map(self._display_price, members) if p is not None]
                options.append(
                    FacetOption(
                        value=value,
                        label=labels.get(value, value),
                        count=len(members),
                        min_price=MoneyOut(amount_minor=min(prices), currency=currency)
                        if prices
                        else None,
                    )
                )
            return options

        stops: dict[str, list[FlightOfferOut]] = defaultdict(list)
        airlines: dict[str, list[FlightOfferOut]] = defaultdict(list)
        windows: dict[str, list[FlightOfferOut]] = defaultdict(list)
        airline_names: dict[str, str] = {}
        for offer in offers:
            stops[str(min(offer.stops, 2))].append(offer)
            windows[_window(offer.legs[0].departure_local.hour)].append(offer)
            for code in {leg.airline_code or "" for leg in offer.legs}:
                airlines[code].append(offer)
            for leg in offer.legs:
                airline_names[leg.airline_code or ""] = leg.airline_name or leg.airline_code or "?"
        prices = [p for p in map(self._display_price, offers) if p is not None]
        return FlightFacets(
            stops=sorted(
                facet(stops, {"0": "Direct", "1": "1 stop", "2": "2+ stops"}), key=lambda o: o.value
            ),
            airlines=sorted(facet(airlines, airline_names), key=lambda o: o.label),
            departure_windows=[
                o
                for name in WINDOWS
                for o in facet({name: windows[name]}, {name: WINDOWS[name][2]})
                if windows[name]
            ],
            price_range=PriceRange(
                min=MoneyOut(amount_minor=min(prices), currency=currency),
                max=MoneyOut(amount_minor=max(prices), currency=currency),
            )
            if prices
            else None,
        )

    def _sort_key(self, sort: FlightSort, offers: list[FlightOfferOut]):  # type: ignore[no-untyped-def]
        unpriced = 10**15
        prices = [p for p in map(self._display_price, offers) if p is not None]
        cheapest = min(prices, default=1) or 1
        fastest = min((o.duration_minutes for o in offers), default=1) or 1

        def price(o: FlightOfferOut) -> int:
            value = self._display_price(o)
            return unpriced if value is None else value

        if sort == "cheapest":
            return lambda o: (price(o), o.duration_minutes)
        if sort == "fastest":
            return lambda o: (o.duration_minutes, price(o))
        if sort == "earliest":
            return lambda o: (o.legs[0].departure_local, price(o))
        # "best": weighs price and journey time, cheapest and fastest scoring 1.0 each.
        return lambda o: (
            price(o) == unpriced,
            0.6 * price(o) / cheapest + 0.4 * o.duration_minutes / fastest,
        )


def _utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes for timestamptz columns; they are UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
