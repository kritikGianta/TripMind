"""Rate limiting.

`RateLimiter` is a protocol so the in-process implementation can be swapped for a Redis-backed one
when the API runs as multiple replicas. The in-process limiter is correct for a single replica.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        ...


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by an arbitrary string."""

    def __init__(self, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._monotonic = monotonic

    def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = self._monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now) + 1)
                return False, retry_after
            events.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
