"""Feature definitions shared by serving code and the training notebooks.

The notebooks (models/<name>/*.ipynb) compute exactly these features from their public datasets
and write the same names into the model card; the registry refuses a model whose features differ.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ── Hotel ranker (trained on Expedia "Personalize Hotel Search", Kaggle) ─────────────────────────
HOTEL_RANKER_FEATURES = (
    "star_rating",  # 0-5
    "review_score",  # 0-5 (TripMind stores 0-10, divided by 2)
    "log_price_usd",  # log1p of nightly price in USD
    "price_rank_pct",  # 0 cheapest .. 1 most expensive within this search
    "star_rank_pct",  # 0 lowest .. 1 highest star rating within this search
    "length_of_stay",
    "adults",
    "rooms",
    "booking_window_days",
)


@dataclass(frozen=True)
class HotelRow:
    star_rating: float
    review_score: float
    nightly_usd: float


def hotel_ranker_rows(
    rows: list[HotelRow], nights: int, adults: int, rooms: int, booking_window_days: int
) -> list[dict[str, float]]:
    def pct(values: list[float], value: float) -> float:
        if len(values) < 2:
            return 0.5
        return sum(v < value for v in values) / (len(values) - 1)

    prices = [r.nightly_usd for r in rows]
    stars = [r.star_rating for r in rows]
    return [
        {
            "star_rating": r.star_rating,
            "review_score": r.review_score,
            "log_price_usd": math.log1p(max(r.nightly_usd, 0.0)),
            "price_rank_pct": pct(prices, r.nightly_usd),
            "star_rank_pct": pct(stars, r.star_rating),
            "length_of_stay": float(nights),
            "adults": float(adults),
            "rooms": float(rooms),
            "booking_window_days": float(max(booking_window_days, 0)),
        }
        for r in rows
    ]


# ── Fare estimator (trained on "Flight Price Prediction", Indian domestic fares, Kaggle) ─────────
FARE_ESTIMATOR_FEATURES = (
    "distance_km",
    "duration_minutes",
    "stops",
    "days_left",
    "departure_hour",
    "business",  # 1 for business class
)

# The model only knows domestic Indian routes up to this distance; anything else is not scored.
FARE_ESTIMATOR_MAX_KM = 2000.0  # longest training route (Delhi-Chennai) is about 1,760 km


def fare_row(
    distance_km: float,
    duration_minutes: int,
    stops: int,
    days_left: int,
    departure_hour: int,
    business: bool,
) -> dict[str, float]:
    return {
        "distance_km": distance_km,
        "duration_minutes": float(duration_minutes),
        "stops": float(min(stops, 2)),
        "days_left": float(min(max(days_left, 1), 50)),
        "departure_hour": float(departure_hour),
        "business": 1.0 if business else 0.0,
    }


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))
