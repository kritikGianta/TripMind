"""Seats, baggage and meals: buy, swap, the one-passenger-per-seat rule, and refunds."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BookingExtra, Refund
from tests.integration.test_bookings import (
    API,
    DECLINED_CARD,
    GOOD_CARD,
    code,
    flight_offer,
    hold,
    hotel_room,
    pay,
    signed_in,  # noqa: F401  (fixture)
)


def booked(client: TestClient, items: list[dict[str, Any]], travellers: int = 1) -> dict[str, Any]:
    created = hold(client, items, travellers=travellers)
    assert created.status_code == 201, created.text
    paid = pay(client, created.json()["id"], GOOD_CARD)
    assert paid.status_code == 200, paid.text
    return dict(paid.json())


def flight_booking(client: TestClient, adults: int = 1) -> dict[str, Any]:
    offer = flight_offer(client, adults=adults)
    return booked(client, [{"kind": "flight", "offer_id": offer, "adults": adults}], adults)


def url(booking: dict[str, Any], suffix: str) -> str:
    return f"{API}/bookings/{booking['id']}/items/{booking['items'][0]['id']}/{suffix}"


def seat_map(client: TestClient, booking: dict[str, Any], flight_id: str) -> dict[str, Any]:
    response = client.get(url(booking, "seat-map"), params={"flight_id": flight_id})
    assert response.status_code == 200, response.text
    return dict(response.json())


def seats_by_zone(seats: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    zones: dict[str, list[dict[str, Any]]] = {}
    for row in seats["rows"]:
        for seat in row["seats"]:
            zones.setdefault(seat["zone"], []).append(seat)
    return zones


def buy(
    client: TestClient,
    booking: dict[str, Any],
    selections: list[dict[str, Any]],
    card: dict[str, Any] | None = GOOD_CARD,
    key: str | None = None,
) -> Any:
    quote = client.post(url(booking, "extras/quote"), json={"selections": selections})
    assert quote.status_code == 200, quote.text
    total = quote.json()["total"]["amount_minor"]
    body: dict[str, Any] = {"selections": selections, "expected_total_minor": total}
    if total and card:
        body["payment"] = card
    return client.post(
        url(booking, "extras"), json=body, headers={"Idempotency-Key": key or uuid.uuid4().hex}
    )


def test_buy_seats_bags_and_meals(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = flight_booking(client, adults=2)
    catalog = client.get(url(booking, "extras")).json()
    assert catalog["open"] and len(catalog["travellers"]) == 2 and catalog["selected"] == []
    leg = catalog["flights"][0]
    assert leg["baggage"] and leg["meals"] and leg["route"].startswith("DEL")
    flight_id = leg["flight_id"]
    seats = seat_map(client, booking, flight_id)
    assert seats["note"].startswith("Seat plan derived") and seats["groups"]
    window = seats_by_zone(seats)["window_or_aisle"][0]
    t1, t2 = (t["id"] for t in catalog["travellers"])
    bag, meal = leg["baggage"][0], leg["meals"][0]
    selections = [
        {"flight_id": flight_id, "traveller_id": t1, "kind": "seat", "code": window["code"]},
        {"flight_id": flight_id, "traveller_id": t1, "kind": "baggage", "code": bag["code"]},
        {"flight_id": flight_id, "traveller_id": t2, "kind": "meal", "code": meal["code"]},
    ]
    expected = (
        window["price"]["amount_minor"]
        + bag["price"]["amount_minor"]
        + meal["price"]["amount_minor"]
    )
    key = uuid.uuid4().hex
    response = buy(client, booking, selections, key=key)
    assert response.status_code == 200, response.text
    after = response.json()
    assert after["total"]["amount_minor"] == booking["total"]["amount_minor"] + expected
    assert {e["kind"] for e in after["items"][0]["extras"]} == {"seat", "baggage", "meal"}
    assert "extras" in [e["type"] for e in after["events"]]
    again = client.post(
        url(booking, "extras"),
        json={"selections": selections, "expected_total_minor": expected, "payment": GOOD_CARD},
        headers={"Idempotency-Key": key},
    )
    assert again.json()["total"] == after["total"]  # retried: charged once
    mine = next(
        s
        for r in seat_map(client, booking, flight_id)["rows"]
        for s in r["seats"]
        if s["code"] == window["code"]
    )
    assert not mine["available"] and mine["traveller_id"] == t1


def test_seat_is_never_sold_twice(signed_in: TestClient, db_session: Session) -> None:  # noqa: F811
    client = signed_in
    first = flight_booking(client)
    second = flight_booking(client)
    flight_id = client.get(url(first, "extras")).json()["flights"][0]["flight_id"]
    seat = seats_by_zone(seat_map(client, first, flight_id))["middle"][0]["code"]

    def pick(booking: dict[str, Any]) -> list[dict[str, Any]]:
        traveller = booking["travellers"][0]["id"]
        return [{"flight_id": flight_id, "traveller_id": traveller, "kind": "seat", "code": seat}]

    free = buy(client, first, pick(first), card=None)  # a middle seat costs nothing
    assert free.status_code == 200, free.text
    assert free.json()["payments"] == booking_payments(first)  # no-charge record stays hidden
    taken = client.post(url(second, "extras/quote"), json={"selections": pick(second)})
    assert taken.status_code == 409 and code(taken) == "SEAT_TAKEN"

    # The database itself refuses a second active passenger in the same seat.
    existing = db_session.scalars(select(BookingExtra).where(BookingExtra.code == seat)).one()
    db_session.add(
        BookingExtra(
            booking_id=uuid.UUID(second["id"]),
            booking_item_id=uuid.UUID(second["items"][0]["id"]),
            flight_id=existing.flight_id,
            traveller_id=uuid.UUID(second["travellers"][0]["id"]),
            kind="seat",
            code=seat,
            label="x",
            price_minor=0,
            paid_minor=0,
            currency="INR",
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def booking_payments(booking: dict[str, Any]) -> list[dict[str, Any]]:
    return list(booking["payments"])


def test_swap_charges_only_the_difference(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = flight_booking(client)
    flight_id = client.get(url(booking, "extras")).json()["flights"][0]["flight_id"]
    zones = seats_by_zone(seat_map(client, booking, flight_id))
    traveller = booking["travellers"][0]["id"]

    def seat(code_: str) -> list[dict[str, Any]]:
        return [{"flight_id": flight_id, "traveller_id": traveller, "kind": "seat", "code": code_}]

    cheap, dear = zones["window_or_aisle"][0], zones["extra_legroom"][0]
    assert buy(client, booking, seat(cheap["code"])).status_code == 200
    quote = client.post(url(booking, "extras/quote"), json={"selections": seat(dear["code"])})
    line = quote.json()["lines"][0]
    assert line["credit"]["amount_minor"] == cheap["price"]["amount_minor"]
    assert line["charge"]["amount_minor"] == (
        dear["price"]["amount_minor"] - cheap["price"]["amount_minor"]
    )
    assert buy(client, booking, seat(dear["code"])).status_code == 200
    back = client.post(url(booking, "extras/quote"), json={"selections": seat(cheap["code"])})
    assert back.json()["total"]["amount_minor"] == 0  # a cheaper pick is never refunded
    seats_now = {
        s["code"]: s["available"]
        for r in seat_map(client, booking, flight_id)["rows"]
        for s in r["seats"]
    }
    assert seats_now[cheap["code"]] and not seats_now[dear["code"]]
    same = client.post(
        url(booking, "extras"),
        json={"selections": seat(dear["code"]), "expected_total_minor": 0},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert same.status_code == 409 and code(same) == "NOTHING_TO_CHANGE"


def test_declined_card_keeps_the_seat_free(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = flight_booking(client)
    flight_id = client.get(url(booking, "extras")).json()["flights"][0]["flight_id"]
    seat = seats_by_zone(seat_map(client, booking, flight_id))["front"][0]["code"]
    pick = [
        {
            "flight_id": flight_id,
            "traveller_id": booking["travellers"][0]["id"],
            "kind": "seat",
            "code": seat,
        }
    ]
    declined = buy(client, booking, pick, card=DECLINED_CARD)
    assert declined.status_code == 402
    still = {s["code"]: s for r in seat_map(client, booking, flight_id)["rows"] for s in r["seats"]}
    assert still[seat]["available"]
    assert code(buy(client, booking, pick, card=None)) == "PAYMENT_REQUIRED"


def test_extras_are_refunded_with_their_flight(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    booking = flight_booking(client)
    catalog = client.get(url(booking, "extras")).json()
    leg = catalog["flights"][0]
    bag = leg["baggage"][0]
    pick = [
        {
            "flight_id": leg["flight_id"],
            "traveller_id": catalog["travellers"][0]["id"],
            "kind": "baggage",
            "code": bag["code"],
        }
    ]
    assert buy(client, booking, pick).status_code == 200
    item_id = booking["items"][0]["id"]
    cancelled = client.post(f"{API}/bookings/{booking['id']}/cancel", json={"item_ids": [item_id]})
    assert cancelled.status_code == 200, cancelled.text
    refunded = sum(
        r.amount_minor
        for r in db_session.scalars(
            select(Refund).where(Refund.booking_item_id == uuid.UUID(item_id))
        )
    )
    # Cancelled inside the free window: fare and bag both come back.
    assert refunded == booking["total"]["amount_minor"] + bag["price"]["amount_minor"]
    assert cancelled.json()["items"][0]["extras"] == []


def test_stays_have_no_extras(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = booked(client, [hotel_room(client)])
    response = client.get(url(booking, "extras"))
    assert response.status_code == 422 and code(response) == "NOT_A_FLIGHT"


def test_flight_change_refunds_extras_and_frees_the_seat(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = flight_booking(client)
    flight_id = client.get(url(booking, "extras")).json()["flights"][0]["flight_id"]
    seat = seats_by_zone(seat_map(client, booking, flight_id))["extra_legroom"][0]
    traveller = booking["travellers"][0]["id"]
    pick = [
        {"flight_id": flight_id, "traveller_id": traveller, "kind": "seat", "code": seat["code"]}
    ]
    assert buy(client, booking, pick).status_code == 200

    other = next(
        o["id"]
        for o in client.get(
            f"{API}/flights/search",
            params={"origin": "DEL", "destination": "BOM", "departure_date": "2026-11-15"},
        ).json()["outbound"]["offers"]
        if o["bookable"]
    )
    quote = client.post(url(booking, "change-quote"), json={"flight_offer_id": other}).json()
    assert quote["extras_refund"]["amount_minor"] == seat["price"]["amount_minor"]
    body: dict[str, Any] = {
        "flight_offer_id": other,
        "expected_amount_due_minor": quote["amount_due"]["amount_minor"],
    }
    if quote["amount_due"]["amount_minor"]:
        body["payment"] = GOOD_CARD
    changed = client.post(
        url(booking, "change"), json=body, headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert changed.status_code == 200, changed.text
    reasons = [r["reason"] for r in changed.json()["refunds"]]
    assert "Seats and extras on the previous flight." in reasons
    old_map = seat_map(client, booking, flight_id)  # old item is replaced but still readable
    assert next(s for r in old_map["rows"] for s in r["seats"] if s["code"] == seat["code"])[
        "available"
    ]
