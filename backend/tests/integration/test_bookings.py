"""Checkout end to end: quote -> hold -> pay -> trips -> cancel, plus the failure paths."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.cli import seed
from app.core.clock import FrozenClock
from app.models import Booking, Flight, FlightInventory, RoomNightInventory
from app.modules.inventory.service import InventoryService, SoldOut

API = "/api/v1"
GOOD_CARD = {
    "card_number": "4242 4242 4242 4242",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvc": "123",
    "cardholder_name": "Asha Rao",
}
DECLINED_CARD = {**GOOD_CARD, "card_number": "4000 0000 0000 0002"}
CONTACT = {"email": "asha@example.com"}


def traveller(first: str = "Asha") -> dict[str, str]:
    return {"first_name": first, "last_name": "Rao"}


@pytest.fixture
def signed_in(client: TestClient, catalog: None) -> TestClient:
    seed()
    assert client.post(f"{API}/auth/demo-login", json={"role": "traveler"}).status_code == 200
    return client


def flight_offer(client: TestClient, adults: int = 1, destination: str = "BOM") -> str:
    body = client.get(
        f"{API}/flights/search",
        params={
            "origin": "DEL",
            "destination": destination,
            "departure_date": "2026-11-14",
            "adults": adults,
            "max_stops": 0,
            "sort": "cheapest",
        },
    ).json()
    return str(next(o for o in body["outbound"]["offers"] if o["bookable"])["id"])


def hotel_room(client: TestClient, refundable: bool | None = None) -> dict[str, Any]:
    city = client.get(f"{API}/locations", params={"q": "Mumbai", "kind": "city"}).json()
    hotels = client.get(
        f"{API}/hotels/search",
        params={
            "city": city["items"][0]["value"],
            "check_in": "2026-11-14",
            "check_out": "2026-11-16",
        },
    ).json()["results"]
    for hotel in hotels:
        detail = client.get(
            f"{API}/hotels/{hotel['id']}",
            params={"check_in": "2026-11-14", "check_out": "2026-11-16"},
        ).json()
        for room in detail["rooms"]:
            if (
                room["fits_party"]
                and room["nightly_rate"]
                and (refundable is None or room["refundable"] is refundable)
            ):
                return {
                    "kind": "hotel",
                    "room_type_id": room["room_type_id"],
                    "check_in": "2026-11-14",
                    "check_out": "2026-11-16",
                    "rooms": 1,
                    "guests": 2,
                }
    raise AssertionError("no suitable room in the fixture")


def hold(
    client: TestClient,
    items: list[dict[str, Any]],
    *,
    travellers: int = 1,
    key: str | None = None,
    **extra: Any,
) -> Any:
    return client.post(
        f"{API}/bookings",
        json={
            "items": items,
            "travellers": [traveller(f"T{i}") for i in range(travellers)],
            "contact": CONTACT,
            **extra,
        },
        headers={"Idempotency-Key": key or uuid.uuid4().hex},
    )


def pay(client: TestClient, booking_id: str, card: dict[str, Any], key: str | None = None) -> Any:
    return client.post(
        f"{API}/bookings/{booking_id}/payments",
        json=card,
        headers={"Idempotency-Key": key or uuid.uuid4().hex},
    )


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


# ── Happy path ─────────────────────────────────────────────────────────────


def test_quote_hold_pay_and_trip(signed_in: TestClient, db_session: Session) -> None:
    client = signed_in
    item = {"kind": "flight", "offer_id": flight_offer(client, adults=2), "adults": 2}
    quote = client.post(f"{API}/bookings/quote", json={"items": [item]}).json()
    assert quote["total"]["currency"] == "INR" and quote["hold_minutes"] == 15
    assert "demo policy" in quote["items"][0]["policy"]

    created = hold(
        client, [item], travellers=2, expected_total_minor=quote["total"]["amount_minor"]
    )
    assert created.status_code == 201, created.text
    booking = created.json()
    assert booking["status"] == "held" and booking["reference"].startswith("TM")
    assert booking["can_pay"] and [e["type"] for e in booking["events"]] == ["hold_created"]
    flight_id = uuid.UUID(item["offer_id"])
    assert db_session.get(FlightInventory, flight_id).reserved == 2  # type: ignore[union-attr]

    paid = pay(client, booking["id"], GOOD_CARD)
    assert paid.status_code == 200, paid.text
    confirmed = paid.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["payments"][0]["card_last4"] == "4242"
    assert all(i["status"] == "confirmed" for i in confirmed["items"])

    trips = client.get(f"{API}/trips").json()["items"]
    assert len(trips) == 1 and trips[0]["state"] == "upcoming" and trips[0]["has_flight"]
    assert trips[0]["title"] == "Trip to Mumbai"


def test_add_on_stay_joins_the_same_trip(signed_in: TestClient) -> None:
    client = signed_in
    first = hold(client, [{"kind": "flight", "offer_id": flight_offer(client)}]).json()
    pay(client, first["id"], GOOD_CARD)
    second = hold(client, [hotel_room(client)], trip_id=first["trip_id"])
    assert second.status_code == 201, second.text
    pay(client, second.json()["id"], GOOD_CARD)

    trip = client.get(f"{API}/trips/{first['trip_id']}").json()
    assert trip["has_flight"] and trip["has_stay"] and len(trip["bookings"]) == 2
    assert len(client.get(f"{API}/trips").json()["items"]) == 1


# ── Safety: idempotency, prices, payments, holds ───────────────────────────


def test_idempotent_checkout(signed_in: TestClient, db_session: Session) -> None:
    client = signed_in
    items = [{"kind": "flight", "offer_id": flight_offer(client)}]
    first = hold(client, items, key="checkout-key-1").json()
    again = hold(client, items, key="checkout-key-1").json()
    assert again["id"] == first["id"]
    assert len(db_session.scalars(select(Booking)).all()) == 1

    reused = hold(client, [hotel_room(client)], key="checkout-key-1")
    assert reused.status_code == 409 and code(reused) == "IDEMPOTENCY_KEY_REUSED"
    missing = client.post(
        f"{API}/bookings", json={"items": items, "travellers": [traveller()], "contact": CONTACT}
    )
    assert missing.status_code == 422

    paid = pay(client, first["id"], GOOD_CARD, key="pay-key-1").json()
    repeat = pay(client, first["id"], GOOD_CARD, key="pay-key-1").json()
    assert len(repeat["payments"]) == len(paid["payments"]) == 1  # charged once


def test_price_change_and_party_checks(signed_in: TestClient) -> None:
    client = signed_in
    item = {"kind": "flight", "offer_id": flight_offer(client, adults=2), "adults": 2}
    stale = hold(client, [item], travellers=2, expected_total_minor=1)
    assert stale.status_code == 409 and code(stale) == "PRICE_CHANGED"
    assert stale.json()["error"]["details"]["total_minor"] > 1
    wrong_party = hold(client, [item], travellers=1)
    assert wrong_party.status_code == 422 and code(wrong_party) == "TRAVELLERS_MISMATCH"


def test_declined_card_keeps_the_hold_and_can_be_retried(signed_in: TestClient) -> None:
    client = signed_in
    booking = hold(client, [{"kind": "flight", "offer_id": flight_offer(client)}]).json()
    declined = pay(client, booking["id"], DECLINED_CARD)
    assert declined.status_code == 402 and code(declined) == "CARD_DECLINED"
    after = client.get(f"{API}/bookings/{booking['id']}").json()
    assert after["status"] == "payment_failed" and after["can_pay"]

    invalid = pay(client, booking["id"], {**GOOD_CARD, "card_number": "4242 4242 4242 4241"})
    assert invalid.status_code == 422 and code(invalid) == "CARD_INVALID"
    assert pay(client, booking["id"], GOOD_CARD).json()["status"] == "confirmed"


def test_expired_hold_releases_inventory(
    signed_in: TestClient, clock: FrozenClock, db_session: Session
) -> None:
    client = signed_in
    room = hotel_room(client)
    booking = hold(client, [room]).json()
    nights = db_session.scalars(select(RoomNightInventory)).all()
    assert len(nights) == 2 and all(n.reserved == 1 for n in nights)

    clock.advance(timedelta(minutes=16))
    client.post(f"{API}/auth/refresh")  # the 15-minute access token expired too; the app renews it
    expired = client.get(f"{API}/bookings/{booking['id']}").json()
    assert expired["status"] == "expired" and not expired["can_pay"]
    db_session.expire_all()
    assert all(n.reserved == 0 for n in db_session.scalars(select(RoomNightInventory)))
    late = pay(client, booking["id"], GOOD_CARD)
    assert late.status_code == 409 and code(late) == "BOOKING_NOT_PAYABLE"


# ── Cancellation and refunds ───────────────────────────────────────────────


def test_item_level_cancellation_and_refund_policy(
    signed_in: TestClient, clock: FrozenClock
) -> None:
    client = signed_in
    flight = {"kind": "flight", "offer_id": flight_offer(client)}
    booking = hold(client, [flight, hotel_room(client, refundable=False)]).json()
    booking = pay(client, booking["id"], GOOD_CARD).json()
    flight_item, hotel_item = booking["items"]

    preview = client.get(
        f"{API}/bookings/{booking['id']}/cancellation", params={"item_id": hotel_item["id"]}
    ).json()
    assert preview["total_refund"]["amount_minor"] == 0
    assert preview["lines"][0]["reason"] == "Non-refundable rate."

    # Flight cancelled within 24 hours of booking: full refund; the stay stays booked.
    after = client.post(
        f"{API}/bookings/{booking['id']}/cancel", json={"item_ids": [flight_item["id"]]}
    ).json()
    statuses = {i["kind"]: i["status"] for i in after["items"]}
    assert statuses == {"flight": "cancelled", "hotel": "confirmed"}
    assert after["status"] == "confirmed"
    assert (
        after["refunds"][0]["amount"]["amount_minor"]
        == flight_item["details"]["price"]["display_total"]["amount_minor"]
    )

    clock.advance(timedelta(hours=1))
    client.post(f"{API}/auth/refresh")
    final = client.post(f"{API}/bookings/{booking['id']}/cancel", json={}).json()
    assert final["status"] == "cancelled" and not final["can_cancel"]
    assert len(final["refunds"]) == 1  # the non-refundable stay refunded nothing


def test_bookings_are_private(signed_in: TestClient) -> None:
    client = signed_in
    booking = hold(client, [{"kind": "flight", "offer_id": flight_offer(client)}]).json()
    client.post(f"{API}/auth/logout")
    other = client.post(
        f"{API}/auth/register",
        json={
            "email": "someone@example.com",
            "password": "another-passphrase",
            "full_name": "Ravi",
        },
    )
    assert other.status_code == 201
    assert client.get(f"{API}/bookings/{booking['id']}").status_code == 404
    assert client.get(f"{API}/trips/{booking['trip_id']}").status_code == 404
    assert client.get(f"{API}/trips").json()["items"] == []


def test_bookings_require_sign_in(client: TestClient, catalog: None) -> None:
    assert client.get(f"{API}/trips").status_code == 401


# ── Inventory under concurrency ────────────────────────────────────────────


def test_last_seat_is_sold_once(signed_in: TestClient, db_session: Session) -> None:
    client = signed_in
    offer = flight_offer(client)
    flight = db_session.get(Flight, uuid.UUID(offer))
    assert flight is not None
    db_session.add(
        FlightInventory(
            flight_id=flight.id, capacity=flight.seat_capacity, reserved=flight.seat_capacity - 1
        )
    )
    db_session.commit()
    assert hold(client, [{"kind": "flight", "offer_id": offer}]).status_code == 201
    second = hold(client, [{"kind": "flight", "offer_id": offer}])
    assert second.status_code == 409 and code(second) == "SOLD_OUT"


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="real row-level concurrency needs PostgreSQL"
)
def test_twenty_buyers_one_seat_real_threads(
    engine: Engine, catalog: None, db_session: Session
) -> None:
    flight = db_session.scalars(select(Flight).limit(1)).one()
    db_session.add(
        FlightInventory(
            flight_id=flight.id, capacity=flight.seat_capacity, reserved=flight.seat_capacity - 1
        )
    )
    db_session.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    results: list[str] = []
    barrier = threading.Barrier(20)

    def buy() -> None:
        with factory() as session:
            barrier.wait()
            try:
                InventoryService(session).reserve_seats(uuid.uuid4(), flight, 1)
                session.commit()
                results.append("won")
            except SoldOut:
                session.rollback()
                results.append("sold_out")

    threads = [threading.Thread(target=buy) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("won") == 1 and results.count("sold_out") == 19


def test_confirm_without_a_card(signed_in: TestClient) -> None:
    client = signed_in
    booking = hold(client, [{"kind": "flight", "offer_id": flight_offer(client)}]).json()
    confirmed = pay(client, booking["id"], {}, key="confirm-1").json()
    assert confirmed["status"] == "confirmed"
    again = pay(client, booking["id"], {}, key="confirm-1").json()
    assert len(again["payments"]) == len(confirmed["payments"]) == 1  # recorded once
    half = pay(client, booking["id"], {"card_number": "4242 4242 4242 4242"})
    assert half.status_code == 422  # a card, when given, must be complete
