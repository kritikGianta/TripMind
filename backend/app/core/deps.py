"""Composition root for shared dependencies.

Every swappable implementation (clock, rate limiter, and later cache, ranker, LLM provider) is
created here from configuration. Tests override these functions through
`app.dependency_overrides` instead of patching modules.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, Request

from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.errors import NotFound, RateLimited
from app.core.features import FeatureFlags, load_feature_flags
from app.core.kv import FailOpenStore, InMemoryStore, KeyValueStore, RedisStore
from app.core.rate_limit import InMemoryRateLimiter, RateLimiter, StoreRateLimiter
from app.core.request_context import RequestMeta


def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache
def _system_clock() -> SystemClock:
    return SystemClock()


def get_clock() -> Clock:
    return _system_clock()


@lru_cache
def _feature_flags() -> FeatureFlags:
    return load_feature_flags(get_settings())


def get_feature_flags() -> FeatureFlags:
    return _feature_flags()


@lru_cache
def _kv_store() -> KeyValueStore:
    settings = get_settings()
    if settings.redis_url:
        return FailOpenStore(RedisStore(settings.redis_url))
    return InMemoryStore()


def get_kv_store() -> KeyValueStore:
    return _kv_store()


@lru_cache
def _rate_limiter() -> RateLimiter:
    if get_settings().redis_url:
        return StoreRateLimiter(_kv_store())
    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter()


def client_ip(request: Request, settings: Settings) -> str | None:
    """Client address. Behind the Next.js proxy the first X-Forwarded-For hop is the browser."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64] or None
    return request.client.host if request.client else None


def get_request_meta(
    request: Request, settings: Settings = Depends(get_settings_dep)
) -> RequestMeta:
    return RequestMeta(
        ip_address=client_ip(request, settings),
        user_agent=request.headers.get("user-agent"),
    )


def require_feature(name: str) -> Callable[..., None]:
    """Disabled features keep their routes and answer 404 FEATURE_DISABLED (plan v2, G4)."""

    def _check(flags: FeatureFlags = Depends(get_feature_flags)) -> None:
        if not flags.enabled(name):
            raise NotFound("This feature is not enabled.", code="FEATURE_DISABLED")

    return _check


def rate_limit(scope: str, *, limit: int, window_seconds: int) -> Callable[..., None]:
    """Per-client-IP limit for one endpoint scope."""

    def _check(
        meta: RequestMeta = Depends(get_request_meta),
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        allowed, retry_after = limiter.hit(
            f"{scope}:{meta.ip_address or 'unknown'}", limit=limit, window_seconds=window_seconds
        )
        if not allowed:
            raise RateLimited(
                details={"retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

    return _check
