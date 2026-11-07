"""Background job: expire unpaid holds so their seats and rooms return to sale.

Reads also expire overdue holds lazily, so correctness never depends on this job; it only makes
inventory come back promptly. Safe with several API workers: rows are locked with SKIP LOCKED.
"""

from __future__ import annotations

import asyncio

import structlog
from starlette.concurrency import run_in_threadpool

from app.core.clock import SystemClock
from app.core.config import Settings
from app.db.session import get_session_factory
from app.modules.bookings.service import BookingService

log = structlog.get_logger(__name__)


def expire_holds_once(settings: Settings) -> int:
    with get_session_factory()() as session:
        return BookingService(session, settings, SystemClock()).expire_due()


async def run_hold_sweeper(settings: Settings, interval_seconds: float = 30.0) -> None:
    while True:
        try:
            expired = await run_in_threadpool(expire_holds_once, settings)
            if expired:
                log.info("holds_expired", count=expired)
        except Exception:  # keep sweeping; one failed pass must not stop the job
            log.exception("hold_sweep_failed")
        await asyncio.sleep(interval_seconds)
