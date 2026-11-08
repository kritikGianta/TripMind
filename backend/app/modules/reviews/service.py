"""Hotel reviews: what guests said, scored for sentiment and summarised by aspect.

Two sources are shown together: reviews supplied with the dataset (catalog `hotel_reviews`) and
reviews written in TripMind by travellers who checked out of a booked stay (`stay_reviews`,
marked as verified stays). Sentiment comes from the review-sentiment model when trained, otherwise
from word lists; the response says which (`scored_by`).
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.auth.models import User
from app.modules.bookings.models import Booking, BookingItem, ItemStatus
from app.modules.catalog.models import Hotel, HotelReview
from app.modules.ml.sentiment import ASPECTS, SentimentScorer
from app.modules.reviews.models import StayReview
from app.modules.search.pricing import rules_section

TravellerType = Literal["couple", "family", "solo", "business", "friends"]
ReviewSort = Literal["recent", "highest", "lowest"]
_CONTACT = re.compile(
    r"(https?://|www\.|\b[\w.+-]+@[\w-]+\.[\w.]+\b|\+?\d[\d\s-]{8,}\d)", re.IGNORECASE
)


class ReviewRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_window_days: int = Field(default=365, ge=1)


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rating: int = Field(ge=1, le=10)
    title: str | None = Field(default=None, max_length=120)
    text: str = Field(min_length=20, max_length=2000)
    traveller_type: TravellerType | None = None


class ReviewOut(BaseModel):
    id: uuid.UUID
    source: Literal["supplied", "traveller"]
    verified_stay: bool
    rating: float | None = Field(description="0-10")
    title: str | None
    text: str
    traveller_type: str | None
    date: date | None
    sentiment: str
    aspects: dict[str, str]


class AspectOut(BaseModel):
    aspect: str
    mentions: int
    positive: int
    negative: int


class ReviewSummaryOut(BaseModel):
    total: int
    average_rating: float | None = Field(description="0-10, over reviews that have a rating")
    sentiment: dict[str, int]
    aspects: list[AspectOut] = Field(description="Most mentioned first")
    scored_by: str = Field(description="'model:<version>' or 'rules'")
    note: str | None


class HotelReviewsOut(BaseModel):
    hotel_id: uuid.UUID
    summary: ReviewSummaryOut
    items: list[ReviewOut]
    offset: int
    limit: int


class AwaitingReviewOut(BaseModel):
    booking_id: uuid.UUID
    item_id: uuid.UUID
    hotel_id: uuid.UUID
    hotel_name: str
    checked_out_on: date


class MyReviewOut(ReviewOut):
    hotel_id: uuid.UUID
    hotel_name: str


class MyReviewsOut(BaseModel):
    written: list[MyReviewOut]
    awaiting: list[AwaitingReviewOut]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass
class _Row:
    id: uuid.UUID
    source: Literal["supplied", "traveller"]
    rating: float | None
    title: str | None
    text: str
    traveller_type: str | None
    when: date | None
    origin: str


class ReviewService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._rules = ReviewRules.model_validate(rules_section(settings.config_dir, "reviews"))
        self._scorer = SentimentScorer(settings.models_dir)

    def _rows(self, hotel_id: uuid.UUID) -> list[_Row]:
        supplied = self._session.scalars(
            select(HotelReview).where(
                HotelReview.hotel_id == hotel_id, HotelReview.is_active.is_(True)
            )
        )
        written = self._session.scalars(
            select(StayReview).where(
                StayReview.hotel_id == hotel_id, StayReview.status == "published"
            )
        )
        rows = [
            _Row(
                r.id,
                "supplied",
                r.rating,
                r.title,
                r.text,
                r.traveller_type,
                r.reviewed_on,
                r.origin,
            )
            for r in supplied
        ]
        rows += [
            _Row(
                r.id,
                "traveller",
                float(r.rating),
                r.title,
                r.text,
                r.traveller_type,
                r.created_at.date(),
                "traveller",
            )
            for r in written
        ]
        return rows

    def _out(self, row: _Row) -> ReviewOut:
        return ReviewOut(
            id=row.id,
            source=row.source,
            verified_stay=row.source == "traveller",
            rating=row.rating,
            title=row.title,
            text=row.text,
            traveller_type=row.traveller_type,
            date=row.when,
            sentiment=self._scorer.score(row.text).label,
            aspects=dict(self._scorer.aspects(row.text)),
        )

    def hotel_reviews(
        self, hotel_id: uuid.UUID, *, sort: ReviewSort, limit: int, offset: int
    ) -> HotelReviewsOut:
        hotel = self._session.get(Hotel, hotel_id)
        if hotel is None or not hotel.is_active:
            raise NotFound("This stay is not available.", code="HOTEL_NOT_FOUND")
        rows = self._rows(hotel_id)
        sentiment: Counter[str] = Counter()
        mentions: Counter[str] = Counter()
        positive: Counter[str] = Counter()
        negative: Counter[str] = Counter()
        for row in rows:
            sentiment[self._scorer.score(row.text).label] += 1
            for aspect, label in self._scorer.aspects(row.text).items():
                mentions[aspect] += 1
                positive[aspect] += label == "positive"
                negative[aspect] += label == "negative"
        rated = [r.rating for r in rows if r.rating is not None]
        if sort == "recent":
            rows.sort(key=lambda r: r.when or date.min, reverse=True)
        else:
            rows.sort(key=lambda r: r.rating or 0, reverse=sort == "highest")
        synthetic = any(r.origin == "synthetic" for r in rows)
        return HotelReviewsOut(
            hotel_id=hotel_id,
            summary=ReviewSummaryOut(
                total=len(rows),
                average_rating=round(sum(rated) / len(rated), 1) if rated else None,
                sentiment={k: sentiment.get(k, 0) for k in ("positive", "neutral", "negative")},
                aspects=[
                    AspectOut(aspect=a, mentions=n, positive=positive[a], negative=negative[a])
                    for a, n in sorted(mentions.items(), key=lambda kv: (-kv[1], kv[0]))
                    if a in ASPECTS
                ],
                scored_by=self._scorer.source,
                note="Supplied reviews in the demo dataset are generated text, not real guests."
                if synthetic
                else None,
            ),
            items=[self._out(r) for r in rows[offset : offset + limit]],
            offset=offset,
            limit=limit,
        )

    # ------------------------------------------------------------------ travellers

    def _completed_stay(self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID) -> BookingItem:
        booking = self._session.get(Booking, booking_id)
        item = self._session.get(BookingItem, item_id)
        if (
            booking is None
            or booking.user_id != user.id
            or item is None
            or (item.booking_id != booking.id)
        ):
            raise NotFound("Booking item not found.", code="ITEM_NOT_FOUND")
        if item.kind != "hotel" or item.hotel_id is None:
            raise ValidationFailed("Only stays can be reviewed.", code="NOT_A_STAY")
        if item.status != ItemStatus.CONFIRMED:
            raise Conflict("Only completed stays can be reviewed.", code="REVIEW_NOT_ALLOWED")
        ends = _aware(item.ends_at)
        now = self._clock.now()
        if now < ends:
            raise Conflict("You can review this stay after check-out.", code="REVIEW_TOO_EARLY")
        if now - ends > timedelta(days=self._rules.review_window_days):
            raise Conflict("This stay is too long ago to review.", code="REVIEW_WINDOW_CLOSED")
        return item

    def write(
        self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID, review: ReviewIn
    ) -> MyReviewOut:
        item = self._completed_stay(user, booking_id, item_id)
        if _CONTACT.search(review.text) or (review.title and _CONTACT.search(review.title)):
            raise ValidationFailed(
                "Please leave out links, email addresses and phone numbers.",
                code="REVIEW_CONTENT",
            )
        row = StayReview(
            user_id=user.id,
            booking_item_id=item.id,
            hotel_id=item.hotel_id,
            rating=review.rating,
            title=review.title or None,
            text=review.text,
            traveller_type=review.traveller_type,
            status="published",
            created_at=self._clock.now(),
        )
        try:
            self._session.add(row)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise Conflict("You have already reviewed this stay.", code="REVIEW_EXISTS") from exc
        return self._mine(row)

    def _mine(self, row: StayReview) -> MyReviewOut:
        hotel = self._session.get(Hotel, row.hotel_id)
        base = self._out(
            _Row(
                row.id,
                "traveller",
                float(row.rating),
                row.title,
                row.text,
                row.traveller_type,
                row.created_at.date(),
                "traveller",
            )
        )
        return MyReviewOut(
            **base.model_dump(), hotel_id=row.hotel_id, hotel_name=hotel.name if hotel else ""
        )

    def mine(self, user: User) -> MyReviewsOut:
        written = list(
            self._session.scalars(
                select(StayReview)
                .where(StayReview.user_id == user.id, StayReview.status == "published")
                .order_by(StayReview.created_at.desc())
            )
        )
        reviewed = set(
            self._session.scalars(
                select(StayReview.booking_item_id).where(StayReview.user_id == user.id)
            )
        )
        now = self._clock.now()
        window = timedelta(days=self._rules.review_window_days)
        stays = self._session.execute(
            select(BookingItem, Hotel)
            .join(Booking, Booking.id == BookingItem.booking_id)
            .join(Hotel, Hotel.id == BookingItem.hotel_id)
            .where(
                Booking.user_id == user.id,
                BookingItem.kind == "hotel",
                BookingItem.status == ItemStatus.CONFIRMED,
            )
            .order_by(BookingItem.ends_at.desc())
        )
        awaiting = []
        for item, hotel in stays:
            ends = _aware(item.ends_at)
            if item.id in reviewed or not (ends <= now <= ends + window):
                continue
            awaiting.append(
                AwaitingReviewOut(
                    booking_id=item.booking_id,
                    item_id=item.id,
                    hotel_id=hotel.id,
                    hotel_name=hotel.name,
                    checked_out_on=item.check_out or ends.date(),
                )
            )
        return MyReviewsOut(written=[self._mine(r) for r in written], awaiting=awaiting)

    def remove(self, user: User, review_id: uuid.UUID) -> None:
        row = self._session.get(StayReview, review_id)
        if row is None or row.user_id != user.id or row.status != "published":
            raise NotFound("Review not found.", code="REVIEW_NOT_FOUND")
        row.status = "removed"
        self._session.commit()
