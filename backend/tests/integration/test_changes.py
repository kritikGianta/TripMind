"""Booking changes: move a flight or a stay without cancelling, with fees, refunds and inventory."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, FlightInventory, Refund, RoomNightInventory
from tests.integration.test_bookings import (
    API,
    DECLINED_CARD,
    GOOD_CARD,
    code,
    hold,
    hotel_room,
    pay,
    signed_in,  # noqa: F401  (fixture)
)


def offers(client: TestClient, day: str, adults: int = 1) -> list[dict[str, Any]]:
    body = client.get(
        f"{API}/flights/search",
        params={
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": day,
            "adults": adults,
            "max_stops": 0,
            "sort": "cheapest",
        },
    ).json()
    return [o for o in body["outbound"]["offers"] if o["bookable"]]


def booked(client: TestClient, items: list[dict[str, Any]]) -> dict[str, Any]:
    created = hold(client, items)
    assert created.status_code == 201, created.text
    paid = pay(client, created.json()["id"], GOOD_CARD)
    assert paid.status_code == 200, paid.text
    return dict(paid.json())


def quote(client: TestClient, booking: dict[str, Any], body: dict[str, Any]) -> Any:
    item_id = booking["items"][0]["id"]
    return client.post(f"{API}/bookings/{booking['id']}/items/{item_id}/change-quote", json=body)


def change(
    client: TestClient, booking: dict[str, Any], body: dict[str, Any], key: str | None = None
) -> Any:
    item_id = booking["items"][0]["id"]
    return client.post(
        f"{API}/bookings/{booking['id']}/items/{item_id}/change",
        json=body,
        headers={"Idempotency-Key": key or uuid.uuid4().hex},
    )


def reserved(session: Session, flight_id: str) -> int:
    session.expire_all()
    row = session.get(FlightInventory, uuid.UUID(flight_id))
    return row.reserved if row else 0


def test_free_flight_change_moves_seats_and_refunds_a_cheaper_fare(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    # Book the dearest flight of the day, then move to the cheapest the next day.
    dearest = offers(client, "2026-11-14")[-1]
    booking = booked(client, [{"kind": "flight", "offer_id": dearest["id"], "adults": 1}])
    target = offers(client, "2026-11-15")[0]

    q = quote(client, booking, {"flight_offer_id": target["id"]}).json()
    assert q["allowed"] and q["change_fee"]["amount_minor"] == 0
    difference = q["price_difference"]["amount_minor"]
    assert q["amount_due"]["amount_minor"] == max(difference, 0)
    assert q["refund_due"]["amount_minor"] == max(-difference, 0)

    body = {
        "flight_offer_id": target["id"],
        "expected_amount_due_minor": q["amount_due"]["amount_minor"],
    }
    if q["amount_due"]["amount_minor"]:
        body["payment"] = GOOD_CARD
    response = change(client, booking, body)
    assert response.status_code == 200, response.text
    after = response.json()
    old, new = after["items"][0], after["items"][1]
    assert old["status"] == "replaced" and old["replaced_by_item_id"] == new["id"]
    assert new["status"] == "confirmed" and "changed" in [e["type"] for e in after["events"]]
    assert reserved(db_session, dearest["id"]) == 0 and reserved(db_session, target["id"]) == 1
    refunds = db_session.scalars(
        select(Refund).where(Refund.booking_item_id == uuid.UUID(old["id"]))
    )
    assert sum(r.amount_minor for r in refunds) == q["refund_due"]["amount_minor"]


def test_late_flight_change_charges_the_fee_and_is_safe_to_retry(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    first, *others = offers(client, "2026-11-14")
    booking = booked(client, [{"kind": "flight", "offer_id": first["id"], "adults": 1}])
    # Booked 25 hours ago: outside the free change window.
    row = db_session.get(Booking, uuid.UUID(booking["id"]))
    assert row is not None and row.confirmed_at is not None
    row.confirmed_at -= timedelta(hours=25)
    db_session.commit()
    target = others[0]
    q = quote(client, booking, {"flight_offer_id": target["id"]}).json()
    due = q["amount_due"]["amount_minor"]
    assert q["change_fee"]["amount_minor"] == 1500 * 100
    assert q["refund_due"]["amount_minor"] == 0  # cheaper fares refund only in the free window
    body: dict[str, Any] = {"flight_offer_id": target["id"], "expected_amount_due_minor": due}

    assert code(change(client, booking, body)) == "PAYMENT_REQUIRED"
    stale = change(
        client, booking, {**body, "expected_amount_due_minor": due + 1, "payment": GOOD_CARD}
    )
    assert stale.status_code == 409 and code(stale) == "CHANGE_PRICE_CHANGED"

    declined = change(client, booking, {**body, "payment": DECLINED_CARD})
    assert declined.status_code == 402
    unchanged = client.get(f"{API}/bookings/{booking['id']}").json()
    assert [i["status"] for i in unchanged["items"]] == ["confirmed"]
    assert reserved(db_session, first["id"]) == 1 and reserved(db_session, target["id"]) == 0

    key = uuid.uuid4().hex
    done = change(client, booking, {**body, "payment": GOOD_CARD}, key=key)
    assert done.status_code == 200, done.text
    assert done.json()["total"]["amount_minor"] == booking["total"]["amount_minor"] + due
    again = change(client, booking, {**body, "payment": GOOD_CARD}, key=key)
    assert again.status_code == 200 and again.json() == done.json()
    assert reserved(db_session, target["id"]) == 1


def test_flight_change_keeps_the_route(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    mine = offers(client, "2026-11-14")[0]["id"]
    booking = booked(client, [{"kind": "flight", "offer_id": mine}])
    other = client.get(
        f"{API}/flights/search",
        params={"origin": "DEL", "destination": "BLR", "departure_date": "2026-11-14"},
    ).json()["outbound"]["offers"][0]
    q = quote(client, booking, {"flight_offer_id": other["id"]}).json()
    assert not q["allowed"] and "same route" in q["reason"]
    refused = change(
        client, booking, {"flight_offer_id": other["id"], "expected_amount_due_minor": 0}
    )
    assert refused.status_code == 409 and code(refused) == "CHANGE_NOT_ALLOWED"
    same = quote(client, booking, {"flight_offer_id": mine}).json()
    assert not same["allowed"]


def test_refundable_stay_moves_to_overlapping_dates(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    room = hotel_room(client, refundable=True)
    booking = booked(client, [room])
    dates = {"check_in": "2026-11-13", "check_out": "2026-11-15"}
    q = quote(client, booking, dates).json()
    assert q["allowed"] and q["change_fee"]["amount_minor"] == 0
    body: dict[str, Any] = {**dates, "expected_amount_due_minor": q["amount_due"]["amount_minor"]}
    if q["amount_due"]["amount_minor"]:
        body["payment"] = GOOD_CARD
    response = change(client, booking, body)
    assert response.status_code == 200, response.text
    db_session.expire_all()
    nights = {
        str(r.night): r.reserved
        for r in db_session.scalars(
            select(RoomNightInventory).where(
                RoomNightInventory.room_type_id == uuid.UUID(room["room_type_id"])
            )
        )
    }
    assert nights == {"2026-11-13": 1, "2026-11-14": 1, "2026-11-15": 0}


def test_non_refundable_stay_cannot_change(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = booked(client, [hotel_room(client, refundable=False)])
    q = quote(client, booking, {"check_in": "2026-11-13", "check_out": "2026-11-15"}).json()
    assert not q["allowed"] and "Non-refundable" in q["reason"]


def test_change_request_must_name_one_kind(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = booked(
        client, [{"kind": "flight", "offer_id": offers(client, "2026-11-14")[0]["id"]}]
    )
    assert quote(client, booking, {}).status_code == 422
    assert quote(client, booking, {"check_in": "2026-11-13"}).status_code == 422
