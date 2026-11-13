"""Shared key-value state: in-process for a single replica, Redis when several processes share it.

Used for things every API replica and the worker must agree on: rate-limit windows, the AI
response cache and provider cooldowns, and job locks (so a job runs once even with several
workers). Business data never lives here; PostgreSQL stays the only source of truth, so losing
Redis loses only caches and counters.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)


class KeyValueStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: float) -> None: ...

    def set_if_absent(self, key: str, value: str, ttl_seconds: float) -> bool:
        """Atomically claim `key` (a lock). True if this caller got it."""
        ...

    def delete(self, key: str) -> None: ...

    def window_hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Sliding-window counter: record a hit, return (allowed, retry_after_seconds)."""
        ...

    def ping(self) -> bool: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, tuple[str, float]] = {}
        self._windows: dict[str, list[float]] = {}

    def _live(self, key: str, now: float) -> str | None:
        item = self._values.get(key)
        if item is None or item[1] <= now:
            self._values.pop(key, None)
            return None
        return item[0]

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._live(key, time.monotonic())

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        with self._lock:
            self._values[key] = (value, time.monotonic() + ttl_seconds)

    def set_if_absent(self, key: str, value: str, ttl_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            if self._live(key, now) is not None:
                return False
            self._values[key] = (value, now + ttl_seconds)
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._values.pop(key, None)

    def window_hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            events = [t for t in self._windows.get(key, []) if t > now - window_seconds]
            if len(events) >= limit:
                self._windows[key] = events
                return False, max(1, int(events[0] + window_seconds - now) + 1)
            events.append(now)
            self._windows[key] = events
            return True, 0

    def ping(self) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._windows.clear()


class RedisStore:
    """Redis-backed store. Keys are namespaced so a shared Redis cannot collide with others."""

    def __init__(self, url: str, namespace: str = "tripmind", client: object | None = None) -> None:
        import redis

        self._redis: Any = client or redis.Redis.from_url(
            url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5
        )
        self._ns = namespace

    def _k(self, key: str) -> str:
        return f"{self._ns}:{key}"

    def get(self, key: str) -> str | None:
        value = self._redis.get(self._k(key))
        return None if value is None else str(value)

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        self._redis.set(self._k(key), value, px=max(1, int(ttl_seconds * 1000)))

    def set_if_absent(self, key: str, value: str, ttl_seconds: float) -> bool:
        return bool(
            self._redis.set(
                self._k(key),
                value,
                nx=True,
                px=max(1, int(ttl_seconds * 1000)),
            )
        )

    def delete(self, key: str) -> None:
        self._redis.delete(self._k(key))

    def window_hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Sliding window on a sorted set of hit timestamps, updated in one transaction."""
        name = self._k(f"rl:{key}")
        now = time.time()
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(name, 0, now - window_seconds)
        pipe.zcard(name)
        pipe.zrange(name, 0, 0, withscores=True)
        _, count, oldest = pipe.execute()
        if count >= limit:
            first = oldest[0][1] if oldest else now
            return False, max(1, int(first + window_seconds - now) + 1)
        pipe = self._redis.pipeline()
        pipe.zadd(name, {f"{now:.6f}:{uuid.uuid4().hex}": now})  # unique even within one tick
        pipe.expire(name, window_seconds + 1)
        pipe.execute()
        return True, 0

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except Exception:
            return False


class FailOpenStore:
    """Wraps a remote store so an outage degrades to 'no cache, no limit' instead of errors."""

    def __init__(self, inner: KeyValueStore) -> None:
        self._inner = inner

    def _call(self, default: object, fn: str, *args: object, **kwargs: object) -> object:
        try:
            return getattr(self._inner, fn)(*args, **kwargs)
        except Exception as exc:
            log.warning("kv_unavailable", operation=fn, error=type(exc).__name__)
            return default

    def get(self, key: str) -> str | None:
        return self._call(None, "get", key)  # type: ignore[return-value]

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        self._call(None, "set", key, value, ttl_seconds)

    def set_if_absent(self, key: str, value: str, ttl_seconds: float) -> bool:
        # Fail closed for locks: without the store we cannot prove nobody else holds it.
        return bool(self._call(False, "set_if_absent", key, value, ttl_seconds))

    def delete(self, key: str) -> None:
        self._call(None, "delete", key)

    def window_hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        return self._call(
            (True, 0),
            "window_hit",
            key,
            limit=limit,  # type: ignore[return-value]
            window_seconds=window_seconds,
        )

    def ping(self) -> bool:
        return bool(self._call(False, "ping"))
