"""Platform features: saved travellers, loyalty points, promo codes, admin console."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cli import seed

API = "/api/v1"
CARD = {
    "card_number": "4242424242424242",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvc": "123",
    "cardholder_name": "Asha Rao",
}


@pytest.fixture
def traveller(client: TestClient, catalog: None) -> TestClient:
    seed()
    assert client.post(f"{API}/auth/demo-login", json={"role": "traveler"}).status_code == 200
    return client


def flight_item(client: TestClient) -> dict[str, Any]:
    body = client.get(
        f"{API}/flights/search",
        params={
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": "2026-11-14",
            "max_stops": 0,
            "sort": "cheapest",
        },
    ).json()
    return {
        "kind": "flight",
        "offer_id": next(o["id"] for o in body["outbound"]["offers"] if o["bookable"]),
    }


def room_item(client: TestClient, nights: int = 3) -> dict[str, Any]:
    city = client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()
    check_out = f"2026-11-{14 + nights}"
    hotel = client.get(
        f"{API}/hotels/search",
        params={
            "city": city["items"][0]["value"],
            "check_in": "2026-11-14",
            "check_out": check_out,
            "sort": "price",
        },
    ).json()["results"][0]
    return {
        "kind": "hotel",
        "room_type_id": hotel["cheapest_room"]["room_type_id"],
        "check_in": "2026-11-14",
        "check_out": check_out,
        "rooms": 1,
        "guests": 2,
    }


def book(
    client: TestClient, items: list[dict[str, Any]], promo: str | None = None, pay: bool = True
) -> Any:
    response = client.post(
        f"{API}/bookings",
        json={
            "items": items,
            "travellers": [{"first_name": "Asha", "last_name": "Rao"}],
            "contact": {"email": "asha@example.com"},
            "promo_code": promo,
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    if pay and response.status_code == 201:
        return client.post(
            f"{API}/bookings/{response.json()['id']}/payments",
            json=CARD,
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
    return response


def test_saved_travellers(traveller: TestClient) -> None:
    created = traveller.post(
        f"{API}/me/travellers", json={"first_name": "Ravi", "last_name": "Rao"}
    )
    assert created.status_code == 201
    listing = traveller.get(f"{API}/me/travellers").json()["items"]
    assert [p["first_name"] for p in listing] == ["Ravi"]
    assert traveller.delete(f"{API}/me/travellers/{created.json()['id']}").status_code == 204
    assert traveller.get(f"{API}/me/travellers").json()["items"] == []
    missing = traveller.delete(f"{API}/me/travellers/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_loyalty_points_follow_payments_and_refunds(traveller: TestClient) -> None:
    paid = book(traveller, [flight_item(traveller)]).json()
    expected = paid["total"]["amount_minor"] // 10000
    loyalty = traveller.get(f"{API}/me/loyalty").json()
    assert loyalty["balance"] == expected > 0 and loyalty["tier"] == "Explorer"
    traveller.post(f"{API}/bookings/{paid['id']}/cancel", json={})  # full refund within 24 h
    after = traveller.get(f"{API}/me/loyalty").json()
    assert after["balance"] == 0 and len(after["history"]) == 2


def test_promo_codes_are_priced_on_the_server(traveller: TestClient) -> None:
    item = flight_item(traveller)
    plain = traveller.post(f"{API}/bookings/quote", json={"items": [item]}).json()
    quote = traveller.post(
        f"{API}/bookings/quote", json={"items": [item], "promo_code": "welcome10"}
    ).json()
    expected = min(plain["total"]["amount_minor"] // 10, 200_000)
    assert quote["discount"]["amount_minor"] == expected
    assert quote["total"]["amount_minor"] == plain["total"]["amount_minor"] - expected

    booked = book(traveller, [item], promo="WELCOME10").json()
    assert booked["promo_code"] == "WELCOME10"
    assert booked["total"]["amount_minor"] == quote["total"]["amount_minor"]

    # First-booking-only, and single use per traveller.
    again = traveller.post(
        f"{API}/bookings/quote", json={"items": [item], "promo_code": "WELCOME10"}
    )
    assert again.status_code == 422
    assert again.json()["error"]["code"] in {"PROMO_INVALID", "PROMO_ALREADY_USED"}

    # Refunds give back what was paid after the discount, not the list price.
    cancelled = traveller.post(f"{API}/bookings/{booked['id']}/cancel", json={}).json()
    assert cancelled["refunds"][0]["amount"]["amount_minor"] == booked["total"]["amount_minor"]


def test_promo_conditions(traveller: TestClient) -> None:
    unknown = traveller.post(
        f"{API}/bookings/quote", json={"items": [flight_item(traveller)], "promo_code": "NOPE"}
    )
    assert unknown.status_code == 422 and "does not exist" in unknown.json()["error"]["message"]
    short = traveller.post(
        f"{API}/bookings/quote",
        json={"items": [room_item(traveller, nights=2)], "promo_code": "STAYLONGER"},
    )
    assert short.status_code == 422
    long = traveller.post(
        f"{API}/bookings/quote",
        json={"items": [room_item(traveller, nights=3)], "promo_code": "STAYLONGER"},
    ).json()
    assert long["discount"]["amount_minor"] == min(100_000, long["subtotal"]["amount_minor"])
    alone = traveller.post(
        f"{API}/bookings/quote",
        json={"items": [flight_item(traveller)], "promo_code": "TRIPTOGETHER"},
    )
    assert alone.status_code == 422
    both = traveller.post(
        f"{API}/bookings/quote",
        json={
            "items": [flight_item(traveller), room_item(traveller)],
            "promo_code": "TRIPTOGETHER",
        },
    )
    assert both.status_code == 200


def test_admin_console(traveller: TestClient) -> None:
    book(traveller, [flight_item(traveller)])
    assert traveller.get(f"{API}/admin/analytics").status_code == 403
    traveller.post(f"{API}/auth/logout")
    traveller.post(f"{API}/auth/demo-login", json={"role": "admin"})
    stats = traveller.get(f"{API}/admin/analytics").json()
    statuses = {c["label"]: c["value"] for c in stats["bookings_by_status"]}
    assert statuses["confirmed"] == 1 and stats["confirmed_value"]["amount_minor"] > 0
    assert stats["hold_conversion_percent"] == 100.0
    assert stats["top_destinations"][0]["label"] == "Mumbai"
    audit = traveller.get(f"{API}/admin/audit", params={"action": "booking.payment"}).json()
    assert audit["total"] == 1 and audit["items"][0]["actor_email"] == "demo@tripmind.dev"
    assert "booking.hold" in audit["actions"]
