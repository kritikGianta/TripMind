"""Catalog: the travel inventory that bookings are made against.

Catalog rows are written only by the data pack loader (modules/holiday/pack.py). Every row
carries:

- a deterministic `id` derived from its `source_key`, so re-importing the same data produces the
  same IDs (plan v2, G15);
- `origin`: `provided` (from the supplied dataset), `synthetic` (from the demo generator) or
  `derived` (built by TripMind from provided fields, for example a city from an airport);
- `row_hash`, so a re-import can tell unchanged rows from updated ones;
- `is_active` / `retired_at`: rows missing from a newer import are retired, never deleted, because
  bookings may still reference them.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin

CATALOG_NAMESPACE = uuid.UUID("6f1c2e1a-3b0e-4a8e-9a49-5b6d1b7a2c01")


def catalog_id(entity: str, source_key: str) -> uuid.UUID:
    """Stable ID for a catalog row: the same source key always maps to the same UUID."""
    return uuid.uuid5(CATALOG_NAMESPACE, f"{entity}:{source_key}")


class DataOrigin(enum.StrEnum):
    PROVIDED = "provided"
    SYNTHETIC = "synthetic"
    DERIVED = "derived"


_ORIGIN_CHECK = "origin IN ('provided', 'synthetic', 'derived')"


class CatalogRowMixin(TimestampMixin):
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class City(CatalogRowMixin, Base):
    __tablename__ = "cities"
    __table_args__ = (CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(64))
    # ISO country code (IN, JP, AE) when the dataset gives one; links a city to `countries`.
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    # A city a holiday can start from (destinations.json `departure_cities`).
    is_departure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Airport(CatalogRowMixin, Base):
    __tablename__ = "airports"
    __table_args__ = (CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),)

    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    city_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    # True when the source had no valid timezone and the configured default was used (G12).
    timezone_assumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Flight(CatalogRowMixin, Base):
    """One bookable flight on one date in one cabin.

    Times are kept both as local wall-clock time (what the traveller sees) and as UTC (what the
    system compares). A row with `stops > 0` is a through itinerary as supplied by the source;
    connections built by TripMind from single segments are assembled at search time instead.
    """

    __tablename__ = "flights"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint("arrival_at > departure_at", name="arrives_after_departure"),
        CheckConstraint("origin_airport_id <> destination_airport_id", name="distinct_airports"),
        CheckConstraint("fare_minor IS NULL OR fare_minor >= 0", name="fare_non_negative"),
        Index(
            "ix_flights_route_departure",
            "origin_airport_id",
            "destination_airport_id",
            "departure_at",
        ),
        Index("ix_flights_departure_at", "departure_at"),
    )

    flight_number: Mapped[str] = mapped_column(String(16), nullable=False)
    airline_code: Mapped[str | None] = mapped_column(String(8))
    airline_name: Mapped[str | None] = mapped_column(String(120))
    origin_airport_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False
    )
    destination_airport_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    departure_local: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    arrival_local: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cabin_class: Mapped[str] = mapped_column(String(24), nullable=False)
    # NULL fare = browse-only: the source had no price and none is invented (G14).
    fare_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    seat_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    aircraft: Mapped[str | None] = mapped_column(String(64))


class Hotel(CatalogRowMixin, Base):
    __tablename__ = "hotels"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint(
            "star_rating IS NULL OR (star_rating >= 0 AND star_rating <= 5)",
            name="star_rating_range",
        ),
        CheckConstraint(
            "guest_rating IS NULL OR (guest_rating >= 0 AND guest_rating <= 10)",
            name="guest_rating_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    city_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    star_rating: Mapped[float | None] = mapped_column(Float)
    guest_rating: Mapped[float | None] = mapped_column(Float)  # normalised to a 0-10 scale
    review_count: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    check_in_time: Mapped[str | None] = mapped_column(String(5))
    check_out_time: Mapped[str | None] = mapped_column(String(5))
    # Part of the city; it decides which airport transfers serve the hotel.
    area: Mapped[str | None] = mapped_column(String(80))
    family_friendly: Mapped[bool | None] = mapped_column(Boolean)
    # Path of a photo inside the data pack (images/hotels/...), shown with its credit.
    image: Mapped[str | None] = mapped_column(String(200))


class HotelAmenity(Base):
    """Amenities as rows, not JSON, so filters are plain indexed joins on every database (G5)."""

    __tablename__ = "hotel_amenities"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id", ondelete="CASCADE"), primary_key=True
    )
    amenity: Mapped[str] = mapped_column(String(48), primary_key=True, index=True)


class RoomType(CatalogRowMixin, Base):
    __tablename__ = "room_types"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint("max_occupancy >= 1", name="occupancy_positive"),
        CheckConstraint("total_rooms >= 0", name="total_rooms_non_negative"),
        CheckConstraint(
            "nightly_rate_minor IS NULL OR nightly_rate_minor >= 0", name="rate_non_negative"
        ),
    )

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    # Capacity of one room split by adults and children, when the dataset gives it. Holiday
    # room-fit rule: k rooms fit when adults <= k * max_adults,
    # adults + children <= k * (max_adults + max_children), and adults >= k.
    max_adults: Mapped[int | None] = mapped_column(Integer)
    max_children: Mapped[int | None] = mapped_column(Integer)
    room_kind: Mapped[str | None] = mapped_column(String(24))  # TWIN, FAMILY, ...
    bed_type: Mapped[str | None] = mapped_column(String(64))
    board: Mapped[str | None] = mapped_column(String(32))
    refundable: Mapped[bool | None] = mapped_column(Boolean)
    # NULL rate = browse-only (G14). Rates are per room per night.
    nightly_rate_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False)


class HotelReview(CatalogRowMixin, Base):
    """A guest review supplied with the dataset (traveller reviews written in TripMind live in
    the reviews module, so a new import never retires them)."""

    __tablename__ = "hotel_reviews"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 10)", name="rating_range"),
    )

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rating: Mapped[float | None] = mapped_column(Float)  # normalised to a 0-10 scale
    title: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    traveller_type: Mapped[str | None] = mapped_column(String(32))
    reviewed_on: Mapped[date | None] = mapped_column(Date)


# ── Holiday catalog: countries, how cities connect, ground transfers and attractions ──────────


class Country(Base):
    """A destination country (destinations.json `countries`)."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class AirportServedCity(Base):
    """A city a traveller can reach from an airport (airports.json `serves_cities`)."""

    __tablename__ = "airport_served_cities"

    airport_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("airports.id", ondelete="CASCADE"), primary_key=True
    )
    city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Transfer(CatalogRowMixin, Base):
    """One ground transfer service: airport taxi or bus, train or bus between cities, city taxi.

    `source_key` is the dataset's `transfer_id`. Airport transfers set `airport_code`,
    `city_name` and `area` (NULL area = every hotel in the city); transfers between cities set
    `from_city_name` and `to_city_name`. Service times are local clock times ("06:00", "24:00").
    """

    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint("pricing IN ('PER_VEHICLE', 'PER_PERSON')", name="pricing_valid"),
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
        CheckConstraint("max_passengers >= 1", name="passengers_positive"),
    )

    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    airport_code: Mapped[str | None] = mapped_column(String(8), index=True)
    city_name: Mapped[str | None] = mapped_column(String(120), index=True)
    area: Mapped[str | None] = mapped_column(String(80))
    from_city_name: Mapped[str | None] = mapped_column(String(120))
    to_city_name: Mapped[str | None] = mapped_column(String(120))
    from_point: Mapped[str | None] = mapped_column(String(160))
    to_point: Mapped[str | None] = mapped_column(String(160))
    door_to_door: Mapped[bool | None] = mapped_column(Boolean)
    max_passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    service_from: Mapped[str] = mapped_column(String(5), nullable=False)
    service_until: Mapped[str] = mapped_column(String(5), nullable=False)
    frequency_minutes: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing: Mapped[str] = mapped_column(String(12), nullable=False)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    child_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class CityLink(Base):
    """A one-way connection between two cities and one transfer that makes it
    (destinations.json `countries[].links`)."""

    __tablename__ = "city_links"

    from_city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True
    )
    to_city_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True
    )
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("transfers.id", ondelete="CASCADE"), primary_key=True
    )


class Attraction(CatalogRowMixin, Base):
    """A sight with opening days and hours, closed dates, visit time and prices.

    `source_key` is the dataset's `attraction_id`. `city_name` is kept as text because some
    attractions are in a city with no hotels (Nara), so no package can include them.
    """

    __tablename__ = "attractions"
    __table_args__ = (
        CheckConstraint(_ORIGIN_CHECK, name="origin_valid"),
        CheckConstraint("visit_minutes > 0", name="visit_positive"),
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    name_local: Mapped[str | None] = mapped_column(String(160))
    city_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(32))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    open_days: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # ["MON", ...]
    open_from: Mapped[str] = mapped_column(String(5), nullable=False)
    open_until: Mapped[str] = mapped_column(String(5), nullable=False)
    closed_dates: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    visit_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    child_friendly: Mapped[bool | None] = mapped_column(Boolean)
    accessible: Mapped[bool | None] = mapped_column(Boolean)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    child_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    image: Mapped[str | None] = mapped_column(String(200))
