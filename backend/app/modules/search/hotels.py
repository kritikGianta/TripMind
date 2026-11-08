"""Hotel search and hotel details.

A hotel is shown when at least one room type fits the party (occupancy per room and number of
rooms). Its headline price is the cheapest fitting room type that matches the filters, priced for
the requested nights and rooms with a ledger. Hotels whose fitting rooms have no rate in the data
are shown as browse-only, never with an invented price.
"""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.modules.catalog.models import City, Hotel, HotelAmenity, RoomType
from app.modules.ml.features import HotelRow, hotel_ranker_rows
from app.modules.ml.preferences import UserPreference, probability, reasons
from app.modules.ml.registry import LoadedModel
from app.modules.ml.similar import HotelProfile, similar_hotels
from app.modules.operations.queries import unavailable_rooms
from app.modules.search.geo import distance_km as _distance_km
from app.modules.search.locations import LocationService
from app.modules.search.pricing import Converter, LedgerLine, MoneyOut, SearchRules
from app.modules.search.schemas import (
    CityOut,
    FacetOption,
    HotelDetailOut,
    HotelFacets,
    HotelResultOut,
    HotelSearchOut,
    HotelSort,
    PriceRange,
    RoomOfferOut,
    SimilarHotelOut,
    StayOut,
)

BREAKFAST_BOARDS = {"breakfast", "half_board", "full_board", "all_inclusive"}
AMENITY_LABELS = {
    "wifi": "Wi-Fi",
    "air_conditioning": "Air conditioning",
    "restaurant": "Restaurant",
    "pool": "Pool",
    "gym": "Gym",
    "spa": "Spa",
    "bar": "Bar",
    "room_service": "Room service",
    "parking": "Parking",
    "airport_shuttle": "Airport shuttle",
    "wheelchair_accessible": "Wheelchair accessible",
    "pet_friendly": "Pet friendly",
    "family_rooms": "Family rooms",
    "beach_access": "Beach access",
    "ev_charging": "EV charging",
    "business_centre": "Business centre",
    "laundry": "Laundry",
    "breakfast": "Breakfast",
}


@dataclass(frozen=True)
class Stay:
    check_in: date
    check_out: date
    guests: int = 2
    rooms: int = 1

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def guests_per_room(self) -> int:
        return math.ceil(self.guests / self.rooms)


@dataclass(frozen=True)
class HotelQuery:
    city: str
    stay: Stay
    stars: tuple[int, ...] = ()
    min_rating: float | None = None
    amenities: tuple[str, ...] = ()
    max_price: int | None = None  # per night, display currency, major units
    free_cancellation: bool = False
    breakfast: bool = False
    sort: HotelSort = "recommended"


class HotelSearchService:
    def __init__(
        self,
        session: Session,
        converter: Converter,
        rules: SearchRules,
        today: date,
        ranker: LoadedModel | None = None,
        preference: UserPreference | None = None,
        preference_blend: float = 0.3,
    ) -> None:
        self._session = session
        self._converter = converter
        self._rules = rules
        self._today = today
        self._ranker = ranker
        self._preference = preference
        self._blend = preference_blend
        self._out_of_service: dict[tuple[date, date], set[uuid.UUID]] = {}

    def validate(self, stay: Stay) -> None:
        if stay.check_in < self._today:
            raise ValidationFailed("The check-in date is in the past.", code="DATE_IN_PAST")
        if stay.nights < 1:
            raise ValidationFailed("Check-out must be after check-in.", code="INVALID_STAY")
        if stay.nights > self._rules.max_hotel_nights:
            raise ValidationFailed(
                f"Stays are limited to {self._rules.max_hotel_nights} nights.",
                code="STAY_TOO_LONG",
            )
        if stay.rooms > stay.guests:
            raise ValidationFailed("Each room needs at least one guest.", code="INVALID_STAY")

    # ------------------------------------------------------------------ rooms and prices

    def _room(self, room: RoomType, stay: Stay | None) -> RoomOfferOut:
        rate = (
            MoneyOut(amount_minor=room.nightly_rate_minor, currency=room.currency)
            if room.nightly_rate_minor is not None
            else None
        )
        fits = stay is None or (
            room.max_occupancy >= stay.guests_per_room
            and room.total_rooms >= stay.rooms
            and room.id not in self._unavailable(stay)
        )
        price = None
        if stay is not None:
            label = f"{room.name}: {stay.nights} night{'s' if stay.nights > 1 else ''}"
            if stay.rooms > 1:
                label += f" x {stay.rooms} rooms"
            price = self._converter.ledger(
                [
                    LedgerLine(
                        label=label,
                        kind="room",
                        amount=(
                            MoneyOut(
                                amount_minor=rate.amount_minor * stay.nights * stay.rooms,
                                currency=rate.currency,
                            )
                            if rate
                            else None
                        ),
                        note=None if rate else "No rate in the supplied data",
                    )
                ]
            )
        return RoomOfferOut(
            room_type_id=room.id,
            name=room.name,
            max_occupancy=room.max_occupancy,
            bed_type=room.bed_type,
            board=room.board,
            refundable=room.refundable,
            total_rooms=room.total_rooms,
            fits_party=fits,
            nightly_rate=rate,
            price=price,
            origin=room.origin,
        )

    def _unavailable(self, stay: Stay) -> set[uuid.UUID]:
        key = (stay.check_in, stay.check_out)
        if key not in self._out_of_service:
            self._out_of_service[key] = unavailable_rooms(self._session, *key)
        return self._out_of_service[key]

    def _nightly_display(self, room: RoomOfferOut) -> int | None:
        if room.nightly_rate is None:
            return None
        converted = self._converter.to_display(
            room.nightly_rate.amount_minor, room.nightly_rate.currency
        )
        return converted.amount_minor if converted else None

    def _rooms_by_hotel(self, hotel_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[RoomType]]:
        rooms: dict[uuid.UUID, list[RoomType]] = defaultdict(list)
        for room in self._session.scalars(
            select(RoomType).where(RoomType.hotel_id.in_(hotel_ids), RoomType.is_active.is_(True))
        ):
            rooms[room.hotel_id].append(room)
        return rooms

    def _amenities(self, hotel_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
        amenities: dict[uuid.UUID, list[str]] = defaultdict(list)
        for row in self._session.scalars(
            select(HotelAmenity).where(HotelAmenity.hotel_id.in_(hotel_ids))
        ):
            amenities[row.hotel_id].append(row.amenity)
        return {k: sorted(v) for k, v in amenities.items()}

    # ------------------------------------------------------------------ search

    def search(self, query: HotelQuery) -> HotelSearchOut:
        stay = query.stay
        self.validate(stay)
        city = LocationService(self._session).city(query.city)
        hotels = list(
            self._session.scalars(
                select(Hotel).where(Hotel.city_id == city.id, Hotel.is_active.is_(True))
            )
        )
        ids = [h.id for h in hotels]
        rooms = self._rooms_by_hotel(ids)
        amenities = self._amenities(ids)

        candidates: list[tuple[HotelResultOut, list[RoomOfferOut]]] = []
        for hotel in hotels:
            fitting = [
                r for r in (self._room(rt, stay) for rt in rooms.get(hotel.id, [])) if r.fits_party
            ]
            if not fitting:
                continue
            result = self._result(hotel, city, fitting, amenities.get(hotel.id, []))
            candidates.append((result, fitting))

        facets = self._facets([c[0] for c in candidates])
        results = []
        for result, fitting in candidates:
            chosen = self._apply_filters(result, fitting, query)
            if chosen is not None:
                results.append(chosen)
        ranked_by = "rules"
        if query.sort == "recommended" and self._ranker is not None and len(results) > 1:
            results = self._model_order(results, stay)
            ranked_by = f"model:{self._ranker.card.version}"
        else:
            results.sort(key=self._sort_key(query.sort, results))
        personalized = False
        if query.sort == "recommended" and self._preference is not None and len(results) > 1:
            results = self._personalize(results, city.id)
            ranked_by, personalized = f"{ranked_by}+preferences", True
        notices = []
        if any(not r.bookable for r in results):
            notices.append("Some stays have no rate in the supplied data and are browse only.")
        return HotelSearchOut(
            city=CityOut(id=city.id, name=city.name, country=city.country),
            check_in=stay.check_in,
            check_out=stay.check_out,
            nights=stay.nights,
            guests=stay.guests,
            rooms=stay.rooms,
            results=results[: self._rules.max_results],
            total=len(results),
            unfiltered_total=len(candidates),
            facets=facets,
            display_currency=self._converter.display_currency,
            notices=notices,
            ranked_by=ranked_by,
            personalized=personalized,
        )

    def _personalize(
        self, results: list[HotelResultOut], city_id: uuid.UUID
    ) -> list[HotelResultOut]:
        """Blend the traveller's preference into the order; unpriced stays stay last."""
        from app.modules.search.preferences import hotel_features

        preference = self._preference
        if preference is None:
            return results
        features = hotel_features(self._session, self._converter, {city_id})
        priced = [r for r in results if self._nightly_display(r.cheapest_room) is not None]
        unpriced = [r for r in results if r not in priced]
        n = len(priced)
        scored = []
        for position, result in enumerate(priced):
            vector = features.get(result.id)
            base = 1 - position / (n - 1) if n > 1 else 1.0
            liking = probability(preference, vector) if vector else 0.5
            if vector:
                result.personal_reasons = reasons(preference, vector)
            scored.append(((1 - self._blend) * base + self._blend * liking, -position, result))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return [r for _, _, r in scored] + unpriced

    def _model_order(self, results: list[HotelResultOut], stay: Stay) -> list[HotelResultOut]:
        """Order by the trained ranker; unpriced stays always go last."""
        if self._ranker is None:
            return sorted(results, key=self._sort_key("recommended", results))
        usd_rate = float(self._converter.rules.fx_rates.get("USD", 0)) or None
        priced = [r for r in results if self._nightly_display(r.cheapest_room) is not None]
        unpriced = [r for r in results if r not in priced]
        if not priced or usd_rate is None:
            return sorted(results, key=self._sort_key("recommended", results))
        rows = hotel_ranker_rows(
            [
                HotelRow(
                    star_rating=r.star_rating or 0.0,
                    review_score=(r.guest_rating or 0.0) / 2,
                    nightly_usd=(self._nightly_display(r.cheapest_room) or 0) / 100 / usd_rate,
                )
                for r in priced
            ],
            nights=stay.nights,
            adults=stay.guests,
            rooms=stay.rooms,
            booking_window_days=(stay.check_in - self._today).days,
        )
        scores = self._ranker.predict(rows)
        ordered = [r for _, r in sorted(zip(scores, priced, strict=True), key=lambda x: -x[0])]
        return ordered + unpriced

    def _cheapest(self, rooms: list[RoomOfferOut]) -> RoomOfferOut:
        priced = [r for r in rooms if self._nightly_display(r) is not None]
        if priced:
            return min(priced, key=lambda r: self._nightly_display(r) or 0)
        return rooms[0]

    def _result(
        self, hotel: Hotel, city: City, fitting: list[RoomOfferOut], amenities: list[str]
    ) -> HotelResultOut:
        cheapest = self._cheapest(fitting)
        return HotelResultOut(
            id=hotel.id,
            name=hotel.name,
            city_name=hotel.city_name,
            address=hotel.address,
            star_rating=hotel.star_rating,
            guest_rating=hotel.guest_rating,
            review_count=hotel.review_count,
            amenities=amenities,
            latitude=hotel.latitude,
            longitude=hotel.longitude,
            distance_km=_distance_km(hotel, city),
            cheapest_room=cheapest,
            bookable=cheapest.nightly_rate is not None,
            free_cancellation=any(r.refundable for r in fitting),
            breakfast_available=any(r.board in BREAKFAST_BOARDS for r in fitting),
        )

    def _apply_filters(
        self, result: HotelResultOut, fitting: list[RoomOfferOut], query: HotelQuery
    ) -> HotelResultOut | None:
        if query.stars and int(result.star_rating or 0) not in query.stars:
            return None
        if query.min_rating is not None and (result.guest_rating or 0) < query.min_rating:
            return None
        if query.amenities and not set(query.amenities) <= set(result.amenities):
            return None
        rooms = fitting
        if query.free_cancellation:
            rooms = [r for r in rooms if r.refundable]
        if query.breakfast:
            rooms = [r for r in rooms if r.board in BREAKFAST_BOARDS]
        if query.max_price is not None:
            rooms = [
                r
                for r in rooms
                if (p := self._nightly_display(r)) is not None and p <= query.max_price * 100
            ]
        if not rooms:
            return None
        cheapest = self._cheapest(rooms)
        return result.model_copy(
            update={"cheapest_room": cheapest, "bookable": cheapest.nightly_rate is not None}
        )

    def _facets(self, results: list[HotelResultOut]) -> HotelFacets:
        stars = Counter(int(r.star_rating or 0) for r in results)
        amenities = Counter(a for r in results for a in r.amenities)
        prices = [
            p for p in (self._nightly_display(r.cheapest_room) for r in results) if p is not None
        ]
        currency = self._converter.display_currency
        return HotelFacets(
            stars=[
                FacetOption(value=str(s), label=f"{s} star" if s else "Unrated", count=n)
                for s, n in sorted(stars.items(), reverse=True)
            ],
            amenities=[
                FacetOption(
                    value=a, label=AMENITY_LABELS.get(a, a.replace("_", " ").capitalize()), count=n
                )
                for a, n in amenities.most_common()
            ],
            price_range=PriceRange(
                min=MoneyOut(amount_minor=min(prices), currency=currency),
                max=MoneyOut(amount_minor=max(prices), currency=currency),
            )
            if prices
            else None,
        )

    def _sort_key(self, sort: HotelSort, results: list[HotelResultOut]):  # type: ignore[no-untyped-def]
        unpriced = 10**15
        prices = [
            p for p in (self._nightly_display(r.cheapest_room) for r in results) if p is not None
        ]
        low, high = min(prices, default=0), max(prices, default=1)
        spread = max(high - low, 1)

        def price(r: HotelResultOut) -> int:
            value = self._nightly_display(r.cheapest_room)
            return unpriced if value is None else value

        if sort == "price":
            return lambda r: (price(r), -(r.guest_rating or 0))
        if sort == "rating":
            return lambda r: (-(r.guest_rating or 0), -(r.review_count or 0), price(r))
        if sort == "distance":
            return lambda r: (r.distance_km is None, r.distance_km or 0.0, price(r))
        if sort == "stars":
            return lambda r: (-(r.star_rating or 0), price(r))

        # "recommended": transparent weighted score (rating 50%, value 30%, stars 20%).
        def score(r: HotelResultOut) -> tuple[bool, float]:
            value = 0.0 if price(r) == unpriced else 1 - (price(r) - low) / spread
            return (
                price(r) == unpriced,
                -(0.5 * (r.guest_rating or 0) / 10 + 0.3 * value + 0.2 * (r.star_rating or 0) / 5),
            )

        return score

    def price_room(self, room_type_id: uuid.UUID, stay: Stay) -> tuple[Hotel, City, RoomOfferOut]:
        """Re-price one room type for a stay (used by checkout; never trusts client prices)."""
        self.validate(stay)
        room = self._session.get(RoomType, room_type_id)
        hotel = self._session.get(Hotel, room.hotel_id) if room else None
        city = self._session.get(City, hotel.city_id) if hotel else None
        if (
            room is None
            or hotel is None
            or city is None
            or not (room.is_active and hotel.is_active)
        ):
            raise NotFound("This room is no longer available.", code="OFFER_UNAVAILABLE")
        offer = self._room(room, stay)
        if not offer.fits_party:
            raise ValidationFailed("This room does not fit your party.", code="ROOM_TOO_SMALL")
        if offer.nightly_rate is None:
            raise ValidationFailed(
                "This room has no rate and cannot be booked.", code="OFFER_NOT_BOOKABLE"
            )
        return hotel, city, offer

    # ------------------------------------------------------------------ details

    def detail(self, hotel_id: uuid.UUID, stay: Stay | None) -> HotelDetailOut:
        if stay is not None:
            self.validate(stay)
        hotel = self._session.get(Hotel, hotel_id)
        if hotel is None or not hotel.is_active:
            raise NotFound("This stay is not available.", code="HOTEL_NOT_FOUND")
        city = self._session.get(City, hotel.city_id)
        if city is None:
            raise NotFound("This stay is not available.", code="HOTEL_NOT_FOUND")
        rooms = [self._room(r, stay) for r in self._rooms_by_hotel([hotel.id]).get(hotel.id, [])]
        rooms.sort(
            key=lambda r: (
                not r.fits_party,
                self._nightly_display(r) is None,
                self._nightly_display(r) or 0,
            )
        )
        return HotelDetailOut(
            id=hotel.id,
            name=hotel.name,
            city=CityOut(id=city.id, name=city.name, country=city.country),
            address=hotel.address,
            description=hotel.description,
            star_rating=hotel.star_rating,
            guest_rating=hotel.guest_rating,
            review_count=hotel.review_count,
            amenities=self._amenities([hotel.id]).get(hotel.id, []),
            latitude=hotel.latitude,
            longitude=hotel.longitude,
            distance_km=_distance_km(hotel, city),
            check_in_time=hotel.check_in_time,
            check_out_time=hotel.check_out_time,
            origin=hotel.origin,
            stay=StayOut(
                check_in=stay.check_in,
                check_out=stay.check_out,
                nights=stay.nights,
                guests=stay.guests,
                rooms=stay.rooms,
            )
            if stay
            else None,
            rooms=rooms,
            display_currency=self._converter.display_currency,
            similar=self._similar(hotel, city),
        )

    def _similar(self, hotel: Hotel, city: City, k: int = 4) -> list[SimilarHotelOut]:
        """Stays in the same city most like this one (see app/modules/ml/similar.py)."""
        hotels = list(
            self._session.scalars(
                select(Hotel).where(Hotel.city_id == city.id, Hotel.is_active.is_(True))
            )
        )
        ids = [h.id for h in hotels]
        amenities = self._amenities(ids)
        cheapest: dict[uuid.UUID, int] = {}
        for hotel_id, rooms in self._rooms_by_hotel(ids).items():
            prices = [
                p
                for p in (self._nightly_display(self._room(r, None)) for r in rooms)
                if p is not None
            ]
            if prices:
                cheapest[hotel_id] = min(prices)
        neighbours = similar_hotels(
            hotel.id,
            [
                HotelProfile(
                    id=h.id,
                    amenities=tuple(amenities.get(h.id, [])),
                    star_rating=h.star_rating,
                    guest_rating=h.guest_rating,
                    nightly_price=cheapest.get(h.id),
                )
                for h in hotels
            ],
            k=k,
        )
        by_id = {h.id: h for h in hotels}
        currency = self._converter.display_currency
        return [
            SimilarHotelOut(
                id=n.id,
                name=by_id[n.id].name,
                star_rating=by_id[n.id].star_rating,
                guest_rating=by_id[n.id].guest_rating,
                distance_km=_distance_km(by_id[n.id], city),
                from_price=MoneyOut(amount_minor=cheapest[n.id], currency=currency)
                if n.id in cheapest
                else None,
                similarity=n.similarity,
                shared_amenities=list(n.shared_amenities),
            )
            for n in neighbours
        ]
