"""Support tickets: filed by category, urgent when the trip is close, worked by admins."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Notification
from tests.integration.test_bookings import (
    API,
    GOOD_CARD,
    code,
    flight_offer,
    hold,
    pay,
    signed_in,  # noqa: F401  (fixture)
)


def ticket(client: TestClient, subject: str, message: str, **extra: Any) -> Any:
    return client.post(
        f"{API}/support/tickets", json={"subject": subject, "message": message, **extra}
    )


def as_admin(client: TestClient) -> None:
    assert client.post(f"{API}/auth/demo-login", json={"role": "admin"}).status_code == 200


def as_traveller(client: TestClient) -> None:
    assert client.post(f"{API}/auth/demo-login", json={"role": "traveler"}).status_code == 200


def test_ticket_is_filed_and_answered(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
) -> None:
    client = signed_in
    created = ticket(client, "Refund please", "I cancelled my trip, when do I get my money back?")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["reference"].startswith("SR") and body["status"] == "open"
    assert (body["category"], body["category_source"]) == ("cancellation_refund", "rules")
    assert body["priority"] == "normal"
    assert [m["author_role"] for m in body["messages"]] == ["traveller", "system"]
    assert "Cancellation or refund" in body["messages"][1]["body"]

    as_admin(client)
    queue = client.get(f"{API}/admin/support/tickets").json()
    assert [t["reference"] for t in queue["items"]] == [body["reference"]]
    assert queue["items"][0]["traveller_email"] == "demo@tripmind.dev"
    reply = client.post(
        f"{API}/admin/support/tickets/{body['id']}/messages",
        json={"body": "Your refund was issued today.", "status": "resolved"},
    )
    assert reply.status_code == 200 and reply.json()["status"] == "resolved"
    refiled = client.patch(
        f"{API}/admin/support/tickets/{body['id']}", json={"category": "existing_booking"}
    ).json()
    assert (refiled["category"], refiled["category_source"]) == ("existing_booking", "admin")
    actions = set(db_session.scalars(select(AuditLog.action)))
    assert {"support.ticket_created", "support.agent_reply", "support.ticket_updated"} <= actions

    as_traveller(client)
    note = db_session.scalars(
        select(Notification).where(Notification.kind == "support_reply")
    ).one()
    assert note.link == f"/support/{body['id']}"
    reopened = client.post(
        f"{API}/support/tickets/{body['id']}/messages", json={"body": "Not received yet."}
    ).json()
    assert reopened["status"] == "open" and reopened["resolved_at"] is None
    closed = client.post(f"{API}/support/tickets/{body['id']}/close").json()
    assert closed["status"] == "closed"
    late = client.post(f"{API}/support/tickets/{body['id']}/messages", json={"body": "hi"})
    assert late.status_code == 409 and code(late) == "TICKET_CLOSED"
    mine = client.get(f"{API}/support/tickets").json()
    assert mine["counts"]["closed"] == 1 and len(mine["items"]) == 1


def test_urgent_when_the_trip_is_close_or_a_person_is_asked_for(
    signed_in: TestClient,  # noqa: F811
) -> None:
    client = signed_in
    created = hold(client, [{"kind": "flight", "offer_id": flight_offer(client), "adults": 1}])
    booking = pay(client, created.json()["id"], GOOD_CARD).json()
    # The flight is a week away: outside the 72-hour urgent window.
    soon = ticket(client, "Baggage", "How many kg can I take?", booking_id=booking["id"]).json()
    assert soon["priority"] == "normal" and soon["booking_reference"] == booking["reference"]
    person = ticket(client, "Help", "I want to speak to a real person about my trip").json()
    assert (person["category"], person["priority"]) == ("human_agent", "high")
    as_admin(client)
    first = client.get(f"{API}/admin/support/tickets").json()["items"][0]
    assert first["id"] == person["id"]  # urgent first


def test_tickets_are_private(client: TestClient, signed_in: TestClient) -> None:  # noqa: F811
    created = ticket(signed_in, "Seat", "Can I choose a window seat?").json()
    other = ticket(signed_in, "x", "y" * 12)
    assert other.status_code == 422  # subject too short
    assert signed_in.get(f"{API}/admin/support/tickets").status_code == 403
    bad_booking = ticket(signed_in, "About booking", "Question about it", booking_id=created["id"])
    assert bad_booking.status_code == 404 and code(bad_booking) == "BOOKING_NOT_FOUND"
    signed_in.post(f"{API}/auth/logout")
    assert signed_in.get(f"{API}/support/tickets/{created['id']}").status_code == 401
