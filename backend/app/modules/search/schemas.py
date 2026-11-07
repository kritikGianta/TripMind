"""Search API contract."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.search.pricing import MoneyOut, PriceLedger

FlightSort = Literal["best", "cheapest", "fastest", "earliest"]
HotelSort = Literal["recommended", "price", "rating", "distance", "stars"]
DepartureWindow = Literal["night", "morning", "afternoon", "evening"]
CabinClass = Literal["economy", "premium_economy", "business", "first"]


class TravelWindowOut(BaseModel):
    first_departure: date
    last_departure: date


# ── Locations ─────────────────────────────────────────────────────────────────────────────────


class LocationOut(BaseModel):
    kind: Literal["airport", "city"]
    value: str = Field(description="Airport code, or city ID: pass it back as the search value")
    name: str
    city_name: str
    country: str | None
    code: str | None = None
    label: str


class LocationListOut(BaseModel):
    items: list[LocationOut]


# ── Flights ───────────────────────────────────────────────────────────────────────────────────


class AirportBrief(BaseModel):
    code: str
    name: str
    city_name: str


class FlightLegOut(BaseModel):
    flight_id: uuid.UUID
    flight_number: str
    airline_code: str | None
    airline_name: str | None
    origin: AirportBrief
    destination: AirportBrief
    departure_local: datetime = Field(description="Wall-clock time at the origin airport")
    arrival_local: datetime = Field(description="Wall-clock time at the destination airport")
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int
    stops: int
    cabin_class: str
    aircraft: str | None
    fare: MoneyOut | None


class LayoverOut(BaseModel):
    airport: AirportBrief
    minutes: int


class FareInsightOut(BaseModel):
    label: Literal["below_typical", "typical", "above_typical"]
    typical_per_adult: MoneyOut
    ratio: float = Field(description="This fare divided by the model's typical fare")
    model_version: str
    basis: str


class FlightOfferOut(BaseModel):
    id: str = Field(description="Stable offer ID: the legs it is made of")
    legs: list[FlightLegOut]
    stops: int
    layovers: list[LayoverOut]
    duration_minutes: int
    self_transfer: bool = Field(description="Legs flown by different airlines")
    bookable: bool = Field(description="False when a leg has no price in the data")
    price: PriceLedger
    notices: list[str] = Field(default_factory=list)
    fare_insight: FareInsightOut | None = None


class FacetOption(BaseModel):
    value: str
    label: str
    count: int
    min_price: MoneyOut | None = None


class PriceRange(BaseModel):
    min: MoneyOut
    max: MoneyOut


class FlightFacets(BaseModel):
    stops: list[FacetOption]
    airlines: list[FacetOption]
    departure_windows: list[FacetOption]
    price_range: PriceRange | None


class FlightResultsOut(BaseModel):
    origin: AirportBrief | None
    destination: AirportBrief | None
    date: date
    offers: list[FlightOfferOut]
    total: int = Field(description="Offers matching the filters (before the result cap)")
    unfiltered_total: int
    facets: FlightFacets


class FlightSearchOut(BaseModel):
    outbound: FlightResultsOut
    inbound: FlightResultsOut | None
    adults: int
    cabin_class: str
    display_currency: str
    travel_window: TravelWindowOut | None
    notices: list[str]


# ── Hotels ────────────────────────────────────────────────────────────────────────────────────


class CityOut(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None


class RoomOfferOut(BaseModel):
    room_type_id: uuid.UUID
    name: str
    max_occupancy: int
    bed_type: str | None
    board: str | None
    refundable: bool | None
    total_rooms: int
    fits_party: bool = Field(description="Enough occupancy and rooms for the requested party")
    nightly_rate: MoneyOut | None
    price: PriceLedger | None = Field(description="For the requested nights and rooms")
    origin: str


class HotelResultOut(BaseModel):
    id: uuid.UUID
    name: str
    city_name: str
    address: str | None
    star_rating: float | None
    guest_rating: float | None
    review_count: int | None
    amenities: list[str]
    latitude: float | None
    longitude: float | None
    distance_km: float | None = Field(description="From the city centre")
    cheapest_room: RoomOfferOut
    bookable: bool
    free_cancellation: bool
    breakfast_available: bool


class HotelFacets(BaseModel):
    stars: list[FacetOption]
    amenities: list[FacetOption]
    price_range: PriceRange | None = Field(description="Per night, display currency")


class HotelSearchOut(BaseModel):
    city: CityOut
    check_in: date
    check_out: date
    nights: int
    guests: int
    rooms: int
    results: list[HotelResultOut]
    total: int
    unfiltered_total: int
    facets: HotelFacets
    display_currency: str
    notices: list[str]
    ranked_by: str = Field(default="rules", description="'model:<version>' or 'rules'")


class HotelDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    city: CityOut
    address: str | None
    description: str | None
    star_rating: float | None
    guest_rating: float | None
    review_count: int | None
    amenities: list[str]
    latitude: float | None
    longitude: float | None
    distance_km: float | None
    check_in_time: str | None
    check_out_time: str | None
    origin: str
    stay: StayOut | None
    rooms: list[RoomOfferOut]
    display_currency: str
    similar: list[SimilarHotelOut] = Field(default_factory=list)


class SimilarHotelOut(BaseModel):
    id: uuid.UUID
    name: str
    star_rating: float | None
    guest_rating: float | None
    distance_km: float | None
    from_price: MoneyOut | None = Field(description="Cheapest nightly rate, display currency")
    similarity: float
    shared_amenities: list[str]


class StayOut(BaseModel):
    check_in: date
    check_out: date
    nights: int
    guests: int
    rooms: int


HotelDetailOut.model_rebuild()
