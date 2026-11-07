"""Disruption and recovery.

1. An operator records a disruption (flight cancelled or delayed, room out of service).
2. Every affected booking item is found. Unpaid holds are released; paid items get a recovery
   case with concrete options (alternative flights or rooms, a refund, or keeping a delayed
   flight), and the traveller is notified.
3. The traveller picks an option. TripMind re-checks price and availability, replaces only the
   affected item (the old item becomes REPLACED and points at the new one), releases and
   reserves inventory, and records everything on the booking timeline. Other items in the trip
   are never touched; the case lists how they are affected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.request_context import RequestMeta
from app.modules.audit.service import AuditService
from app.modules.auth.models import User
from app.modules.bookings.models import (
    Booking,
    BookingEvent,
    BookingItem,
    BookingStatus,
    ItemStatus,
    Refund,
    Trip,
)
from app.modules.catalog.models import Airport, Flight, Hotel, RoomType
from app.modules.inventory.models import FlightInventory
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import NotificationService
from app.modules.operations.models import Disruption, DisruptionKind
from app.modules.recovery.models import RecoveryCase
from app.modules.recovery.schemas import (
    BookedFlightListOut,
    BookedFlightOut,
    DisruptionIn,
    DisruptionListOut,
    DisruptionOut,
    RecoveryCaseListOut,
    RecoveryCaseOut,
    RecoveryOptionOut,
)
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.pricing import (
    Converter,
    MoneyOut,
    load_pricing_rules,
    load_search_rules,
    rules_section,
)
from app.modules.search.schemas import FlightOfferOut

OPEN_ITEMS = (ItemStatus.HELD, ItemStatus.CONFIRMED)


class RecoveryRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    significant_delay_minutes: int = Field(default=180, ge=15)
    search_days: int = Field(default=2, ge=1, le=7)
    max_alternatives: int = Field(default=4, ge=1, le=10)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


class RecoveryService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        config = settings.config_dir
        self._rules = RecoveryRules.model_validate(rules_section(config, "recovery"))
        self._converter = Converter(load_pricing_rules(config))
        today = (clock.now() - timedelta(hours=12)).date()
        search = load_search_rules(config)
        self._flights = FlightSearchService(session, self._converter, search, today)
        self._hotels = HotelSearchService(session, self._converter, search, today)
        self._inventory = InventoryService(session)
        self._notify = NotificationService(session)
        self._audit = AuditService(session)
        self._currency = self._converter.display_currency

    # ------------------------------------------------------------------ operator side

    def booked_flights(self) -> BookedFlightListOut:
        """Upcoming flights with seats sold, so an operator (or a demo) can disrupt one."""
        now = self._clock.now()
        rows = (
            self._session.execute(
                select(Flight, FlightInventory.reserved)
                .join(FlightInventory, FlightInventory.flight_id == Flight.id)
                .where(FlightInventory.reserved > 0, Flight.departure_at > now)
                .order_by(Flight.departure_at)
                .limit(50)
            )
            .tuples()
            .all()
        )
        codes = dict(self._session.execute(select(Airport.id, Airport.code)).tuples().all())
        disrupted = dict(
            self._session.execute(
                select(Disruption.flight_id, Disruption.kind).where(
                    Disruption.flight_id.in_([f.id for f, _ in rows])
                )
            )
            .tuples()
            .all()
        )
        return BookedFlightListOut(
            items=[
                BookedFlightOut(
                    flight_id=f.id,
                    flight_number=f.flight_number,
                    route=" → ".join(
                        str(codes.get(a)) for a in (f.origin_airport_id, f.destination_airport_id)
                    ),
                    departure_local=f.departure_local,
                    cabin_class=f.cabin_class,
                    booked_seats=reserved,
                    disruption=disrupted.get(f.id),
                )
                for f, reserved in rows
            ]
        )

    def disruptions(self) -> DisruptionListOut:
        rows = self._session.scalars(
            select(Disruption).order_by(Disruption.created_at.desc()).limit(50)
        )
        return DisruptionListOut(items=[self._disruption_out(d) for d in rows])

    def _disruption_out(self, d: Disruption) -> DisruptionOut:
        if d.flight_id:
            flight = self._session.get(Flight, d.flight_id)
            target = (
                f"{flight.flight_number} on {flight.departure_local:%d %b %H:%M}"
                if flight
                else "flight"
            )
        else:
            room = self._session.get(RoomType, d.room_type_id) if d.room_type_id else None
            hotel = self._session.get(Hotel, room.hotel_id) if room else None
            target = (
                f"{room.name if room else 'room'} at {hotel.name if hotel else 'hotel'}, "
                f"{d.starts_on} to {d.ends_on}"
            )
        return DisruptionOut(
            id=d.id,
            kind=d.kind,
            target=target,
            reason=d.reason,
            delay_minutes=d.delay_minutes,
            affected_items=d.affected_items,
            created_at=d.created_at,
        )

    def disrupt(self, operator: User, request: DisruptionIn, meta: RequestMeta) -> DisruptionOut:
        now = self._clock.now()
        if request.flight_id is not None:
            flight = self._session.get(Flight, request.flight_id)
            if flight is None:
                raise NotFound("Flight not found.", code="FLIGHT_NOT_FOUND")
            if self._session.scalar(
                select(Disruption.id).where(
                    Disruption.flight_id == flight.id,
                    Disruption.kind == DisruptionKind.FLIGHT_CANCELLED,
                )
            ):
                raise Conflict("This flight is already cancelled.", code="ALREADY_DISRUPTED")
        elif (
            request.room_type_id is not None
            and self._session.get(RoomType, request.room_type_id) is None
        ):
            raise NotFound("Room type not found.", code="ROOM_NOT_FOUND")

        disruption = Disruption(
            kind=request.kind,
            flight_id=request.flight_id,
            room_type_id=request.room_type_id,
            starts_on=request.starts_on,
            ends_on=request.ends_on,
            delay_minutes=request.delay_minutes,
            reason=request.reason,
            created_by_user_id=operator.id,
        )
        self._session.add(disruption)
        self._session.flush()

        affected = 0
        for item in self._affected_items(request):
            booking = self._session.get(Booking, item.booking_id)
            if booking is None:
                continue
            affected += 1
            if booking.status != BookingStatus.CONFIRMED:
                self._release_unpaid(booking, request, now)
            else:
                self._open_case(disruption, booking, item, request, now)
        disruption.affected_items = affected
        self._audit.record(
            action="operations.disruption",
            outcome="success",
            meta=meta,
            actor_user_id=operator.id,
            details={
                "disruption_id": str(disruption.id),
                "kind": request.kind,
                "affected_items": affected,
            },
        )
        self._session.commit()
        return self._disruption_out(disruption)

    def _affected_items(self, request: DisruptionIn) -> list[BookingItem]:
        if request.flight_id is not None:
            # Offer IDs are "leg~leg"; a leg appears verbatim in every offer that uses it.
            return list(
                self._session.scalars(
                    select(BookingItem).where(
                        BookingItem.kind == "flight",
                        BookingItem.status.in_([s.value for s in OPEN_ITEMS]),
                        BookingItem.offer_id.contains(str(request.flight_id)),
                    )
                )
            )
        return list(
            self._session.scalars(
                select(BookingItem).where(
                    BookingItem.kind == "hotel",
                    BookingItem.status.in_([s.value for s in OPEN_ITEMS]),
                    BookingItem.room_type_id == request.room_type_id,
                    BookingItem.check_in < request.ends_on,
                    BookingItem.check_out > request.starts_on,
                )
            )
        )

    def _event(self, booking: Booking, type_: str, message: str, now: datetime) -> None:
        self._session.add(
            BookingEvent(booking_id=booking.id, type=type_, message=message, occurred_at=now)
        )

    def _what(self, request: DisruptionIn, item: BookingItem) -> str:
        if request.kind == "flight_cancelled":
            return f"The airline cancelled a flight in {item.title}"
        if request.kind == "flight_delayed":
            return f"A flight in {item.title} is delayed by {_hm(request.delay_minutes or 0)}"
        return f"Your room at {item.title} is no longer available for some nights"

    def _release_unpaid(self, booking: Booking, request: DisruptionIn, now: datetime) -> None:
        if request.kind == "flight_delayed":
            return  # an unpaid hold on a delayed flight stays valid; the price page shows it
        items = list(
            self._session.scalars(select(BookingItem).where(BookingItem.booking_id == booking.id))
        )
        self._inventory.release([i.id for i in items], now)
        for item in items:
            if item.status in OPEN_ITEMS:
                item.status = ItemStatus.RELEASED
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        self._event(
            booking,
            "disruption",
            "Released before payment because part of it is no "
            "longer available. Nothing was charged.",
            now,
        )
        self._notify.notify(
            user_id=booking.user_id,
            kind="disruption",
            severity="warning",
            title=f"Hold {booking.reference} released",
            body="Part of your unpaid selection is no longer available, so the "
            "hold was released. Nothing was charged.",
            link=f"/bookings/{booking.id}",
            now=now,
        )

    def _open_case(
        self,
        disruption: Disruption,
        booking: Booking,
        item: BookingItem,
        request: DisruptionIn,
        now: datetime,
    ) -> None:
        what = self._what(request, item)
        significant = (
            request.kind != "flight_delayed"
            or (request.delay_minutes or 0) >= self._rules.significant_delay_minutes
        )
        options = self._options(item, request, significant)
        impact = self._impact(booking, item, options)
        self._session.add(
            RecoveryCase(
                disruption_id=disruption.id,
                booking_id=booking.id,
                booking_item_id=item.id,
                user_id=booking.user_id,
                status="open",
                summary=f"{what}. {request.reason}.",
                impact=impact,
                options=[o.model_dump(mode="json") for o in options],
            )
        )
        self._event(booking, "disruption", f"{what}. {request.reason}.", now)
        self._notify.notify(
            user_id=booking.user_id,
            kind="disruption",
            severity="critical",
            title=f"Action needed on booking {booking.reference}",
            body=f"{what}. We've found {len([o for o in options if o.type != 'keep'])} ways to "
            "sort it out; choose one in TripMind.",
            link=f"/bookings/{booking.id}",
            now=now,
        )

    # ------------------------------------------------------------------ options

    def _paid(self, item: BookingItem) -> int:
        return int(item.snapshot.get("display_minor", 0))

    def _options(
        self, item: BookingItem, request: DisruptionIn, significant: bool
    ) -> list[RecoveryOptionOut]:
        free = MoneyOut(amount_minor=0, currency=self._currency)
        options: list[RecoveryOptionOut] = []
        if request.kind == "flight_delayed":
            options.append(
                RecoveryOptionOut(
                    id="keep",
                    type="keep",
                    title="Keep my delayed flight",
                    description=f"Travel as booked, {_hm(request.delay_minutes or 0)} later.",
                    extra_cost=free,
                )
            )
        if significant:
            options += (
                self._flight_alternatives(item, request)
                if item.kind == "flight"
                else self._room_alternatives(item, request)
            )
            options.append(
                RecoveryOptionOut(
                    id="refund",
                    type="refund",
                    title="Cancel this part for a full refund",
                    description="Everything else in your trip stays booked.",
                    extra_cost=free,
                    refund=MoneyOut(amount_minor=self._paid(item), currency=self._currency),
                )
            )
        return options

    def _flight_alternatives(
        self, item: BookingItem, request: DisruptionIn
    ) -> list[RecoveryOptionOut]:
        original = FlightOfferOut.model_validate(item.snapshot.get("details", {}))
        first, last = original.legs[0], original.legs[-1]
        found: list[FlightOfferOut] = []
        for offset in range(self._rules.search_days):
            day = first.departure_local.date() + timedelta(days=offset)
            if day < self._clock.now().date():
                continue
            results = self._flights.search(
                FlightQuery(
                    origin=first.origin.code,
                    destination=last.destination.code,
                    departure_date=day,
                    adults=item.quantity,
                    cabin_class=first.cabin_class,  # type: ignore[arg-type]
                    max_stops=1,
                    sort="earliest",
                )
            )
            for offer in results.outbound.offers:
                legs = {str(leg.flight_id) for leg in offer.legs}
                if (
                    offer.bookable
                    and offer.id != original.id
                    and str(request.flight_id) not in legs
                    and offer.legs[0].departure_at >= self._clock.now()
                ):
                    found.append(offer)
            if len(found) >= self._rules.max_alternatives:
                break
        # Rebook like an airline would: soonest arrival first, each stop counting as two hours
        # later, so a direct flight beats a slightly earlier connection.
        found.sort(key=lambda o: o.legs[-1].arrival_at + timedelta(hours=2 * o.stops))
        options = []
        for offer in found[: self._rules.max_alternatives]:
            later = int((offer.legs[-1].arrival_at - last.arrival_at).total_seconds() // 60)
            notes = []
            if later > 0:
                notes.append(f"Arrives {_hm(later)} later than your original flight.")
            elif later < 0:
                notes.append(f"Arrives {_hm(-later)} earlier than your original flight.")
            if offer.stops:
                notes.append(
                    f"{offer.stops} stop via "
                    f"{', '.join(lay.airport.city_name for lay in offer.layovers)}."
                )
            new_total = offer.price.display_total.amount_minor if offer.price.display_total else 0
            if new_total > self._paid(item):
                notes.append("Costs more than your original fare; the difference is waived.")
            options.append(
                RecoveryOptionOut(
                    id=f"flight:{offer.id}",
                    type="rebook_flight",
                    title=(
                        f"{' + '.join(leg.flight_number for leg in offer.legs)} · "
                        f"{offer.legs[0].departure_local:%a %d %b %H:%M} → "
                        f"{offer.legs[-1].arrival_local:%H:%M}"
                    ),
                    description="Rebook at no extra cost.",
                    offer=offer,
                    extra_cost=MoneyOut(amount_minor=0, currency=self._currency),
                    notes=notes,
                )
            )
        return options

    def _room_alternatives(
        self, item: BookingItem, request: DisruptionIn
    ) -> list[RecoveryOptionOut]:
        hotel = self._session.get(Hotel, item.hotel_id) if item.hotel_id else None
        if hotel is None or item.check_in is None or item.check_out is None:
            return []
        guests = int(item.snapshot.get("details", {}).get("guests", 2))
        stay = Stay(
            check_in=item.check_in, check_out=item.check_out, guests=guests, rooms=item.quantity
        )
        options: list[RecoveryOptionOut] = []
        detail = self._hotels.detail(hotel.id, stay)
        for room in detail.rooms:
            if room.fits_party and room.nightly_rate and room.room_type_id != item.room_type_id:
                options.append(
                    self._room_option(
                        hotel.id,
                        hotel.name,
                        room.model_dump(mode="json"),
                        "Same hotel, different room, no extra cost.",
                    )
                )
                break
        results = self._hotels.search(
            HotelQuery(city=str(hotel.city_id), stay=stay, sort="recommended")
        )
        min_stars = max(0, int(hotel.star_rating or 0) - 1)
        for result in results.results:
            if len(options) >= self._rules.max_alternatives:
                break
            if (
                result.id == hotel.id
                or not result.bookable
                or int(result.star_rating or 0) < (min_stars)
            ):
                continue
            options.append(
                self._room_option(
                    result.id,
                    result.name,
                    result.cheapest_room.model_dump(mode="json"),
                    f"{result.distance_km} km from the centre, rated "
                    f"{result.guest_rating or '-'}; no extra cost.",
                )
            )
        return options

    def _room_option(
        self, hotel_id: uuid.UUID, hotel_name: str, room: dict[str, Any], description: str
    ) -> RecoveryOptionOut:
        return RecoveryOptionOut(
            id=f"room:{room['room_type_id']}",
            type="rebook_room",
            title=f"{hotel_name} · {room['name']}",
            description=description,
            room={**room, "hotel_id": str(hotel_id), "hotel_name": hotel_name},
            extra_cost=MoneyOut(amount_minor=0, currency=self._currency),
        )

    def _impact(
        self, booking: Booking, item: BookingItem, options: list[RecoveryOptionOut]
    ) -> list[str]:
        trip_items = list(
            self._session.scalars(
                select(BookingItem)
                .join(Booking, Booking.id == BookingItem.booking_id)
                .where(
                    Booking.trip_id == booking.trip_id,
                    BookingItem.status.in_([s.value for s in OPEN_ITEMS]),
                    BookingItem.id != item.id,
                )
            )
        )
        lines = []
        for other in trip_items:
            lines.append(f"{other.title} is not affected and stays booked.")
            if item.kind == "flight" and other.kind == "hotel" and other.check_in:
                late = [
                    o
                    for o in options
                    if o.offer and o.offer.legs[-1].arrival_local.date() > other.check_in
                ]
                if late:
                    lines.append(
                        f"Some alternatives land after your check-in date at "
                        f"{other.title}; tell the hotel you'll arrive late."
                    )
        return lines or ["Nothing else in this trip is affected."]

    # ------------------------------------------------------------------ traveller side

    def _case_out(self, case: RecoveryCase) -> RecoveryCaseOut:
        booking = self._session.get(Booking, case.booking_id)
        item = self._session.get(BookingItem, case.booking_item_id)
        disruption = self._session.get(Disruption, case.disruption_id)
        if booking is None or item is None or disruption is None:
            raise NotFound("Recovery case not found.", code="CASE_NOT_FOUND")
        return RecoveryCaseOut(
            id=case.id,
            status=case.status,
            resolution=case.resolution,
            booking_id=booking.id,
            booking_reference=booking.reference,
            trip_id=booking.trip_id,
            item_id=item.id,
            item_title=item.title,
            disruption_kind=disruption.kind,
            disruption_reason=disruption.reason,
            summary=case.summary,
            impact=case.impact,
            options=[RecoveryOptionOut.model_validate(o) for o in case.options],
            chosen_option_id=case.chosen_option_id,
            created_at=case.created_at,
            resolved_at=case.resolved_at,
        )

    def cases(self, user: User, booking_id: uuid.UUID | None = None) -> RecoveryCaseListOut:
        query = select(RecoveryCase).where(RecoveryCase.user_id == user.id)
        if booking_id is not None:
            query = query.where(RecoveryCase.booking_id == booking_id)
        rows = self._session.scalars(
            query.order_by(RecoveryCase.status.desc(), RecoveryCase.created_at.desc())
        )
        return RecoveryCaseListOut(items=[self._case_out(c) for c in rows])

    def open_case_count(self, user: User) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(RecoveryCase)
                .where(RecoveryCase.user_id == user.id, RecoveryCase.status == "open")
            )
            or 0
        )

    def case(self, user: User, case_id: uuid.UUID) -> RecoveryCaseOut:
        case = self._session.get(RecoveryCase, case_id)
        if case is None or case.user_id != user.id:
            raise NotFound("Recovery case not found.", code="CASE_NOT_FOUND")
        return self._case_out(case)

    def accept(
        self, user: User, case_id: uuid.UUID, option_id: str, meta: RequestMeta
    ) -> RecoveryCaseOut:
        case = self._session.scalar(
            select(RecoveryCase).where(RecoveryCase.id == case_id).with_for_update()
        )
        if case is None or case.user_id != user.id:
            raise NotFound("Recovery case not found.", code="CASE_NOT_FOUND")
        if case.status != "open":
            raise Conflict("This has already been resolved.", code="CASE_RESOLVED")
        option = next(
            (RecoveryOptionOut.model_validate(o) for o in case.options if o["id"] == option_id),
            None,
        )
        if option is None:
            raise NotFound("That option is not part of this case.", code="OPTION_NOT_FOUND")
        booking = self._session.get(Booking, case.booking_id)
        item = self._session.get(BookingItem, case.booking_item_id)
        if booking is None or item is None or item.status != ItemStatus.CONFIRMED:
            raise Conflict("This booking item can no longer be changed.", code="CASE_RESOLVED")

        now = self._clock.now()
        if option.type == "keep":
            message, resolution = f"Kept {item.title} with the new times.", "kept"
        elif option.type == "refund":
            amount = self._paid(item)
            item.status = ItemStatus.CANCELLED
            self._inventory.release([item.id], now)
            self._session.add(
                Refund(
                    booking_id=booking.id,
                    booking_item_id=item.id,
                    amount_minor=amount,
                    currency=booking.currency,
                    reason="Disrupted by the supplier: full refund.",
                )
            )
            message = (
                f"Cancelled {item.title}; full refund of {amount / 100:,.2f} {booking.currency}."
            )
            resolution = "refunded"
            self._session.flush()  # the count below must see this item's new status
            if not self._session.scalar(
                select(func.count())
                .select_from(BookingItem)
                .where(
                    BookingItem.booking_id == booking.id,
                    BookingItem.status.in_([s.value for s in OPEN_ITEMS]),
                )
            ):
                booking.status = BookingStatus.CANCELLED
                booking.cancelled_at = now
        else:
            new_item = (
                self._rebook_flight(item, option)
                if option.type == "rebook_flight"
                else self._rebook_room(item, option)
            )
            item.status = ItemStatus.REPLACED
            item.replaced_by_item_id = new_item.id
            self._inventory.release([item.id], now)
            message = f"Rebooked: {new_item.title}, {new_item.snapshot.get('subtitle', '')}."
            resolution = "rebooked"
            self._update_trip_dates(booking.trip_id)

        case.status, case.resolution = "resolved", resolution
        case.chosen_option_id, case.resolved_at = option.id, now
        self._event(booking, "recovered", message, now)
        self._notify.notify(
            user_id=user.id,
            kind="recovery",
            severity="success",
            title=f"Booking {booking.reference} updated",
            body=message,
            link=f"/bookings/{booking.id}",
            now=now,
        )
        self._audit.record(
            action="recovery.accept",
            outcome="success",
            meta=meta,
            actor_user_id=user.id,
            details={"case_id": str(case.id), "option": option.id},
        )
        self._session.commit()
        return self._case_out(case)

    def _new_item(self, old: BookingItem, **fields: Any) -> BookingItem:
        item = BookingItem(
            booking_id=old.booking_id,
            status=ItemStatus.CONFIRMED,
            position=old.position,
            refundable=old.refundable,
            **fields,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def _rebook_flight(self, old: BookingItem, option: RecoveryOptionOut) -> BookingItem:
        if option.offer is None:
            raise ValidationFailed("Invalid option.", code="OPTION_NOT_FOUND")
        ids = [leg.flight_id for leg in option.offer.legs]
        offer = self._flights.price_offer(ids, old.quantity)  # re-checks the flights exist
        first, last = offer.legs[0], offer.legs[-1]
        total = offer.price.total or offer.price.display_total
        new = self._new_item(
            old,
            kind="flight",
            offer_id=offer.id,
            quantity=old.quantity,
            starts_at=first.departure_at,
            ends_at=last.arrival_at,
            title=old.title,
            price_minor=total.amount_minor if total else old.price_minor,
            currency=total.currency if total else old.currency,
            snapshot={
                "subtitle": (
                    f"{' + '.join(leg.flight_number for leg in offer.legs)} · "
                    f"{first.departure_local:%a %d %b, %H:%M} · rebooked"
                ),
                "policy": old.snapshot.get("policy", ""),
                "display_minor": self._paid(old),  # what the traveller paid; difference waived
                "details": offer.model_dump(mode="json"),
            },
        )
        flights = {f.id: f for f in self._session.scalars(select(Flight).where(Flight.id.in_(ids)))}
        for flight_id in ids:
            self._inventory.reserve_seats(new.id, flights[flight_id], old.quantity)
        return new

    def _rebook_room(self, old: BookingItem, option: RecoveryOptionOut) -> BookingItem:
        room_data = option.room or {}
        room_type_id = uuid.UUID(str(room_data.get("room_type_id")))
        guests = int(old.snapshot.get("details", {}).get("guests", 2))
        if old.check_in is None or old.check_out is None:
            raise ValidationFailed("Invalid stay.", code="OPTION_NOT_FOUND")
        stay = Stay(
            check_in=old.check_in, check_out=old.check_out, guests=guests, rooms=old.quantity
        )
        hotel, city, room = self._hotels.price_room(room_type_id, stay)
        room_type = self._session.get(RoomType, room_type_id)
        if room_type is None or room.price is None or room.price.total is None:
            raise Conflict("That room is no longer available.", code="SOLD_OUT")
        new = self._new_item(
            old,
            kind="hotel",
            room_type_id=room_type_id,
            hotel_id=hotel.id,
            check_in=old.check_in,
            check_out=old.check_out,
            quantity=old.quantity,
            starts_at=old.starts_at,
            ends_at=old.ends_at,
            title=hotel.name,
            price_minor=room.price.total.amount_minor,
            currency=room.price.total.currency,
            snapshot={
                "subtitle": f"{room.name} · {stay.nights} nights · rebooked",
                "policy": old.snapshot.get("policy", ""),
                "display_minor": self._paid(old),
                "details": {
                    **old.snapshot.get("details", {}),
                    "hotel_id": str(hotel.id),
                    "city": city.name,
                    "room": room.model_dump(mode="json"),
                },
            },
        )
        new.refundable = room.refundable
        self._inventory.reserve_rooms(new.id, room_type, old.check_in, old.check_out, old.quantity)
        return new

    def _update_trip_dates(self, trip_id: uuid.UUID) -> None:
        trip = self._session.get(Trip, trip_id)
        if trip is None:
            return
        self._session.flush()
        spans = self._session.execute(
            select(func.min(BookingItem.starts_at), func.max(BookingItem.ends_at))
            .join(Booking, Booking.id == BookingItem.booking_id)
            .where(
                Booking.trip_id == trip_id,
                or_(
                    BookingItem.status == ItemStatus.CONFIRMED,
                    BookingItem.status == ItemStatus.HELD,
                ),
            )
        ).one()
        if spans[0] and spans[1]:
            trip.starts_on = _aware(spans[0]).date()
            trip.ends_on = _aware(spans[1]).date()
