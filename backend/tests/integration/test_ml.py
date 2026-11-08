"""Model serving: registry contract, ranker and fare insight through the API, similar stays,
and anomaly detection during import. Models here are tiny ones trained in the test, so the
loading and feature contract are exercised exactly as with the Kaggle-trained artifacts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import lightgbm
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import seed
from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.models import Airport
from app.modules.ml.features import (
    FARE_ESTIMATOR_FEATURES,
    FARE_ESTIMATOR_MAX_KM,
    HOTEL_RANKER_FEATURES,
    haversine_km,
)
from app.modules.ml.registry import load_model
from app.modules.ml.similar import HotelProfile, similar_hotels

API = "/api/v1"


def train(directory: Path, name: str, features: tuple[str, ...], target: str) -> None:
    """Write a small real LightGBM model plus its model card, like the notebooks do."""
    rng = np.random.default_rng(0)
    x = rng.random((400, len(features)))
    directory.mkdir(parents=True, exist_ok=True)
    if target == "rank":
        # Prefers higher review scores and lower price rank, like real booking behaviour.
        y = (x[:, 1] * 3 - x[:, 3] * 2 + rng.random(400) > 1.2).astype(int)
        params = {"objective": "lambdarank", "verbose": -1, "min_data_in_leaf": 5}
        data = lightgbm.Dataset(x, y, group=[20] * 20)
    else:
        y = np.log(3000 + 4 * x[:, 0] * 2000)  # log fare rising with distance
        params = {"objective": "regression", "verbose": -1, "min_data_in_leaf": 5}
        data = lightgbm.Dataset(x, y)
    lightgbm.train(params, data, num_boost_round=20).save_model(str(directory / "model.txt"))
    (directory / "model_card.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": "test-1",
                "trained_at": datetime.now(UTC).isoformat(),
                "framework": "lightgbm",
                "framework_version": lightgbm.__version__,
                "dataset": "unit test",
                "features": list(features),
                "metrics": {},
            }
        )
    )


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    train(tmp_path / "hotel_ranker" / "artifacts", "hotel_ranker", HOTEL_RANKER_FEATURES, "rank")
    train(
        tmp_path / "fare_estimator" / "artifacts", "fare_estimator", FARE_ESTIMATOR_FEATURES, "fare"
    )
    return tmp_path


def test_registry_enforces_the_feature_contract(models_dir: Path) -> None:
    model = load_model(models_dir, "hotel_ranker", HOTEL_RANKER_FEATURES)
    assert model is not None and model.card.version == "test-1"
    assert load_model(models_dir, "hotel_ranker", ("something", "else")) is None
    assert load_model(models_dir, "missing_model", HOTEL_RANKER_FEATURES) is None


def test_models_are_used_when_present(
    client: TestClient,
    catalog: None,
    settings: Settings,
    models_dir: Path,
    db_session: Session,
) -> None:
    city = client.get(f"{API}/locations", params={"q": "Delhi", "kind": "city"}).json()
    params = {
        "city": city["items"][0]["value"],
        "check_in": "2026-11-14",
        "check_out": "2026-11-16",
    }
    assert client.get(f"{API}/hotels/search", params=params).json()["ranked_by"] == "rules"

    client.app.dependency_overrides[get_settings_dep] = lambda: settings.model_copy(  # type: ignore[attr-defined]
        update={"models_dir": models_dir}
    )
    ranked = client.get(f"{API}/hotels/search", params=params).json()
    assert ranked["ranked_by"] == "model:test-1" and ranked["results"]
    price_sorted = client.get(f"{API}/hotels/search", params={**params, "sort": "price"}).json()
    assert price_sorted["ranked_by"] == "rules"  # explicit sorts never use the model

    flights = client.get(
        f"{API}/flights/search",
        params={
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": "2026-11-14",
            "max_stops": 0,
        },
    ).json()["outbound"]["offers"]
    insights = [o["fare_insight"] for o in flights if o["fare_insight"]]
    assert insights and insights[0]["label"] in {"below_typical", "typical", "above_typical"}
    assert insights[0]["typical_per_adult"]["currency"] == "INR"
    long_haul = client.get(
        f"{API}/flights/search",
        params={"origin": "DEL", "destination": "LHR", "departure_date": "2026-11-14"},
    ).json()
    assert all(o["fare_insight"] is None for o in long_haul["outbound"]["offers"])  # out of domain
    # Short international routes priced in rupees are out of domain too: it learned domestic fares.
    india = {"India", "IN"}
    foreign = [a for a in db_session.scalars(select(Airport)) if a.country not in india]
    delhi = db_session.scalar(select(Airport).where(Airport.code == "DEL"))
    assert delhi is not None
    short = [
        a.code
        for a in foreign
        if a.latitude is not None
        and haversine_km((delhi.latitude, delhi.longitude), (a.latitude, a.longitude))
        <= FARE_ESTIMATOR_MAX_KM
    ]
    assert short  # the demo network has short international routes from Delhi
    for code in short:
        offers = client.get(
            f"{API}/flights/search",
            params={"origin": "DEL", "destination": code, "departure_date": "2026-11-14"},
        ).json()["outbound"]["offers"]
        assert all(o["fare_insight"] is None for o in offers)


def test_similar_stays() -> None:
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    hotels = [
        HotelProfile(a, ("beach_access", "pool", "spa", "wifi"), 5, 9.0, 12000),
        HotelProfile(b, ("beach_access", "pool", "spa", "wifi"), 5, 8.8, 11500),
        HotelProfile(c, ("wifi", "parking"), 2, 6.5, 1800),
        HotelProfile(d, ("wifi", "parking", "laundry"), 2, 6.8, 2000),
    ]
    best = similar_hotels(a, hotels, k=2)
    assert best[0].id == b and "beach_access" in best[0].shared_amenities
    assert similar_hotels(uuid.uuid4(), hotels) == []


def test_hotel_detail_lists_similar_stays(client: TestClient, catalog: None) -> None:
    city = client.get(f"{API}/locations", params={"q": "Delhi", "kind": "city"}).json()
    hotel = client.get(
        f"{API}/hotels/search",
        params={
            "city": city["items"][0]["value"],
            "check_in": "2026-11-14",
            "check_out": "2026-11-16",
        },
    ).json()["results"][0]
    detail = client.get(f"{API}/hotels/{hotel['id']}").json()
    assert detail["similar"] and all(s["id"] != hotel["id"] for s in detail["similar"])
    scores = [s["similarity"] for s in detail["similar"]]
    assert scores == sorted(scores, reverse=True)


def test_import_flags_injected_price_errors(client: TestClient, catalog: None) -> None:
    seed()
    client.post(f"{API}/auth/demo-login", json={"role": "admin"})
    runs = client.get(f"{API}/admin/imports").json()["items"]
    assert runs[0]["adjustments"].get("PRICE_ANOMALY", 0) >= 1
