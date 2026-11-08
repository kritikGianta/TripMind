"""Seats, checked baggage and meals for a booked flight.

Flow: catalog (options and prices per flight, current picks) and seat map -> quote -> purchase.
The purchase re-prices on the server and refuses a total different from the one the traveller saw
(EXTRAS_PRICE_CHANGED). Seats are claimed before the card is charged; the database allows one
active passenger per seat, so two people picking the same seat at once get exactly one winner.
Changing a pick charges only the difference to its list price and never refunds a cheaper one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.metrics import ANCILLARIES
from app.core.request_context import RequestMeta
from app.modules.auth.models import User
from app.modules.bookings import payments
from app.modules.bookings.extras import (
    PREMIUM_CABINS,
    Cabin,
    ExtraKind,
    Option,
    build_cabin,
    load_ancillary_rules,
    taken_seats,
)
from app.modules.bookings.models import (
    Booking,
    BookingExtra,
    BookingItem,
    BookingStatus,
    BookingTraveller,
    ExtraStatus,
    ItemStatus,
    Payment,
)
from app.modules.bookings.schemas import BookingOut, ExtraOut, PaymentRequest
from app.modules.bookings.service import BookingService, PaymentDeclined, _aware
from app.modules.catalog.models import Airport, Flight
from app.modules.search.pricing import MoneyOut

# ------------------------------------------------------------------------------ schemas


class SeatOut(BaseModel):
    code: str
    letter: str
    position: Literal["window", "aisle", "middle"]
    zone: str = Field(description="extra_legroom, front, window_or_aisle, middle or included")
    price: MoneyOut
    available: bool
    traveller_id: uuid.UUID | None = Field(
        description="Set when a traveller on this booking has it"
    )


class SeatRowOut(BaseModel):
    row: int
    seats: list[SeatOut]


class SeatMapOut(BaseModel):
    flight_id: uuid.UUID
    flight_number: str
    aircraft: str | None
    cabin_class: str
    layout: str
    groups: list[str] = Field(description="Seat letters per block; aisles sit between blocks")
    rows: list[SeatRowOut]
    note: str


class OptionOut(BaseModel):
    code: str
    label: str
    price: MoneyOut


class FlightExtrasOut(BaseModel):
    flight_id: uuid.UUID
    flight_number: str
    route: str
    departure_at: datetime
    cabin_class: str
    seats_included: bool
    baggage: list[OptionOut]
    meals: list[OptionOut]


class PassengerOut(BaseModel):
    id: uuid.UUID
    name: str


class ExtrasCatalogOut(BaseModel):
    item_id: uuid.UUID
    open: bool
    reason: str | None
    closes_at: datetime
    travellers: list[PassengerOut]
    flights: list[FlightExtrasOut]
    selected: list[ExtraOut]
    policy: str


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flight_id: uuid.UUID
    traveller_id: uuid.UUID
    kind: ExtraKind
    code: str = Field(min_length=2, max_length=16, pattern=r"^[A-Z0-9]+$")


class ExtrasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selections: list[Selection] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def _unique(self) -> ExtrasRequest:
        slots = [(s.flight_id, s.traveller_id, s.kind) for s in self.selections]
        if len(slots) != len(set(slots)):
            raise ValueError("one seat, one bag and one meal per traveller per flight")
        seats = [(s.flight_id, s.code) for s in self.selections if s.kind == "seat"]
        if len(seats) != len(set(seats)):
            raise ValueError("two travellers cannot take the same seat")
        return self


class ExtrasPurchase(ExtrasRequest):
    expected_total_minor: int = Field(ge=0, description="From the quote the traveller saw")
    payment: PaymentRequest | None = Field(default=None, description="Needed when money is due")


class ExtraLineOut(BaseModel):
    flight_id: uuid.UUID
    traveller_id: uuid.UUID
    kind: str
    code: str
    label: str
    price: MoneyOut
    credit: MoneyOut = Field(description="List price of the pick it replaces")
    charge: MoneyOut
    unchanged: bool


class ExtrasQuoteOut(BaseModel):
    lines: list[ExtraLineOut]
    total: MoneyOut


# ------------------------------------------------------------------------------ service


@dataclass
class _Line:
    selection: Selection
    label: str
    price: int  # minor units, display currency
    existing: BookingExtra | None

    @property
    def unchanged(self) -> bool:
        return self.existing is not None and self.existing.code == self.selection.code

    @property
    def charge(self) -> int:
        if self.unchanged:
            return 0
        credit = self.existing.price_minor if self.existing else 0
        return max(self.price - credit, 0)


@dataclass
class _Context:
    booking: Booking
    item: BookingItem
    flights: list[Flight]
    travellers: list[BookingTraveller]
    domestic: dict[uuid.UUID, bool]
    closes_at: datetime
    reason: str | None


class AncillaryService(BookingService):
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        super().__init__(session, settings, clock)
        self._extras = load_ancillary_rules(settings.config_dir)

    # ------------------------------------------------------------------ context

    def _context(self, booking: Booking, item_id: uuid.UUID) -> _Context:
        item = self._session.get(BookingItem, item_id)
        if item is None or item.booking_id != booking.id:
            raise NotFound("Booking item not found.", code="ITEM_NOT_FOUND")
        if item.kind != "flight" or not item.offer_id:
            raise ValidationFailed("Seats and extras are sold with flights.", code="NOT_A_FLIGHT")
        flights: list[Flight] = []
        for part in item.offer_id.split("~"):
            flight = self._session.get(Flight, uuid.UUID(part))
            if flight is None:
                raise NotFound("This flight is no longer in the schedule.", code="FLIGHT_GONE")
            flights.append(flight)
        airports = {
            a.id: a.country
            for a in self._session.scalars(
                select(Airport).where(
                    Airport.id.in_(
                        {f.origin_airport_id for f in flights}
                        | {f.destination_airport_id for f in flights}
                    )
                )
            )
        }
        travellers = list(
            self._session.scalars(
                select(BookingTraveller)
                .where(BookingTraveller.booking_id == booking.id)
                .order_by(BookingTraveller.position)
            )
        )
        closes_at = _aware(item.starts_at) - timedelta(
            hours=self._extras.cutoff_hours_before_departure
        )
        reason = None
        if booking.status != BookingStatus.CONFIRMED or item.status != ItemStatus.CONFIRMED:
            reason = "Seats and extras can be added to confirmed flights."
        elif self._clock.now() >= closes_at:
            reason = (
                f"Seats and extras close {self._extras.cutoff_hours_before_departure} hours "
                "before departure."
            )
        return _Context(
            booking=booking,
            item=item,
            flights=flights,
            travellers=travellers,
            domestic={
                f.id: airports.get(f.origin_airport_id) == airports.get(f.destination_airport_id)
                for f in flights
            },
            closes_at=closes_at,
            reason=reason,
        )

    def _cabin(self, flight: Flight) -> Cabin:
        return build_cabin(
            self._extras.seat_maps, flight.aircraft, flight.cabin_class, flight.seat_capacity
        )

    def _baggage(self, ctx: _Context, flight: Flight) -> list[Option]:
        rules = self._extras.baggage
        return rules.domestic if ctx.domestic[flight.id] else rules.international

    def _meal_price(self, flight: Flight, option: Option) -> int:
        included = flight.cabin_class in PREMIUM_CABINS and self._extras.meals.premium_included
        return 0 if included else option.price

    def _money(self, minor: int) -> MoneyOut:
        return MoneyOut(amount_minor=minor, currency=self._converter.display_currency)

    # ------------------------------------------------------------------ reads

    def catalog(self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID) -> ExtrasCatalogOut:
        booking = self._owned(user, booking_id)
        ctx = self._context(booking, item_id)
        names = {t.id: f"{t.first_name} {t.last_name}" for t in ctx.travellers}
        out = self.to_out(booking)
        selected = next((i.extras for i in out.items if i.id == ctx.item.id), [])
        flights = []
        for flight in ctx.flights:
            origin = self._session.get(Airport, flight.origin_airport_id)
            destination = self._session.get(Airport, flight.destination_airport_id)
            flights.append(
                FlightExtrasOut(
                    flight_id=flight.id,
                    flight_number=flight.flight_number,
                    route=f"{origin.code if origin else '?'} to "
                    f"{destination.code if destination else '?'}",
                    departure_at=_aware(flight.departure_at),
                    cabin_class=flight.cabin_class,
                    seats_included=flight.cabin_class in PREMIUM_CABINS,
                    baggage=[
                        OptionOut(code=o.code, label=o.label, price=self._money(o.price * 100))
                        for o in self._baggage(ctx, flight)
                    ],
                    meals=[
                        OptionOut(
                            code=o.code,
                            label=o.label,
                            price=self._money(self._meal_price(flight, o) * 100),
                        )
                        for o in self._extras.meals.options
                    ],
                )
            )
        return ExtrasCatalogOut(
            item_id=ctx.item.id,
            open=ctx.reason is None,
            reason=ctx.reason,
            closes_at=ctx.closes_at,
            travellers=[PassengerOut(id=t, name=n) for t, n in names.items()],
            flights=flights,
            selected=selected,
            policy=(
                "Prices are per traveller per flight. Changing a pick charges only the difference "
                "and never refunds a cheaper one. Extras follow their flight: refunded under the "
                "same rule if it is cancelled, and in full if it is changed or disrupted."
            ),
        )

    def seat_map(
        self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID, flight_id: uuid.UUID
    ) -> SeatMapOut:
        booking = self._owned(user, booking_id)
        ctx = self._context(booking, item_id)
        flight = next((f for f in ctx.flights if f.id == flight_id), None)
        if flight is None:
            raise NotFound("That flight is not part of this booking.", code="FLIGHT_NOT_IN_ITEM")
        cabin = self._cabin(flight)
        taken = taken_seats(self._session, flight.id)
        mine = {t.id for t in ctx.travellers}
        return SeatMapOut(
            flight_id=flight.id,
            flight_number=flight.flight_number,
            aircraft=flight.aircraft,
            cabin_class=flight.cabin_class,
            layout=cabin.layout,
            groups=cabin.groups,
            rows=[
                SeatRowOut(
                    row=row[0].row,
                    seats=[
                        SeatOut(
                            code=s.code,
                            letter=s.letter,
                            position=s.position,
                            zone=s.zone,
                            price=self._money(s.price * 100),
                            available=s.code not in taken,
                            traveller_id=taken[s.code] if taken.get(s.code) in mine else None,
                        )
                        for s in row
                    ],
                )
                for row in cabin.rows
                if row
            ],
            note=(
                "Seat plan derived from the aircraft type in the flight data. Only seats chosen "
                "through TripMind show as taken."
            ),
        )

    # ------------------------------------------------------------------ pricing

    def _lines(self, ctx: _Context, request: ExtrasRequest) -> list[_Line]:
        if ctx.reason is not None:
            raise Conflict(ctx.reason, code="EXTRAS_CLOSED")
        flights = {f.id: f for f in ctx.flights}
        travellers = {t.id for t in ctx.travellers}
        existing = {
            (e.flight_id, e.traveller_id, e.kind): e
            for e in self._session.scalars(
                select(BookingExtra).where(
                    BookingExtra.booking_item_id == ctx.item.id,
                    BookingExtra.status == ExtraStatus.ACTIVE,
                )
            )
        }
        lines: list[_Line] = []
        for s in request.selections:
            flight = flights.get(s.flight_id)
            if flight is None:
                raise ValidationFailed(
                    "That flight is not part of this booking.", code="FLIGHT_NOT_IN_ITEM"
                )
            if s.traveller_id not in travellers:
                raise ValidationFailed(
                    "That traveller is not on this booking.", code="TRAVELLER_NOT_IN_BOOKING"
                )
            if s.kind == "seat":
                seat = self._cabin(flight).seat(s.code)
                if seat is None:
                    raise ValidationFailed(f"Seat {s.code} does not exist.", code="SEAT_UNKNOWN")
                holder = taken_seats(self._session, flight.id).get(s.code)
                if holder is not None and holder != s.traveller_id:
                    raise Conflict(f"Seat {s.code} has just been taken.", code="SEAT_TAKEN")
                label, price = f"Seat {seat.code} ({seat.position})", seat.price
            else:
                options = (
                    self._baggage(ctx, flight)
                    if s.kind == "baggage"
                    else self._extras.meals.options
                )
                option = next((o for o in options if o.code == s.code), None)
                if option is None:
                    raise ValidationFailed(
                        f"{s.code} is not offered on this flight.", code="EXTRA_UNKNOWN"
                    )
                label = option.label
                price = option.price if s.kind == "baggage" else self._meal_price(flight, option)
            lines.append(
                _Line(
                    selection=s,
                    label=label,
                    price=price * 100,
                    existing=existing.get((s.flight_id, s.traveller_id, s.kind)),
                )
            )
        return lines

    def _quote_out(self, lines: list[_Line]) -> ExtrasQuoteOut:
        return ExtrasQuoteOut(
            lines=[
                ExtraLineOut(
                    flight_id=line.selection.flight_id,
                    traveller_id=line.selection.traveller_id,
                    kind=line.selection.kind,
                    code=line.selection.code,
                    label=line.label,
                    price=self._money(line.price),
                    credit=self._money(line.existing.price_minor if line.existing else 0),
                    charge=self._money(line.charge),
                    unchanged=line.unchanged,
                )
                for line in lines
            ],
            total=self._money(sum(line.charge for line in lines)),
        )

    def quote_extras(
        self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID, request: ExtrasRequest
    ) -> ExtrasQuoteOut:
        booking = self._owned(user, booking_id)
        return self._quote_out(self._lines(self._context(booking, item_id), request))

    # ------------------------------------------------------------------ purchase

    def purchase(
        self,
        user: User,
        booking_id: uuid.UUID,
        item_id: uuid.UUID,
        request: ExtrasPurchase,
        key: str,
        meta: RequestMeta,
    ) -> BookingOut:
        booking = self._owned(user, booking_id, lock=True)
        if self._session.scalar(
            select(Payment.id).where(
                Payment.booking_id == booking.id, Payment.idempotency_key == key
            )
        ):
            return self.to_out(booking)  # retried request: already done
        ctx = self._context(booking, item_id)
        lines = [line for line in self._lines(ctx, request) if not line.unchanged]
        total = sum(line.charge for line in lines)
        if total != request.expected_total_minor:
            raise Conflict(
                "The price changed; review the new total.",
                code="EXTRAS_PRICE_CHANGED",
                details={"total_minor": total},
            )
        if total > 0 and request.payment is None:
            raise ValidationFailed(
                "Payment details are needed for the amount due.", code="PAYMENT_REQUIRED"
            )
        if not lines:
            raise Conflict("These are already your choices.", code="NOTHING_TO_CHANGE")

        currency = booking.currency
        try:
            for line in lines:
                if line.existing is not None:
                    line.existing.status = ExtraStatus.REPLACED
            self._session.flush()  # free replaced seats before claiming new ones
            for line in lines:
                self._session.add(
                    BookingExtra(
                        booking_id=booking.id,
                        booking_item_id=ctx.item.id,
                        flight_id=line.selection.flight_id,
                        traveller_id=line.selection.traveller_id,
                        kind=line.selection.kind,
                        code=line.selection.code,
                        label=line.label,
                        price_minor=line.price,
                        paid_minor=line.charge,
                        currency=currency,
                        status=ExtraStatus.ACTIVE,
                    )
                )
            self._session.flush()  # the one-passenger-per-seat index is checked here
        except IntegrityError as exc:
            self._session.rollback()
            raise Conflict(
                "One of these seats has just been taken. Pick another.", code="SEAT_TAKEN"
            ) from exc

        now = self._clock.now()
        result = None
        if total > 0 and request.payment is not None:
            result = payments.charge(
                request.payment.card_number,
                request.payment.expiry_month,
                request.payment.expiry_year,
                now.date(),
            )
            if not result.succeeded:
                self._session.rollback()  # give the seats back
                booking = self._owned(user, booking_id, lock=True)
        self._session.add(
            Payment(
                booking_id=booking.id,
                idempotency_key=key,
                status="failed" if result and not result.succeeded else "succeeded",
                amount_minor=total,
                currency=currency,
                card_brand=result.brand if result else "none",
                card_last4=result.last4 if result else "0000",
                failure_code=result.failure_code if result else None,
                provider_reference=result.reference if result else payments.NO_CHARGE,
            )
        )
        if result is not None and not result.succeeded:
            self._event(
                booking,
                "payment_failed",
                f"Extras not added: card ending {result.last4} was declined.",
            )
            self._session.commit()
            raise PaymentDeclined(
                code=result.failure_code or "PAYMENT_DECLINED",
                details={"booking_id": str(booking.id)},
            )
        booking.total_minor += total
        if total:
            self._loyalty.earn(user.id, booking.id, total, booking.reference, now)
        summary = ", ".join(line.label for line in lines)
        self._event(
            booking,
            "extras",
            f"Added {summary}."
            + (f" Paid {total / 100:,.2f} {currency}." if total else " No charge."),
        )
        self._audit.record(
            action="booking.extras",
            outcome="success",
            meta=meta,
            actor_user_id=user.id,
            details={"booking_id": str(booking.id), "lines": len(lines), "total_minor": total},
        )
        self._session.commit()
        for line in lines:
            ANCILLARIES.labels(kind=line.selection.kind).inc()
        return self.to_out(booking)
