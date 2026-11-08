"""Per-traveller preference model: what kind of stay this traveller tends to choose.

Each signed-in traveller with enough activity gets a small logistic regression over readable
stay features (stars, guest rating, value for the city, distance from the centre, amenities).
Positives are stays they viewed, saved or booked (weighted 1, 3 and 5); negatives are stays they
did not touch, sampled across the catalog with a seed derived from the user ID so training is
reproducible. Features are centred on each city's average, so the model learns how a chosen stay
differs from its neighbours rather than which city it is in (sampling negatives only from the same
small city would label nearly every unseen stay "disliked", including the ones they would love;
see models/preference_model). The weights are stored per user and only adjust the "Recommended"
order; the traveller can see what was learned and reset it.

This module is pure: the search module builds the feature vectors from the catalog.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PREFERENCE_AMENITIES = (
    "pool",
    "spa",
    "gym",
    "breakfast",
    "restaurant",
    "bar",
    "parking",
    "beach_access",
    "family_rooms",
    "airport_shuttle",
    "pet_friendly",
    "business_centre",
)
FEATURES = (
    "stars",
    "rating",
    "value",
    "near_centre",
    *(f"amenity_{a}" for a in PREFERENCE_AMENITIES),
)
READABLE = {
    "stars": "more stars",
    "rating": "high guest ratings",
    "value": "good value for the city",
    "near_centre": "close to the centre",
    **{f"amenity_{a}": a.replace("_", " ") for a in PREFERENCE_AMENITIES},
}
INTERACTION_WEIGHTS = {"view": 1.0, "save": 3.0, "book": 5.0}
MODEL_VERSION = "logreg-v1"


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    weights: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    intercept: Mapped[float] = mapped_column(Float, nullable=False)
    positives: Mapped[int] = mapped_column(Integer, nullable=False)
    interactions: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class Fitted:
    weights: dict[str, float]
    intercept: float
    positives: int


def feature_vector(
    *,
    stars: float | None,
    rating: float | None,
    value: float | None,
    distance_km: float | None,
    amenities: set[str],
) -> dict[str, float]:
    """All features scaled to 0..1 so the weights are comparable and readable."""
    return {
        "stars": (stars or 0.0) / 5,
        "rating": (rating or 0.0) / 10,
        "value": value if value is not None else 0.5,
        "near_centre": 1 - min(distance_km if distance_km is not None else 7.5, 15.0) / 15,
        **{f"amenity_{a}": float(a in amenities) for a in PREFERENCE_AMENITIES},
    }


def fit(
    positives: dict[uuid.UUID, float],
    pool: dict[uuid.UUID, dict[str, float]],
    *,
    user_id: uuid.UUID,
    negatives_per_positive: int,
    min_positive_hotels: int,
) -> Fitted | None:
    """Fit on weighted positives against sampled untouched stays from `pool`."""
    from sklearn.linear_model import LogisticRegression

    known = [h for h in positives if h in pool]
    candidates = sorted(h for h in pool if h not in positives)
    if len(known) < min_positive_hotels or not candidates:
        return None
    rng = random.Random(user_id.int)  # noqa: S311 - reproducible sampling, not security
    negatives = rng.sample(candidates, min(len(candidates), negatives_per_positive * len(known)))
    rows = [[pool[h][f] for f in FEATURES] for h in known + negatives]
    labels = [1] * len(known) + [0] * len(negatives)
    # Each negative carries the average positive weight, so both sides count equally overall.
    mean_weight = sum(positives[h] for h in known) / len(known)
    weights = [positives[h] for h in known] + [mean_weight * len(known) / len(negatives)] * len(
        negatives
    )
    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(rows, labels, sample_weight=weights)
    return Fitted(
        weights={f: round(float(w), 4) for f, w in zip(FEATURES, model.coef_[0], strict=True)},
        intercept=round(float(model.intercept_[0]), 4),
        positives=len(known),
    )


def probability(pref: UserPreference | Fitted, vector: dict[str, float]) -> float:
    z = pref.intercept + sum(w * vector.get(f, 0.0) for f, w in pref.weights.items())
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))


def reasons(pref: UserPreference | Fitted, vector: dict[str, float], top: int = 2) -> list[str]:
    """The features that raise this stay's score most, in plain words."""
    contributions = sorted(
        ((w * vector.get(f, 0.0), f) for f, w in pref.weights.items()), reverse=True
    )
    return [READABLE[f] for c, f in contributions[:top] if c > 0.15]


def learned(pref: UserPreference) -> list[dict[str, Any]]:
    """What the traveller tends to like (positive weights) or avoid, strongest first."""
    ranked = sorted(pref.weights.items(), key=lambda kv: -abs(kv[1]))
    return [
        {
            "feature": f,
            "label": READABLE[f],
            "weight": w,
            "direction": "likes" if w > 0 else "avoids",
        }
        for f, w in ranked
        if abs(w) >= 0.3
    ][:6]
