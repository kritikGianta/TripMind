"""Personalised "Recommended" order: learned from activity, explained, and resettable."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.core.config import Settings
from app.modules.search.preferences import load_preference_rules, train_due
from app.modules.search.pricing import Converter, load_pricing_rules
from tests.integration.test_bookings import API, signed_in  # noqa: F401  (fixture)

STAY = {"check_in": "2026-11-14", "check_out": "2026-11-16"}


def city(client: TestClient, name: str) -> str:
    return str(
        client.get(f"{API}/locations", params={"q": name, "kind": "city"}).json()["items"][0][
            "value"
        ]
    )


def search(client: TestClient, city_id: str) -> dict[str, Any]:
    return dict(client.get(f"{API}/hotels/search", params={"city": city_id, **STAY}).json())


def test_activity_personalises_recommended(
    client: TestClient,
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
    settings: Settings,
    clock: FrozenClock,
) -> None:
    mumbai = city(signed_in, "Mumbai")
    before = search(signed_in, mumbai)
    assert not before["personalized"] and before["ranked_by"] == "rules"
    for result in before["results"][:3]:
        signed_in.get(f"{API}/hotels/{result['id']}", params=STAY)  # views
    signed_in.put(f"{API}/me/saved-hotels/{before['results'][0]['id']}")  # a save
    assert signed_in.get(f"{API}/me/preferences").json()["personalized"] is False

    trained = train_due(
        db_session,
        Converter(load_pricing_rules(settings.config_dir)),
        load_preference_rules(settings),
        clock.now(),
    )
    assert trained == 1
    prefs = signed_in.get(f"{API}/me/preferences").json()
    assert prefs["personalized"] and prefs["stays_learned_from"] == 3
    assert prefs["activity_count"] == 4
    assert all(item["direction"] in ("likes", "avoids") for item in prefs["learned"])

    after = search(signed_in, mumbai)
    assert after["personalized"] and after["ranked_by"] == "rules+preferences"
    assert {r["id"] for r in after["results"]} == {r["id"] for r in before["results"]}
    # Nothing new happened, so nobody is due for retraining.
    assert (
        train_due(
            db_session,
            Converter(load_pricing_rules(settings.config_dir)),
            load_preference_rules(settings),
            clock.now(),
        )
        == 0
    )

    assert signed_in.delete(f"{API}/me/preferences").status_code == 204
    reset = signed_in.get(f"{API}/me/preferences").json()
    assert not reset["personalized"] and reset["activity_count"] == 0
    assert not search(signed_in, mumbai)["personalized"]
