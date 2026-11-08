"""Per-traveller preference model: fitting, scoring and explanations."""

from __future__ import annotations

import uuid

from app.modules.ml.preferences import FEATURES, feature_vector, fit, probability, reasons

USER = uuid.UUID("00000000-0000-0000-0000-000000000042")


def stay(i: int, *, pool: bool, stars: float = 3) -> tuple[uuid.UUID, dict[str, float]]:
    vector = feature_vector(
        stars=stars,
        rating=7.5 + (i % 3) * 0.3,
        value=(i % 10) / 10,
        distance_km=float(i % 12),
        amenities={"pool", "wifi"} if pool else {"wifi"},
    )
    return uuid.UUID(int=i + 1), vector


def test_features_are_scaled_and_complete() -> None:
    vector = feature_vector(stars=5, rating=10, value=1, distance_km=0, amenities={"spa"})
    assert set(vector) == set(FEATURES) and all(0 <= v <= 1 for v in vector.values())
    assert vector["amenity_spa"] == 1 and vector["amenity_pool"] == 0
    assert (
        feature_vector(stars=None, rating=None, value=None, distance_km=None, amenities=set())[
            "near_centre"
        ]
        == 0.5
    )


def test_needs_enough_stays() -> None:
    pool = dict(stay(i, pool=i % 2 == 0) for i in range(30))
    two = {h: 1.0 for h in list(pool)[:2]}
    assert fit(two, pool, user_id=USER, negatives_per_positive=4, min_positive_hotels=3) is None


def test_learns_a_taste_for_pools_reproducibly() -> None:
    pool = dict(stay(i, pool=i % 2 == 0) for i in range(60))
    liked = {h: 3.0 for h, v in pool.items() if v["amenity_pool"] == 1.0}
    first = fit(liked, pool, user_id=USER, negatives_per_positive=4, min_positive_hotels=3)
    again = fit(liked, pool, user_id=USER, negatives_per_positive=4, min_positive_hotels=3)
    assert first is not None and first == again  # seeded by the user ID
    assert first.weights["amenity_pool"] > 0.5
    with_pool, without = stay(999, pool=True)[1], stay(999, pool=False)[1]
    assert probability(first, with_pool) > probability(first, without)
    assert "pool" in reasons(first, with_pool)
    assert "pool" not in reasons(first, without)
