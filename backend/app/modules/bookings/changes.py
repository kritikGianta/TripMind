"""Booking changes: move a flight to another date or time, or a stay to other dates, without
cancelling the booking.

Flow: quote (what changes, the price difference, the fee, what is due or refunded) -> change.
The change re-prices from the catalog and refuses if the amount differs from what the traveller
accepted (CHANGE_PRICE_CHANGED), takes a simulated payment when money is due, reserves the new
seats or room-nights, releases the old ones, and replaces only that item (old item REPLACED,
pointing at the new one). Everything happens in one transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.metrics import BOOKING_CHANGES
from app.core.request_context import RequestMeta
from app.modules.auth.models import User
from app.modules.bookings import payments
from app.modules.bookings.models import (
    Booking,
    BookingItem,
    BookingStatus,
    ItemStatus,
    Payment,
    Refund,
)
from app.modules.bookings.schemas import BookingOut, FlightItemIn, HotelItemIn, PaymentRequest
from app.modules.bookings.service import (
    BookingService,
    PaymentDeclined,
    PricedItem,
    _aware,
)
from app.modules.inventory.service import SoldOut
from app.modules.search.pricing import MoneyOut


class ChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flight_offer_id: str | None = Field(default=None, min_length=36, max_length=80)
    check_in: date | None = None
    check_out: date | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> ChangeRequest:
        flight = self.flight_offer_id is not None
        stay = self.check_in is not None or self.check_out is not None
        if flight == stay:
            raise ValueError("give either flight_offer_id, or check_in and check_out")
        if stay and not (self.check_in and self.check_out):
            raise ValueError("give both check_in and check_out")
        return self


class ChangeConfirm(ChangeRequest):
    expected_amount_due_minor: int = Field(ge=0, description="From the quote the traveller saw")
    payment: PaymentRequest | None = Field(default=None, description="Needed when money is due")


class ChangeQuoteOut(BaseModel):
    item_id: uuid.UUID
    allowed: bool
    reason: str | None
    current_title: str
    current_subtitle: str
    new_title: str | None
    new_subtitle: str | None
    paid: MoneyOut
    new_price: MoneyOut | None
    price_difference: MoneyOut | None
    change_fee: MoneyOut
    amount_due: MoneyOut
    refund_due: MoneyOut
    policy: str


@dataclass
class _Plan:
    item: BookingItem
    new: PricedItem | None
    fee: int
    due: int
    refund: int
    reason: str | None


class BookingChangeService(BookingService):
    def _plan(self, booking: Booking, item: BookingItem, request: ChangeRequest) -> _Plan:
        now = self._clock.now()

        def refuse(reason: str) -> _Plan:
            return _Plan(item=item, new=None, fee=0, due=0, refund=0, reason=reason)

        if booking.status != BookingStatus.CONFIRMED or item.status != ItemStatus.CONFIRMED:
            return refuse("Only confirmed bookings can be changed.")
        if now >= _aware(item.starts_at):
            return refuse("This has already started.")
        paid = int(item.snapshot.get("display_minor", 0))
        rules = self._rules
        if item.kind == "flight":
            if request.flight_offer_id is None:
                return refuse("Choose a new flight for this change.")
            new = self._price_flight(
                FlightItemIn(offer_id=request.flight_offer_id, adults=item.quantity)
            )
            old_legs = item.snapshot.get("details", {}).get("legs", [])
            new_legs = new.details.get("legs", [])
            same_route = bool(old_legs and new_legs) and (
                old_legs[0]["origin"]["code"] == new_legs[0]["origin"]["code"]
                and old_legs[-1]["destination"]["code"] == new_legs[-1]["destination"]["code"]
            )
            if not same_route:
                return refuse("A change keeps the same route; book a new flight to go elsewhere.")
            if new.offer_id == item.offer_id:
                return refuse("That is the flight you already have.")
            confirmed = _aware(booking.confirmed_at or booking.created_at)
            free = now - confirmed <= timedelta(hours=rules.flight_free_change_hours)
            fee = 0 if free else rules.flight_change_fee * 100 * item.quantity
            difference = new.display_minor - paid
            refund = -difference if difference < 0 and free else 0
            return _Plan(
                item=item,
                new=new,
                fee=fee,
                due=max(difference, 0) + fee,
                refund=refund,
                reason=None,
            )

        if request.check_in is None or request.check_out is None or item.room_type_id is None:
            return refuse("Choose new dates for this stay.")
        if not item.refundable:
            return refuse("Non-refundable rooms cannot change dates.")
        deadline = _aware(item.starts_at) - timedelta(
            hours=rules.hotel_free_cancellation_hours_before_check_in
        )
        if now > deadline:
            return refuse("It is too close to check-in to change dates.")
        if (request.check_in, request.check_out) == (item.check_in, item.check_out):
            return refuse("Those are the dates you already have.")
        guests = int(item.snapshot.get("details", {}).get("guests", 2))
        # The current room-nights are still held by this booking, so price the new stay on the
        # same room type; availability is checked for real when the change is made.
        new = self._price_hotel(
            HotelItemIn(
                room_type_id=item.room_type_id,
                check_in=request.check_in,
                check_out=request.check_out,
                rooms=item.quantity,
                guests=guests,
            )
        )
        difference = new.display_minor - paid
        return _Plan(
            item=item,
            new=new,
            fee=0,
            due=max(difference, 0),
            refund=max(-difference, 0),
            reason=None,
        )

    def _item(self, booking: Booking, item_id: uuid.UUID) -> BookingItem:
        item = self._session.get(BookingItem, item_id)
        if item is None or item.booking_id != booking.id:
            raise NotFound("Booking item not found.", code="ITEM_NOT_FOUND")
        return item

    def _quote_out(self, booking: Booking, plan: _Plan) -> ChangeQuoteOut:
        currency = booking.currency

        def money(amount: int) -> MoneyOut:
            return MoneyOut(amount_minor=amount, currency=currency)

        paid = int(plan.item.snapshot.get("display_minor", 0))
        policy = (
            f"Free within {self._rules.flight_free_change_hours} hours of booking, then "
            f"{self._rules.flight_change_fee:,} {currency} per traveller plus any fare difference."
            if plan.item.kind == "flight"
            else "Refundable rooms can change dates until the cancellation deadline."
        )
        return ChangeQuoteOut(
            item_id=plan.item.id,
            allowed=plan.reason is None,
            reason=plan.reason,
            current_title=plan.item.title,
            current_subtitle=str(plan.item.snapshot.get("subtitle", "")),
            new_title=plan.new.title if plan.new else None,
            new_subtitle=plan.new.subtitle if plan.new else None,
            paid=money(paid),
            new_price=money(plan.new.display_minor) if plan.new else None,
            price_difference=money(plan.new.display_minor - paid) if plan.new else None,
            change_fee=money(plan.fee),
            amount_due=money(plan.due),
            refund_due=money(plan.refund),
            policy=policy,
        )

    def change_quote(
        self, user: User, booking_id: uuid.UUID, item_id: uuid.UUID, request: ChangeRequest
    ) -> ChangeQuoteOut:
        booking = self._owned(user, booking_id)
        return self._quote_out(booking, self._plan(booking, self._item(booking, item_id), request))

    def change(
        self,
        user: User,
        booking_id: uuid.UUID,
        item_id: uuid.UUID,
        request: ChangeConfirm,
        key: str,
        meta: RequestMeta,
    ) -> BookingOut:
        booking = self._owned(user, booking_id, lock=True)
        if self._session.scalar(
            select(Payment.id).where(
                Payment.booking_id == booking.id, Payment.idempotency_key == key
            )
        ):
            return self.to_out(booking)  # retried request: the change already happened
        item = self._item(booking, item_id)
        plan = self._plan(booking, item, request)
        if plan.reason is not None or plan.new is None:
            raise Conflict(plan.reason or "This change is not possible.", code="CHANGE_NOT_ALLOWED")
        if plan.due != request.expected_amount_due_minor:
            raise Conflict(
                "The price changed; review the new quote.",
                code="CHANGE_PRICE_CHANGED",
                details={"amount_due_minor": plan.due},
            )
        if plan.due > 0 and request.payment is None:
            raise ValidationFailed(
                "Payment details are needed for the amount due.", code="PAYMENT_REQUIRED"
            )
        now = self._clock.now()
        new = plan.new
        replacement = BookingItem(
            booking_id=booking.id,
            kind=item.kind,
            status=ItemStatus.CONFIRMED,
            position=item.position,
            offer_id=new.offer_id,
            room_type_id=new.room.id if new.room else None,
            hotel_id=new.hotel_id,
            check_in=new.check_in,
            check_out=new.check_out,
            quantity=new.quantity,
            starts_at=new.starts_at,
            ends_at=new.ends_at,
            title=new.title,
            price_minor=new.price.amount_minor,
            currency=new.price.currency,
            refundable=new.refundable,
            snapshot={
                "subtitle": new.subtitle,
                "policy": new.policy,
                "display_minor": new.display_minor,
                "details": new.details,
                "changed_from": str(item.id),
            },
        )
        # Secure the new seats or nights before taking any money. Release first: a stay moved
        # by a day overlaps its own old nights.
        try:
            self._session.add(replacement)
            self._inventory.release([item.id], now)
            self._session.flush()
            for flight in new.flights:
                self._inventory.reserve_seats(replacement.id, flight, new.quantity)
            if new.room is not None and new.check_in and new.check_out:
                self._inventory.reserve_rooms(
                    replacement.id, new.room, new.check_in, new.check_out, new.quantity
                )
        except SoldOut:
            self._session.rollback()
            BOOKING_CHANGES.labels(kind=item.kind, outcome="sold_out").inc()
            raise
        result = None
        if plan.due > 0 and request.payment is not None:
            result = payments.charge(
                request.payment.card_number,
                request.payment.expiry_month,
                request.payment.expiry_year,
                now.date(),
            )
            if not result.succeeded:
                # Undo the inventory moves; keep only the declined attempt on record.
                self._session.rollback()
                booking = self._owned(user, booking_id, lock=True)
        self._session.add(
            Payment(
                booking_id=booking.id,
                idempotency_key=key,
                status="failed" if result and not result.succeeded else "succeeded",
                amount_minor=plan.due,
                currency=booking.currency,
                card_brand=result.brand if result else "none",
                card_last4=result.last4 if result else "0000",
                failure_code=result.failure_code if result else None,
                # A change with nothing to pay still records the key, so a retry is recognised.
                provider_reference=result.reference if result else "no_charge",
            )
        )
        if result is not None and not result.succeeded:
            self._event(
                booking,
                "payment_failed",
                f"Change not made: card ending {result.last4} was declined.",
            )
            self._session.commit()
            BOOKING_CHANGES.labels(kind=item.kind, outcome="declined").inc()
            raise PaymentDeclined(
                code=result.failure_code or "PAYMENT_DECLINED",
                details={"booking_id": str(booking.id)},
            )
        item.status = ItemStatus.REPLACED
        item.replaced_by_item_id = replacement.id
        if plan.refund:
            self._session.add(
                Refund(
                    booking_id=booking.id,
                    booking_item_id=item.id,
                    amount_minor=plan.refund,
                    currency=booking.currency,
                    reason="Change to a cheaper option.",
                )
            )
            self._loyalty.reverse(user.id, booking.id, plan.refund, booking.reference, now)
        if plan.due:
            booking.total_minor += plan.due
            self._loyalty.earn(user.id, booking.id, plan.due, booking.reference, now)
        message = (
            f"Changed {item.title} to {new.subtitle}."
            + (f" Paid {plan.due / 100:,.2f} {booking.currency}." if plan.due else "")
            + (f" Refund {plan.refund / 100:,.2f} {booking.currency}." if plan.refund else "")
        )
        self._event(booking, "changed", message)
        self._notifications.notify(
            user_id=user.id,
            kind="booking_changed",
            severity="success",
            title=f"Booking {booking.reference} changed",
            body=message,
            link=f"/bookings/{booking.id}",
            now=now,
        )
        self._audit.record(
            action="booking.change",
            outcome="success",
            meta=meta,
            actor_user_id=user.id,
            details={
                "booking_id": str(booking.id),
                "item_id": str(item.id),
                "due_minor": plan.due,
                "refund_minor": plan.refund,
            },
        )
        self._session.commit()
        BOOKING_CHANGES.labels(kind=item.kind, outcome="changed").inc()
        return self.to_out(booking)
