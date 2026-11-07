from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Airport, City, Flight, Hotel, RoomType


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for name, model in (
            ("cities", City),
            ("airports", Airport),
            ("flights", Flight),
            ("hotels", Hotel),
            ("room_types", RoomType),
        ):
            result[name] = int(
                self._session.scalar(
                    select(func.count()).select_from(model).where(model.is_active.is_(True))
                )
                or 0
            )
        return result

    def origin_counts(self) -> dict[str, int]:
        """Active rows by provenance across the bookable tables."""
        totals: dict[str, int] = {}
        for model in (Flight, Hotel, RoomType):
            rows = self._session.execute(
                select(model.origin, func.count())
                .where(model.is_active.is_(True))
                .group_by(model.origin)
            )
            for origin, count in rows:
                totals[origin] = totals.get(origin, 0) + int(count)
        return totals

    def flight_window(self) -> tuple[datetime, datetime] | None:
        first, last = self._session.execute(
            select(func.min(Flight.departure_local), func.max(Flight.departure_local)).where(
                Flight.is_active.is_(True)
            )
        ).one()
        if first is None or last is None:
            return None
        return first, last

    def active_airports(self) -> list[tuple[Airport, str]]:
        """Active airports with their city's source key."""
        rows = self._session.execute(
            select(Airport, City.source_key)
            .join(City, City.id == Airport.city_id)
            .where(Airport.is_active.is_(True))
        )
        return [(airport, city_key) for airport, city_key in rows.tuples()]
