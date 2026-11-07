"""Connected-trip planner over the imported synthetic dataset (13-15 Nov 2026)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cli import seed

API = "/api/v1"


@pytest.fixture
def signed_in(client: TestClient, catalog: None) -> TestClient:
    seed()
    assert client.post(f"{API}/auth/demo-login", json={"role": "traveler"}).status_code == 200
    return client


def plan(client: TestClient, **overrides: Any) -> Any:
    city = client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()
    body = {
        "origin": "DEL",
        "destination_city_id": city["items"][0]["value"],
        "depart_date": "2026-11-13",
        "return_date": "2026-11-15",
        "adults": 2,
        **overrides,
    }
    return client.post(f"{API}/plans", json=body)


def test_plan_ranks_complete_feasible_bundles(signed_in: TestClient) -> None:
    response = plan(signed_in)
    assert response.status_code == 201, response.text
    body = response.json()
    options = body["options"]
    assert options and body["title"].startswith("Mumbai")
    totals = [o["scores"]["total"] for o in options]
    assert totals == sorted(totals, reverse=True)
    for o in options:
        assert o["outbound"]["legs"][-1]["destination"]["code"] == "BOM"
        assert o["inbound"]["legs"][0]["origin"]["code"] == "BOM"
        assert o["outbound"]["legs"][-1]["arrival_at"] < o["inbound"]["legs"][0]["departure_at"]
        assert o["stay"]["check_in"] < o["stay"]["check_out"] and o["stay"]["rooms"] == 1
        assert len(o["explanation"]) == 4 and o["explanation"][-1].startswith(
            f"Ranked #{o['rank']}"
        )
        names = {c["name"] for c in o["confidence"]["checks"]}
        assert {"Arrival and check-in", "Seats", "Cancellation cover", "Price"} <= names
        assert o["confidence"]["level"] in {"high", "medium", "low"}
    hotels = [o["hotel"]["id"] for o in options]
    assert max(hotels.count(h) for h in hotels) <= 3  # diversified


def test_priority_changes_the_ranking(signed_in: TestClient) -> None:
    cheapest = plan(signed_in, priority="cheapest").json()["options"]
    comfort = plan(signed_in, priority="comfort").json()["options"]
    # Price carries 70% of the "cheapest" score: its winner is within 2% of the lowest total.
    lowest = min(o["total"]["amount_minor"] for o in cheapest)
    assert cheapest[0]["total"]["amount_minor"] <= lowest * 1.02
    assert cheapest[0]["scores"]["price"] >= 0.98
    # The stay carries 40% of "comfort": its winner has at least as good a stay score.
    assert comfort[0]["scores"]["stay"] >= cheapest[0]["scores"]["stay"]

    budget = lowest // 100
    capped = plan(signed_in, priority="cheapest", max_budget=budget).json()
    assert all(o["total"]["amount_minor"] <= budget * 100 for o in capped["options"])
    assert any("above your budget" in n for n in capped["notices"])


def test_decisions_are_remembered(signed_in: TestClient) -> None:
    created = plan(signed_in).json()
    first, second = created["options"][0]["id"], created["options"][1]["id"]
    signed_in.put(f"{API}/plans/{created['id']}/options/{first}", json={"state": "saved"})
    signed_in.put(f"{API}/plans/{created['id']}/options/{second}", json={"state": "dismissed"})
    again = signed_in.get(f"{API}/plans/{created['id']}").json()
    states = {o["id"]: o["state"] for o in again["options"]}
    assert states[first] == "saved" and states[second] == "dismissed"
    listing = signed_in.get(f"{API}/plans").json()["items"]
    assert listing[0]["saved"] == 1
    missing = signed_in.put(f"{API}/plans/{created['id']}/options/nope", json={"state": "saved"})
    assert missing.status_code == 404


def test_a_planned_trip_books_in_one_checkout(signed_in: TestClient) -> None:
    option = plan(signed_in).json()["options"][0]
    items = [
        {"kind": "flight", "offer_id": option["outbound"]["id"], "adults": 2},
        {"kind": "flight", "offer_id": option["inbound"]["id"], "adults": 2},
        {
            "kind": "hotel",
            "room_type_id": option["hotel"]["cheapest_room"]["room_type_id"],
            "check_in": option["stay"]["check_in"],
            "check_out": option["stay"]["check_out"],
            "rooms": option["stay"]["rooms"],
            "guests": 2,
        },
    ]
    booking = signed_in.post(
        f"{API}/bookings",
        json={
            "items": items,
            "contact": {"email": "a@example.com"},
            "travellers": [
                {"first_name": "A", "last_name": "B"},
                {"first_name": "C", "last_name": "D"},
            ],
            "expected_total_minor": option["total"]["amount_minor"],
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert booking.status_code == 201, booking.text
    assert [i["kind"] for i in booking.json()["items"]] == ["flight", "flight", "hotel"]
    trip = signed_in.get(f"{API}/trips/{booking.json()['trip_id']}").json()
    assert trip["has_flight"] and trip["has_stay"] and trip["title"] == "Trip to Mumbai"


def test_plan_rules(signed_in: TestClient) -> None:
    same_day = plan(signed_in, return_date="2026-11-13")
    assert same_day.status_code == 422 and same_day.json()["error"]["code"] == "INVALID_STAY"
    other = signed_in.get(f"{API}/plans/{uuid.uuid4()}")
    assert other.status_code == 404
