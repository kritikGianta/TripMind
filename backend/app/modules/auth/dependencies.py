"""Authentication dependencies used by every protected route in every module."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.deps import get_clock, get_settings_dep
from app.core.errors import Forbidden, Unauthorized
from app.core.security import TokenError, decode_access_token
from app.db.session import get_session
from app.modules.auth.cookies import ACCESS_COOKIE
from app.modules.auth.models import User, UserRole
from app.modules.auth.repository import UserRepository


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise Unauthorized()
    try:
        claims = decode_access_token(token, now=clock.now(), settings=settings)
    except TokenError as exc:
        # TOKEN_EXPIRED tells the client to refresh silently; anything else means sign in again.
        raise Unauthorized(code=exc.code) from exc

    user = UserRepository(session).get(claims.user_id)
    if user is None or not user.is_active:
        raise Unauthorized(code="TOKEN_INVALID")
    return user


def require_role(*roles: UserRole) -> Callable[..., User]:
    allowed = {str(r) for r in roles}

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise Forbidden()
        return user

    return _check


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    clock: Clock = Depends(get_clock),
) -> User | None:
    """The signed-in user on public endpoints, or None. Never raises: an expired or invalid
    token simply means the request is treated as anonymous."""
    if not request.cookies.get(ACCESS_COOKIE):
        return None
    try:
        return get_current_user(request, session, settings, clock)
    except Unauthorized:
        return None
