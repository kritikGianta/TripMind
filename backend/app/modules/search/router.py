"""Search endpoints. Public (no sign-in needed), rate-limited per client, read-only."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import ErrorEnvelope, NotFound, ValidationFailed
from app.core.metrics import SEARCH_LATENCY, SEARCHES
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, get_optional_user
from app.modules.auth.models import User
from app.modules.catalog.vocabulary import load_vocabulary
from app.modules.search.discover import DiscoverService, ExploreOut, FareCalendarOut
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.history import (
    SearchHistoryListOut,
    forget_searches,
    recent_searches,
    remember_search,
)
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.locations import LocationService
from app.modules.search.pricing import Converter, load_pricing_rules, load_search_rules
from app.modules.search.schemas import (
    CabinClass,
    DepartureWindow,
    FlightSearchOut,
    FlightSort,
    HotelDetailOut,
    HotelSearchOut,
    HotelSort,
    LocationListOut,
)

router = APIRouter(
    tags=["search"],
    dependencies=[Depends(rate_limit("search", limit=120, window_seconds=60))],
)

Viewer = Annotated[User | None, Depends(get_optional_user)]

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}


def _earliest_travel_date(clock: Clock) -> date:
    # A date is "in the past" only once it has ended everywhere (UTC-12), so a traveller in any
    # timezone can still search for their own today.
    return (clock.now() - timedelta(hours=12)).date()


def _flights(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> FlightSearchService:
    return FlightSearchService(
        session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_search_rules(settings.config_dir),
        _earliest_travel_date(clock),
    )


def _hotels(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> HotelSearchService:
    return HotelSearchService(
        session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_search_rules(settings.config_dir),
        _earliest_travel_date(clock),
    )


@router.get(
    "/locations",
    response_model=LocationListOut,
    responses=_ERRORS,
    summary="Airports (for flights) or cities (for stays) matching a search box",
)
def locations(
    q: Annotated[str, Query(max_length=80)] = "",
    kind: Literal["airport", "city"] = "airport",
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> LocationListOut:
    service = LocationService(session, load_vocabulary(settings.config_dir))
    return LocationListOut(items=service.search(q, kind, limit))


@router.get(
    "/flights/search",
    response_model=FlightSearchOut,
    responses=_ERRORS,
    dependencies=[Depends(require_feature("flight_search"))],
    summary="One-way or return flights, direct and with one connection",
)
def search_flights(
    origin: Annotated[
        str, Query(min_length=2, max_length=64, description="Airport code or city ID")
    ],
    destination: Annotated[str, Query(min_length=2, max_length=64)],
    departure_date: date,
    return_date: date | None = None,
    adults: Annotated[int, Query(ge=1, le=9)] = 1,
    cabin_class: CabinClass = "economy",
    max_stops: Annotated[int | None, Query(ge=0, le=1)] = None,
    airlines: Annotated[list[str] | None, Query(max_length=20)] = None,
    departure_windows: Annotated[list[DepartureWindow] | None, Query()] = None,
    max_price: Annotated[int | None, Query(ge=0, description="Display currency")] = None,
    sort: FlightSort = "best",
    service: FlightSearchService = Depends(_flights),
    viewer: Viewer = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> FlightSearchOut:
    with SEARCH_LATENCY.labels(vertical="flights").time():
        result = service.search(
            FlightQuery(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                adults=adults,
                cabin_class=cabin_class,
                max_stops=max_stops,
                airlines=tuple(a.upper() for a in airlines or ()),
                departure_windows=tuple(departure_windows or ()),
                max_price=max_price,
                sort=sort,
            )
        )
    SEARCHES.labels(vertical="flights", result="found" if result.outbound.total else "empty").inc()
    if viewer is not None:
        out = result.outbound
        route = (
            f"{out.origin.city_name} to {out.destination.city_name}"
            if out.origin and out.destination
            else f"{origin} to {destination}"
        )
        remember_search(
            session,
            user_id=viewer.id,
            vertical="flights",
            params={
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "adults": adults,
                "cabin_class": cabin_class,
            },
            label=f"{route} · {departure_date:%d %b}"
            + (f" to {return_date:%d %b}" if return_date else "")
            + f" · {adults} adult{'s' if adults > 1 else ''}",
            result_count=out.total,
            at=clock.now(),
            keep=load_search_rules(settings.config_dir).history_keep,
        )
    return result


@router.get(
    "/hotels/search",
    response_model=HotelSearchOut,
    responses=_ERRORS,
    dependencies=[Depends(require_feature("hotel_search"))],
    summary="Stays in a city for given dates and party size",
)
def search_hotels(
    city: Annotated[str, Query(description="City ID from /locations?kind=city")],
    check_in: date,
    check_out: date,
    guests: Annotated[int, Query(ge=1, le=16)] = 2,
    rooms: Annotated[int, Query(ge=1, le=8)] = 1,
    stars: Annotated[list[int] | None, Query()] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=10)] = None,
    amenities: Annotated[list[str] | None, Query(max_length=20)] = None,
    max_price: Annotated[int | None, Query(ge=0, description="Per night, display currency")] = None,
    free_cancellation: bool = False,
    breakfast: bool = False,
    sort: HotelSort = "recommended",
    service: HotelSearchService = Depends(_hotels),
    viewer: Viewer = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> HotelSearchOut:
    if any(s < 0 or s > 5 for s in stars or ()):
        raise ValidationFailed("Stars must be between 0 and 5.")
    with SEARCH_LATENCY.labels(vertical="hotels").time():
        result = service.search(
            HotelQuery(
                city=city,
                stay=Stay(check_in=check_in, check_out=check_out, guests=guests, rooms=rooms),
                stars=tuple(stars or ()),
                min_rating=min_rating,
                amenities=tuple(amenities or ()),
                max_price=max_price,
                free_cancellation=free_cancellation,
                breakfast=breakfast,
                sort=sort,
            )
        )
    SEARCHES.labels(vertical="hotels", result="found" if result.total else "empty").inc()
    if viewer is not None:
        remember_search(
            session,
            user_id=viewer.id,
            vertical="hotels",
            params={
                "city": city,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
                "rooms": rooms,
            },
            label=f"Stays in {result.city.name} · {check_in:%d %b} to {check_out:%d %b} · "
            f"{guests} guest{'s' if guests > 1 else ''}",
            result_count=result.total,
            at=clock.now(),
            keep=load_search_rules(settings.config_dir).history_keep,
        )
    return result


@router.get(
    "/hotels/{hotel_id}",
    response_model=HotelDetailOut,
    responses=_ERRORS,
    dependencies=[Depends(require_feature("hotel_search"))],
    summary="One stay with all its room types; priced when dates are given",
)
def hotel_detail(
    hotel_id: uuid.UUID,
    check_in: date | None = None,
    check_out: date | None = None,
    guests: Annotated[int, Query(ge=1, le=16)] = 2,
    rooms: Annotated[int, Query(ge=1, le=8)] = 1,
    service: HotelSearchService = Depends(_hotels),
) -> HotelDetailOut:
    stay = (
        Stay(check_in=check_in, check_out=check_out, guests=guests, rooms=rooms)
        if check_in and check_out
        else None
    )
    return service.detail(hotel_id, stay)


@router.get(
    "/me/searches",
    response_model=SearchHistoryListOut,
    responses={401: {"model": ErrorEnvelope}},
    summary="My recent searches, newest first",
)
def my_searches(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> SearchHistoryListOut:
    return recent_searches(session, user.id)


@router.delete(
    "/me/searches",
    status_code=204,
    responses={401: {"model": ErrorEnvelope}},
    summary="Clear my search history",
)
def clear_searches(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> None:
    forget_searches(session, user.id, None)


@router.delete(
    "/me/searches/{search_id}",
    status_code=204,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Remove one search from my history",
)
def forget_search(
    search_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    if not forget_searches(session, user.id, search_id):
        raise NotFound("That search is not in your history.", code="SEARCH_NOT_FOUND")


def _discover(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> DiscoverService:
    return DiscoverService(
        session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_search_rules(settings.config_dir),
        _earliest_travel_date(clock),
    )


@router.get(
    "/flights/calendar",
    response_model=FareCalendarOut,
    responses=_ERRORS,
    dependencies=[Depends(require_feature("flight_search"))],
    summary="Cheapest direct fare per day, to find the best day to fly",
)
def fare_calendar(
    origin: Annotated[str, Query(min_length=2, max_length=64)],
    destination: Annotated[str, Query(min_length=2, max_length=64)],
    start: date,
    days: Annotated[int, Query(ge=1, le=62)] = 30,
    adults: Annotated[int, Query(ge=1, le=9)] = 1,
    cabin_class: CabinClass = "economy",
    service: DiscoverService = Depends(_discover),
) -> FareCalendarOut:
    return service.calendar(origin, destination, start, days, adults, cabin_class)


@router.get(
    "/explore",
    response_model=ExploreOut,
    responses=_ERRORS,
    dependencies=[Depends(require_feature("flight_search"))],
    summary="Where can I go? Flight + stay totals per destination, cheapest first",
)
def explore(
    origin: Annotated[str, Query(min_length=2, max_length=64)],
    departure_date: date,
    nights: Annotated[int, Query(ge=1, le=30)] = 3,
    adults: Annotated[int, Query(ge=1, le=9)] = 2,
    budget: Annotated[int | None, Query(gt=0, description="Display currency, whole units")] = None,
    min_rating: Annotated[float, Query(ge=0, le=10)] = 7.0,
    service: DiscoverService = Depends(_discover),
) -> ExploreOut:
    return service.explore(origin, departure_date, nights, adults, budget, min_rating)
