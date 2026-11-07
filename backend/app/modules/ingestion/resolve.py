"""Resolve: entity rules that need more than one field or more than one file.

- Cities are derived from airports and hotels, matched through aliases and fuzzy names.
- Flights reference airports by code, airport name or (unambiguous) city; local times are
  converted to UTC with the airport's timezone; arrival is derived from a clock time or duration.
- Hotels without room types get one derived room type priced from the hotel rate.
- Every row gets a deterministic source key and catalog ID.

Each fallback used instead of rejecting a row is counted in the import report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from app.core.money import CURRENCY_PATTERN, to_minor_units
from app.modules.catalog.models import DataOrigin, catalog_id
from app.modules.ingestion.extract import EntityFrame
from app.modules.ingestion.rejects import RejectCode, RejectLog
from app.modules.ingestion.rules import (
    IngestionRules,
    Vocabulary,
    is_valid_timezone,
    normalize_text,
    slugify,
)


@dataclass(frozen=True)
class AirportRef:
    """An airport that flights may reference (from this import or the live catalog)."""

    id: str
    code: str
    name: str
    city_key: str
    timezone: str


@dataclass
class CityRecord:
    key: str
    name: str
    country: str | None
    timezone: str
    timezone_assumed: bool
    points: list[tuple[float, float]] = field(default_factory=list)
    airport_points: list[tuple[float, float]] = field(default_factory=list)


def _country(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text.upper() if len(text) == 2 else text or None


def _missing(value: Any) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value))


def _utc_column(data: pd.DataFrame, name: str) -> pd.Series | None:
    """Instants parsed from values that carried their own UTC offset (see parse_datetime)."""
    return pd.to_datetime(data[name], utc=True) if name in data else None


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))


class CityRegistry:
    """Builds the city list. Keys are the canonical normalised name plus normalised country."""

    def __init__(self, rules: IngestionRules, vocabulary: Vocabulary, log: RejectLog) -> None:
        self._rules = rules
        self._aliases = vocabulary.city_alias_index()
        self._log = log
        self.cities: dict[str, CityRecord] = {}

    def _canonical(self, name: str) -> str:
        norm = normalize_text(name)
        return self._aliases.get(norm, norm)

    @staticmethod
    def _key(canonical: str, country: str | None) -> str:
        return f"{canonical}|{normalize_text(country or '')}"

    def resolve(
        self,
        name: str,
        country: str | None,
        *,
        timezone: str | None,
        point: tuple[float, float] | None,
        from_airport: bool,
    ) -> str:
        canonical = self._canonical(name)
        key = self._key(canonical, country)
        city = self.cities.get(key)
        if city is None:
            city = self._match_existing(name, canonical, country)
        if city is None:
            tz = timezone if timezone and is_valid_timezone(timezone) else None
            city = CityRecord(
                key=key,
                name=name.strip(),
                country=country,
                timezone=tz or self._rules.default_timezone,
                timezone_assumed=tz is None,
            )
            self.cities[key] = city
        if point is not None:
            (city.airport_points if from_airport else city.points).append(point)
        return city.key

    def _match_existing(self, name: str, canonical: str, country: str | None) -> CityRecord | None:
        same_name = [c for c in self.cities.values() if self._canonical(c.name) == canonical]
        if len(same_name) == 1:
            # Same city written with a different country form ("IN" vs "India") or none at all.
            if country and same_name[0].country and country != same_name[0].country:
                self._log.adjust(
                    "CITY_COUNTRY_FORM_DIFFERS",
                    example=f"{name} ({country} ~ {same_name[0].country})",
                )
            return same_name[0]
        candidates = {
            c.key: self._canonical(c.name)
            for c in self.cities.values()
            if country is None
            or c.country is None
            or normalize_text(c.country) == normalize_text(country)
        }
        if not candidates:
            return None
        match = process.extractOne(
            canonical, candidates, scorer=fuzz.WRatio, score_cutoff=self._rules.city_match_threshold
        )
        if match is None:
            return None
        city = self.cities[match[2]]
        self._log.adjust("CITY_FUZZY_MATCH", example=f"{name} -> {city.name} ({match[1]:.0f})")
        return city

    def assign_missing_timezones(self) -> None:
        """A hotel-only city takes the timezone of the nearest airport city within 300 km."""
        anchors = [c for c in self.cities.values() if not c.timezone_assumed and c.airport_points]
        for city in self.cities.values():
            if not city.timezone_assumed or not city.points:
                continue
            centre = _centre(city.points)
            nearest = min(
                ((_haversine_km(centre, _centre(a.airport_points)), a) for a in anchors),
                default=None,
                key=lambda item: item[0],
            )
            if nearest and nearest[0] < 300:
                city.timezone, city.timezone_assumed = nearest[1].timezone, False
                self._log.adjust("CITY_TIMEZONE_FROM_NEAREST_AIRPORT", example=city.name)
            else:
                self._log.adjust("TIMEZONE_ASSUMED", example=f"city {city.name}")

    def frame(self, origin: str) -> pd.DataFrame:
        rows = []
        for city in self.cities.values():
            points = city.points or city.airport_points
            lat, lon = _centre(points) if points else (None, None)
            rows.append(
                {
                    "id": catalog_id("city", city.key),
                    "source_key": city.key,
                    "name": city.name,
                    "country": city.country,
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": city.timezone,
                    "origin": origin,
                }
            )
        return pd.DataFrame(rows)


def _centre(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        round(sum(p[0] for p in points) / len(points), 6),
        round(sum(p[1] for p in points) / len(points), 6),
    )


def _point(row: pd.Series) -> tuple[float, float] | None:
    lat, lon = row.get("latitude"), row.get("longitude")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return None
    return float(lat), float(lon)


def _dedupe(frame: EntityFrame, key: str, log: RejectLog) -> None:
    dupes = frame.data[key].duplicated(keep="first")
    frame.drop(
        dupes, log, RejectCode.DUPLICATE_KEY, key, "same identity as an earlier row in this file"
    )


def _currency(
    frame: EntityFrame, log: RejectLog, default: str, fallback: pd.Series | None = None
) -> None:
    currency = frame.data["currency"]
    missing = currency.isna()
    if fallback is not None:
        currency = currency.where(~missing, fallback)
        missing = currency.isna()
    log.adjust("DEFAULT_CURRENCY", int(missing.sum()))
    currency = currency.where(~missing, default).astype(str).str.upper()
    frame.data["currency"] = currency
    frame.drop(
        ~currency.str.match(CURRENCY_PATTERN.pattern),
        log,
        RejectCode.INVALID_VALUE,
        "currency",
        "currency must be a 3-letter ISO 4217 code",
    )


def _minor_units(frame: EntityFrame, column: str, log: RejectLog, target: str) -> None:
    data = frame.data
    data[target] = pd.Series(
        [
            None if _missing(amount) else to_minor_units(Decimal(amount), currency)
            for amount, currency in zip(data[column], data["currency"], strict=True)
        ],
        index=data.index,
        dtype="Int64",
    )
    frame.drop(
        data[target].lt(0).fillna(False),
        log,
        RejectCode.OUT_OF_RANGE,
        column,
        f"'{column}' cannot be negative",
    )


# --------------------------------------------------------------------------------------------
# Airports


def resolve_airports(
    frame: EntityFrame, cities: CityRegistry, rules: IngestionRules, log: RejectLog, origin: str
) -> pd.DataFrame:
    data = frame.data
    data["code"] = data["code"].astype(str).str.upper()
    _dedupe(frame, "code", log)
    data = frame.data

    tz = data["timezone"].map(lambda v: v if isinstance(v, str) and is_valid_timezone(v) else None)
    assumed = tz.isna()
    log.adjust(
        "TIMEZONE_ASSUMED",
        int(assumed.sum()),
        example=", ".join(data.loc[assumed, "code"].head(5)) or None,
    )
    data["timezone"] = tz.where(~assumed, rules.default_timezone)
    data["timezone_assumed"] = assumed
    data["country"] = data["country"].map(_country)

    data["city_key"] = [
        cities.resolve(
            row["city"],
            row["country"],
            timezone=None if row["timezone_assumed"] else row["timezone"],
            point=_point(row),
            from_airport=True,
        )
        for _, row in data.iterrows()
    ]
    data["source_key"] = data["code"]
    data["id"] = data["source_key"].map(lambda k: catalog_id("airport", k))
    data["city_name"] = data["city"]
    data["origin"] = origin
    frame.data = data
    return data


def airport_refs(airports: pd.DataFrame) -> list[AirportRef]:
    return [
        AirportRef(
            id=str(r["id"]),
            code=r["code"],
            name=r["name"],
            city_key=r["city_key"],
            timezone=r["timezone"],
        )
        for _, r in airports.iterrows()
    ]


# --------------------------------------------------------------------------------------------
# Flights


class AirportIndex:
    """Find an airport by IATA code, airport name, or city name when the city has one airport."""

    def __init__(self, refs: list[AirportRef], vocabulary: Vocabulary) -> None:
        aliases = vocabulary.city_alias_index()
        self._by_code = {r.code.upper(): r for r in refs}
        self._by_name = {normalize_text(r.name): r for r in refs}
        by_city: dict[str, list[AirportRef]] = {}
        for ref in refs:
            city = ref.city_key.split("|", 1)[0]
            by_city.setdefault(city, []).append(ref)
        self._by_city = {k: v[0] for k, v in by_city.items() if len(v) == 1}
        self._aliases = aliases

    def find(self, value: str) -> AirportRef | None:
        code = value.strip().upper()
        if code in self._by_code:
            return self._by_code[code]
        norm = normalize_text(value)
        return self._by_name.get(norm) or self._by_city.get(self._aliases.get(norm, norm))


def _localize(local: pd.Series, zones: pd.Series) -> pd.Series:
    """Naive local timestamps + per-row IANA zone -> UTC. Ambiguous or skipped times become NaT."""
    result = pd.Series(pd.NaT, index=local.index, dtype="datetime64[ns, UTC]")
    for zone, rows in local.groupby(zones).groups.items():
        values = pd.to_datetime(local.loc[rows])
        localized = values.dt.tz_localize(str(zone), ambiguous="NaT", nonexistent="NaT")
        result.loc[rows] = localized.dt.tz_convert("UTC")
    return result


def _to_local(utc: pd.Series, zones: pd.Series) -> pd.Series:
    result = pd.Series(pd.NaT, index=utc.index, dtype="datetime64[ns]")
    for zone, rows in utc.groupby(zones).groups.items():
        result.loc[rows] = utc.loc[rows].dt.tz_convert(str(zone)).dt.tz_localize(None)
    return result


def resolve_flights(
    frame: EntityFrame,
    airports: AirportIndex,
    rules: IngestionRules,
    vocabulary: Vocabulary,
    log: RejectLog,
    origin: str,
) -> pd.DataFrame:
    # References
    for end in ("origin", "destination"):
        refs = frame.data[end].map(lambda v: airports.find(str(v)))
        frame.data[f"{end}_ref"] = refs
        frame.drop(
            refs.isna(),
            log,
            RejectCode.UNKNOWN_REFERENCE,
            end,
            f"'{end}' does not match any airport code, airport name or single-airport city",
        )
    data = frame.data
    same = data["origin_ref"].map(lambda r: r.id) == data["destination_ref"].map(lambda r: r.id)
    frame.drop(
        same,
        log,
        RejectCode.INCONSISTENT,
        "destination",
        "origin and destination are the same airport",
    )
    data = frame.data
    origin_tz = data["origin_ref"].map(lambda r: r.timezone)
    dest_tz = data["destination_ref"].map(lambda r: r.timezone)

    # Departure: explicit instant, local date-time, or date + clock time.
    departure_local = pd.to_datetime(data["departure_local"])
    combined = pd.to_datetime(data["departure_date"]) + pd.to_timedelta(data["departure_clock"])
    departure_local = departure_local.fillna(combined)
    departure_at = _localize(departure_local, origin_tz)
    explicit = _utc_column(data, "departure_local__utc")
    if explicit is not None:
        departure_at = explicit.fillna(departure_at)
    frame.data["departure_at"] = departure_at
    frame.drop(
        departure_at.isna(),
        log,
        RejectCode.MISSING_REQUIRED,
        "departure_local",
        "a departure date and time is required (and must exist in the airport's timezone)",
    )
    data = frame.data
    departure_at = data["departure_at"]
    origin_tz, dest_tz = origin_tz.loc[data.index], dest_tz.loc[data.index]

    # Arrival: explicit local time, else clock time after departure, else departure + duration.
    arrival_at = _localize(pd.to_datetime(data["arrival_local"]), dest_tz)
    explicit_arr = _utc_column(data, "arrival_local__utc")
    if explicit_arr is not None:
        arrival_at = explicit_arr.fillna(arrival_at)
    clock = pd.to_timedelta(data["arrival_clock"])
    needs_clock = arrival_at.isna() & clock.notna()
    if needs_clock.any():
        base = _to_local(departure_at[needs_clock], origin_tz[needs_clock]).dt.normalize()
        candidate = _localize(base + clock[needs_clock], dest_tz[needs_clock])
        for _ in range(2):  # roll over midnight (at most two days)
            early = candidate.notna() & (candidate <= departure_at[needs_clock])
            candidate = candidate.where(~early, candidate + timedelta(days=1))
        arrival_at = arrival_at.where(~needs_clock, candidate)
        log.adjust("ARRIVAL_FROM_CLOCK_TIME", int(needs_clock.sum()))
    supplied = pd.to_numeric(data["duration_minutes"], errors="coerce")
    needs_duration = arrival_at.isna() & supplied.notna()
    if needs_duration.any():
        arrival_at = arrival_at.where(
            ~needs_duration, departure_at + pd.to_timedelta(supplied, unit="min")
        )
        log.adjust("ARRIVAL_FROM_DURATION", int(needs_duration.sum()))
    frame.data["arrival_at"] = arrival_at
    frame.drop(
        arrival_at.isna(),
        log,
        RejectCode.MISSING_REQUIRED,
        "arrival_local|arrival_clock|duration_minutes",
        "an arrival time or a duration is required",
    )
    data = frame.data
    duration = (data["arrival_at"] - data["departure_at"]).dt.total_seconds() // 60
    frame.drop(
        duration <= 0,
        log,
        RejectCode.INCONSISTENT,
        "arrival_local",
        "arrival is not after departure",
    )
    frame.drop(
        duration > rules.max_flight_duration_minutes,
        log,
        RejectCode.INCONSISTENT,
        "duration_minutes",
        f"journey is longer than {rules.max_flight_duration_minutes} minutes",
    )
    data = frame.data
    data["duration_minutes_computed"] = (
        (data["arrival_at"] - data["departure_at"]).dt.total_seconds() // 60
    ).astype("int64")
    supplied = pd.to_numeric(data["duration_minutes"], errors="coerce")
    mismatch = (
        supplied - data["duration_minutes_computed"]
    ).abs() > rules.duration_mismatch_minutes
    log.adjust("DURATION_MISMATCH", int(mismatch.fillna(False).sum()))
    data["duration_minutes"] = data["duration_minutes_computed"]
    origin_tz, dest_tz = origin_tz.loc[data.index], dest_tz.loc[data.index]
    data["departure_local"] = _to_local(data["departure_at"], origin_tz)
    data["arrival_local"] = _to_local(data["arrival_at"], dest_tz)

    # Product attributes
    cabins = vocabulary.cabin_index()
    cabin = data["cabin_class"].map(
        lambda v: (
            None if v is None or pd.isna(v) else cabins.get(normalize_text(str(v)), slugify(str(v)))
        )
    )
    log.adjust("DEFAULT_CABIN_CLASS", int(cabin.isna().sum()))
    data["cabin_class"] = cabin.fillna(rules.default_cabin_class)
    seats = pd.to_numeric(data["seat_capacity"], errors="coerce")
    log.adjust("DEFAULT_SEAT_CAPACITY", int(seats.isna().sum()))
    data["seat_capacity"] = seats.fillna(rules.default_seat_capacity).astype("int64")
    data["stops"] = pd.to_numeric(data["stops"], errors="coerce").fillna(0).astype("int64")

    code = data["airline_code"].astype("object")
    number = data["flight_number"].astype(str).str.replace(r"[^A-Za-z0-9]", "", regex=True)
    digits_only = number.str.fullmatch(r"\d+") & code.notna()
    data["flight_number"] = number.where(~digits_only, code.astype(str) + number)
    frame.data = data

    _currency(frame, log, rules.default_currency)
    _minor_units(frame, "fare", log, "fare_minor")
    data = frame.data
    log.adjust("FARE_MISSING_BROWSE_ONLY", int(data["fare_minor"].isna().sum()))

    data["origin_airport_id"] = data["origin_ref"].map(lambda r: r.id)
    data["destination_airport_id"] = data["destination_ref"].map(lambda r: r.id)
    natural = (
        data["flight_number"]
        + "|"
        + data["departure_local"].dt.strftime("%Y-%m-%dT%H:%M")
        + "|"
        + data["origin_ref"].map(lambda r: r.code)
        + "|"
        + data["cabin_class"]
    )
    data["source_key"] = (
        data["source_key"].astype("object").where(data["source_key"].notna(), natural)
    )
    frame.data = data
    _dedupe(frame, "source_key", log)
    data = frame.data
    data["id"] = data["source_key"].map(lambda k: catalog_id("flight", k))
    data["origin"] = origin
    return data


# --------------------------------------------------------------------------------------------
# Hotels and room types


def _clock_text(value: Any) -> str | None:
    if _missing(value) or pd.isna(value):
        return None
    minutes = int(pd.Timedelta(value).total_seconds() // 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def resolve_hotels(
    frame: EntityFrame,
    cities: CityRegistry,
    rules: IngestionRules,
    vocabulary: Vocabulary,
    log: RejectLog,
    origin: str,
) -> pd.DataFrame:
    data = frame.data
    data["country"] = data["country"].map(_country)
    natural = data["name"].map(normalize_text) + "|" + data["city"].map(normalize_text)
    data["source_key"] = (
        data["source_key"].astype("object").where(data["source_key"].notna(), natural)
    )
    frame.data = data
    _dedupe(frame, "source_key", log)
    data = frame.data

    data["city_key"] = [
        cities.resolve(
            row["city"], row["country"], timezone=None, point=_point(row), from_airport=False
        )
        for _, row in data.iterrows()
    ]
    amenity_index = vocabulary.amenity_index()

    def amenities(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        codes = {amenity_index.get(normalize_text(v), slugify(v)) for v in value}
        return sorted(c[:48] for c in codes if c)

    data["amenity_codes"] = data["amenities"].map(amenities)
    data["check_in_time"] = data["check_in_time"].map(_clock_text)
    data["check_out_time"] = data["check_out_time"].map(_clock_text)
    for column in ("star_rating", "guest_rating"):
        data[column] = pd.to_numeric(data[column], errors="coerce").round(1)
    frame.data = data
    _currency(frame, log, rules.default_currency)
    _minor_units(frame, "nightly_rate", log, "nightly_rate_minor")
    data = frame.data
    data["id"] = data["source_key"].map(lambda k: catalog_id("hotel", k))
    data["city_name"] = data["city"]
    data["origin"] = origin
    return data


def resolve_room_types(
    frame: EntityFrame | None,
    hotels: pd.DataFrame,
    rules: IngestionRules,
    vocabulary: Vocabulary,
    log: RejectLog,
    origin: str,
) -> pd.DataFrame:
    """Room types from the source, plus one derived room type for every hotel that has none."""
    hotel_ids = dict(zip(hotels["source_key"], hotels["id"], strict=True))
    hotel_currency = dict(zip(hotels["source_key"], hotels["currency"], strict=True))
    parts: list[pd.DataFrame] = []

    if frame is not None:
        data = frame.data
        data["hotel_key"] = data["hotel_key"].astype(str)
        frame.drop(
            ~data["hotel_key"].isin(hotel_ids),
            log,
            RejectCode.UNKNOWN_REFERENCE,
            "hotel_key",
            "room type refers to a hotel that is not in this import",
        )
        data = frame.data
        natural = data["hotel_key"] + "|" + data["name"].map(normalize_text)
        data["source_key"] = (
            data["source_key"].astype("object").where(data["source_key"].notna(), natural)
        )
        frame.data = data
        _dedupe(frame, "source_key", log)
        data = frame.data
        boards = vocabulary.board_index()
        data["board"] = data["board"].map(
            lambda v: (
                None
                if v is None or pd.isna(v)
                else boards.get(normalize_text(str(v)), slugify(str(v)))
            )
        )
        occupancy = pd.to_numeric(data["max_occupancy"], errors="coerce")
        log.adjust("DEFAULT_MAX_OCCUPANCY", int(occupancy.isna().sum()))
        data["max_occupancy"] = occupancy.fillna(rules.default_max_occupancy).astype("int64")
        rooms = pd.to_numeric(data["total_rooms"], errors="coerce")
        log.adjust("DEFAULT_ROOMS_PER_TYPE", int(rooms.isna().sum()))
        data["total_rooms"] = rooms.fillna(rules.default_rooms_per_type).astype("int64")
        frame.data = data
        _currency(
            frame, log, rules.default_currency, fallback=data["hotel_key"].map(hotel_currency)
        )
        _minor_units(frame, "nightly_rate", log, "nightly_rate_minor")
        data = frame.data
        data["hotel_id"] = data["hotel_key"].map(hotel_ids)
        data["origin"] = origin
        data["refundable"] = data["refundable"].astype("object")
        parts.append(data)

    covered = set(parts[0]["hotel_key"]) if parts else set()
    bare = hotels[~hotels["source_key"].isin(covered)]
    if len(bare):
        rooms = pd.to_numeric(bare["total_rooms"], errors="coerce")
        derived = pd.DataFrame(
            {
                "source_key": bare["source_key"] + "|default",
                "hotel_key": bare["source_key"],
                "hotel_id": bare["id"],
                "name": rules.default_room_name,
                "max_occupancy": rules.default_max_occupancy,
                "bed_type": None,
                "board": None,
                "refundable": None,
                "nightly_rate_minor": bare["nightly_rate_minor"],
                "currency": bare["currency"],
                "total_rooms": rooms.fillna(rules.default_rooms_per_type).astype("int64"),
                "origin": DataOrigin.DERIVED.value,
            }
        )
        log.adjust("DERIVED_ROOM_TYPE", len(derived))
        parts.append(derived)

    if not parts:
        return pd.DataFrame()
    result = pd.concat(parts, ignore_index=True)
    log.adjust("RATE_MISSING_BROWSE_ONLY", int(result["nightly_rate_minor"].isna().sum()))
    result["id"] = result["source_key"].map(lambda k: catalog_id("room_type", k))
    return result
