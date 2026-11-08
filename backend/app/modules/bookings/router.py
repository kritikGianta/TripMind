"""Checkout, bookings and My Trips. Every endpoint requires a signed-in traveller and only ever
returns that traveller's own records (another user's ID answers 404)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_request_meta, get_settings_dep, rate_limit, require_feature
from app.core.errors import ErrorEnvelope
from app.core.request_context import RequestMeta
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.bookings.ancillaries import (
    AncillaryService,
    ExtrasCatalogOut,
    ExtrasPurchase,
    ExtrasQuoteOut,
    ExtrasRequest,
    SeatMapOut,
)
from app.modules.bookings.changes import (
    BookingChangeService,
    ChangeConfirm,
    ChangeQuoteOut,
    ChangeRequest,
)
from app.modules.bookings.connected import ConnectedTripService, TripSuggestionsOut
from app.modules.bookings.schemas import (
    BookingOut,
    CancellationQuoteOut,
    CancelRequest,
    CreateBookingRequest,
    PaymentRequest,
    QuoteOut,
    QuoteRequest,
    TripListOut,
    TripOut,
)
from app.modules.bookings.service import BookingService

router = APIRouter(tags=["bookings"], dependencies=[Depends(require_feature("bookings"))])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    402: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}

Traveller = Annotated[User, Depends(get_current_user)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        description="Unique per checkout attempt; retries with the same key are safe",
    ),
]


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> BookingService:
    return BookingService(session, settings, clock)


@router.post(
    "/bookings/quote",
    response_model=QuoteOut,
    responses=_ERRORS,
    summary="Price items for checkout without holding anything",
)
def quote(
    body: QuoteRequest, user: Traveller, service: BookingService = Depends(_service)
) -> QuoteOut:
    return service.quote(user, body.items, body.promo_code)


@router.post(
    "/bookings",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("bookings.create", limit=20, window_seconds=60))],
    summary="Hold seats and rooms and create a booking awaiting payment",
)
def create_booking(
    body: CreateBookingRequest,
    user: Traveller,
    idempotency_key: IdempotencyKey,
    service: BookingService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> BookingOut:
    booking = service.create(user, body, idempotency_key, meta)
    return service.to_out(booking)


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingOut,
    responses=_ERRORS,
    summary="One booking with its items, travellers, payments and timeline",
)
def get_booking(
    booking_id: uuid.UUID, user: Traveller, service: BookingService = Depends(_service)
) -> BookingOut:
    return service.get(user, booking_id)


@router.post(
    "/bookings/{booking_id}/payments",
    response_model=BookingOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("bookings.pay", limit=20, window_seconds=60))],
    summary="Pay for a held booking (simulated card processor)",
)
def pay(
    booking_id: uuid.UUID,
    body: PaymentRequest,
    user: Traveller,
    idempotency_key: IdempotencyKey,
    service: BookingService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> BookingOut:
    return service.pay(user, booking_id, body, idempotency_key, meta)


@router.get(
    "/bookings/{booking_id}/cancellation",
    response_model=CancellationQuoteOut,
    responses=_ERRORS,
    summary="What cancelling would refund, before committing",
)
def cancellation_quote(
    booking_id: uuid.UUID,
    user: Traveller,
    item_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    service: BookingService = Depends(_service),
) -> CancellationQuoteOut:
    return service.cancellation_quote(user, booking_id, item_id)


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingOut,
    responses=_ERRORS,
    summary="Cancel a booking or some of its items, refunding under the policy",
)
def cancel(
    booking_id: uuid.UUID,
    body: CancelRequest,
    user: Traveller,
    service: BookingService = Depends(_service),
    meta: RequestMeta = Depends(get_request_meta),
) -> BookingOut:
    return service.cancel(user, booking_id, body.item_ids, meta)


def _changes(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> BookingChangeService:
    return BookingChangeService(session, settings, clock)


@router.post(
    "/bookings/{booking_id}/items/{item_id}/change-quote",
    response_model=ChangeQuoteOut,
    responses=_ERRORS,
    summary="What moving a flight or stay would cost, before committing",
)
def change_quote(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ChangeRequest,
    user: Traveller,
    service: BookingChangeService = Depends(_changes),
) -> ChangeQuoteOut:
    return service.change_quote(user, booking_id, item_id, body)


@router.post(
    "/bookings/{booking_id}/items/{item_id}/change",
    response_model=BookingOut,
    responses=_ERRORS,
    summary="Move a flight to another date or time, or a stay to other dates",
    dependencies=[Depends(rate_limit("bookings.change", limit=20, window_seconds=60))],
)
def change(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ChangeConfirm,
    user: Traveller,
    key: IdempotencyKey,
    service: BookingChangeService = Depends(_changes),
    meta: RequestMeta = Depends(get_request_meta),
) -> BookingOut:
    return service.change(user, booking_id, item_id, body, key, meta)


def _extras(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> AncillaryService:
    return AncillaryService(session, settings, clock)


@router.get(
    "/bookings/{booking_id}/items/{item_id}/extras",
    response_model=ExtrasCatalogOut,
    responses=_ERRORS,
    summary="Seats, baggage and meals on offer for a booked flight, with current picks",
)
def extras_catalog(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    user: Traveller,
    service: AncillaryService = Depends(_extras),
) -> ExtrasCatalogOut:
    return service.catalog(user, booking_id, item_id)


@router.get(
    "/bookings/{booking_id}/items/{item_id}/seat-map",
    response_model=SeatMapOut,
    responses=_ERRORS,
    summary="Seat map of one flight in a booked flight item",
)
def seat_map(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    flight_id: uuid.UUID,
    user: Traveller,
    service: AncillaryService = Depends(_extras),
) -> SeatMapOut:
    return service.seat_map(user, booking_id, item_id, flight_id)


@router.post(
    "/bookings/{booking_id}/items/{item_id}/extras/quote",
    response_model=ExtrasQuoteOut,
    responses=_ERRORS,
    summary="Price seats, baggage and meals before buying",
)
def extras_quote(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ExtrasRequest,
    user: Traveller,
    service: AncillaryService = Depends(_extras),
) -> ExtrasQuoteOut:
    return service.quote_extras(user, booking_id, item_id, body)


@router.post(
    "/bookings/{booking_id}/items/{item_id}/extras",
    response_model=BookingOut,
    responses=_ERRORS,
    summary="Buy seats, baggage and meals for a booked flight",
    dependencies=[Depends(rate_limit("bookings.extras", limit=30, window_seconds=60))],
)
def extras_purchase(
    booking_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ExtrasPurchase,
    user: Traveller,
    key: IdempotencyKey,
    service: AncillaryService = Depends(_extras),
    meta: RequestMeta = Depends(get_request_meta),
) -> BookingOut:
    return service.purchase(user, booking_id, item_id, body, key, meta)


def _connected(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> ConnectedTripService:
    return ConnectedTripService(session, settings, clock)


@router.get(
    "/trips/{trip_id}/suggestions",
    response_model=TripSuggestionsOut,
    responses=_ERRORS,
    summary="What this trip is missing, with stays and flights ready to add",
)
def trip_suggestions(
    trip_id: uuid.UUID, user: Traveller, service: ConnectedTripService = Depends(_connected)
) -> TripSuggestionsOut:
    return service.suggestions(user, trip_id)


@router.get(
    "/trips/{trip_id}/calendar.ics",
    responses=_ERRORS,
    response_class=Response,
    summary="Add the trip to any calendar app",
)
def trip_calendar(
    trip_id: uuid.UUID, user: Traveller, service: ConnectedTripService = Depends(_connected)
) -> Response:
    filename, body = service.calendar(user, trip_id)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trips", response_model=TripListOut, responses=_ERRORS, summary="My Trips")
def trips(user: Traveller, service: BookingService = Depends(_service)) -> TripListOut:
    return service.trips(user)


@router.get(
    "/trips/{trip_id}",
    response_model=TripOut,
    responses=_ERRORS,
    summary="One trip with all its bookings",
)
def trip(
    trip_id: uuid.UUID, user: Traveller, service: BookingService = Depends(_service)
) -> TripOut:
    return service.trip(user, trip_id)
