"""Saved stays, search history, the interaction log and price alerts."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.core.config import Settings
from app.models import Flight, HotelInteraction, Notification
from app.modules.watchlist.service import WatchlistService
from app.worker_jobs import jobs
from tests.integration.test_bookings import (
    API,
    GOOD_CARD,
    code,
    hold,
    hotel_room,
    pay,
    signed_in,  # noqa: F401  (fixture)
)

FLIGHT_SEARCH = {"origin": "DEL", "destination": "BOM", "departure_date": "2026-11-14"}


def mumbai(client: TestClient) -> str:
    return str(
        client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()["items"][0][
            "value"
        ]
    )


def a_hotel(client: TestClient) -> str:
    results = client.get(
        f"{API}/hotels/search",
        params={"city": mumbai(client), "check_in": "2026-11-14", "check_out": "2026-11-16"},
    ).json()["results"]
    return str(results[0]["id"])


# ── Saved stays ───────────────────────────────────────────────────────────────


def test_save_and_unsave_a_stay(signed_in: TestClient, db_session: Session) -> None:  # noqa: F811
    client = signed_in
    hotel = a_hotel(client)
    first = client.put(f"{API}/me/saved-hotels/{hotel}")
    assert first.status_code == 200, first.text
    again = client.put(f"{API}/me/saved-hotels/{hotel}").json()
    assert [h["hotel_id"] for h in again["items"]] == [hotel] and again["items"][0]["available"]
    saves = db_session.scalars(
        select(HotelInteraction).where(HotelInteraction.kind == "save")
    ).all()
    assert len(saves) == 1  # saving twice is one signal
    assert client.delete(f"{API}/me/saved-hotels/{hotel}").json()["items"] == []
    missing = client.put(f"{API}/me/saved-hotels/{uuid.uuid4()}")
    assert missing.status_code == 404 and code(missing) == "HOTEL_NOT_FOUND"


def test_watchlist_needs_sign_in(client: TestClient, catalog: None) -> None:
    assert client.get(f"{API}/me/saved-hotels").status_code == 401
    assert client.get(f"{API}/me/price-alerts").status_code == 401
    assert client.get(f"{API}/me/searches").status_code == 401


# ── Search history and interactions ───────────────────────────────────────────


def test_search_history_is_kept_for_signed_in_travellers(
    signed_in: TestClient,  # noqa: F811
    clock: FrozenClock,
) -> None:
    signed_in.get(f"{API}/flights/search", params=FLIGHT_SEARCH)
    clock.advance(timedelta(minutes=1))
    signed_in.get(
        f"{API}/hotels/search",
        params={"city": mumbai(signed_in), "check_in": "2026-11-14", "check_out": "2026-11-16"},
    )
    clock.advance(timedelta(minutes=1))
    signed_in.get(f"{API}/flights/search", params={**FLIGHT_SEARCH, "sort": "cheapest"})
    clock.advance(timedelta(minutes=1))
    signed_in.get(
        f"{API}/hotels/search",
        params={"city": mumbai(signed_in), "check_in": "2026-11-14", "check_out": "2026-11-16"},
    )
    items = signed_in.get(f"{API}/me/searches").json()["items"]
    # Sorting is not part of the search, so repeats move to the top instead of duplicating.
    assert [i["vertical"] for i in items] == ["hotels", "flights"]
    assert items[1]["label"].startswith("Delhi to Mumbai · 14 Nov")
    assert items[1]["params"]["origin"] == "DEL" and items[1]["result_count"] > 0
    assert items[0]["label"].startswith("Stays in Mumbai")

    assert signed_in.delete(f"{API}/me/searches/{items[0]['id']}").status_code == 204
    gone = signed_in.delete(f"{API}/me/searches/{items[0]['id']}")
    assert gone.status_code == 404 and code(gone) == "SEARCH_NOT_FOUND"
    assert signed_in.delete(f"{API}/me/searches").status_code == 204
    assert signed_in.get(f"{API}/me/searches").json()["items"] == []


def test_views_and_bookings_feed_the_interaction_log(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    room = hotel_room(client)
    created = hold(client, [room])
    assert pay(client, created.json()["id"], GOOD_CARD).status_code == 200
    kinds = {i.kind for i in db_session.scalars(select(HotelInteraction))}
    assert kinds == {"view", "book"}  # hotel_room() opened detail pages, then one was booked


# ── Price alerts ──────────────────────────────────────────────────────────────


def alert(client: TestClient, watch: dict[str, Any], target: int | None = None) -> Any:
    body: dict[str, Any] = {"watch": watch}
    if target is not None:
        body["target_price"] = target
    return client.post(f"{API}/me/price-alerts", json=body)


def cheapest(client: TestClient) -> dict[str, Any]:
    offers = client.get(
        f"{API}/flights/search", params={**FLIGHT_SEARCH, "sort": "cheapest"}
    ).json()["outbound"]["offers"]
    return next(o for o in offers if o["bookable"])


def test_flight_alert_fires_once_on_a_price_drop(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
    settings: Settings,
    clock: FrozenClock,
) -> None:
    client = signed_in
    offer = cheapest(client)
    price = offer["price"]["display_total"]["amount_minor"]
    created = alert(client, {"kind": "flight", **FLIGHT_SEARCH})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["baseline"]["amount_minor"] == price and body["status"] == "active"
    assert body["link"].startswith("/flights?trip=oneway&from=DEL&to=BOM&depart=2026-11-14")
    met = alert(client, {"kind": "flight", **FLIGHT_SEARCH}, target=price // 100 + 1)
    assert met.status_code == 422 and code(met) == "ALERT_TARGET_MET"

    service = WatchlistService(db_session, settings, clock)
    assert service.check_alerts().triggered == 0  # nothing changed yet

    # A new dataset halves the fare of the cheapest flight.
    for leg in offer["legs"]:
        flight = db_session.get(Flight, uuid.UUID(leg["flight_id"]))
        assert flight is not None and flight.fare_minor is not None
        flight.fare_minor //= 2
    db_session.commit()
    summary = service.check_alerts()
    assert summary.triggered == 1
    after = client.get(f"{API}/me/price-alerts").json()["items"][0]
    assert after["status"] == "triggered" and after["current"]["amount_minor"] < price
    note = db_session.scalars(select(Notification).where(Notification.kind == "price_alert")).one()
    assert note.title == "Price drop: Delhi to Mumbai" and note.link == after["link"]
    assert service.check_alerts().checked == 0  # one-shot: it does not fire again


def test_stay_alert_with_target_and_expiry(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
    settings: Settings,
    clock: FrozenClock,
) -> None:
    client = signed_in
    room = hotel_room(client)
    detail = client.get(
        f"{API}/hotels/{a_hotel(client)}",
        params={"check_in": "2026-11-14", "check_out": "2026-11-16"},
    ).json()
    watch = {
        "kind": "hotel",
        "hotel_id": detail["id"],
        "check_in": room["check_in"],
        "check_out": room["check_out"],
    }
    created = alert(client, watch, target=1)
    assert created.status_code == 201, created.text
    assert created.json()["link"].startswith(f"/stays/{detail['id']}?checkIn=2026-11-14")
    assert "1 INR or less" in created.json()["rule"]

    clock.advance(timedelta(days=10))  # the stay is in the past now
    summary = WatchlistService(db_session, settings, clock).check_alerts()
    assert summary.expired == 1


def test_alert_needs_something_bookable(signed_in: TestClient) -> None:  # noqa: F811
    response = alert(signed_in, {"kind": "flight", **FLIGHT_SEARCH, "departure_date": "2026-12-30"})
    assert response.status_code == 409 and code(response) == "ALERT_NOTHING_TO_WATCH"


def test_cancel_alert(signed_in: TestClient) -> None:  # noqa: F811
    created = alert(signed_in, {"kind": "flight", **FLIGHT_SEARCH}).json()
    assert signed_in.delete(f"{API}/me/price-alerts/{created['id']}").status_code == 204
    assert signed_in.get(f"{API}/me/price-alerts").json()["items"] == []
    again = signed_in.delete(f"{API}/me/price-alerts/{created['id']}")
    assert again.status_code == 404


def test_worker_runs_the_alert_job(settings: Settings) -> None:
    names = {name: interval for name, interval, _ in jobs(settings)}
    assert names == {
        "expire_holds": 30,
        "check_price_alerts": 30 * 60,
        "train_preferences": 3600,
        "purge_expired_data": 86400,
    }
