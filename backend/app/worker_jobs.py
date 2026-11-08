"""The worker's job list: (name, interval in seconds, function). Each function opens its own
session, does idempotent work, commits, and returns how many records it changed."""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings
from app.modules.bookings.jobs import expire_holds_once

JOBS: list[tuple[str, float, Callable[[Settings], int]]] = [
    ("expire_holds", 30, expire_holds_once),
]
