"""Search endpoints. Public (no sign-in needed), rate-limited per client, read-only."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_settings_dep, rate_limit, require_feature
from app.core.errors import ErrorEnvelope, ValidationFailed
from app.db.session import get_session
from app.modules.catalog.vocabulary import load_vocabulary
from app.modules.search.flights import FlightQuery, FlightSearchService
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
) -> FlightSearchOut:
    return service.search(
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
) -> HotelSearchOut:
    if any(s < 0 or s > 5 for s in stars or ()):
        raise ValidationFailed("Stars must be between 0 and 5.")
    return service.search(
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
