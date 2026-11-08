"""Preference model glue: stay features from the catalog, training, and what search needs.

The features for a stay are computed the same way for training and for ranking, from the
catalog (not from one search's filtered results), so a stay always has the same vector.
"""

from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import datetime

import structlog
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import Settings
from app.db.session import get_session_factory
from app.modules.catalog.models import City, Hotel, HotelAmenity, RoomType
from app.modules.ml.interactions import HotelInteraction
from app.modules.ml.preferences import (
    FEATURES,
    INTERACTION_WEIGHTS,
    MODEL_VERSION,
    UserPreference,
    feature_vector,
    fit,
)
from app.modules.search.geo import distance_km as _distance_km
from app.modules.search.pricing import Converter, load_pricing_rules, rules_section

log = structlog.get_logger(__name__)


class PreferenceRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_positive_hotels: int = Field(default=3, ge=1)
    negatives_per_positive: int = Field(default=4, ge=1)
    blend: float = Field(default=0.3, ge=0, le=1, description="Share of the preference score")
    retrain_minutes: int = Field(default=60, ge=1)
    extra_cities: int = Field(default=20, ge=0, description="Other cities to draw negatives from")


def load_preference_rules(settings: Settings) -> PreferenceRules:
    return PreferenceRules.model_validate(rules_section(settings.config_dir, "preferences"))


def hotel_features(
    session: Session, converter: Converter, city_ids: set[uuid.UUID]
) -> dict[uuid.UUID, dict[str, float]]:
    hotels = list(
        session.scalars(select(Hotel).where(Hotel.city_id.in_(city_ids), Hotel.is_active.is_(True)))
    )
    if not hotels:
        return {}
    ids = [h.id for h in hotels]
    cities = {c.id: c for c in session.scalars(select(City).where(City.id.in_(city_ids)))}
    amenities: dict[uuid.UUID, set[str]] = defaultdict(set)
    for hotel_id, amenity in session.execute(
        select(HotelAmenity.hotel_id, HotelAmenity.amenity).where(HotelAmenity.hotel_id.in_(ids))
    ):
        amenities[hotel_id].add(amenity)
    cheapest: dict[uuid.UUID, int] = {}
    for room in session.scalars(
        select(RoomType).where(
            RoomType.hotel_id.in_(ids),
            RoomType.is_active.is_(True),
            RoomType.nightly_rate_minor.is_not(None),
        )
    ):
        shown = converter.to_display(room.nightly_rate_minor or 0, room.currency)
        if shown is not None:
            cheapest[room.hotel_id] = min(
                cheapest.get(room.hotel_id, shown.amount_minor), shown.amount_minor
            )
    # Value: where the stay's cheapest rate sits among its city's stays (cheapest = 1).
    value: dict[uuid.UUID, float] = {}
    by_city: dict[uuid.UUID, list[tuple[int, uuid.UUID]]] = defaultdict(list)
    for hotel in hotels:
        if hotel.id in cheapest:
            by_city[hotel.city_id].append((cheapest[hotel.id], hotel.id))
    for prices in by_city.values():
        prices.sort()
        for rank, (_, hotel_id) in enumerate(prices):
            value[hotel_id] = 1.0 if len(prices) == 1 else 1 - rank / (len(prices) - 1)
    raw = {
        h.id: feature_vector(
            stars=h.star_rating,
            rating=h.guest_rating,
            value=value.get(h.id),
            distance_km=_distance_km(h, cities[h.city_id]) if h.city_id in cities else None,
            amenities=amenities[h.id],
        )
        for h in hotels
    }
    # Centre on each city's average: "how this stay differs from the others in its city".
    members: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for h in hotels:
        members[h.city_id].append(h.id)
    centred: dict[uuid.UUID, dict[str, float]] = {}
    for ids_in_city in members.values():
        means = {f: sum(raw[i][f] for i in ids_in_city) / len(ids_in_city) for f in FEATURES}
        for i in ids_in_city:
            centred[i] = {f: raw[i][f] - means[f] for f in FEATURES}
    return centred


def train_user(
    session: Session,
    converter: Converter,
    rules: PreferenceRules,
    user_id: uuid.UUID,
    now: datetime,
) -> UserPreference | None:
    """Refit one traveller's model; None (model left as it was) when there is too little."""
    rows = list(
        session.execute(
            select(HotelInteraction.hotel_id, HotelInteraction.kind).where(
                HotelInteraction.user_id == user_id
            )
        )
    )
    positives: dict[uuid.UUID, float] = defaultdict(float)
    for hotel_id, kind in rows:
        positives[hotel_id] += INTERACTION_WEIGHTS.get(kind, 0.0)
    own = set(session.scalars(select(Hotel.city_id).where(Hotel.id.in_(list(positives)))))
    # Negatives come from the traveller's cities and a reproducible sample of others.
    others = sorted(
        set(session.scalars(select(Hotel.city_id).where(Hotel.is_active.is_(True)).distinct()))
        - own
    )
    sample = random.Random(user_id.int).sample(others, min(len(others), rules.extra_cities))  # noqa: S311
    pool = hotel_features(session, converter, own | set(sample))
    fitted = fit(
        dict(positives),
        pool,
        user_id=user_id,
        negatives_per_positive=rules.negatives_per_positive,
        min_positive_hotels=rules.min_positive_hotels,
    )
    if fitted is None:
        return None
    existing = session.get(UserPreference, user_id)
    if existing is None:
        existing = UserPreference(user_id=user_id)
        session.add(existing)
    existing.weights, existing.intercept = fitted.weights, fitted.intercept
    existing.positives, existing.interactions = fitted.positives, len(rows)
    existing.version, existing.trained_at = MODEL_VERSION, now
    return existing


def train_due(session: Session, converter: Converter, rules: PreferenceRules, now: datetime) -> int:
    """Retrain travellers with interactions newer than their model (or no model yet)."""
    latest = (
        select(HotelInteraction.user_id, func.max(HotelInteraction.occurred_at).label("last"))
        .group_by(HotelInteraction.user_id)
        .subquery()
    )
    due = session.execute(
        select(latest.c.user_id)
        .outerjoin(UserPreference, UserPreference.user_id == latest.c.user_id)
        .where((UserPreference.user_id.is_(None)) | (latest.c.last > UserPreference.trained_at))
        .limit(500)
    ).scalars()
    trained = 0
    for user_id in list(due):
        pref = train_user(session, converter, rules, user_id, now)
        session.commit()
        trained += pref is not None
    return trained


def forget(session: Session, user_id: uuid.UUID) -> None:
    """Reset personalisation: delete the model and the activity it learned from."""
    session.execute(delete(UserPreference).where(UserPreference.user_id == user_id))
    session.execute(delete(HotelInteraction).where(HotelInteraction.user_id == user_id))
    session.commit()


def train_preferences_once(settings: Settings) -> int:
    with get_session_factory()() as session:
        trained = train_due(
            session,
            Converter(load_pricing_rules(settings.config_dir)),
            load_preference_rules(settings),
            SystemClock().now(),
        )
    if trained:
        log.info("preferences_trained", users=trained)
    return trained
