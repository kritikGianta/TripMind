"""Booking use cases: quote, hold, pay, cancel, expire, and the traveller's trips.

Rules that make this safe to run with real concurrency:
- Prices are re-computed from the catalog at quote and at hold; the browser's price is only
  compared, never trusted (PRICE_CHANGED when it differs).
- Inventory is reserved with conditional updates inside the hold transaction (see inventory).
- `Idempotency-Key` + a unique (user, key) constraint: a retried or double-clicked checkout
  returns the first booking instead of creating a second one (plan v2, G18).
- Every state change writes a timeline event and an audit record in the same transaction.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, DomainError, NotFound, ValidationFailed
from app.core.metrics import (
    BOOKING_HOLDS,
    BOOKING_REVENUE,
    HOLDS_EXPIRED,
    PAYMENTS,
    REFUNDS,
)
from app.core.request_context import RequestMeta
from app.modules.audit.service import AuditService
from app.modules.auth.models import User
from app.modules.bookings import payments
from app.modules.bookings.extras import close_extras, paid_for_extras
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingExtra,
    BookingItem,
    BookingStatus,
    BookingTraveller,
    ExtraStatus,
    ItemStatus,
    Payment,
    Refund,
    Trip,
)
from app.modules.bookings.promotions import (
    PromoInvalid,
    Promotion,
    discount_for,
    load_promotions,
)
from app.modules.bookings.schemas import (
    BookingItemOut,
    BookingOut,
    BookingSummaryOut,
    CancellationLineOut,
    CancellationQuoteOut,
    CreateBookingRequest,
    EventOut,
    ExtraOut,
    FlightItemIn,
    HotelItemIn,
    ItemIn,
    PaymentOut,
    PaymentRequest,
    QuoteItemOut,
    QuoteOut,
    RefundOut,
    TravellerOut,
    TripListOut,
    TripOut,
)
from app.modules.catalog.models import Airport, City, Flight, RoomType
from app.modules.inventory.service import InventoryService, SoldOut
from app.modules.loyalty.module import LoyaltyService, load_loyalty_rules
from app.modules.notifications.service import NotificationService
from app.modules.search.flights import FlightSearchService
from app.modules.search.hotels import HotelSearchService, Stay
from app.modules.search.pricing import (
    Converter,
    MoneyOut,
    PriceLedger,
    load_pricing_rules,
    load_search_rules,
    rules_section,
)

_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
OPEN = (BookingStatus.HELD, BookingStatus.PAYMENT_FAILED)


class BookingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_minutes: int = Field(default=15, ge=1, le=120)
    max_travellers: int = Field(default=9, ge=1)
    flight_free_cancellation_hours: int = Field(default=24, ge=0)
    flight_refund_percent_after_window: int = Field(default=0, ge=0, le=100)
    hotel_free_cancellation_hours_before_check_in: int = Field(default=24, ge=0)
    flight_free_change_hours: int = Field(default=24, ge=0)
    flight_change_fee: int = Field(
        default=1500, ge=0, description="Per traveller, display currency"
    )


class PaymentDeclined(DomainError):
    status_code = 402
    code = "PAYMENT_DECLINED"
    message = "The payment was declined. Try another card."


@dataclass
class PricedItem:
    kind: str
    title: str
    subtitle: str
    starts_at: datetime
    ends_at: datetime
    ledger: PriceLedger
    price: MoneyOut  # supplier currency (display currency when legs are priced in several)
    display_minor: int
    refundable: bool | None
    policy: str
    details: dict[str, Any]
    quantity: int
    destination_city_id: uuid.UUID | None
    flights: list[Flight] = field(default_factory=list)
    room: RoomType | None = None
    check_in: date | None = None
    check_out: date | None = None
    offer_id: str | None = None
    hotel_id: uuid.UUID | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class BookingService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        config = settings.config_dir
        self._rules = BookingRules.model_validate(rules_section(config, "bookings"))
        self._converter = Converter(load_pricing_rules(config))
        today = (clock.now() - timedelta(hours=12)).date()
        search_rules = load_search_rules(config)
        self._flights = FlightSearchService(session, self._converter, search_rules, today)
        self._hotels = HotelSearchService(session, self._converter, search_rules, today)
        self._inventory = InventoryService(session)
        self._audit = AuditService(session)
        self._notifications = NotificationService(session)
        self._loyalty = LoyaltyService(session, load_loyalty_rules(config))

    # ------------------------------------------------------------------ pricing

    def _policy_text(self, kind: str, refundable: bool | None) -> str:
        r = self._rules
        if kind == "flight":
            after = (
                f"{r.flight_refund_percent_after_window}% refund"
                if r.flight_refund_percent_after_window
                else "no refund"
            )
            return (
                f"Free cancellation for {r.flight_free_cancellation_hours} hours after booking, "
                f"then {after}. TripMind demo policy: the supplied data has no fare rules."
            )
        if refundable:
            return (
                f"Free cancellation until {r.hotel_free_cancellation_hours_before_check_in} "
                "hours before check-in."
            )
        if refundable is False:
            return "Non-refundable rate."
        return "Cancellation terms not provided in the data; treated as non-refundable."

    def _display(self, ledger: PriceLedger) -> int:
        if ledger.display_total is None:
            raise ValidationFailed(
                "This price cannot be converted to the booking currency.", code="OFFER_NOT_BOOKABLE"
            )
        return ledger.display_total.amount_minor

    def _price_flight(self, item: FlightItemIn) -> PricedItem:
        try:
            ids = [uuid.UUID(part) for part in item.offer_id.split("~")]
        except ValueError as exc:
            raise ValidationFailed("Unknown flight offer.", code="OFFER_INVALID") from exc
        offer = self._flights.price_offer(ids, item.adults)
        seats = self._inventory.availability(ids)
        if any(seats.get(i, 0) < item.adults for i in ids):
            raise SoldOut("Not enough seats are left on this flight for your party.")
        flights = {f.id: f for f in self._session.scalars(select(Flight).where(Flight.id.in_(ids)))}
        first, last = offer.legs[0], offer.legs[-1]
        destination = self._session.scalar(
            select(Airport.city_id).where(Airport.code == last.destination.code)
        )
        total = offer.price.total or offer.price.display_total
        if total is None:  # price_offer already refuses unpriced legs; defensive
            raise ValidationFailed("This flight cannot be priced.", code="OFFER_NOT_BOOKABLE")
        cabin = first.cabin_class.replace("_", " ")
        return PricedItem(
            kind="flight",
            title=f"{first.origin.city_name} to {last.destination.city_name}",
            subtitle=(
                f"{' + '.join(leg.flight_number for leg in offer.legs)} · "
                f"{first.departure_local:%a %d %b, %H:%M} · {item.adults} adult"
                f"{'s' if item.adults > 1 else ''} · {cabin}"
            ),
            starts_at=first.departure_at,
            ends_at=last.arrival_at,
            ledger=offer.price,
            price=total,
            display_minor=self._display(offer.price),
            refundable=None,
            policy=self._policy_text("flight", None),
            details=offer.model_dump(mode="json"),
            quantity=item.adults,
            destination_city_id=destination,
            flights=[flights[i] for i in ids],
            offer_id=item.offer_id,
        )

    def _price_hotel(self, item: HotelItemIn) -> PricedItem:
        stay = Stay(
            check_in=item.check_in, check_out=item.check_out, guests=item.guests, rooms=item.rooms
        )
        hotel, city, room = self._hotels.price_room(item.room_type_id, stay)
        if room.price is None or room.price.total is None:
            raise ValidationFailed("This room cannot be priced.", code="OFFER_NOT_BOOKABLE")
        zone = ZoneInfo(city.timezone)
        check_in_clock = time.fromisoformat(hotel.check_in_time or "14:00")
        check_out_clock = time.fromisoformat(hotel.check_out_time or "11:00")
        room_type = self._session.get(RoomType, item.room_type_id)
        if room_type is None:
            raise NotFound("This room is no longer available.", code="OFFER_UNAVAILABLE")
        return PricedItem(
            kind="hotel",
            title=hotel.name,
            subtitle=(
                f"{room.name} · {stay.nights} night{'s' if stay.nights > 1 else ''} · "
                f"{item.rooms} room{'s' if item.rooms > 1 else ''} · {item.guests} guests"
            ),
            starts_at=datetime.combine(item.check_in, check_in_clock, zone).astimezone(UTC),
            ends_at=datetime.combine(item.check_out, check_out_clock, zone).astimezone(UTC),
            ledger=room.price,
            price=room.price.total,
            display_minor=self._display(room.price),
            refundable=room.refundable,
            policy=self._policy_text("hotel", room.refundable),
            details={
                "hotel_id": str(hotel.id),
                "city": city.name,
                "address": hotel.address,
                "room": room.model_dump(mode="json"),
                "check_in": str(item.check_in),
                "check_out": str(item.check_out),
                "guests": item.guests,
                "check_in_time": hotel.check_in_time,
                "check_out_time": hotel.check_out_time,
            },
            quantity=item.rooms,
            destination_city_id=city.id,
            room=room_type,
            check_in=item.check_in,
            check_out=item.check_out,
            hotel_id=hotel.id,
        )

    def _price(self, items: list[ItemIn]) -> list[PricedItem]:
        return [
            self._price_flight(i) if isinstance(i, FlightItemIn) else self._price_hotel(i)
            for i in items
        ]

    def _promo(
        self, user: User, code: str | None, priced: list[PricedItem]
    ) -> tuple[Promotion | None, int, list[int]]:
        """Validate a promo code for these items; (promotion, discount, split per item)."""
        if not code:
            return None, 0, [0] * len(priced)
        promo = load_promotions(self._settings.config_dir).get(code.strip().upper())
        if promo is None:
            raise PromoInvalid("That promo code does not exist.")
        confirmed = self._session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.user_id == user.id, Booking.status == BookingStatus.CONFIRMED)
        )
        used = self._session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.user_id == user.id,
                Booking.promo_code == promo.code,
                Booking.status.in_([BookingStatus.CONFIRMED, *OPEN]),
            )
        )
        discount, split = discount_for(
            promo,
            items=[
                (
                    p.kind,
                    p.display_minor,
                    (p.check_out - p.check_in).days if p.check_in and p.check_out else 0,
                )
                for p in priced
            ],
            today=self._clock.now().date(),
            has_confirmed_booking=bool(confirmed),
            already_used=bool(used),
        )
        return promo, discount, split

    def quote(self, user: User, items: list[ItemIn], promo_code: str | None = None) -> QuoteOut:
        priced = self._price(items)
        promo, discount, _ = self._promo(user, promo_code, priced)
        converted = [p for p in priced if p.ledger.converted]
        return QuoteOut(
            items=[
                QuoteItemOut(
                    kind=p.kind,
                    title=p.title,
                    subtitle=p.subtitle,
                    starts_at=p.starts_at,
                    ends_at=p.ends_at,
                    price=p.ledger,
                    refundable=p.refundable,
                    policy=p.policy,
                    details=p.details,
                )
                for p in priced
            ],
            subtotal=MoneyOut(
                amount_minor=sum(p.display_minor for p in priced),
                currency=self._converter.display_currency,
            ),
            discount=MoneyOut(amount_minor=discount, currency=self._converter.display_currency)
            if promo
            else None,
            promo_code=promo.code if promo else None,
            promo_description=promo.description if promo else None,
            total=MoneyOut(
                amount_minor=sum(p.display_minor for p in priced) - discount,
                currency=self._converter.display_currency,
            ),
            complete=all(p.ledger.complete for p in priced),
            fx_note=converted[0].ledger.fx_note if converted else None,
            hold_minutes=self._rules.hold_minutes,
        )

    # ------------------------------------------------------------------ hold

    @staticmethod
    def _request_hash(request: CreateBookingRequest) -> str:
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _existing(self, user: User, key: str) -> Booking | None:
        return self._session.scalar(
            select(Booking).where(Booking.user_id == user.id, Booking.idempotency_key == key)
        )

    def _reference(self) -> str:
        while True:
            ref = "TM" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))
            if self._session.scalar(select(Booking.id).where(Booking.reference == ref)) is None:
                return ref

    def _event(
        self, booking: Booking, type_: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self._session.add(
            BookingEvent(
                booking_id=booking.id,
                type=type_,
                message=message,
                details=details,
                occurred_at=self._clock.now(),
            )
        )

    def _validate_party(self, request: CreateBookingRequest) -> None:
        adults = {i.adults for i in request.items if isinstance(i, FlightItemIn)}
        if len(adults) > 1:
            raise ValidationFailed(
                "All flights in one booking must be for the same travellers.",
                code="TRAVELLERS_MISMATCH",
            )
        if adults and len(request.travellers) != adults.pop():
            raise ValidationFailed(
                "Enter details for every adult on the flight.", code="TRAVELLERS_MISMATCH"
            )
        if len(request.travellers) > self._rules.max_travellers:
            raise ValidationFailed(
                "Too many travellers for one booking.", code="TRAVELLERS_MISMATCH"
            )

    def _trip_for(self, user: User, trip_id: uuid.UUID | None, priced: list[PricedItem]) -> Trip:
        if trip_id is not None:
            trip = self._session.get(Trip, trip_id)
            if trip is None or trip.user_id != user.id:
                raise NotFound("Trip not found.", code="TRIP_NOT_FOUND")
        else:
            main = next((p for p in priced if p.kind == "flight"), priced[0])
            city = (
                self._session.get(City, main.destination_city_id)
                if (main.destination_city_id)
                else None
            )
            name = city.name if city else main.title
            trip = Trip(
                user_id=user.id,
                title=f"Trip to {name}" if main.kind == "flight" else f"Stay in {name}",
                destination_city_id=main.destination_city_id,
            )
            self._session.add(trip)
        starts = min(p.starts_at for p in priced).date()
        ends = max(p.ends_at for p in priced).date()
        trip.starts_on = min(filter(None, [trip.starts_on, starts]))
        trip.ends_on = max(filter(None, [trip.ends_on, ends]))
        return trip

    def create(
        self, user: User, request: CreateBookingRequest, key: str, meta: RequestMeta
    ) -> Booking:
        request_hash = self._request_hash(request)
        existing = self._existing(user, key)
        if existing is not None:
            BOOKING_HOLDS.labels(outcome="replayed").inc()
            return self._replay(existing, request_hash)
        self._validate_party(request)
        priced = self._price(request.items)
        promo, discount, split = self._promo(user, request.promo_code, priced)
        total = sum(p.display_minor for p in priced) - discount
        if request.expected_total_minor is not None and request.expected_total_minor != total:
            BOOKING_HOLDS.labels(outcome="price_changed").inc()
            raise Conflict(
                "The price has changed since you started checkout.",
                code="PRICE_CHANGED",
                details={"total_minor": total, "currency": self._converter.display_currency},
            )
        now = self._clock.now()
        trip = self._trip_for(user, request.trip_id, priced)
        self._session.flush()
        booking = Booking(
            reference=self._reference(),
            user_id=user.id,
            trip_id=trip.id,
            status=BookingStatus.HELD,
            idempotency_key=key,
            request_hash=request_hash,
            hold_expires_at=now + timedelta(minutes=self._rules.hold_minutes),
            total_minor=total,
            currency=self._converter.display_currency,
            price_snapshot={"items": [p.ledger.model_dump(mode="json") for p in priced]},
            promo_code=promo.code if promo else None,
            discount_minor=discount,
            contact_email=str(request.contact.email).lower(),
            contact_phone=request.contact.phone,
        )
        try:
            self._session.add(booking)
            self._session.flush()  # the unique (user, key) check happens here
            for position, p in enumerate(priced):
                item = BookingItem(
                    booking_id=booking.id,
                    kind=p.kind,
                    status=ItemStatus.HELD,
                    position=position,
                    offer_id=p.offer_id,
                    room_type_id=p.room.id if p.room else None,
                    hotel_id=p.hotel_id,
                    check_in=p.check_in,
                    check_out=p.check_out,
                    quantity=p.quantity,
                    starts_at=p.starts_at,
                    ends_at=p.ends_at,
                    title=p.title,
                    price_minor=p.price.amount_minor,
                    currency=p.price.currency,
                    refundable=p.refundable,
                    snapshot={
                        "subtitle": p.subtitle,
                        "policy": p.policy,
                        # What the traveller pays for this item after any promo share, so
                        # refunds give back exactly what was paid.
                        "display_minor": p.display_minor - split[position],
                        "discount_minor": split[position],
                        "details": p.details,
                    },
                )
                self._session.add(item)
                self._session.flush()
                for flight in p.flights:
                    self._inventory.reserve_seats(item.id, flight, p.quantity)
                if p.room is not None and p.check_in and p.check_out:
                    self._inventory.reserve_rooms(
                        item.id, p.room, p.check_in, p.check_out, p.quantity
                    )
            self._session.add_all(
                [
                    BookingTraveller(
                        booking_id=booking.id,
                        position=i,
                        first_name=t.first_name,
                        last_name=t.last_name,
                        date_of_birth=t.date_of_birth,
                    )
                    for i, t in enumerate(request.travellers)
                ]
            )
            self._event(
                booking,
                "hold_created",
                f"Held for {self._rules.hold_minutes} minutes while you pay.",
            )
            self._audit.record(
                action="booking.hold",
                outcome="success",
                meta=meta,
                actor_user_id=user.id,
                details={"booking_id": str(booking.id), "reference": booking.reference},
            )
            self._session.commit()
        except IntegrityError:
            # A concurrent request with the same key won the race: return its booking.
            self._session.rollback()
            existing = self._existing(user, key)
            if existing is None:
                raise
            return self._replay(existing, request_hash)
        except SoldOut:
            self._session.rollback()
            BOOKING_HOLDS.labels(outcome="sold_out").inc()
            raise
        BOOKING_HOLDS.labels(outcome="created").inc()
        return booking

    def _replay(self, booking: Booking, request_hash: str) -> Booking:
        if booking.request_hash != request_hash:
            raise Conflict(
                "This idempotency key was used for a different booking.",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return booking

    # ------------------------------------------------------------------ reads and expiry

    def _owned(self, user: User, booking_id: uuid.UUID, *, lock: bool = False) -> Booking:
        query = select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id)
        if lock:
            query = query.with_for_update()
        booking = self._session.scalar(query)
        if booking is None:
            raise NotFound("Booking not found.", code="BOOKING_NOT_FOUND")
        return booking

    def _items(self, booking: Booking) -> list[BookingItem]:
        return list(
            self._session.scalars(
                select(BookingItem)
                .where(BookingItem.booking_id == booking.id)
                .order_by(
                    BookingItem.position, BookingItem.created_at
                )  # a change follows its original
            )
        )

    def _expire_if_due(self, booking: Booking) -> bool:
        now = self._clock.now()
        if booking.status not in OPEN or _aware(booking.hold_expires_at) > now:
            return False
        items = self._items(booking)
        self._inventory.release([i.id for i in items], now)
        for item in items:
            item.status = ItemStatus.RELEASED
        booking.status = BookingStatus.EXPIRED
        HOLDS_EXPIRED.inc()
        self._event(
            booking, "hold_expired", "The hold expired before payment; nothing was charged."
        )
        return True

    def get(self, user: User, booking_id: uuid.UUID) -> BookingOut:
        booking = self._owned(user, booking_id)
        if self._expire_if_due(booking):
            self._session.commit()
        return self.to_out(booking)

    def expire_due(self) -> int:
        """Background sweep: expire every overdue hold and release its inventory."""
        now = self._clock.now()
        due = list(
            self._session.scalars(
                select(Booking)
                .where(Booking.status.in_([s.value for s in OPEN]), Booking.hold_expires_at < now)
                .with_for_update(skip_locked=True)
                .limit(200)
            )
        )
        for booking in due:
            self._expire_if_due(booking)
        self._session.commit()
        return len(due)

    # ------------------------------------------------------------------ payment

    def pay(
        self,
        user: User,
        booking_id: uuid.UUID,
        request: PaymentRequest,
        key: str,
        meta: RequestMeta,
    ) -> BookingOut:
        booking = self._owned(user, booking_id, lock=True)
        previous = self._session.scalar(
            select(Payment).where(Payment.booking_id == booking.id, Payment.idempotency_key == key)
        )
        if previous is not None:  # retried request: same outcome, no second charge
            return self.to_out(booking)
        if self._expire_if_due(booking):
            self._session.commit()
            raise Conflict("Your hold expired. Please search again.", code="HOLD_EXPIRED")
        if booking.status not in OPEN:
            raise Conflict("This booking cannot be paid.", code="BOOKING_NOT_PAYABLE")

        result = payments.charge(
            request.card_number, request.expiry_month, request.expiry_year, self._clock.now().date()
        )
        self._session.add(
            Payment(
                booking_id=booking.id,
                idempotency_key=key,
                status="succeeded" if result.succeeded else "failed",
                amount_minor=booking.total_minor,
                currency=booking.currency,
                card_brand=result.brand,
                card_last4=result.last4,
                failure_code=result.failure_code,
                provider_reference=result.reference,
            )
        )
        if result.succeeded:
            booking.status = BookingStatus.CONFIRMED
            booking.confirmed_at = self._clock.now()
            for item in self._items(booking):
                item.status = ItemStatus.CONFIRMED
            self._event(
                booking,
                "confirmed",
                f"Paid with {result.brand} ending {result.last4}. Booking confirmed.",
            )
            points = self._loyalty.earn(
                user.id, booking.id, booking.total_minor, booking.reference, self._clock.now()
            )
            if points:
                self._event(booking, "loyalty", f"Earned {points} loyalty points.")
            self._notifications.notify(
                user_id=user.id,
                kind="booking_confirmed",
                severity="success",
                title=f"Booking {booking.reference} confirmed",
                body=f"{', '.join(i.title for i in self._items(booking))}. Confirmation sent to "
                f"{booking.contact_email}.",
                link=f"/bookings/{booking.id}",
                now=self._clock.now(),
            )
        else:
            booking.status = BookingStatus.PAYMENT_FAILED
            self._event(
                booking,
                "payment_failed",
                f"Card ending {result.last4} was declined ({result.failure_code}). "
                "Your hold is kept until it expires.",
            )
        self._audit.record(
            action="booking.payment",
            outcome="success" if result.succeeded else "failure",
            meta=meta,
            actor_user_id=user.id,
            details={"booking_id": str(booking.id), "failure_code": result.failure_code},
        )
        self._session.commit()
        PAYMENTS.labels(outcome="succeeded" if result.succeeded else "declined").inc()
        if result.succeeded:
            BOOKING_REVENUE.labels(currency=booking.currency).inc(booking.total_minor)
        if not result.succeeded:
            raise PaymentDeclined(
                code=result.failure_code or "PAYMENT_DECLINED",
                details={"booking_id": str(booking.id)},
            )
        return self.to_out(booking)

    # ------------------------------------------------------------------ cancellation

    def _refund(self, booking: Booking, item: BookingItem, now: datetime) -> tuple[int, str]:
        # Seats, bags and meals follow their flight's refund rule.
        paid = int(item.snapshot.get("display_minor", 0))
        paid += paid_for_extras(self._session, [item.id]).get(item.id, 0)
        if booking.status != BookingStatus.CONFIRMED:
            return 0, "Not paid: nothing to refund."
        if now >= _aware(item.starts_at):
            return 0, "Already started: no refund."
        if item.kind == "flight":
            confirmed = _aware(booking.confirmed_at or booking.created_at)
            if now - confirmed <= timedelta(hours=self._rules.flight_free_cancellation_hours):
                return paid, "Cancelled within the free cancellation window."
            share = self._rules.flight_refund_percent_after_window
            return paid * share // 100, f"{share}% refund after the free cancellation window."
        if not item.refundable:
            return 0, "Non-refundable rate."
        deadline = _aware(item.starts_at) - timedelta(
            hours=self._rules.hotel_free_cancellation_hours_before_check_in
        )
        if now <= deadline:
            return paid, "Free cancellation before the deadline."
        return 0, "Too close to check-in for a refund."

    def _cancellable(self, booking: Booking, item_ids: list[uuid.UUID] | None) -> list[BookingItem]:
        items = [
            i for i in self._items(booking) if i.status in (ItemStatus.HELD, ItemStatus.CONFIRMED)
        ]
        if item_ids:
            wanted = set(item_ids)
            items = [i for i in items if i.id in wanted]
            if len(items) != len(wanted):
                raise NotFound("Some of these items cannot be cancelled.", code="ITEM_NOT_FOUND")
        if not items:
            raise Conflict("Nothing left to cancel in this booking.", code="NOTHING_TO_CANCEL")
        return items

    def cancellation_quote(
        self, user: User, booking_id: uuid.UUID, item_ids: list[uuid.UUID] | None
    ) -> CancellationQuoteOut:
        booking = self._owned(user, booking_id)
        now = self._clock.now()
        lines = []
        for item in self._cancellable(booking, item_ids):
            amount, reason = self._refund(booking, item, now)
            lines.append(
                CancellationLineOut(
                    item_id=item.id,
                    title=item.title,
                    reason=reason,
                    refund=MoneyOut(amount_minor=amount, currency=booking.currency),
                )
            )
        return CancellationQuoteOut(
            lines=lines,
            total_refund=MoneyOut(
                amount_minor=sum(line.refund.amount_minor for line in lines),
                currency=booking.currency,
            ),
        )

    def cancel(
        self, user: User, booking_id: uuid.UUID, item_ids: list[uuid.UUID] | None, meta: RequestMeta
    ) -> BookingOut:
        booking = self._owned(user, booking_id, lock=True)
        if self._expire_if_due(booking):
            self._session.commit()
            raise Conflict("This hold has already expired.", code="NOTHING_TO_CANCEL")
        now = self._clock.now()
        items = self._cancellable(booking, item_ids)
        refunded = 0
        for item in items:
            amount, reason = self._refund(booking, item, now)
            if amount:
                self._session.add(
                    Refund(
                        booking_id=booking.id,
                        booking_item_id=item.id,
                        amount_minor=amount,
                        currency=booking.currency,
                        reason=reason,
                    )
                )
                refunded += amount
            item.status = (
                ItemStatus.CANCELLED
                if booking.status == BookingStatus.CONFIRMED
                else ItemStatus.RELEASED
            )
        self._inventory.release([i.id for i in items], now)
        close_extras(self._session, [i.id for i in items])
        remaining = [
            i for i in self._items(booking) if i.status in (ItemStatus.HELD, ItemStatus.CONFIRMED)
        ]
        if not remaining:
            booking.status = BookingStatus.CANCELLED
            booking.cancelled_at = now
        names = ", ".join(i.title for i in items)
        self._event(
            booking,
            "cancelled",
            f"Cancelled {names}."
            + (
                f" Refund of {refunded / 100:.2f} {booking.currency} issued."
                if refunded
                else " No refund due."
            ),
        )
        if refunded:
            self._loyalty.reverse(user.id, booking.id, refunded, booking.reference, now)
        self._notifications.notify(
            user_id=user.id,
            kind="booking_cancelled",
            title=f"Booking {booking.reference} updated",
            body=f"Cancelled {names}."
            + (
                f" Refund of {refunded / 100:,.2f} {booking.currency} on its way."
                if refunded
                else " No refund was due."
            ),
            link=f"/bookings/{booking.id}",
            now=now,
        )
        self._audit.record(
            action="booking.cancel",
            outcome="success",
            meta=meta,
            actor_user_id=user.id,
            details={"booking_id": str(booking.id), "items": len(items), "refund_minor": refunded},
        )
        self._session.commit()
        if refunded:
            REFUNDS.labels(currency=booking.currency, reason="traveller").inc(refunded)
        return self.to_out(booking)

    # ------------------------------------------------------------------ views

    def _item_out(self, item: BookingItem, extras: list[ExtraOut] | None = None) -> BookingItemOut:
        return BookingItemOut(
            id=item.id,
            kind=item.kind,
            status=item.status,
            title=item.title,
            subtitle=item.snapshot.get("subtitle", ""),
            starts_at=_aware(item.starts_at),
            ends_at=_aware(item.ends_at),
            price=MoneyOut(amount_minor=item.price_minor, currency=item.currency),
            refundable=item.refundable,
            policy=item.snapshot.get("policy", ""),
            details=item.snapshot.get("details", {}),
            replaced_by_item_id=item.replaced_by_item_id,
            extras=extras or [],
        )

    def _extras_out(
        self, booking: Booking, names: dict[uuid.UUID, str]
    ) -> dict[uuid.UUID, list[ExtraOut]]:
        rows = self._session.scalars(
            select(BookingExtra)
            .where(BookingExtra.booking_id == booking.id, BookingExtra.status == ExtraStatus.ACTIVE)
            .order_by(BookingExtra.created_at)
        )
        grouped: dict[uuid.UUID, list[ExtraOut]] = {}
        for e in rows:
            grouped.setdefault(e.booking_item_id, []).append(
                ExtraOut(
                    id=e.id,
                    kind=e.kind,
                    code=e.code,
                    label=e.label,
                    flight_id=e.flight_id,
                    traveller_id=e.traveller_id,
                    traveller_name=names.get(e.traveller_id, ""),
                    price=MoneyOut(amount_minor=e.price_minor, currency=e.currency),
                )
            )
        return grouped

    def to_out(self, booking: Booking) -> BookingOut:
        items = self._items(booking)
        travellers = list(
            self._session.scalars(
                select(BookingTraveller)
                .where(BookingTraveller.booking_id == booking.id)
                .order_by(BookingTraveller.position)
            )
        )
        extras = self._extras_out(
            booking, {t.id: f"{t.first_name} {t.last_name}" for t in travellers}
        )
        paid = self._session.scalars(
            select(Payment)
            .where(
                Payment.booking_id == booking.id,
                Payment.provider_reference != payments.NO_CHARGE,
            )
            .order_by(Payment.created_at)
        )
        refunds = self._session.scalars(select(Refund).where(Refund.booking_id == booking.id))
        events = self._session.scalars(
            select(BookingEvent)
            .where(BookingEvent.booking_id == booking.id)
            .order_by(BookingEvent.occurred_at)
        )
        snapshot_items = booking.price_snapshot.get("items", [])
        fx = next((s.get("fx_note") for s in snapshot_items if s.get("fx_note")), None)
        return BookingOut(
            id=booking.id,
            reference=booking.reference,
            trip_id=booking.trip_id,
            status=booking.status,
            hold_expires_at=_aware(booking.hold_expires_at),
            confirmed_at=booking.confirmed_at,
            cancelled_at=booking.cancelled_at,
            total=MoneyOut(amount_minor=booking.total_minor, currency=booking.currency),
            discount=MoneyOut(amount_minor=booking.discount_minor, currency=booking.currency)
            if booking.discount_minor
            else None,
            promo_code=booking.promo_code,
            fx_note=fx,
            contact_email=booking.contact_email,
            items=[self._item_out(i, extras.get(i.id)) for i in items],
            travellers=[
                TravellerOut(
                    id=t.id,
                    first_name=t.first_name,
                    last_name=t.last_name,
                    date_of_birth=t.date_of_birth,
                )
                for t in travellers
            ],
            payments=[
                PaymentOut(
                    status=p.status,
                    amount=MoneyOut(amount_minor=p.amount_minor, currency=p.currency),
                    card_brand=p.card_brand,
                    card_last4=p.card_last4,
                    failure_code=p.failure_code,
                    created_at=p.created_at,
                )
                for p in paid
            ],
            refunds=[
                RefundOut(
                    booking_item_id=r.booking_item_id,
                    amount=MoneyOut(amount_minor=r.amount_minor, currency=r.currency),
                    reason=r.reason,
                    created_at=r.created_at,
                )
                for r in refunds
            ],
            events=[
                EventOut(type=e.type, message=e.message, occurred_at=e.occurred_at) for e in events
            ],
            can_pay=booking.status in OPEN,
            can_cancel=any(i.status in (ItemStatus.HELD, ItemStatus.CONFIRMED) for i in items),
        )

    def _trip_out(self, trip: Trip, bookings: list[Booking]) -> TripOut:
        summaries = []
        items_all: list[BookingItem] = []
        for b in bookings:
            if b.status in OPEN and self._expire_if_due(b):
                self._session.commit()
            items = self._items(b)
            items_all += [i for i in items if b.status in (*OPEN, BookingStatus.CONFIRMED)]
            summaries.append(
                BookingSummaryOut(
                    id=b.id,
                    reference=b.reference,
                    status=b.status,
                    total=MoneyOut(amount_minor=b.total_minor, currency=b.currency),
                    items=[self._item_out(i) for i in items],
                    created_at=b.created_at,
                )
            )
        live = [i for i in items_all if i.status in (ItemStatus.HELD, ItemStatus.CONFIRMED)]
        today = self._clock.now().date()
        if not live:
            state = "cancelled"
        elif all(i.status == ItemStatus.HELD for i in live):
            state = "pending"
        elif trip.ends_on and trip.ends_on < today:
            state = "past"
        elif trip.starts_on and trip.starts_on <= today:
            state = "in_progress"
        else:
            state = "upcoming"
        city = (
            self._session.get(City, trip.destination_city_id)
            if (trip.destination_city_id)
            else None
        )
        return TripOut(
            id=trip.id,
            title=trip.title,
            starts_on=trip.starts_on,
            ends_on=trip.ends_on,
            destination_city_id=trip.destination_city_id,
            destination_city_name=city.name if city else None,
            state=state,
            has_flight=any(i.kind == "flight" for i in live),
            has_stay=any(i.kind == "hotel" for i in live),
            bookings=summaries,
        )

    def trips(self, user: User) -> TripListOut:
        trips = list(
            self._session.scalars(
                select(Trip).where(Trip.user_id == user.id).order_by(Trip.starts_on.desc())
            )
        )
        by_trip: dict[uuid.UUID, list[Booking]] = {t.id: [] for t in trips}
        for booking in self._session.scalars(
            select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at)
        ):
            by_trip.setdefault(booking.trip_id, []).append(booking)
        return TripListOut(items=[self._trip_out(t, by_trip.get(t.id, [])) for t in trips])

    def trip(self, user: User, trip_id: uuid.UUID) -> TripOut:
        trip = self._session.get(Trip, trip_id)
        if trip is None or trip.user_id != user.id:
            raise NotFound("Trip not found.", code="TRIP_NOT_FOUND")
        bookings = list(
            self._session.scalars(
                select(Booking).where(Booking.trip_id == trip.id).order_by(Booking.created_at)
            )
        )
        return self._trip_out(trip, bookings)
