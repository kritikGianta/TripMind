"""Distance of a stay from its city centre."""

from __future__ import annotations

import math

from app.modules.catalog.models import City, Hotel


def distance_km(hotel: Hotel, city: City) -> float | None:
    if (
        hotel.latitude is None
        or hotel.longitude is None
        or city.latitude is None
        or city.longitude is None
    ):
        return None
    lat1, lon1 = math.radians(hotel.latitude), math.radians(hotel.longitude)
    lat2, lon2 = math.radians(city.latitude), math.radians(city.longitude)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return round(6371.0 * 2 * math.asin(math.sqrt(h)), 1)
