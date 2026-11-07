from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

SETTINGS = Settings(environment="test", jwt_secret="x" * 64)  # type: ignore[arg-type]
NOW = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)


def test_password_hash_verifies_and_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery", hashed)[0] is True
    assert verify_password("wrong", hashed)[0] is False


def test_password_hashes_are_salted() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    token, expires_at = create_access_token(
        user_id=user_id, role="admin", now=NOW, settings=SETTINGS
    )
    claims = decode_access_token(token, now=NOW + timedelta(minutes=1), settings=SETTINGS)
    assert claims.user_id == user_id
    assert claims.role == "admin"
    assert expires_at == NOW + timedelta(minutes=SETTINGS.access_token_ttl_minutes)


def test_expired_access_token_is_rejected() -> None:
    token, expires_at = create_access_token(
        user_id=uuid.uuid4(), role="traveler", now=NOW, settings=SETTINGS
    )
    with pytest.raises(TokenError) as exc:
        decode_access_token(token, now=expires_at, settings=SETTINGS)
    assert exc.value.code == "TOKEN_EXPIRED"


def test_token_signed_with_another_secret_is_rejected() -> None:
    other = Settings(environment="test", jwt_secret="y" * 64)  # type: ignore[arg-type]
    token, _ = create_access_token(user_id=uuid.uuid4(), role="traveler", now=NOW, settings=other)
    with pytest.raises(TokenError) as exc:
        decode_access_token(token, now=NOW, settings=SETTINGS)
    assert exc.value.code == "TOKEN_INVALID"


def test_tampered_token_is_rejected() -> None:
    token, _ = create_access_token(
        user_id=uuid.uuid4(), role="traveler", now=NOW, settings=SETTINGS
    )
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}x.{signature}"
    with pytest.raises(TokenError):
        decode_access_token(tampered, now=NOW, settings=SETTINGS)


def test_refresh_tokens_are_random_and_hashed_deterministically() -> None:
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second and len(first) >= 60
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert hash_refresh_token(first) != first
