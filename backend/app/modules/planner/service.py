"""Connected-trip planner.

Builds complete trips (outbound flight + return flight + stay), checks that the pieces fit
together, ranks them with a transparent weighted score, and explains each rank with its own
numbers. No AI is involved: every sentence in an explanation is computed from the bundle.

Pipeline: candidate flights each way (search) -> hotels for the nights between landing and
leaving -> every combination -> feasibility and confidence checks -> scores -> rank and
diversify (at most N options per hotel) -> stored as a plan snapshot.
"""

from __future__ import annotations

import hashlib
import math
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.core.metrics import PLANS
from app.modules.auth.models import User
from app.modules.catalog.models import Airport, City, Hotel
from app.modules.inventory.service import InventoryService
from app.modules.planner.models import TripPlan
from app.modules.planner.schemas import (
    BundleOut,
    CheckOut,
    ConfidenceOut,
    OptionState,
    PlanListOut,
    PlanOut,
    PlanRequest,
    PlanSummaryOut,
    ScoresOut,
    StayPlanOut,
)
from app.modules.search.flights import FlightQuery, FlightSearchService
from app.modules.search.hotels import HotelQuery, HotelSearchService, Stay
from app.modules.search.pricing import (
    Converter,
    MoneyOut,
    load_pricing_rules,
    load_search_rules,
)
from app.modules.search.schemas import FlightOfferOut, HotelResultOut

AIRPORT_BUFFER = timedelta(hours=2)  # be at the airport two hours before departure


class Weights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: float = Field(ge=0, le=1)
    time: float = Field(ge=0, le=1)
    stay: float = Field(ge=0, le=1)
    convenience: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _sum_to_one(self) -> Weights:
        if abs(self.price + self.time + self.stay + self.convenience - 1) > 0.001:
            raise ValueError("ranking weights must add up to 1")
        return self


class Candidates(BaseModel):
    flights_per_direction: int = 8
    hotels: int = 10
    max_options: int = 20
    max_options_per_hotel: int = 3


class ConfidenceRules(BaseModel):
    wait_before_check_in_warn_hours: float = 4
    wait_before_check_in_risk_hours: float = 10
    gap_after_check_out_warn_hours: float = 6
    transfer_warn_km: float = 30
    transfer_speed_kmh: float = 25
    transfer_buffer_minutes: int = 15
    low_availability_seats: int = 9


class RankingConfig(BaseModel):
    profiles: dict[str, Weights]
    candidates: Candidates = Candidates()
    confidence: ConfidenceRules = ConfidenceRules()


@lru_cache(maxsize=4)
def _ranking(path: str, mtime: float) -> RankingConfig:
    return RankingConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def load_ranking(config_dir: Path) -> RankingConfig:
    path = config_dir / "ranking.yaml"
    return _ranking(str(path), path.stat().st_mtime)


def _km(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return round(6371.0 * 2 * math.asin(math.sqrt(h)), 1)


def _hours(delta: timedelta) -> float:
    return delta.total_seconds() / 3600


def _money(minor: int, currency: str) -> str:
    return f"{currency} {minor / 100:,.0f}"


@dataclass
class _Draft:
    outbound: FlightOfferOut
    inbound: FlightOfferOut
    hotel: HotelResultOut
    stay: Stay
    total: int
    complete: bool
    travel_minutes: int
    stops: int
    wait_hours: float
    leave_by: datetime
    gap_hours: float
    transfer_in_km: float | None
    transfer_out_km: float | None
    min_seats: int
    synthetic: bool
    scores: ScoresOut = field(
        default_factory=lambda: ScoresOut(price=0, time=0, stay=0, convenience=0, total=0)
    )


class PlannerService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        config = settings.config_dir
        self._ranking = load_ranking(config)
        self._converter = Converter(load_pricing_rules(config))
        today = (clock.now() - timedelta(hours=12)).date()
        rules = load_search_rules(config)
        self._flights = FlightSearchService(session, self._converter, rules, today)
        self._hotels = HotelSearchService(session, self._converter, rules, today)
        self._currency = self._converter.display_currency

    # ------------------------------------------------------------------ public

    def generate(self, user: User, request: PlanRequest) -> PlanOut:
        if request.return_date <= request.depart_date:
            raise ValidationFailed(
                "A connected trip needs at least one night away.", code="INVALID_STAY"
            )
        city = self._session.get(City, request.destination_city_id)
        if city is None or not city.is_active:
            raise NotFound("Unknown destination.", code="LOCATION_NOT_FOUND")
        weights = self._ranking.profiles.get(request.priority)
        if weights is None:
            raise ValidationFailed("Unknown priority.")

        notices: list[str] = []
        drafts = self._drafts(request, city, notices)
        if request.max_budget is not None:
            within = [d for d in drafts if d.total <= request.max_budget * 100]
            if len(within) < len(drafts):
                notices.append(f"{len(drafts) - len(within)} options were above your budget.")
            drafts = within
        self._score(drafts, weights)
        ranked = self._rank(drafts)
        options = [self._bundle(d, i + 1, ranked, weights) for i, d in enumerate(ranked)]
        if not options and not notices:
            notices.append("No complete trips were found for these dates in the dataset.")

        plan = TripPlan(
            user_id=user.id,
            title=f"{city.name}, {request.depart_date:%d %b} to {request.return_date:%d %b}",
            request=request.model_dump(mode="json"),
            options=[o.model_dump(mode="json") for o in options],
            option_states={},
            notices=notices,
            generated_at=self._clock.now(),
        )
        self._session.add(plan)
        self._session.commit()
        PLANS.labels(priority=request.priority).inc()
        return self._out(plan)

    def get(self, user: User, plan_id: uuid.UUID) -> PlanOut:
        return self._out(self._owned(user, plan_id))

    def plans(self, user: User) -> PlanListOut:
        plans = self._session.scalars(
            select(TripPlan)
            .where(TripPlan.user_id == user.id)
            .order_by(TripPlan.generated_at.desc())
            .limit(50)
        )
        items = []
        for plan in plans:
            req = PlanRequest.model_validate(plan.request)
            items.append(
                PlanSummaryOut(
                    id=plan.id,
                    title=plan.title,
                    depart_date=req.depart_date,
                    return_date=req.return_date,
                    adults=req.adults,
                    priority=req.priority,
                    options=len(plan.options),
                    saved=sum(1 for s in plan.option_states.values() if s == "saved"),
                    generated_at=plan.generated_at,
                )
            )
        return PlanListOut(items=items)

    def set_state(
        self, user: User, plan_id: uuid.UUID, option_id: str, state: OptionState
    ) -> PlanOut:
        plan = self._owned(user, plan_id)
        if not any(o["id"] == option_id for o in plan.options):
            raise NotFound("Option not found.", code="OPTION_NOT_FOUND")
        states = dict(plan.option_states)
        if state == "none":
            states.pop(option_id, None)
        else:
            states[option_id] = state
        plan.option_states = states  # reassign so the JSON change is persisted
        self._session.commit()
        return self._out(plan)

    # ------------------------------------------------------------------ building bundles

    def _owned(self, user: User, plan_id: uuid.UUID) -> TripPlan:
        plan = self._session.get(TripPlan, plan_id)
        if plan is None or plan.user_id != user.id:
            raise NotFound("Plan not found.", code="PLAN_NOT_FOUND")
        return plan

    def _out(self, plan: TripPlan) -> PlanOut:
        request = PlanRequest.model_validate(plan.request)
        options = [
            BundleOut.model_validate({**o, "state": plan.option_states.get(o["id"], "none")})
            for o in plan.options
        ]
        return PlanOut(
            id=plan.id,
            title=plan.title,
            request=request,
            weights=self._ranking.profiles[request.priority].model_dump(),
            generated_at=plan.generated_at,
            options=options,
            notices=list(plan.notices),
        )

    def _drafts(self, request: PlanRequest, city: City, notices: list[str]) -> list[_Draft]:
        k = self._ranking.candidates.flights_per_direction
        flights = self._flights.search(
            FlightQuery(
                origin=request.origin,
                destination=str(city.id),
                departure_date=request.depart_date,
                return_date=request.return_date,
                adults=request.adults,
                max_stops=1,
                sort="best",
            )
        )
        notices.extend(flights.notices)
        outbound = [o for o in flights.outbound.offers if o.bookable][:k]
        inbound = [o for o in (flights.inbound.offers if flights.inbound else []) if o.bookable][:k]
        if not outbound or not inbound:
            notices.append("No bookable flights were found in one of the directions.")
            return []

        rooms = max(1, math.ceil(request.adults / 2))
        stars = tuple(range(request.min_stars, 6)) if request.min_stars else ()
        hotel_cache: dict[tuple[date, date], list[HotelResultOut]] = {}
        coords = self._coordinates(outbound, inbound)
        seats = InventoryService(self._session).availability(
            [leg.flight_id for o in outbound + inbound for leg in o.legs]
        )
        synthetic = (
            self._session.scalar(
                select(Hotel.id)
                .where(Hotel.city_id == city.id, Hotel.origin == "synthetic")
                .limit(1)
            )
            is not None
        )
        zone = city.timezone

        drafts: list[_Draft] = []
        for out in outbound:
            arrival = out.legs[-1].arrival_local
            check_in_day = arrival.date()
            for back in inbound:
                departure = back.legs[0].departure_local
                check_out_day = departure.date()
                if (
                    check_out_day <= check_in_day
                    or back.legs[0].departure_at <= out.legs[-1].arrival_at
                ):
                    continue
                key = (check_in_day, check_out_day)
                if key not in hotel_cache:
                    result = self._hotels.search(
                        HotelQuery(
                            city=str(city.id),
                            stay=Stay(
                                check_in=check_in_day,
                                check_out=check_out_day,
                                guests=request.adults,
                                rooms=rooms,
                            ),
                            stars=stars,
                            sort="recommended",
                        )
                    )
                    hotel_cache[key] = [h for h in result.results if h.bookable][
                        : self._ranking.candidates.hotels
                    ]
                for hotel in hotel_cache[key]:
                    drafts.append(
                        self._draft(
                            out,
                            back,
                            hotel,
                            Stay(
                                check_in=check_in_day,
                                check_out=check_out_day,
                                guests=request.adults,
                                rooms=rooms,
                            ),
                            coords,
                            seats,
                            synthetic,
                            zone,
                        )
                    )
        return drafts

    def _coordinates(
        self, outbound: list[FlightOfferOut], inbound: list[FlightOfferOut]
    ) -> dict[str, tuple[float, float] | None]:
        codes = {o.legs[-1].destination.code for o in outbound} | {
            o.legs[0].origin.code for o in inbound
        }
        rows = self._session.execute(
            select(Airport.code, Airport.latitude, Airport.longitude).where(Airport.code.in_(codes))
        ).tuples()
        return {
            code: (lat, lon) if lat is not None and lon is not None else None
            for code, lat, lon in rows
        }

    def _draft(
        self,
        out: FlightOfferOut,
        back: FlightOfferOut,
        hotel: HotelResultOut,
        stay: Stay,
        coords: dict[str, tuple[float, float] | None],
        seats: dict[uuid.UUID, int],
        synthetic: bool,
        zone: str,
    ) -> _Draft:
        rules = self._ranking.confidence
        hotel_point = (
            (hotel.latitude, hotel.longitude)
            if hotel.latitude is not None and hotel.longitude is not None
            else None
        )
        transfer_in = _km(coords.get(out.legs[-1].destination.code), hotel_point)
        transfer_out = _km(coords.get(back.legs[0].origin.code), hotel_point)

        def transfer(km: float | None) -> timedelta:
            minutes = (km or 0) / rules.transfer_speed_kmh * 60 + rules.transfer_buffer_minutes
            return timedelta(minutes=minutes)

        check_in_at = datetime.combine(stay.check_in, time(14, 0))
        at_hotel = out.legs[-1].arrival_local + transfer(transfer_in)
        wait = max(0.0, _hours(check_in_at - at_hotel))
        check_out_at = datetime.combine(stay.check_out, time(11, 0))
        leave_by = back.legs[0].departure_local - AIRPORT_BUFFER - transfer(transfer_out)
        gap = max(0.0, _hours(leave_by - check_out_at))

        room = hotel.cheapest_room
        prices = [
            out.price.display_total,
            back.price.display_total,
            room.price.display_total if room.price else None,
        ]
        total = sum(p.amount_minor for p in prices if p is not None)
        complete = all(p is not None for p in prices)
        flight_ids = [leg.flight_id for o in (out, back) for leg in o.legs]
        return _Draft(
            outbound=out,
            inbound=back,
            hotel=hotel,
            stay=stay,
            total=total,
            complete=complete and out.price.complete and back.price.complete,
            travel_minutes=out.duration_minutes + back.duration_minutes,
            stops=out.stops + back.stops,
            wait_hours=round(wait, 1),
            leave_by=leave_by,
            gap_hours=round(gap, 1),
            transfer_in_km=transfer_in,
            transfer_out_km=transfer_out,
            min_seats=min(seats.get(i, 0) for i in flight_ids),
            synthetic=synthetic,
        )

    # ------------------------------------------------------------------ scoring and ranking

    def _score(self, drafts: list[_Draft], w: Weights) -> None:
        if not drafts:
            return
        cheapest = min(d.total for d in drafts) or 1
        quickest = min(d.travel_minutes for d in drafts) or 1
        for d in drafts:
            price = cheapest / d.total if d.total else 0.0
            time_score = quickest / d.travel_minutes
            stay = 0.7 * (d.hotel.guest_rating or 0) / 10 + 0.3 * (d.hotel.star_rating or 0) / 5
            penalty = (
                0.15 * d.stops
                + d.wait_hours / 24
                + d.gap_hours / 24
                + ((d.transfer_in_km or 0) + (d.transfer_out_km or 0)) / 200
            )
            convenience = max(0.0, 1 - penalty)
            total = (
                w.price * price + w.time * time_score + w.stay * stay + w.convenience * convenience
            )
            d.scores = ScoresOut(
                price=round(price, 3),
                time=round(time_score, 3),
                stay=round(stay, 3),
                convenience=round(convenience, 3),
                total=round(total, 4),
            )

    def _rank(self, drafts: list[_Draft]) -> list[_Draft]:
        ordered = sorted(drafts, key=lambda d: -d.scores.total)
        per_hotel: dict[uuid.UUID, int] = {}
        ranked: list[_Draft] = []
        for d in ordered:
            if per_hotel.get(d.hotel.id, 0) >= self._ranking.candidates.max_options_per_hotel:
                continue
            per_hotel[d.hotel.id] = per_hotel.get(d.hotel.id, 0) + 1
            ranked.append(d)
            if len(ranked) >= self._ranking.candidates.max_options:
                break
        return ranked

    def _explain(self, d: _Draft, rank: int, ranked: list[_Draft], weights: Weights) -> list[str]:
        lines: list[str] = []
        totals = [x.total for x in ranked]
        median = statistics.median(totals)
        if d.total == min(totals):
            lines.append(f"Lowest total of the {len(ranked)} options shown.")
        elif d.total < median:
            lines.append(
                f"{_money(int(median - d.total), self._currency)} below the median option."
            )
        else:
            lines.append(
                f"{_money(int(d.total - median), self._currency)} above the median "
                "option, traded for the strengths below."
            )
        if d.stops == 0:
            lines.append("Direct flights both ways.")
        else:
            lines.append(
                f"{d.stops} stop{'s' if d.stops > 1 else ''} in total; "
                f"{d.travel_minutes // 60}h {d.travel_minutes % 60}m flying."
            )
        rating = f"rated {d.hotel.guest_rating:.1f}/10" if d.hotel.guest_rating else "unrated"
        stars = f"{int(d.hotel.star_rating)}-star" if d.hotel.star_rating else "unclassified"
        lines.append(
            f"{d.hotel.name}: {stars}, {rating}"
            + (
                f", {d.hotel.distance_km} km from the centre."
                if d.hotel.distance_km is not None
                else "."
            )
        )
        contributions = {
            name: getattr(weights, name) * getattr(d.scores, name)
            for name in ("price", "time", "stay", "convenience")
        }
        top = max(contributions, key=lambda k: contributions[k])
        share = contributions[top] / d.scores.total if d.scores.total else 0
        label = {
            "price": "price",
            "time": "journey time",
            "stay": "the stay",
            "convenience": "convenience",
        }[top]
        lines.append(f"Ranked #{rank} mostly on {label} ({share:.0%} of its score).")
        return lines

    def _confidence(self, d: _Draft, adults: int) -> ConfidenceOut:
        rules = self._ranking.confidence
        checks: list[CheckOut] = []
        for name, offer in (("Outbound connection", d.outbound), ("Return connection", d.inbound)):
            for layover in offer.layovers:
                status = "ok" if layover.minutes >= 90 else "warn"
                text = f"{layover.minutes} min to change planes in {layover.airport.city_name}."
                if offer.self_transfer:
                    status = "warn"
                    text += " Different airlines: bags may need re-checking."
                checks.append(CheckOut(name=name, status=status, message=text))
        arrival = d.outbound.legs[-1].arrival_local
        if d.wait_hours >= rules.wait_before_check_in_risk_hours:
            checks.append(
                CheckOut(
                    name="Arrival and check-in",
                    status="risk",
                    message=(
                        f"Lands {arrival:%H:%M}, about {d.wait_hours:.0f} h before the 14:00 "
                        "check-in. Consider booking the night before or asking for early check-in."
                    ),
                )
            )
        elif d.wait_hours >= rules.wait_before_check_in_warn_hours:
            checks.append(
                CheckOut(
                    name="Arrival and check-in",
                    status="warn",
                    message=(
                        f"Lands {arrival:%H:%M}, about {d.wait_hours:.0f} h to wait "
                        "for check-in at 14:00."
                    ),
                )
            )
        else:
            checks.append(
                CheckOut(
                    name="Arrival and check-in",
                    status="ok",
                    message=(f"Lands {arrival:%H:%M}; check-in from 14:00 fits."),
                )
            )
        if d.leave_by.time() < time(11, 0) and d.leave_by.date() == d.stay.check_out:
            checks.append(
                CheckOut(
                    name="Check-out and return",
                    status="info",
                    message=(f"Leave the hotel by {d.leave_by:%H:%M}, before the 11:00 check-out."),
                )
            )
        elif d.gap_hours >= rules.gap_after_check_out_warn_hours:
            checks.append(
                CheckOut(
                    name="Check-out and return",
                    status="warn",
                    message=(
                        f"About {d.gap_hours:.0f} h between the 11:00 check-out and "
                        "leaving for the airport. Ask about late check-out or luggage storage."
                    ),
                )
            )
        else:
            checks.append(
                CheckOut(
                    name="Check-out and return",
                    status="ok",
                    message=(f"Leave the hotel by {d.leave_by:%H:%M} for the return flight."),
                )
            )
        if d.transfer_in_km is None:
            checks.append(
                CheckOut(
                    name="Airport transfer",
                    status="info",
                    message="Hotel location not in the data; transfer time unknown.",
                )
            )
        else:
            minutes = int(
                d.transfer_in_km / rules.transfer_speed_kmh * 60 + rules.transfer_buffer_minutes
            )
            status = "warn" if d.transfer_in_km > rules.transfer_warn_km else "ok"
            checks.append(
                CheckOut(
                    name="Airport transfer",
                    status=status,
                    message=(
                        f"{d.transfer_in_km} km from the airport, roughly {minutes} min "
                        "(estimate from straight-line distance)."
                    ),
                )
            )
        if d.min_seats < adults:
            checks.append(
                CheckOut(
                    name="Seats",
                    status="risk",
                    message="Not enough seats left on one of the flights.",
                )
            )
        elif d.min_seats <= rules.low_availability_seats:
            checks.append(
                CheckOut(
                    name="Seats",
                    status="warn",
                    message=f"Only {d.min_seats} seats left on one flight.",
                )
            )
        else:
            checks.append(
                CheckOut(name="Seats", status="ok", message="Seats available on every flight.")
            )
        if d.hotel.cheapest_room.refundable:
            checks.append(
                CheckOut(
                    name="Cancellation cover",
                    status="ok",
                    message=("The room is refundable, so a flight change will not cost the stay."),
                )
            )
        else:
            checks.append(
                CheckOut(
                    name="Cancellation cover",
                    status="warn",
                    message=(
                        "Non-refundable room: if the flights change, the stay is not refunded."
                    ),
                )
            )
        checks.append(
            CheckOut(
                name="Price",
                status="info" if d.complete else "warn",
                message="Total includes every item."
                if d.complete
                else "Taxes and fees are not in the supplied data; the real total is higher.",
            )
        )
        if d.synthetic:
            checks.append(
                CheckOut(
                    name="Data",
                    status="info",
                    message="Demo data: schedules, prices and hotels are synthetic.",
                )
            )

        risks = sum(c.status == "risk" for c in checks)
        warns = sum(c.status == "warn" for c in checks)
        level = "low" if risks else "medium" if warns >= 2 else "high"
        summary = {
            "high": "Everything fits together.",
            "medium": f"{warns} things to be aware of.",
            "low": f"{risks} serious issue{'s' if risks > 1 else ''} to resolve.",
        }[level]
        return ConfidenceOut(level=level, summary=summary, checks=checks)

    def _bundle(self, d: _Draft, rank: int, ranked: list[_Draft], weights: Weights) -> BundleOut:
        option_id = hashlib.sha1(  # noqa: S324 - identifier, not security
            f"{d.outbound.id}|{d.inbound.id}|{d.hotel.cheapest_room.room_type_id}".encode()
        ).hexdigest()[:16]
        return BundleOut(
            id=option_id,
            rank=rank,
            outbound=d.outbound,
            inbound=d.inbound,
            hotel=d.hotel,
            stay=StayPlanOut(
                check_in=d.stay.check_in,
                check_out=d.stay.check_out,
                nights=d.stay.nights,
                rooms=d.stay.rooms,
                guests=d.stay.guests,
            ),
            total=MoneyOut(amount_minor=d.total, currency=self._currency),
            complete=d.complete,
            scores=d.scores,
            explanation=self._explain(d, rank, ranked, weights),
            confidence=self._confidence(d, d.stay.guests),
        )
