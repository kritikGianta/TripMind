"""Password hashing and token primitives. No HTTP or database code lives here."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

_password_hash = PasswordHash.recommended()  # Argon2id with library-recommended parameters

# Verified against when an email is unknown, so failed sign-ins take the same time either way.
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    """Return (valid, upgraded_hash). `upgraded_hash` is set when parameters have changed."""
    return _password_hash.verify_and_update(password, password_hash)


def burn_password_check(password: str) -> None:
    _password_hash.verify(password, _DUMMY_HASH)


class TokenError(Exception):
    """Raised when an access token is missing, malformed, expired or has the wrong type."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: str
    expires_at: datetime


def create_access_token(
    *, user_id: uuid.UUID, role: str, now: datetime, settings: Settings
) -> tuple[str, datetime]:
    expires_at = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, expires_at


def decode_access_token(token: str, *, now: datetime, settings: Settings) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "type"], "verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("TOKEN_INVALID") from exc

    # Expiry is checked against the injected clock rather than the wall clock.
    if int(payload["exp"]) <= int(now.timestamp()):
        raise TokenError("TOKEN_EXPIRED")
    if payload.get("type") != "access":
        raise TokenError("TOKEN_INVALID")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise TokenError("TOKEN_INVALID") from exc

    return AccessClaims(
        user_id=user_id,
        role=str(payload.get("role", "")),
        expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=now.tzinfo),
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Refresh tokens are high-entropy random values, so a fast hash is appropriate."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
