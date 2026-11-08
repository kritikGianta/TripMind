"""Target schemas: the fields TripMind understands for each catalog entity.

A dataset mapping (config/mappings/*.yaml) says which source column feeds which target field. The
profiler uses `synonyms` to suggest a mapping for an unseen dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldKind = Literal[
    "str", "code", "int", "float", "money", "datetime", "date", "time", "duration", "bool", "list"
]
EntityName = Literal["airports", "flights", "hotels", "room_types"]
ENTITY_ORDER: tuple[EntityName, ...] = ("airports", "flights", "hotels", "room_types")


@dataclass(frozen=True)
class TargetField:
    name: str
    kind: FieldKind
    required: bool = False
    synonyms: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = None
    description: str = ""


@dataclass(frozen=True)
class TargetEntity:
    name: EntityName
    fields: tuple[TargetField, ...]
    # Fields that identify a row when the source has no explicit ID column.
    natural_key: tuple[str, ...]
    # Groups where at least one field must be present ("any of").
    any_of: tuple[tuple[str, ...], ...] = field(default_factory=tuple)

    def get(self, name: str) -> TargetField | None:
        return next((f for f in self.fields if f.name == name), None)

    def require(self, name: str) -> TargetField:
        found = self.get(name)
        if found is None:
            raise KeyError(f"{self.name} has no field {name!r}")
        return found

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


F = TargetField

AIRPORTS = TargetEntity(
    name="airports",
    natural_key=("code",),
    fields=(
        F("code", "code", True, ("iata", "iata_code", "airport_code", "code"), max_length=8),
        F("name", "str", True, ("airport_name", "name", "airport"), max_length=160),
        F("city", "str", True, ("city", "city_name", "municipality", "town"), max_length=120),
        F(
            "country",
            "str",
            False,
            ("country", "country_code", "iso_country", "country_name"),
            max_length=64,
        ),
        F("latitude", "float", False, ("latitude", "lat", "latitude_deg"), -90, 90),
        F(
            "longitude",
            "float",
            False,
            ("longitude", "lon", "lng", "long", "longitude_deg"),
            -180,
            180,
        ),
        F(
            "timezone",
            "str",
            False,
            ("timezone", "tz", "time_zone", "tz_database_time_zone"),
            max_length=64,
        ),
    ),
)

FLIGHTS = TargetEntity(
    name="flights",
    natural_key=("flight_number", "departure_local", "cabin_class"),
    any_of=(
        ("airline_code", "airline_name"),
        ("departure_local", "departure_date", "valid_from"),
    ),
    fields=(
        F("source_key", "str", False, ("flight_id", "id", "itinerary_id"), max_length=160),
        F(
            "flight_number",
            "code",
            True,
            ("flight_number", "flight_no", "flight", "flight_code"),
            max_length=16,
        ),
        F(
            "airline_code",
            "code",
            False,
            ("airline_code", "carrier_code", "carrier", "iata_airline"),
            max_length=8,
        ),
        F(
            "airline_name",
            "str",
            False,
            ("airline", "airline_name", "carrier_name", "operator"),
            max_length=120,
        ),
        F(
            "origin",
            "str",
            True,
            (
                "origin",
                "from",
                "source",
                "source_city",
                "departure_airport",
                "origin_airport",
                "dep_airport",
            ),
            max_length=120,
        ),
        F(
            "destination",
            "str",
            True,
            (
                "destination",
                "to",
                "dest",
                "destination_city",
                "arrival_airport",
                "destination_airport",
                "arr_airport",
            ),
            max_length=120,
        ),
        F(
            "departure_local",
            "datetime",
            False,
            ("departure", "departure_time", "dep_time", "departure_datetime", "std"),
        ),
        F(
            "departure_date",
            "date",
            False,
            ("date", "departure_date", "date_of_journey", "flight_date"),
        ),
        F("departure_clock", "time", False, ("dep_clock", "departure_hhmm")),
        F(
            "arrival_local",
            "datetime",
            False,
            ("arrival", "arrival_time", "arr_time", "arrival_datetime", "sta"),
        ),
        F("arrival_clock", "time", False, ("arr_clock", "arrival_hhmm")),
        # Schedule rows: a repeating flight, expanded into dated flights at import.
        F(
            "operating_days",
            "str",
            False,
            ("days", "operating_days", "days_of_operation", "frequency", "dow"),
            max_length=40,
        ),
        F("valid_from", "date", False, ("valid_from", "effective_from", "start_date", "from_date")),
        F(
            "valid_to",
            "date",
            False,
            ("valid_to", "effective_to", "end_date", "to_date", "discontinue"),
        ),
        F(
            "duration_minutes",
            "duration",
            False,
            ("duration", "duration_min", "flight_duration", "duration_minutes"),
            1,
            72 * 60,
        ),
        F("stops", "int", False, ("stops", "total_stops", "num_stops"), 0, 4),
        F(
            "cabin_class",
            "str",
            False,
            ("cabin", "class", "cabin_class", "fare_class"),
            max_length=24,
        ),
        F("fare", "money", False, ("price", "fare", "amount", "base_fare", "ticket_price")),
        F("currency", "code", False, ("currency", "currency_code", "ccy"), max_length=3),
        F(
            "seat_capacity",
            "int",
            False,
            ("seats", "capacity", "seat_capacity", "seats_total"),
            1,
            1000,
        ),
        F("aircraft", "str", False, ("aircraft", "aircraft_type", "equipment"), max_length=64),
    ),
)

HOTELS = TargetEntity(
    name="hotels",
    natural_key=("name", "city"),
    fields=(
        F(
            "source_key",
            "str",
            False,
            ("hotel_id", "id", "property_id", "hotel_code"),
            max_length=160,
        ),
        F("name", "str", True, ("name", "hotel_name", "property_name", "hotel"), max_length=200),
        F("city", "str", True, ("city", "city_name", "location", "destination"), max_length=120),
        F("country", "str", False, ("country", "country_code", "country_name"), max_length=64),
        F("address", "str", False, ("address", "street_address", "full_address"), max_length=300),
        F("latitude", "float", False, ("latitude", "lat"), -90, 90),
        F("longitude", "float", False, ("longitude", "lon", "lng", "long"), -180, 180),
        F("star_rating", "float", False, ("stars", "star_rating", "hotel_class", "category"), 0, 5),
        F(
            "guest_rating",
            "float",
            False,
            ("rating", "guest_rating", "review_score", "score", "user_rating"),
            0,
            10,
        ),
        F(
            "review_count",
            "int",
            False,
            ("reviews", "review_count", "num_reviews", "number_of_reviews"),
            0,
            10_000_000,
        ),
        F("description", "str", False, ("description", "summary", "about", "overview")),
        F("amenities", "list", False, ("amenities", "facilities", "features")),
        F("check_in_time", "time", False, ("check_in", "checkin", "check_in_time")),
        F("check_out_time", "time", False, ("check_out", "checkout", "check_out_time")),
        F(
            "nightly_rate",
            "money",
            False,
            ("price", "price_per_night", "nightly_rate", "rate", "min_price"),
        ),
        F("currency", "code", False, ("currency", "currency_code"), max_length=3),
        F("total_rooms", "int", False, ("rooms", "total_rooms", "room_count"), 0, 100_000),
    ),
)

ROOM_TYPES = TargetEntity(
    name="room_types",
    natural_key=("hotel_key", "name"),
    fields=(
        F("source_key", "str", False, ("room_id", "room_type_id", "id"), max_length=160),
        F(
            "hotel_key",
            "str",
            True,
            ("hotel_id", "hotel_key", "property_id", "hotel_code"),
            max_length=160,
        ),
        F("name", "str", True, ("room_name", "room_type", "name", "room"), max_length=120),
        F(
            "max_occupancy",
            "int",
            False,
            ("max_guests", "occupancy", "max_occupancy", "capacity"),
            1,
            20,
        ),
        F("bed_type", "str", False, ("bed", "bed_type", "beds"), max_length=64),
        F("board", "str", False, ("board", "meal_plan", "meals", "board_basis"), max_length=32),
        F("refundable", "bool", False, ("refundable", "is_refundable", "free_cancellation")),
        F("nightly_rate", "money", False, ("price", "rate", "nightly_rate", "price_per_night")),
        F("currency", "code", False, ("currency", "currency_code"), max_length=3),
        F(
            "total_rooms",
            "int",
            False,
            ("rooms_count", "total_rooms", "inventory", "rooms", "quantity"),
            0,
            10_000,
        ),
    ),
)

TARGETS: dict[EntityName, TargetEntity] = {
    "airports": AIRPORTS,
    "flights": FLIGHTS,
    "hotels": HOTELS,
    "room_types": ROOM_TYPES,
}
