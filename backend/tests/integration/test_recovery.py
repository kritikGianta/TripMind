"""Disruption and recovery: operator records a problem, traveller resolves it item by item."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import seed
from app.models import FlightInventory

API = "/api/v1"
CARD = {
    "card_number": "4242424242424242",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvc": "123",
    "cardholder_name": "Asha Rao",
}
DAY = "2026-11-14"


def login(client: TestClient, role: str) -> None:
    client.post(f"{API}/auth/logout")
    assert client.post(f"{API}/auth/demo-login", json={"role": role}).status_code == 200


@pytest.fixture
def traveller(client: TestClient, catalog: None) -> TestClient:
    seed()
    login(client, "traveler")
    return client


def first_direct(client: TestClient, destination: str = "BOM") -> dict[str, Any]:
    body = client.get(
        f"{API}/flights/search",
        params={
            "origin": "DEL",
            "destination": destination,
            "departure_date": DAY,
            "max_stops": 0,
            "sort": "earliest",
        },
    ).json()
    return next(o for o in body["outbound"]["offers"] if o["bookable"])


def mumbai_room(client: TestClient) -> dict[str, Any]:
    city = client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()
    hotel = client.get(
        f"{API}/hotels/search",
        params={
            "city": city["items"][0]["value"],
            "check_in": DAY,
            "check_out": "2026-11-16",
            "sort": "price",
        },
    ).json()["results"][0]
    return {
        "kind": "hotel",
        "room_type_id": hotel["cheapest_room"]["room_type_id"],
        "check_in": DAY,
        "check_out": "2026-11-16",
        "rooms": 1,
        "guests": 2,
    }


def book(client: TestClient, items: list[dict[str, Any]], pay: bool = True) -> dict[str, Any]:
    created = client.post(
        f"{API}/bookings",
        json={
            "items": items,
            "travellers": [{"first_name": "Asha", "last_name": "Rao"}],
            "contact": {"email": "asha@example.com"},
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert created.status_code == 201, created.text
    booking = created.json()
    if pay:
        booking = client.post(
            f"{API}/bookings/{booking['id']}/payments",
            json=CARD,
            headers={"Idempotency-Key": uuid.uuid4().hex},
        ).json()
    return booking


def disrupt(client: TestClient, **body: Any) -> Any:
    login(client, "admin")
    response = client.post(f"{API}/admin/operations/disruptions", json=body)
    login(client, "traveler")
    return response


def open_case(client: TestClient, booking_id: str) -> dict[str, Any]:
    cases = client.get(f"{API}/recovery/cases", params={"booking_id": booking_id}).json()["items"]
    assert len(cases) == 1
    return cases[0]


def test_cancelled_flight_is_rebooked_and_the_stay_is_untouched(
    traveller: TestClient, db_session: Session
) -> None:
    client = traveller
    offer = first_direct(client)
    flight_id = offer["legs"][0]["flight_id"]
    booking = book(client, [{"kind": "flight", "offer_id": offer["id"]}, mumbai_room(client)])
    assert booking["status"] == "confirmed"

    created = disrupt(client, kind="flight_cancelled", flight_id=flight_id, reason="Crew shortage")
    assert created.status_code == 201, created.text
    assert created.json()["affected_items"] == 1

    # No longer for sale.
    ids = [
        o["legs"][0]["flight_id"]
        for o in client.get(
            f"{API}/flights/search",
            params={"origin": "DEL", "destination": "BOM", "departure_date": DAY},
        ).json()["outbound"]["offers"]
    ]
    assert flight_id not in ids

    case = open_case(client, booking["id"])
    assert case["status"] == "open" and "Crew shortage" in case["summary"]
    assert any("not affected" in line for line in case["impact"])
    kinds = {o["type"] for o in case["options"]}
    assert {"rebook_flight", "refund"} <= kinds
    notes = client.get(f"{API}/notifications").json()
    assert notes["unread"] >= 1
    assert any(
        n["severity"] == "critical" and n["link"] == f"/bookings/{booking['id']}"
        for n in notes["items"]
    )

    option = next(o for o in case["options"] if o["type"] == "rebook_flight")
    resolved = client.post(
        f"{API}/recovery/cases/{case['id']}/accept", json={"option_id": option["id"]}
    ).json()
    assert resolved["status"] == "resolved" and resolved["resolution"] == "rebooked"

    after = client.get(f"{API}/bookings/{booking['id']}").json()
    by_status = {i["status"]: i for i in after["items"]}
    assert set(by_status) == {"replaced", "confirmed"}
    flights = [i for i in after["items"] if i["kind"] == "flight"]
    old = next(i for i in flights if i["status"] == "replaced")
    new = next(i for i in flights if i["status"] == "confirmed")
    assert old["replaced_by_item_id"] == new["id"]
    hotel = next(i for i in after["items"] if i["kind"] == "hotel")
    assert hotel["status"] == "confirmed"  # item-level: the stay never changed
    assert after["status"] == "confirmed" and after["events"][-1]["type"] == "recovered"

    db_session.expire_all()
    old_inventory = db_session.get(FlightInventory, uuid.UUID(flight_id))
    assert old_inventory is not None and old_inventory.reserved == 0
    again = client.post(
        f"{API}/recovery/cases/{case['id']}/accept", json={"option_id": option["id"]}
    )
    assert again.status_code == 409


def test_refund_option_cancels_only_that_item(traveller: TestClient) -> None:
    client = traveller
    offer = first_direct(client, destination="GOI")
    booking = book(client, [{"kind": "flight", "offer_id": offer["id"]}])
    disrupt(client, kind="flight_cancelled", flight_id=offer["legs"][0]["flight_id"])
    case = open_case(client, booking["id"])
    refund = next(o for o in case["options"] if o["type"] == "refund")
    client.post(f"{API}/recovery/cases/{case['id']}/accept", json={"option_id": refund["id"]})
    after = client.get(f"{API}/bookings/{booking['id']}").json()
    assert after["status"] == "cancelled"
    assert after["refunds"][0]["amount"]["amount_minor"] == booking["total"]["amount_minor"]


def test_short_delay_notifies_and_long_delay_offers_choices(traveller: TestClient) -> None:
    client = traveller
    offer = first_direct(client)
    booking = book(client, [{"kind": "flight", "offer_id": offer["id"]}])
    flight_id = offer["legs"][0]["flight_id"]

    disrupt(client, kind="flight_delayed", flight_id=flight_id, delay_minutes=45)
    short = open_case(client, booking["id"])
    assert [o["type"] for o in short["options"]] == ["keep"]
    client.post(f"{API}/recovery/cases/{short['id']}/accept", json={"option_id": "keep"})

    disrupt(client, kind="flight_delayed", flight_id=flight_id, delay_minutes=240)
    cases = client.get(f"{API}/recovery/cases", params={"booking_id": booking["id"]}).json()
    long = next(c for c in cases["items"] if c["status"] == "open")
    assert {"keep", "refund"} <= {o["type"] for o in long["options"]}


def test_room_outage_offers_another_room(traveller: TestClient) -> None:
    client = traveller
    room = mumbai_room(client)
    booking = book(client, [room])
    created = disrupt(
        client,
        kind="room_unavailable",
        room_type_id=room["room_type_id"],
        starts_on=DAY,
        ends_on="2026-11-15",
        reason="Water damage",
    )
    assert created.json()["affected_items"] == 1
    case = open_case(client, booking["id"])
    option = next(o for o in case["options"] if o["type"] == "rebook_room")
    assert option["room"]["room_type_id"] != room["room_type_id"]
    resolved = client.post(
        f"{API}/recovery/cases/{case['id']}/accept", json={"option_id": option["id"]}
    ).json()
    assert resolved["resolution"] == "rebooked"
    # The out-of-service room is not offered for those nights any more.
    detail = client.get(
        f"{API}/hotels/{booking['items'][0]['details']['hotel_id']}",
        params={"check_in": DAY, "check_out": "2026-11-16"},
    ).json()
    broken = next(r for r in detail["rooms"] if r["room_type_id"] == room["room_type_id"])
    assert broken["fits_party"] is False


def test_unpaid_hold_on_a_cancelled_flight_is_released(
    traveller: TestClient, db_session: Session
) -> None:
    client = traveller
    offer = first_direct(client)
    booking = book(client, [{"kind": "flight", "offer_id": offer["id"]}], pay=False)
    disrupt(client, kind="flight_cancelled", flight_id=offer["legs"][0]["flight_id"])
    after = client.get(f"{API}/bookings/{booking['id']}").json()
    assert after["status"] == "cancelled" and not after["payments"]
    assert client.get(f"{API}/recovery/cases").json()["items"] == []
    db_session.expire_all()
    assert all(r.reserved == 0 for r in db_session.scalars(select(FlightInventory)))


def test_operations_are_admin_only(traveller: TestClient) -> None:
    client = traveller
    assert client.get(f"{API}/admin/operations/booked-flights").status_code == 403
    login(client, "admin")
    assert client.get(f"{API}/admin/operations/booked-flights").status_code == 200
    bad = client.post(
        f"{API}/admin/operations/disruptions",
        json={"kind": "flight_delayed", "flight_id": str(uuid.uuid4())},
    )
    assert bad.status_code == 422  # a delay needs delay_minutes
