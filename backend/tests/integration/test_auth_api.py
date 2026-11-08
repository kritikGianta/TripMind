from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli import seed
from app.core.clock import FrozenClock
from app.core.deps import get_feature_flags
from app.core.features import FeatureFlags
from app.models import AuditLog, RefreshToken

API = "/api/v1"
ALICE = {"email": "Alice@Example.com", "password": "a-long-passphrase", "full_name": "Alice Rao"}


def register(client: TestClient, **overrides: Any) -> Any:
    return client.post(f"{API}/auth/register", json={**ALICE, **overrides})


def error_code(response: Any) -> str:
    return str(response.json()["error"]["code"])


# ── Sign-up ────────────────────────────────────────────────────────────────


def test_register_creates_session_cookies_and_normalises_email(client: TestClient) -> None:
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["role"] == "traveler"
    assert "access_token" not in body  # tokens never appear in response bodies
    assert response.headers["cache-control"] == "no-store"

    set_cookie = response.headers.get_list("set-cookie")
    access = next(c for c in set_cookie if c.startswith("tm_access="))
    refresh = next(c for c in set_cookie if c.startswith("tm_refresh="))
    assert "HttpOnly" in access and "SameSite=lax" in access and "Path=/" in access
    assert "HttpOnly" in refresh and "Path=/api/v1/auth" in refresh

    me = client.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Alice Rao"


def test_register_duplicate_email_is_conflict(client: TestClient) -> None:
    register(client)
    response = register(client, email="ALICE@example.com")
    assert response.status_code == 409
    assert error_code(response) == "EMAIL_TAKEN"


def test_register_validation_uses_error_envelope(client: TestClient) -> None:
    response = register(client, email="not-an-email", password="short")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert {f["field"] for f in error["details"]["fields"]} == {"email", "password"}
    assert error["request_id"] == response.headers["x-request-id"]


def test_register_rejects_unknown_fields(client: TestClient) -> None:
    response = register(client, role="admin")
    assert response.status_code == 422


def test_registration_flag_off_returns_feature_disabled(client: TestClient) -> None:
    client.app.dependency_overrides[get_feature_flags] = lambda: FeatureFlags(  # type: ignore[attr-defined]
        {"registration": False}
    )
    response = register(client)
    assert response.status_code == 404
    assert error_code(response) == "FEATURE_DISABLED"


# ── Sign-in ────────────────────────────────────────────────────────────────


def test_login_with_correct_password(client: TestClient) -> None:
    register(client)
    client.cookies.clear()
    response = client.post(
        f"{API}/auth/login", json={"email": "alice@example.com", "password": ALICE["password"]}
    )
    assert response.status_code == 200
    assert client.get(f"{API}/auth/me").status_code == 200


def test_login_failures_are_indistinguishable_and_audited(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    wrong_password = client.post(
        f"{API}/auth/login", json={"email": ALICE["email"], "password": "nope-nope-nope"}
    )
    unknown_email = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-nope"}
    )
    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert error_code(response) == "INVALID_CREDENTIALS"
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]

    failures = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "auth.login", AuditLog.outcome == "failure")
    ).all()
    assert sorted(f.details["reason"] for f in failures if f.details) == [
        "unknown_email",
        "wrong_password",
    ]


def test_login_is_rate_limited(client: TestClient) -> None:
    # A different address each time: this is the per-client limit, not the per-account lockout.
    statuses = [
        client.post(
            f"{API}/auth/login", json={"email": f"nobody{i}@example.com", "password": "nope-nope"}
        ).status_code
        for i in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    limited = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "nope-nope"}
    )
    assert int(limited.headers["retry-after"]) >= 1
    assert error_code(limited) == "RATE_LIMITED"


# ── Session lifecycle ──────────────────────────────────────────────────────


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get(f"{API}/auth/me")
    assert response.status_code == 401
    assert error_code(response) == "AUTH_REQUIRED"


def test_expired_access_token_reports_token_expired(client: TestClient, clock: FrozenClock) -> None:
    register(client)
    clock.advance(timedelta(minutes=16))
    response = client.get(f"{API}/auth/me", cookies={"tm_access": client.cookies["tm_access"]})
    assert response.status_code == 401
    assert error_code(response) == "TOKEN_EXPIRED"


def test_refresh_rotates_tokens(client: TestClient, clock: FrozenClock) -> None:
    register(client)
    old_refresh = client.cookies["tm_refresh"]
    clock.advance(timedelta(minutes=16))

    response = client.post(f"{API}/auth/refresh")
    assert response.status_code == 200
    assert client.cookies["tm_refresh"] != old_refresh
    assert client.get(f"{API}/auth/me").status_code == 200


def test_reusing_a_rotated_refresh_token_revokes_the_family(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    stolen = client.cookies["tm_refresh"]
    assert client.post(f"{API}/auth/refresh").status_code == 200
    current = client.cookies["tm_refresh"]

    client.cookies.clear()
    reuse = client.post(f"{API}/auth/refresh", cookies={"tm_refresh": stolen})
    assert reuse.status_code == 401
    assert error_code(reuse) == "SESSION_REVOKED"

    # The legitimate, newest token is revoked too.
    client.cookies.clear()
    follow_up = client.post(f"{API}/auth/refresh", cookies={"tm_refresh": current})
    assert follow_up.status_code == 401
    assert (
        db_session.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))).all()
        == []
    )


def test_expired_refresh_token_is_rejected(client: TestClient, clock: FrozenClock) -> None:
    register(client)
    clock.advance(timedelta(days=8))
    response = client.post(f"{API}/auth/refresh")
    assert response.status_code == 401
    assert error_code(response) == "SESSION_EXPIRED"


def test_logout_revokes_session_and_is_idempotent(client: TestClient) -> None:
    register(client)
    refresh = client.cookies["tm_refresh"]
    assert client.post(f"{API}/auth/logout").status_code == 204
    assert client.post(f"{API}/auth/logout").status_code == 204

    client.cookies.clear()
    response = client.post(f"{API}/auth/refresh", cookies={"tm_refresh": refresh})
    assert response.status_code == 401


# ── Demo login ─────────────────────────────────────────────────────────────


def test_demo_login_requires_seeded_accounts(client: TestClient) -> None:
    response = client.post(f"{API}/auth/demo-login", json={"role": "traveler"})
    assert response.status_code == 404
    assert error_code(response) == "DEMO_ACCOUNT_MISSING"


def test_demo_login_after_seed(client: TestClient) -> None:
    assert seed() == 0
    assert seed() == 0  # idempotent
    response = client.post(f"{API}/auth/demo-login", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


# ── Operational endpoints ──────────────────────────────────────────────────


def test_health_ready_and_features(client: TestClient) -> None:
    assert client.get(f"{API}/health").json()["status"] == "ok"
    ready = client.get(f"{API}/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert "demo_login" in client.get(f"{API}/meta/features").json()["features"]


def test_request_id_is_propagated(client: TestClient) -> None:
    response = client.get(f"{API}/health", headers={"x-request-id": "trace-abc-12345"})
    assert response.headers["x-request-id"] == "trace-abc-12345"
    generated = client.get(f"{API}/health", headers={"x-request-id": "bad id!"})
    assert generated.headers["x-request-id"] != "bad id!"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get(f"{API}/does-not-exist")
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


def test_metrics_endpoint_exposes_auth_counters(client: TestClient) -> None:
    register(client)
    body = client.get("/metrics").text
    assert 'auth_events_total{event="register",outcome="success"}' in body
    assert "http_request_duration_seconds" in body
