"""Location lookup for search boxes: airports (for flights) and cities (for stays)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.modules.catalog.models import Airport, AirportServedCity, City
from app.modules.catalog.vocabulary import Vocabulary, normalize_text
from app.modules.search.schemas import LocationOut

_MIN_FUZZY = 80


@dataclass(frozen=True)
class _Candidate:
    location: LocationOut
    keys: tuple[str, ...]


def _norm(text: str) -> str:
    return normalize_text(text)


class LocationService:
    def __init__(self, session: Session, vocabulary: Vocabulary | None = None) -> None:
        self._session = session
        # canonical city -> other names travellers use for it ("bengaluru" -> ["bangalore"])
        self._aliases: dict[str, list[str]] = {}
        for alias, canonical in (vocabulary.city_alias_index() if vocabulary else {}).items():
            if alias != canonical:
                self._aliases.setdefault(canonical, []).append(alias)

    def _city_keys(self, name: str) -> tuple[str, ...]:
        norm = _norm(name)
        return (norm, *self._aliases.get(norm, []))

    def _airports(self) -> list[_Candidate]:
        rows = self._session.execute(
            select(Airport, City)
            .join(City, City.id == Airport.city_id)
            .where(Airport.is_active.is_(True))
        )
        return [
            _Candidate(
                LocationOut(
                    kind="airport",
                    value=a.code,
                    code=a.code,
                    name=a.name,
                    city_name=c.name,
                    country=c.country,
                    label=f"{c.name} ({a.code}) · {a.name}",
                ),
                (a.code.lower(), *self._city_keys(c.name), _norm(a.name)),
            )
            for a, c in rows
        ]

    def _cities(self) -> list[_Candidate]:
        cities = self._session.scalars(select(City).where(City.is_active.is_(True))).all()
        return [
            _Candidate(
                LocationOut(
                    kind="city",
                    value=str(c.id),
                    name=c.name,
                    city_name=c.name,
                    country=c.country,
                    label=f"{c.name}, {c.country}" if c.country else c.name,
                ),
                self._city_keys(c.name),
            )
            for c in cities
        ]

    def search(self, query: str, kind: str, limit: int) -> list[LocationOut]:
        q = _norm(query)
        candidates = self._airports() if kind == "airport" else self._cities()
        if not q:
            return sorted((c.location for c in candidates), key=lambda loc: loc.label)[:limit]
        scored: list[tuple[int, str, LocationOut]] = []
        for candidate in candidates:
            keys = candidate.keys
            if q in keys:
                score = 300  # exact code, city name or alias
            elif any(k.startswith(q) for k in keys):
                score = 200
            elif any(q in k for k in keys):
                score = 150
            else:
                score = max(int(fuzz.partial_ratio(q, k)) for k in keys)
                if score < _MIN_FUZZY:
                    continue
            scored.append((score, candidate.location.label, candidate.location))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [location for _, _, location in scored[:limit]]

    def airports_for(self, value: str) -> list[Airport]:
        """An airport code, or a city ID meaning every airport in that city."""
        code = value.strip().upper()
        airport = self._session.scalar(
            select(Airport).where(Airport.code == code, Airport.is_active.is_(True))
        )
        if airport is not None:
            return [airport]
        try:
            city_id = uuid.UUID(value)
        except ValueError:
            city_id = None
        if city_id is not None:
            # The airports that serve the city (Kyoto has none of its own: KIX serves it), as the
            # data lists them; otherwise the airports located in the city.
            served = self._session.scalars(
                select(Airport)
                .join(AirportServedCity, AirportServedCity.airport_id == Airport.id)
                .where(AirportServedCity.city_id == city_id, Airport.is_active.is_(True))
            ).all()
            airports = (
                served
                or self._session.scalars(
                    select(Airport).where(Airport.city_id == city_id, Airport.is_active.is_(True))
                ).all()
            )
            if airports:
                return list(airports)
        raise NotFound(f"No airport matches '{value}'.", code="LOCATION_NOT_FOUND")

    def city(self, value: str) -> City:
        try:
            city_id = uuid.UUID(value)
        except ValueError as exc:
            raise NotFound("Unknown city.", code="LOCATION_NOT_FOUND") from exc
        city = self._session.get(City, city_id)
        if city is None or not city.is_active:
            raise NotFound("Unknown city.", code="LOCATION_NOT_FOUND")
        return city
