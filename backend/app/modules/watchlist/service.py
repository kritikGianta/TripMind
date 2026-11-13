"""Saved stays and price alerts.

A price alert watches the cheapest bookable price of one flight search or one stay, priced by
the same search services the traveller uses, in the display currency. The worker re-prices
active alerts on a schedule (prices move when a new dataset is published). An alert fires once,
when the price reaches the traveller's target, or, without a target, drops by at least the
configured share below the price when it was set. Alerts expire after the travel date.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, DomainError, NotFound, ValidationFailed
from app.core.metrics import PRICE_ALERTS
from app.modules.auth.models import User
from app.modules.catalog.models import Hotel
from app.modules.notifications.service import NotificationService
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.hotels import HotelSearchService, Stay
from app.modules.search.pricing import (
    Converter,
    MoneyOut,
    load_pricing_rules,
    load_search_rules,
    rules_section,
)
from app.modules.search.schemas import CabinClass
from app.modules.watchlist.models import PriceAlert, SavedHotel


class WatchlistRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_saved_hotels: int = Field(default=200, ge=1)
    max_active_alerts: int = Field(default=20, ge=1)
    alert_min_drop_percent: float = Field(default=5, gt=0, lt=100)
    alert_check_minutes: int = Field(default=30, ge=1)


# ------------------------------------------------------------------------------ schemas


class SavedHotelOut(BaseModel):
    hotel_id: uuid.UUID
    name: str
    city_name: str
    star_rating: float | None
    guest_rating: float | None
    review_count: int | None
    available: bool = Field(description="False when the stay is no longer in the current data")
    saved_at: datetime


class SavedHotelListOut(BaseModel):
    items: list[SavedHotelOut]


class FlightWatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flight"] = "flight"
    origin: str = Field(min_length=2, max_length=64, description="Airport code or city ID")
    destination: str = Field(min_length=2, max_length=64)
    departure_date: date
    adults: int = Field(default=1, ge=1, le=9)
    cabin_class: CabinClass = "economy"


class HotelWatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["hotel"] = "hotel"
    hotel_id: uuid.UUID
    check_in: date
    check_out: date
    guests: int = Field(default=2, ge=1, le=16)
    rooms: int = Field(default=1, ge=1, le=8)


Watch = Annotated[FlightWatch | HotelWatch, Field(discriminator="kind")]


class PriceAlertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watch: Watch
    target_price: int | None = Field(
        default=None, gt=0, description="Display currency, whole units; omit to hear of any drop"
    )


class PriceAlertOut(BaseModel):
    id: uuid.UUID
    kind: str
    label: str
    status: str
    params: dict[str, object]
    link: str
    target: MoneyOut | None
    baseline: MoneyOut
    current: MoneyOut | None
    lowest: MoneyOut
    rule: str
    last_checked_at: datetime | None
    triggered_at: datetime | None
    created_at: datetime


class PriceAlertListOut(BaseModel):
    items: list[PriceAlertOut]


class AlertCheckSummary(BaseModel):
    checked: int = 0
    triggered: int = 0
    expired: int = 0
    failed: int = 0


# ------------------------------------------------------------------------------ service


class WatchlistService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        config = settings.config_dir
        self._rules = WatchlistRules.model_validate(rules_section(config, "watchlist"))
        self._converter = Converter(load_pricing_rules(config))
        self._search_rules = load_search_rules(config)
        self._notifications = NotificationService(session)

    def _today(self) -> date:
        return (self._clock.now() - timedelta(hours=12)).date()

    # ------------------------------------------------------------------ saved stays

    def saved(self, user: User) -> SavedHotelListOut:
        rows = self._session.execute(
            select(SavedHotel, Hotel)
            .join(Hotel, Hotel.id == SavedHotel.hotel_id)
            .where(SavedHotel.user_id == user.id)
            .order_by(SavedHotel.created_at.desc())
        )
        return SavedHotelListOut(
            items=[
                SavedHotelOut(
                    hotel_id=hotel.id,
                    name=hotel.name,
                    city_name=hotel.city_name,
                    star_rating=hotel.star_rating,
                    guest_rating=hotel.guest_rating,
                    review_count=hotel.review_count,
                    available=hotel.is_active,
                    saved_at=saved.created_at,
                )
                for saved, hotel in rows
            ]
        )

    def save(self, user: User, hotel_id: uuid.UUID) -> SavedHotelListOut:
        hotel = self._session.get(Hotel, hotel_id)
        if hotel is None or not hotel.is_active:
            raise NotFound("This stay is not available.", code="HOTEL_NOT_FOUND")
        exists = self._session.scalar(
            select(SavedHotel.id).where(
                SavedHotel.user_id == user.id, SavedHotel.hotel_id == hotel_id
            )
        )
        if exists is None:
            count = self._session.scalar(
                select(func.count()).select_from(SavedHotel).where(SavedHotel.user_id == user.id)
            )
            if (count or 0) >= self._rules.max_saved_hotels:
                raise Conflict(
                    f"You can save up to {self._rules.max_saved_hotels} stays.",
                    code="SAVED_LIMIT",
                )
            try:
                self._session.add(SavedHotel(user_id=user.id, hotel_id=hotel_id))
                self._session.commit()
            except IntegrityError:  # saved twice at once: the first one stands
                self._session.rollback()
        return self.saved(user)

    def unsave(self, user: User, hotel_id: uuid.UUID) -> SavedHotelListOut:
        row = self._session.scalar(
            select(SavedHotel).where(SavedHotel.user_id == user.id, SavedHotel.hotel_id == hotel_id)
        )
        if row is not None:
            self._session.delete(row)
            self._session.commit()
        return self.saved(user)

    # ------------------------------------------------------------------ pricing

    def _price(self, kind: str, params: dict[str, object]) -> tuple[int | None, str]:
        """Cheapest bookable price in display minor units (None when nothing is bookable)."""
        today = self._today()
        if kind == "flight":
            watch = FlightWatch.model_validate(params)
            flights = FlightSearchService(self._session, self._converter, self._search_rules, today)
            result = flights.search(
                FlightQuery(
                    origin=watch.origin,
                    destination=watch.destination,
                    departure_date=watch.departure_date,
                    adults=watch.adults,
                    cabin_class=watch.cabin_class,
                    sort="cheapest",
                )
            ).outbound
            prices = [
                o.price.display_total.amount_minor
                for o in result.offers
                if o.bookable and o.price.display_total
            ]
            route = (
                f"{result.origin.city_name} to {result.destination.city_name}"
                if result.origin and result.destination
                else f"{watch.origin} to {watch.destination}"
            )
            label = (
                f"{route} · {watch.departure_date:%d %b} · {watch.adults} adult"
                f"{'s' if watch.adults > 1 else ''}"
            )
            return (min(prices) if prices else None), label
        stay_watch = HotelWatch.model_validate(params)
        hotels = HotelSearchService(self._session, self._converter, self._search_rules, today)
        detail = hotels.detail(
            stay_watch.hotel_id,
            Stay(
                check_in=stay_watch.check_in,
                check_out=stay_watch.check_out,
                guests=stay_watch.guests,
                rooms=stay_watch.rooms,
            ),
        )
        prices = [
            r.price.display_total.amount_minor
            for r in detail.rooms
            if r.fits_party and r.price and r.price.display_total
        ]
        label = f"{detail.name} · {stay_watch.check_in:%d %b} to {stay_watch.check_out:%d %b}"
        return (min(prices) if prices else None), label

    @staticmethod
    def _link(alert: PriceAlert) -> str:
        p = alert.params
        if alert.kind == "flight":
            query = {
                "trip": "oneway",
                "from": p["origin"],
                "to": p["destination"],
                "depart": p["departure_date"],
                "adults": p.get("adults", 1),
                "cabin": p.get("cabin_class", "economy"),
            }
            return f"/flights?{urlencode(query)}"
        query = {
            "checkIn": p["check_in"],
            "checkOut": p["check_out"],
            "guests": p.get("guests", 2),
            "rooms": p.get("rooms", 1),
        }
        return f"/stays/{p['hotel_id']}?{urlencode(query)}"

    def _threshold(self, alert: PriceAlert) -> int:
        if alert.target_minor is not None:
            return alert.target_minor
        return int(alert.baseline_minor * (1 - self._rules.alert_min_drop_percent / 100))

    def _out(self, alert: PriceAlert) -> PriceAlertOut:
        def money(v: int) -> MoneyOut:
            return MoneyOut(amount_minor=v, currency=alert.currency)

        rule = (
            f"Tells you once the price is {alert.target_minor / 100:,.0f} {alert.currency} or less."
            if alert.target_minor is not None
            else f"Tells you once the price drops {self._rules.alert_min_drop_percent:g}% or more "
            "below the price when you set it."
        )
        return PriceAlertOut(
            id=alert.id,
            kind=alert.kind,
            label=alert.label,
            status=alert.status,
            params=alert.params,
            link=self._link(alert),
            target=money(alert.target_minor) if alert.target_minor is not None else None,
            baseline=money(alert.baseline_minor),
            current=money(alert.last_price_minor) if alert.last_price_minor is not None else None,
            lowest=money(alert.lowest_price_minor),
            rule=rule,
            last_checked_at=alert.last_checked_at,
            triggered_at=alert.triggered_at,
            created_at=alert.created_at,
        )

    # ------------------------------------------------------------------ alerts API

    def alerts(self, user: User) -> PriceAlertListOut:
        rows = self._session.scalars(
            select(PriceAlert)
            .where(PriceAlert.user_id == user.id, PriceAlert.status != "cancelled")
            .order_by(PriceAlert.created_at.desc())
        )
        return PriceAlertListOut(items=[self._out(a) for a in rows])

    def create_alert(self, user: User, request: PriceAlertIn) -> PriceAlertOut:
        active = self._session.scalar(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user.id, PriceAlert.status == "active")
        )
        if (active or 0) >= self._rules.max_active_alerts:
            raise Conflict(
                f"You can have up to {self._rules.max_active_alerts} active alerts.",
                code="ALERT_LIMIT",
            )
        watch = request.watch
        params = watch.model_dump(mode="json")
        price, label = self._price(watch.kind, params)
        if price is None:
            raise Conflict(
                "Nothing bookable to watch for these dates.", code="ALERT_NOTHING_TO_WATCH"
            )
        target = request.target_price * 100 if request.target_price is not None else None
        if target is not None and target >= price:
            raise ValidationFailed(
                f"The price is already {price / 100:,.0f} {self._converter.display_currency}; "
                "set a lower target.",
                code="ALERT_TARGET_MET",
            )
        travel = watch.departure_date if isinstance(watch, FlightWatch) else watch.check_in
        now = self._clock.now()
        alert = PriceAlert(
            user_id=user.id,
            kind=watch.kind,
            params=params,
            label=label,
            travel_date=travel,
            currency=self._converter.display_currency,
            target_minor=target,
            baseline_minor=price,
            last_price_minor=price,
            lowest_price_minor=price,
            status="active",
            last_checked_at=now,
            created_at=now,
        )
        self._session.add(alert)
        self._session.commit()
        PRICE_ALERTS.labels(event="created").inc()
        return self._out(alert)

    def cancel_alert(self, user: User, alert_id: uuid.UUID) -> None:
        alert = self._session.get(PriceAlert, alert_id)
        if alert is None or alert.user_id != user.id or alert.status == "cancelled":
            raise NotFound("Price alert not found.", code="ALERT_NOT_FOUND")
        alert.status = "cancelled"
        self._session.commit()

    # ------------------------------------------------------------------ worker

    def check_alerts(self, limit: int = 500) -> AlertCheckSummary:
        """Re-price active alerts, oldest check first. Each alert commits on its own, so one
        failure never stops the rest."""
        summary = AlertCheckSummary()
        today = self._today()
        alerts = list(
            self._session.scalars(
                select(PriceAlert)
                .where(PriceAlert.status == "active")
                .order_by(PriceAlert.last_checked_at.asc().nulls_first())
                .limit(limit)
            )
        )
        for alert in alerts:
            now = self._clock.now()
            if alert.travel_date < today:
                alert.status = "expired"
                summary.expired += 1
                self._session.commit()
                PRICE_ALERTS.labels(event="expired").inc()
                continue
            try:
                price, _ = self._price(alert.kind, alert.params)
            except DomainError as exc:  # e.g. the stay left the data after a new import
                alert.last_error = exc.message[:200]
                alert.last_checked_at = now
                summary.failed += 1
                self._session.commit()
                continue
            summary.checked += 1
            alert.last_checked_at, alert.last_error = now, None
            alert.last_price_minor = price
            if price is not None:
                alert.lowest_price_minor = min(alert.lowest_price_minor, price)
            if price is not None and price <= self._threshold(alert):
                alert.status, alert.triggered_at = "triggered", now
                summary.triggered += 1
                was = alert.baseline_minor
                self._notifications.notify(
                    user_id=alert.user_id,
                    kind="price_alert",
                    severity="success",
                    title=f"Price drop: {alert.label.split(' · ')[0]}",
                    body=f"{alert.label}: now {price / 100:,.0f} {alert.currency}, "
                    f"down from {was / 100:,.0f} {alert.currency} when you set the alert.",
                    link=self._link(alert),
                    now=now,
                )
                PRICE_ALERTS.labels(event="triggered").inc()
            self._session.commit()
        return summary


def alert_check_interval_seconds(settings: Settings) -> float:
    rules = WatchlistRules.model_validate(rules_section(settings.config_dir, "watchlist"))
    return rules.alert_check_minutes * 60.0
