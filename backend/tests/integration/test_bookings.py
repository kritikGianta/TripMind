"""Flight booking as a guest: confirm in one step, a 10-digit reference, and no overselling."""

from __future__ import annotations

import os
import threading
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Flight, FlightInventory
from app.modules.inventory.service import InventoryService, SoldOut

API = "/api/v1"


@pytest.fixture
def guest(client: TestClient, holiday_pack: None) -> TestClient:
    """A private guest session: no sign-up, no password."""
    assert client.post(f"{API}/auth/guest").status_code in (200, 201)
    return client


def a_flight(session: Session) -> Flight:
    return session.scalars(
        select(Flight).where(Flight.fare_minor.is_not(None)).order_by(Flight.departure_at)
    ).first()  # type: ignore[return-value]


def book(client: TestClient, flight: Flight) -> Any:
    return client.post(
        f"{API}/bookings",
        json={
            "items": [{"kind": "flight", "offer_id": str(flight.id), "adults": 1}],
            "travellers": [{"first_name": "Asha", "last_name": "Rao"}],
            "contact": {"email": "asha@example.com"},
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )


def confirm(client: TestClient, booking_id: str, key: str = "confirm-1") -> Any:
    # No card: the empty body confirms the booking (payment is out of scope).
    return client.post(
        f"{API}/bookings/{booking_id}/payments", json={}, headers={"Idempotency-Key": key}
    )


def test_guest_books_and_confirms_with_a_10_digit_reference(
    guest: TestClient, db_session: Session
) -> None:
    flight = a_flight(db_session)
    created = book(guest, flight)
    assert created.status_code == 201, created.text
    booking = created.json()
    assert booking["reference"].isdigit() and len(booking["reference"]) == 10

    confirmed = confirm(guest, booking["id"]).json()
    assert confirmed["status"] == "confirmed"
    again = confirm(guest, booking["id"]).json()  # same key: recorded once
    assert len(again["payments"]) == 1
    assert db_session.get(FlightInventory, flight.id).reserved == 1  # type: ignore[union-attr]

    trips = guest.get(f"{API}/trips").json()["items"]
    assert len(trips) == 1


def test_bookings_are_private(guest: TestClient, db_session: Session) -> None:
    booking = book(guest, a_flight(db_session)).json()
    guest.cookies.clear()
    guest.post(f"{API}/auth/guest")  # a different guest
    assert guest.get(f"{API}/bookings/{booking['id']}").status_code == 404


def test_last_seat_is_sold_once(guest: TestClient, db_session: Session) -> None:
    flight = a_flight(db_session)
    db_session.add(
        FlightInventory(
            flight_id=flight.id, capacity=flight.seat_capacity, reserved=flight.seat_capacity - 1
        )
    )
    db_session.commit()
    assert book(guest, flight).status_code == 201
    second = book(guest, flight)
    assert second.status_code == 409 and second.json()["error"]["code"] == "SOLD_OUT"


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="real row-level concurrency needs PostgreSQL"
)
def test_twenty_buyers_one_seat_real_threads(
    engine: Engine, holiday_pack: None, db_session: Session
) -> None:
    flight = a_flight(db_session)
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
