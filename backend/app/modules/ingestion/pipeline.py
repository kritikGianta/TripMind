"""The ingestion pipeline without side effects:

    read -> profile -> extract (map, parse, validate) -> resolve -> prepared dataset

Writing to the database is the service's job (`service.py`), so the pipeline can be run as a dry
run, in tests, or from the CLI with identical results.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from app.modules.catalog.models import DataOrigin
from app.modules.ingestion.anomalies import flag_fare_anomalies
from app.modules.ingestion.extract import EntityFrame, extract
from app.modules.ingestion.mapping import DatasetMapping
from app.modules.ingestion.profiler import profile_table
from app.modules.ingestion.rejects import RejectLog
from app.modules.ingestion.resolve import (
    AirportIndex,
    AirportRef,
    CityRegistry,
    airport_refs,
    resolve_airports,
    resolve_flights,
    resolve_hotels,
    resolve_room_types,
)
from app.modules.ingestion.rules import IngestionRules, Vocabulary
from app.modules.ingestion.schedules import expand_schedules
from app.modules.ingestion.sources import DatasetSource, Table
from app.modules.ingestion.targets import EntityName


@dataclass
class PreparedDataset:
    mapping: DatasetMapping
    frames: dict[EntityName, EntityFrame]
    log: RejectLog
    profile: list[dict[str, Any]]
    cities: pd.DataFrame | None = None
    airports: pd.DataFrame | None = None
    flights: pd.DataFrame | None = None
    hotels: pd.DataFrame | None = None
    room_types: pd.DataFrame | None = None
    rejected_rows: dict[str, int] = field(default_factory=dict)

    def entity_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {}
        for entity, frame in self.frames.items():
            rejected = len({r.row_number for r in self.log.rejects if r.entity == entity})
            counts[entity] = {
                "read": frame.rows_read,
                "accepted": frame.rows_read - rejected,
                "rejected": rejected,
            }
        if self.room_types is not None and "room_types" not in counts:
            derived = len(self.room_types)
            counts["room_types"] = {"read": 0, "accepted": derived, "rejected": 0}
        if self.cities is not None:
            counts["cities"] = {"read": 0, "accepted": len(self.cities), "rejected": 0}
        return counts

    def reject_ratio_exceeded(self, limit: float) -> dict[str, float]:
        """Entities whose share of rejected rows is above `limit`."""
        over: dict[str, float] = {}
        for entity, c in self.entity_counts().items():
            if c["read"] and c["rejected"] / c["read"] > limit:
                over[entity] = round(c["rejected"] / c["read"], 3)
        return over

    def travel_window(self) -> dict[str, str] | None:
        if self.flights is None or self.flights.empty:
            return None
        local = self.flights["departure_local"]
        return {
            "first_departure": local.min().date().isoformat(),
            "last_departure": local.max().date().isoformat(),
        }


def prepare(
    source: DatasetSource,
    mapping: DatasetMapping,
    rules: IngestionRules,
    vocabulary: Vocabulary,
    *,
    catalog_airports: Callable[[], list[AirportRef]],
    today: date | None = None,
) -> PreparedDataset:
    log = RejectLog()
    frames = extract(source, mapping, log)
    profile = [
        profile_table(Table(frame.table, frame.raw, frame.encoding)) | {"entity": entity}
        for entity, frame in frames.items()
    ]
    prepared = PreparedDataset(mapping=mapping, frames=frames, log=log, profile=profile)
    origin = DataOrigin(mapping.origin).value
    cities = CityRegistry(rules, vocabulary, log)

    if "airports" in frames:
        prepared.airports = resolve_airports(frames["airports"], cities, rules, log, origin)
    if "flights" in frames:
        refs = (
            airport_refs(prepared.airports) if prepared.airports is not None else catalog_airports()
        )
        expand_schedules(
            frames["flights"],
            log,
            today=today or date.today(),
            horizon_days=rules.schedule_horizon_days,
        )
        prepared.flights = resolve_flights(
            frames["flights"], AirportIndex(refs, vocabulary), rules, vocabulary, log, origin
        )
        flag_fare_anomalies(prepared.flights, log)  # warnings only; nothing is rejected
    if "hotels" in frames:
        prepared.hotels = resolve_hotels(frames["hotels"], cities, rules, vocabulary, log, origin)
        prepared.room_types = resolve_room_types(
            frames.get("room_types"), prepared.hotels, rules, vocabulary, log, origin
        )

    if cities.cities:
        cities.assign_missing_timezones()
        prepared.cities = cities.frame(DataOrigin.DERIVED.value)
        city_ids = dict(zip(prepared.cities["source_key"], prepared.cities["id"], strict=True))
        names = dict(zip(prepared.cities["source_key"], prepared.cities["name"], strict=True))
        for frame in (prepared.airports, prepared.hotels):
            if frame is not None:
                frame["city_id"] = frame["city_key"].map(city_ids)
                frame["city_name"] = frame["city_key"].map(names)
    return prepared
