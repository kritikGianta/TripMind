"""Hotel reviews (public) and the signed-in traveller's own reviews."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_settings_dep, rate_limit, require_feature
from app.core.errors import ErrorEnvelope
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.reviews.service import (
    HotelReviewsOut,
    MyReviewOut,
    MyReviewsOut,
    ReviewIn,
    ReviewService,
    ReviewSort,
)

router = APIRouter(tags=["reviews"], dependencies=[Depends(require_feature("reviews"))])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    429: {"model": ErrorEnvelope},
}
Traveller = Annotated[User, Depends(get_current_user)]


def _service(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> ReviewService:
    return ReviewService(session, settings, clock)


Service = Annotated[ReviewService, Depends(_service)]


@router.get(
    "/hotels/{hotel_id}/reviews",
    response_model=HotelReviewsOut,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("reviews", limit=120, window_seconds=60))],
    summary="Guest reviews of a stay with the average rating",
)
def hotel_reviews(
    hotel_id: uuid.UUID,
    service: Service,
    sort: ReviewSort = "recent",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> HotelReviewsOut:
    return service.hotel_reviews(hotel_id, sort=sort, limit=limit, offset=offset)


@router.post(
    "/bookings/{booking_id}/items/{item_id}/review",
    response_model=MyReviewOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    dependencies=[Depends(rate_limit("reviews.write", limit=10, window_seconds=60))],
    summary="Review a stay after check-out (one review per booked stay)",
)
def write_review(
    booking_id: uuid.UUID, item_id: uuid.UUID, body: ReviewIn, user: Traveller, service: Service
) -> MyReviewOut:
    return service.write(user, booking_id, item_id, body)


@router.get(
    "/me/reviews",
    response_model=MyReviewsOut,
    responses=_ERRORS,
    summary="My reviews and stays awaiting one",
)
def my_reviews(user: Traveller, service: Service) -> MyReviewsOut:
    return service.mine(user)


@router.delete(
    "/me/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
    summary="Remove one of my reviews",
)
def remove_review(review_id: uuid.UUID, user: Traveller, service: Service) -> None:
    service.remove(user, review_id)
