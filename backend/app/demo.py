"""A ready-made demo: `python -m app.cli demo-scenario` fills the demo traveller's account.

It goes through the real services (holds, payments, extras, disruption, alerts, tickets, the
preference model), so every screen shows genuine data. Safe to run twice: it does nothing when the
demo traveller already has bookings. Requires a published dataset and the demo accounts.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import Settings
from app.core.request_context import RequestMeta
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import Booking, BookingItem, User
from app.modules.auth.models import UserRole
from app.modules.bookings.ancillaries import (
    AncillaryService,
    ExtrasPurchase,
    ExtrasRequest,
    Selection,
)
from app.modules.bookings.schemas import (
    ContactIn,
    CreateBookingRequest,
    FlightItemIn,
    HotelItemIn,
    PaymentRequest,
    TravellerIn,
)
from app.modules.bookings.service import BookingService
from app.modules.ml.interactions import record_interaction
from app.modules.recovery.schemas import DisruptionIn
from app.modules.recovery.service import RecoveryService
from app.modules.reviews.service import ReviewIn, ReviewService
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.history import remember_search
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.locations import LocationService
from app.modules.search.preferences import load_preference_rules, train_due
from app.modules.search.pricing import Converter, load_pricing_rules, load_search_rules
from app.modules.support.service import AgentReplyIn, SupportService, TicketIn
from app.modules.watchlist.service import FlightWatch, PriceAlertIn, WatchlistService

META = RequestMeta(ip_address=None, user_agent="demo-scenario")
CARD = PaymentRequest(
    card_number="4242 4242 4242 4242",
    expiry_month=12,
    expiry_year=2030,
    cvc="123",
    cardholder_name="Demo Traveller",
)


class _Demo:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session, self.settings = session, settings
        self.clock = SystemClock()
        self.today = self.clock.now().date()
        self.converter = Converter(load_pricing_rules(settings.config_dir))
        rules = load_search_rules(settings.config_dir)
        self.flights = FlightSearchService(session, self.converter, rules, self.today)
        self.hotels = HotelSearchService(session, self.converter, rules, self.today)
        self.bookings = BookingService(session, settings, self.clock)

    def book(self, user: User, items: list[Any], trip_id: uuid.UUID | None = None) -> Booking:
        request = CreateBookingRequest(
            items=items,
            travellers=[TravellerIn(first_name="Demo", last_name="Traveller")],
            contact=ContactIn(email=user.email),
            trip_id=trip_id,
        )
        booking = self.bookings.create(user, request, uuid.uuid4().hex, META)
        self.bookings.pay(user, booking.id, CARD, uuid.uuid4().hex, META)
        return booking

    def offer(self, origin: str, destination: str, day: date) -> str:
        offers = self.flights.search(
            FlightQuery(
                origin=origin,
                destination=destination,
                departure_date=day,
                max_stops=0,
                sort="cheapest",
            )
        ).outbound.offers
        return next(o.id for o in offers if o.bookable)

    def stay_results(self, city: str, start: date, end: date) -> list[Any]:
        city_id = LocationService(self.session).search(city, "city", 1)[0].value
        result = self.hotels.search(
            HotelQuery(city=city_id, stay=Stay(check_in=start, check_out=end, guests=2, rooms=1))
        )
        return [r for r in result.results if r.bookable]


def run(settings: Settings, *, fresh: bool = False) -> str:
    with get_session_factory()() as session:
        user = session.scalar(select(User).where(User.email == settings.demo_traveler_email))
        if fresh and user is not None:  # nothing is deleted: the old account is set aside
            user.email = f"demo-archived-{uuid.uuid4().hex[:8]}@tripmind.dev"
            session.flush()
            user = User(
                email=settings.demo_traveler_email,
                full_name="Demo Traveller",
                password_hash=hash_password(secrets.token_urlsafe(24)),
                role=UserRole.TRAVELER,
            )
            session.add(user)
            session.commit()
        admin = session.scalar(select(User).where(User.email == settings.demo_admin_email))
        if user is None or admin is None:
            return "Run `python -m app.cli seed` first."
        if session.scalar(select(Booking.id).where(Booking.user_id == user.id).limit(1)):
            return "The demo traveller already has bookings; nothing to do."
        demo = _Demo(session, settings)
        today = demo.today
        now = demo.clock.now()

        # 1. A connected trip ahead: flight + stay in Goa, with a seat, bag and meal.
        start, end = today + timedelta(days=20), today + timedelta(days=24)
        goa = demo.stay_results("Goa", start, end)
        outbound = demo.book(
            user, [FlightItemIn(offer_id=demo.offer("DEL", "GOI", start), adults=1)]
        )
        demo.book(
            user,
            [
                HotelItemIn(
                    room_type_id=goa[0].cheapest_room.room_type_id,
                    check_in=start,
                    check_out=end,
                    rooms=1,
                    guests=2,
                )
            ],
            trip_id=outbound.trip_id,
        )
        extras = AncillaryService(session, settings, demo.clock)
        item = session.scalar(select(BookingItem).where(BookingItem.booking_id == outbound.id))
        assert item is not None  # noqa: S101 - just booked
        catalog = extras.catalog(user, outbound.id, item.id)
        leg, traveller = catalog.flights[0], catalog.travellers[0]
        seat_map = extras.seat_map(user, outbound.id, item.id, leg.flight_id)
        seat = next(
            s for r in seat_map.rows[6:] for s in r.seats if s.position == "window" and s.available
        )
        selections = [
            Selection(flight_id=leg.flight_id, traveller_id=traveller.id, kind=kind, code=code)
            for kind, code in (
                ("seat", seat.code),
                ("baggage", leg.baggage[0].code),
                ("meal", leg.meals[0].code),
            )
        ]
        total = extras.quote_extras(
            user, outbound.id, item.id, ExtrasRequest(selections=selections)
        ).total.amount_minor
        extras.purchase(
            user,
            outbound.id,
            item.id,
            ExtrasPurchase(selections=selections, expected_total_minor=total, payment=CARD),
            uuid.uuid4().hex,
            META,
        )

        # 2. A disrupted trip: the airline cancels a flight, so a recovery case awaits a decision.
        day = today + timedelta(days=9)
        disrupted = demo.book(
            user, [FlightItemIn(offer_id=demo.offer("DEL", "BOM", day), adults=1)]
        )
        disrupted_item = session.scalar(
            select(BookingItem).where(BookingItem.booking_id == disrupted.id)
        )
        assert disrupted_item is not None and disrupted_item.offer_id  # noqa: S101
        RecoveryService(session, settings, demo.clock).disrupt(
            admin,
            DisruptionIn(
                kind="flight_cancelled",
                flight_id=uuid.UUID(disrupted_item.offer_id.split("~")[0]),
                reason="Crew shortage at the departure airport",
            ),
            META,
        )

        # 3. Two finished stays: one reviewed, one still waiting for a review.
        for index, city in enumerate(("Jaipur", "Mumbai")):
            first, last = today + timedelta(days=3), today + timedelta(days=5)
            room = demo.stay_results(city, first, last)[0]
            past = demo.book(
                user,
                [
                    HotelItemIn(
                        room_type_id=room.cheapest_room.room_type_id,
                        check_in=first,
                        check_out=last,
                        rooms=1,
                        guests=2,
                    )
                ],
            )
            stayed = session.scalar(select(BookingItem).where(BookingItem.booking_id == past.id))
            assert stayed is not None  # noqa: S101
            shift = timedelta(days=30 + index * 20)
            stayed.starts_at -= shift
            stayed.ends_at -= shift
            stayed.check_in, stayed.check_out = first - shift, last - shift
            session.commit()
            if index == 0:
                ReviewService(session, settings, demo.clock).write(
                    user,
                    past.id,
                    stayed.id,
                    ReviewIn(
                        rating=9,
                        title="Lovely stay",
                        text="Friendly staff, a spotless room and a great location.",
                        traveller_type="couple",
                    ),
                )

        # 4. Saved stays, an alert, recent searches, and enough activity to personalise results.
        watchlist = WatchlistService(session, settings, demo.clock)
        for result in goa[:3]:
            watchlist.save(user, result.id)
            record_interaction(session, user.id, result.id, "view", now)
        session.commit()
        watchlist.create_alert(
            user,
            PriceAlertIn(
                watch=FlightWatch(
                    origin="DEL", destination="BLR", departure_date=today + timedelta(days=25)
                )
            ),
        )
        remember_search(
            session,
            user_id=user.id,
            vertical="flights",
            params={
                "origin": "DEL",
                "destination": "GOI",
                "departure_date": start,
                "adults": 1,
                "cabin_class": "economy",
            },
            label=f"Delhi to Goa · {start:%d %b} · 1 adult",
            result_count=len(goa),
            at=now,
            keep=30,
        )
        train_due(session, demo.converter, load_preference_rules(settings), now)

        # 5. Support: one answered request and one waiting in the admin queue.
        support = SupportService(session, settings, demo.clock)
        answered = support.create(
            user,
            TicketIn(
                subject="Seat on my Goa flight",
                message="Can I pick a window seat for my flight?",
                booking_id=outbound.id,
            ),
            META,
        )
        support.agent_reply(
            admin,
            answered.id,
            AgentReplyIn(
                body="Yes, open the booking and choose Seats and extras.", status="resolved"
            ),
            META,
        )
        support.create(
            user,
            TicketIn(
                subject="Refund for the cancelled flight",
                message="The airline cancelled my Mumbai flight. When do I get my money back?",
                booking_id=disrupted.id,
            ),
            META,
        )
    return (
        "Demo ready for demo@tripmind.dev: a connected Goa trip with extras, a cancelled flight to "
        "resolve, a past stay to review, saved stays, a price alert and support requests."
    )
