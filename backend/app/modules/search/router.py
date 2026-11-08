"""Search endpoints. Public (no sign-in needed), rate-limited per client, read-only."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import (
    get_clock,
    get_feature_flags,
    get_settings_dep,
    rate_limit,
    require_feature,
)
from app.core.errors import ErrorEnvelope, NotFound, ValidationFailed
from app.core.features import FeatureFlags
from app.core.metrics import SEARCH_LATENCY, SEARCHES
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, get_optional_user
from app.modules.auth.models import User
from app.modules.catalog.vocabulary import load_vocabulary
from app.modules.ml.features import FARE_ESTIMATOR_FEATURES, HOTEL_RANKER_FEATURES
from app.modules.ml.interactions import HotelInteraction, record_interaction
from app.modules.ml.preferences import UserPreference, learned
from app.modules.ml.registry import load_model
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.history import (
    SearchHistoryListOut,
    forget_searches,
    recent_searches,
    remember_search,
)
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.locations import LocationService
from app.modules.search.preferences import forget, load_preference_rules
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
    flags: FeatureFlags = Depends(get_feature_flags),
) -> FlightSearchService:
    fare_model = (
        load_model(settings.models_dir, "fare_estimator", FARE_ESTIMATOR_FEATURES)
        if flags.enabled("ml_fare_insight")
        else None
    )
    return FlightSearchService(
        session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_search_rules(settings.config_dir),
        _earliest_travel_date(clock),
        fare_model=fare_model,
    )


def _hotels(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
    flags: FeatureFlags = Depends(get_feature_flags),
    viewer: Viewer = None,
) -> HotelSearchService:
    ranker = (
        load_model(settings.models_dir, "hotel_ranker", HOTEL_RANKER_FEATURES)
        if flags.enabled("ml_hotel_ranker")
        else None
    )
    preference = (
        session.get(UserPreference, viewer.id)
        if viewer is not None and flags.enabled("personalization")
        else None
    )
    return HotelSearchService(
        session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_search_rules(settings.config_dir),
        _earliest_travel_date(clock),
        ranker=ranker,
        preference=preference,
        preference_blend=load_preference_rules(settings).blend,
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
    viewer: Viewer = None,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> HotelDetailOut:
    stay = (
        Stay(check_in=check_in, check_out=check_out, guests=guests, rooms=rooms)
        if check_in and check_out
        else None
    )
    detail = service.detail(hotel_id, stay)
    if viewer is not None:  # a signal for the preference model; never blocks the page
        try:
            record_interaction(session, viewer.id, hotel_id, "view", clock.now())
            session.commit()
        except SQLAlchemyError:
            session.rollback()
    return detail


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


class LearnedPreferenceOut(BaseModel):
    feature: str
    label: str
    weight: float
    direction: str


class PreferencesOut(BaseModel):
    personalized: bool = Field(description="True once enough activity has been learned from")
    trained_at: datetime | None
    stays_learned_from: int
    activity_count: int
    learned: list[LearnedPreferenceOut]
    how_it_works: str


@router.get(
    "/me/preferences",
    response_model=PreferencesOut,
    responses={401: {"model": ErrorEnvelope}},
    summary="What TripMind has learned about the stays I like",
)
def my_preferences(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> PreferencesOut:
    pref = session.get(UserPreference, user.id)
    activity = session.scalar(
        select(func.count())
        .select_from(HotelInteraction)
        .where(HotelInteraction.user_id == user.id)
    )
    return PreferencesOut(
        personalized=pref is not None,
        trained_at=pref.trained_at if pref else None,
        stays_learned_from=pref.positives if pref else 0,
        activity_count=int(activity or 0),
        learned=[LearnedPreferenceOut(**item) for item in learned(pref)] if pref else [],
        how_it_works=(
            "Stays you open, save and book teach a small model what you tend to choose. It only "
            "adjusts the Recommended order and shows why. Reset it at any time."
        ),
    )


@router.delete(
    "/me/preferences",
    status_code=204,
    responses={401: {"model": ErrorEnvelope}},
    summary="Reset personalisation: forget my stay activity and what was learned",
)
def reset_preferences(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> None:
    forget(session, user.id)
