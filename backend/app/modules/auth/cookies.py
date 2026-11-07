"""Session cookies. See ADR 0003 for why tokens live only in httpOnly cookies."""

from __future__ import annotations

from datetime import datetime

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "tm_access"
REFRESH_COOKIE = "tm_refresh"


def _max_age(expires_at: datetime, now: datetime) -> int:
    return max(0, int((expires_at - now).total_seconds()))


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    refresh_expires_at: datetime,
    now: datetime,
    settings: Settings,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=_max_age(access_expires_at, now),
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=_max_age(refresh_expires_at, now),
        path=settings.auth_path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path=settings.auth_path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
