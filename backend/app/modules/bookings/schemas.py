"""Bookings and trips API contract."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.modules.search.pricing import MoneyOut, PriceLedger

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class FlightItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flight"] = "flight"
    offer_id: Annotated[str, StringConstraints(min_length=36, max_length=80)]
    adults: Annotated[int, Field(ge=1, le=9)] = 1


class HotelItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["hotel"] = "hotel"
    room_type_id: uuid.UUID
    check_in: date
    check_out: date
    rooms: Annotated[int, Field(ge=1, le=8)] = 1
    guests: Annotated[int, Field(ge=1, le=16)] = 2


ItemIn = Annotated[FlightItemIn | HotelItemIn, Field(discriminator="kind")]


PromoCode = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=24)]


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ItemIn], Field(min_length=1, max_length=4)]
    promo_code: PromoCode = None


class TravellerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name
    last_name: Name
    date_of_birth: date | None = None


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    phone: Annotated[str | None, StringConstraints(max_length=32)] = None


class CreateBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[ItemIn], Field(min_length=1, max_length=4)]
    travellers: Annotated[list[TravellerIn], Field(min_length=1, max_length=9)]
    contact: ContactIn
    trip_id: uuid.UUID | None = Field(default=None, description="Add to an existing trip")
    promo_code: PromoCode = None
    expected_total_minor: int | None = Field(
        default=None, description="Total the traveller saw; a different server price is refused"
    )


class PaymentRequest(BaseModel):
    """Card details are optional: an empty body confirms the booking without a card (the
    prototype has no payment step). When a card is given, all its fields are required."""

    model_config = ConfigDict(extra="forbid")

    card_number: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=23)]
        | None
    ) = None
    expiry_month: Annotated[int, Field(ge=1, le=12)] | None = None
    expiry_year: Annotated[int, Field(ge=2000, le=2100)] | None = None
    cvc: Annotated[str, StringConstraints(pattern=r"^\d{3,4}$")] | None = None
    cardholder_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    ) = None

    @model_validator(mode="after")
    def _card_complete(self) -> PaymentRequest:
        fields = (self.card_number, self.expiry_month, self.expiry_year, self.cvc)
        if any(f is not None for f in fields) and any(f is None for f in fields):
            raise ValueError("Give the card number, expiry month, expiry year and CVC together.")
        return self


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[uuid.UUID] | None = Field(
        default=None, description="Cancel only these items; all items when omitted"
    )


# ── Responses ──────────────────────────────────────────────────────────────────────────────────


class QuoteItemOut(BaseModel):
    kind: Literal["flight", "hotel"]
    title: str
    subtitle: str
    starts_at: datetime
    ends_at: datetime
    price: PriceLedger
    refundable: bool | None
    policy: str
    details: dict[str, Any]


class QuoteOut(BaseModel):
    items: list[QuoteItemOut]
    subtotal: MoneyOut
    discount: MoneyOut | None = None
    promo_code: str | None = None
    promo_description: str | None = None
    total: MoneyOut
    complete: bool
    fx_note: str | None
    hold_minutes: int


class ExtraOut(BaseModel):
    id: uuid.UUID
    kind: str = Field(description="seat, baggage or meal")
    code: str = Field(description="Seat (12A) or option code (BAG10, VGML)")
    label: str
    flight_id: uuid.UUID
    traveller_id: uuid.UUID
    traveller_name: str
    price: MoneyOut


class BookingItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    title: str
    subtitle: str
    starts_at: datetime
    ends_at: datetime
    price: MoneyOut
    refundable: bool | None
    policy: str
    details: dict[str, Any]
    replaced_by_item_id: uuid.UUID | None
    extras: list[ExtraOut] = Field(default_factory=list, description="Active seats, bags, meals")


class TravellerOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date | None


class PaymentOut(BaseModel):
    status: str
    amount: MoneyOut
    card_brand: str
    card_last4: str
    failure_code: str | None
    created_at: datetime


class RefundOut(BaseModel):
    booking_item_id: uuid.UUID
    amount: MoneyOut
    reason: str
    created_at: datetime


class EventOut(BaseModel):
    type: str
    message: str
    occurred_at: datetime


class BookingOut(BaseModel):
    id: uuid.UUID
    reference: str
    trip_id: uuid.UUID
    status: str
    hold_expires_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    total: MoneyOut
    discount: MoneyOut | None = None
    promo_code: str | None = None
    fx_note: str | None
    contact_email: str
    items: list[BookingItemOut]
    travellers: list[TravellerOut]
    payments: list[PaymentOut]
    refunds: list[RefundOut]
    events: list[EventOut]
    can_pay: bool
    can_cancel: bool


class CancellationLineOut(BaseModel):
    item_id: uuid.UUID
    title: str
    refund: MoneyOut
    reason: str


class CancellationQuoteOut(BaseModel):
    lines: list[CancellationLineOut]
    total_refund: MoneyOut


class BookingSummaryOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    total: MoneyOut
    items: list[BookingItemOut]
    created_at: datetime


class TripOut(BaseModel):
    id: uuid.UUID
    title: str
    starts_on: date | None
    ends_on: date | None
    destination_city_id: uuid.UUID | None
    destination_city_name: str | None
    state: Literal["upcoming", "in_progress", "past", "cancelled", "pending"]
    has_flight: bool
    has_stay: bool
    bookings: list[BookingSummaryOut]


class TripListOut(BaseModel):
    items: list[TripOut]
