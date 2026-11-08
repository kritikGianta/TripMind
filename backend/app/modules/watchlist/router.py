"""Saved stays and price alerts. Every endpoint is the signed-in traveller's own data."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_settings_dep, require_feature
from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.watchlist.service import (
    PriceAlertIn,
    PriceAlertListOut,
    PriceAlertOut,
    SavedHotelListOut,
    WatchlistService,
)

router = APIRouter(
    prefix="/me", tags=["watchlist"], dependencies=[Depends(require_feature("watchlist"))]
)
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
}
Traveller = Annotated[User, Depends(get_current_user)]


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> WatchlistService:
    return WatchlistService(session, settings, clock)


Service = Annotated[WatchlistService, Depends(_service)]


@router.get(
    "/saved-hotels", response_model=SavedHotelListOut, responses=_ERRORS, summary="My saved stays"
)
def saved_hotels(user: Traveller, service: Service) -> SavedHotelListOut:
    return service.saved(user)


@router.put(
    "/saved-hotels/{hotel_id}",
    response_model=SavedHotelListOut,
    responses=_ERRORS,
    summary="Save a stay (saving it again changes nothing)",
)
def save_hotel(hotel_id: uuid.UUID, user: Traveller, service: Service) -> SavedHotelListOut:
    return service.save(user, hotel_id)


@router.delete(
    "/saved-hotels/{hotel_id}",
    response_model=SavedHotelListOut,
    responses=_ERRORS,
    summary="Remove a saved stay",
)
def unsave_hotel(hotel_id: uuid.UUID, user: Traveller, service: Service) -> SavedHotelListOut:
    return service.unsave(user, hotel_id)


@router.get(
    "/price-alerts", response_model=PriceAlertListOut, responses=_ERRORS, summary="My price alerts"
)
def price_alerts(user: Traveller, service: Service) -> PriceAlertListOut:
    return service.alerts(user)


@router.post(
    "/price-alerts",
    response_model=PriceAlertOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Watch a flight search or a stay for a price drop",
)
def create_price_alert(body: PriceAlertIn, user: Traveller, service: Service) -> PriceAlertOut:
    return service.create_alert(user, body)


@router.delete(
    "/price-alerts/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Stop a price alert",
)
def cancel_price_alert(alert_id: uuid.UUID, user: Traveller, service: Service) -> None:
    service.cancel_alert(user, alert_id)
