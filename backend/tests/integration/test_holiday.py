"""Build My Holiday: the must-have features of Problem 1, tested through the real API."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1/holiday"

# The handout's example traveller: the Menon family.
MENON = {
    "departure_airport": "BLR",
    "country": "Japan",
    "start_date": "2027-04-10",
    "nights": 6,
    "adults": 2,
    "child_ages": [6],
    "budget_inr": 350000,
}


def build(client: TestClient, **changes: Any) -> Any:
    return client.post(f"{API}/packages", json={**MENON, **changes})


def test_m1_invalid_request_gets_a_clear_message(client: TestClient, holiday_pack: None) -> None:
    response = build(client, nights=2)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert "3 to 10 nights" in error["message"]


def test_m2_m3_menon_packages_pass_every_rule(client: TestClient, holiday_pack: None) -> None:
    body = build(client).json()
    assert body["ok"] is True
    assert [p["label"] for p in body["packages"]] == ["cheapest", "fastest", "best_rated"]
    for package in body["packages"]:
        assert package["problems"] == []  # the rule checker found nothing wrong
        items = package["items"]
        arrival = next(i for i in items if i["details"].get("leg") == "arrival")
        home = next(i for i in items if i["details"].get("leg") == "return")
        assert arrival["end"].startswith("2027-04-10")  # lands on the holiday start date
        assert home["start"].startswith("2027-04-16")  # flies home on the last day
        assert package["total_inr"] == sum(i["price_inr"] for i in items)
        assert package["total_inr"] <= MENON["budget_inr"]


def test_m6_changes_are_checked_and_a_bad_change_is_refused(
    client: TestClient, holiday_pack: None
) -> None:
    package = build(client).json()["packages"][0]
    visit = next(i for i in package["items"] if i["type"] == "attraction")
    removed = client.post(
        f"{API}/packages/{package['id']}/changes",
        json={"action": "remove_attraction", "item_id": visit["item_id"]},
    )
    assert removed.status_code == 200
    assert removed.json()["total_inr"] == package["total_inr"] - visit["price_inr"]

    # An attraction in a city the traveller is not in that day breaks a rule: refused, with why.
    cities = {c["city"] for c in package["cities"]}
    elsewhere = "ATT-OSA-001" if "Osaka" not in cities else "ATT-TYO-001"
    refused = client.post(
        f"{API}/packages/{package['id']}/changes",
        json={"action": "add_attraction", "attraction_id": elsewhere, "day": "2027-04-12"},
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "CHANGE_REFUSED"


def test_m7_confirm_gives_a_10_digit_number_that_opens_the_summary(
    client: TestClient, holiday_pack: None
) -> None:
    package = build(client).json()["packages"][0]
    booked = client.post(f"{API}/packages/{package['id']}/confirm").json()
    reference = booked["reference"]
    assert booked["status"] == "BOOKED"
    assert len(reference) == 10 and reference.isdigit()

    opened = client.get(f"{API}/reservations/{reference}").json()
    assert opened["id"] == package["id"] and opened["status"] == "BOOKED"
    assert client.get(f"{API}/reservations/0000000000").status_code == 404  # "not found"

    exported = client.get(f"{API}/packages/{package['id']}/export").json()
    assert exported["status"] == "BOOKED"
    assert all(i["booking"] == {"reference": reference} for i in exported["items"])


def test_m8_budget_too_small_shows_cheapest_and_a_suggestion(
    client: TestClient, holiday_pack: None
) -> None:
    body = build(client, budget_inr=20000).json()
    assert body["ok"] is False
    assert "budget" in body["message"]
    assert body["cheapest_total_inr"] > 20000
    assert body["suggestion"]
