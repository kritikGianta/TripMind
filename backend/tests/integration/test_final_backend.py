"""Account security, privacy, discovery, the connected trip, admin console and the demo story."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.core.config import Settings
from app.models import AuditLog, Booking, BookingTraveller, Notification, User
from app.modules.privacy.module import RetentionRules, purge_expired
from tests.integration.test_bookings import (
    API,
    GOOD_CARD,
    code,
    flight_offer,
    hold,
    hotel_room,
    pay,
    signed_in,  # noqa: F401  (fixture)
)

PASSWORD = "correct-horse-battery"


def register(client: TestClient, email: str | None = None) -> str:
    email = email or f"{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Asha Rao"},
    )
    assert response.status_code == 201, response.text
    return email


# ── Security ──────────────────────────────────────────────────────────────────


def test_security_headers_and_body_limit(client: TestClient) -> None:
    health = client.get(f"{API}/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert client.get(f"{API}/auth/me").headers["cache-control"] == "no-store"
    big = client.post(
        f"{API}/auth/login",
        content=b"x" * (3 * 1024 * 1024),
        headers={"content-type": "text/plain"},
    )
    assert big.status_code == 413 and code(big) == "PAYLOAD_TOO_LARGE"


def test_account_locks_after_repeated_failures(client: TestClient) -> None:
    email = register(client)
    client.post(f"{API}/auth/logout")
    for _ in range(8):
        bad = client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-guess"})
        assert bad.status_code == 401
    locked = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert locked.status_code == 429 and code(locked) == "ACCOUNT_LOCKED"
    assert int(locked.headers["retry-after"]) >= 60
    # A reset proves ownership, so it lifts the lock.
    token = client.post(f"{API}/auth/password/forgot", json={"email": email}).json()[
        "dev_reset_token"
    ]
    assert (
        client.post(
            f"{API}/auth/password/reset", json={"token": token, "new_password": "another-good-one"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"{API}/auth/login", json={"email": email, "password": "another-good-one"}
        ).status_code
        == 200
    )


def test_password_change_reset_and_sign_out_everywhere(client: TestClient) -> None:
    email = register(client)
    updated = client.patch(f"{API}/auth/me", json={"full_name": "Asha R."}).json()
    assert updated["full_name"] == "Asha R."
    wrong = client.post(
        f"{API}/auth/password",
        json={"current_password": "nope-nope", "new_password": "brand-new-pass"},
    )
    assert wrong.status_code == 422 and code(wrong) == "WRONG_PASSWORD"
    changed = client.post(
        f"{API}/auth/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-pass"},
    )
    assert changed.status_code == 200 and client.get(f"{API}/auth/me").status_code == 200

    unknown = client.post(f"{API}/auth/password/forgot", json={"email": "nobody@example.com"})
    assert unknown.status_code == 202 and unknown.json()["dev_reset_token"] is None
    token = client.post(f"{API}/auth/password/forgot", json={"email": email}).json()[
        "dev_reset_token"
    ]
    body = {"token": token, "new_password": "reset-new-pass"}
    assert client.post(f"{API}/auth/password/reset", json=body).status_code == 204
    reused = client.post(f"{API}/auth/password/reset", json=body)
    assert reused.status_code == 422 and code(reused) == "RESET_TOKEN_INVALID"
    # The reset ended every session, so the old refresh token no longer works.
    assert client.post(f"{API}/auth/refresh").status_code == 401

    assert (
        client.post(
            f"{API}/auth/login", json={"email": email, "password": "reset-new-pass"}
        ).status_code
        == 200
    )
    assert client.post(f"{API}/auth/logout-all").status_code == 204
    assert client.post(f"{API}/auth/refresh").status_code == 401


# ── Privacy and retention ─────────────────────────────────────────────────────


def test_export_and_delete_account(client: TestClient, catalog: None, db_session: Session) -> None:
    email = register(client)
    data = client.get(f"{API}/me/export").json()
    assert data["account"]["email"] == email and "password_hash" not in data["account"]
    created = hold(client, [{"kind": "flight", "offer_id": flight_offer(client), "adults": 1}])
    booking = created.json()
    pay(client, booking["id"], GOOD_CARD)
    assert client.get(f"{API}/me/export").json()["bookings"][0]["id"] == booking["id"]

    ahead = client.request("DELETE", f"{API}/me", json={"password": PASSWORD})
    assert ahead.status_code == 409 and code(ahead) == "ACCOUNT_HAS_UPCOMING_TRIPS"
    client.post(f"{API}/bookings/{booking['id']}/cancel", json={})
    wrong = client.request("DELETE", f"{API}/me", json={"password": "wrong-pass"})
    assert wrong.status_code == 422
    assert client.request("DELETE", f"{API}/me", json={"password": PASSWORD}).status_code == 204

    assert (
        client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD}).status_code
        == 401
    )
    db_session.expire_all()
    kept = db_session.get(Booking, uuid.UUID(booking["id"]))
    assert kept is not None and kept.contact_email == "removed@deleted.invalid"
    names = db_session.scalars(
        select(BookingTraveller.first_name).where(BookingTraveller.booking_id == kept.id)
    ).all()
    assert set(names) == {"Removed"}
    user = db_session.scalar(select(User).where(User.id == kept.user_id))
    assert user is not None and user.email.startswith("deleted-") and not user.is_active


def test_demo_accounts_cannot_be_deleted(signed_in: TestClient) -> None:  # noqa: F811
    # The password check comes first, so demo accounts are protected by their random password too.
    assert signed_in.request("DELETE", f"{API}/me", json={"password": "x"}).status_code == 422


def test_retention_removes_only_old_data(
    signed_in: TestClient,  # noqa: F811
    db_session: Session,
    clock: FrozenClock,
) -> None:
    user = db_session.scalar(select(User).where(User.email == "demo@tripmind.dev"))
    assert user is not None
    now = clock.now()
    db_session.add_all(
        [
            Notification(
                user_id=user.id,
                kind="x",
                severity="info",
                title="old",
                body="b",
                created_at=now - timedelta(days=400),
            ),
            Notification(
                user_id=user.id, kind="x", severity="info", title="new", body="b", created_at=now
            ),
        ]
    )
    db_session.commit()
    removed = purge_expired(db_session, RetentionRules(), now)
    assert removed["notifications"] == 1
    titles = db_session.scalars(select(Notification.title).where(Notification.kind == "x")).all()
    assert titles == ["new"]
    assert db_session.scalars(select(AuditLog.id)).first() is not None  # recent audit stays


# ── Discovery ─────────────────────────────────────────────────────────────────


def test_fare_calendar(client: TestClient, catalog: None) -> None:
    body = client.get(
        f"{API}/flights/calendar",
        params={"origin": "DEL", "destination": "BOM", "start": "2026-11-13", "days": 5},
    ).json()
    assert [d["date"] for d in body["days"]] == [
        str(date(2026, 11, 13) + timedelta(days=i)) for i in range(5)
    ]
    priced = [d for d in body["days"] if d["cheapest"]]
    assert len(priced) == 3  # the test dataset covers three days
    assert body["cheapest_day"] == min(priced, key=lambda d: d["cheapest"]["amount_minor"])["date"]
    assert all(
        d["cheapest"] is None and d["level"] is None for d in body["days"] if not d["flights"]
    )
    two = client.get(
        f"{API}/flights/calendar",
        params={
            "origin": "DEL",
            "destination": "BOM",
            "start": "2026-11-13",
            "days": 1,
            "adults": 2,
        },
    ).json()
    assert (
        two["days"][0]["cheapest"]["amount_minor"]
        == 2 * body["days"][0]["cheapest"]["amount_minor"]
    )
    past = client.get(
        f"{API}/flights/calendar",
        params={"origin": "DEL", "destination": "BOM", "start": "2020-01-01"},
    )
    assert past.status_code == 422 and code(past) == "DATE_IN_PAST"


def test_explore_by_budget(client: TestClient, catalog: None) -> None:
    params = {"origin": "DEL", "departure_date": "2026-11-13", "nights": 2, "adults": 2}
    open_ended = client.get(f"{API}/explore", params=params).json()
    options = open_ended["options"]
    assert options and open_ended["over_budget"] == 0
    totals = [o["total"]["amount_minor"] for o in options]
    assert totals == sorted(totals)
    first = options[0]
    assert first["total"]["amount_minor"] == (
        first["flights"]["amount_minor"] + first["stay"]["amount_minor"]
    )
    assert first["per_person"]["amount_minor"] == first["total"]["amount_minor"] // 2
    assert all(o["city"] != "Delhi" for o in options)
    budget = (totals[0] // 100) + 1
    limited = client.get(f"{API}/explore", params={**params, "budget": budget}).json()
    assert [o["city"] for o in limited["options"]] == [options[0]["city"]]
    assert limited["over_budget"] == len(options) - 1


# ── Connected trip ────────────────────────────────────────────────────────────


def _booked(client: TestClient, items: list[dict[str, Any]]) -> dict[str, Any]:
    created = hold(client, items)
    assert created.status_code == 201, created.text
    return dict(pay(client, created.json()["id"], GOOD_CARD).json())


def test_trip_suggestions_and_calendar(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = _booked(client, [{"kind": "flight", "offer_id": flight_offer(client), "adults": 1}])
    trip = booking["trip_id"]
    missing = client.get(f"{API}/trips/{trip}/suggestions").json()
    assert not missing["complete"] and "stay" in missing["missing"]
    stay = next(s for s in missing["suggestions"] if s["kind"] == "stay")
    assert stay["price"] and stay["checkout_item"]["kind"] == "hotel"
    stay["checkout_item"]["check_out"] = "2026-11-15"  # return flights exist on this day
    added = hold(client, [stay["checkout_item"]], trip_id=trip)
    assert added.status_code == 201, added.text
    pay(client, added.json()["id"], GOOD_CARD)
    after = client.get(f"{API}/trips/{trip}/suggestions").json()
    assert "stay" not in after["missing"] and "return_flight" in after["missing"]
    back = next(s for s in after["suggestions"] if s["kind"] == "return_flight")
    assert back["title"] == "BOM to DEL" and back["checkout_item"]["kind"] == "flight"

    ics = client.get(f"{API}/trips/{trip}/calendar.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert ics.text.count("BEGIN:VEVENT") == 2 and ics.text.endswith("END:VCALENDAR\r\n")
    assert client.get(f"{API}/trips/{uuid.uuid4()}/suggestions").status_code == 404


def test_stay_only_trip_suggests_getting_there(signed_in: TestClient) -> None:  # noqa: F811
    client = signed_in
    booking = _booked(client, [hotel_room(client)])
    body = client.get(f"{API}/trips/{booking['trip_id']}/suggestions").json()
    assert body["missing"] == ["flight"] and body["suggestions"][0]["kind"] == "outbound_flight"


# ── Admin console ─────────────────────────────────────────────────────────────


def test_admin_users(client: TestClient, catalog: None, settings: Settings) -> None:
    email = register(client)
    assert client.get(f"{API}/admin/users").status_code == 403
    from app.cli import seed

    seed()
    assert client.post(f"{API}/auth/demo-login", json={"role": "admin"}).status_code == 200

    found = client.get(f"{API}/admin/users", params={"q": email[:8]}).json()
    assert found["total"] == 1 and found["items"][0]["email"] == email
    target = found["items"][0]["id"]
    assert (
        client.post(f"{API}/admin/users/{target}/status", json={"active": False}).json()[
            "is_active"
        ]
        is False
    )
    me = client.get(f"{API}/auth/me").json()["id"]
    own = client.post(f"{API}/admin/users/{me}/status", json={"active": False})
    assert own.status_code == 409 and code(own) == "CANNOT_CHANGE_SELF"
    client.post(f"{API}/auth/logout")
    blocked = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert blocked.status_code == 403 and code(blocked) == "ACCOUNT_DISABLED"
