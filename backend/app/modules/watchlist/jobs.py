"""Worker job: re-price active price alerts and notify travellers when one fires."""

from __future__ import annotations

import structlog

from app.core.clock import SystemClock
from app.core.config import Settings
from app.db.session import get_session_factory
from app.modules.watchlist.service import WatchlistService

log = structlog.get_logger(__name__)


def check_price_alerts_once(settings: Settings) -> int:
    with get_session_factory()() as session:
        summary = WatchlistService(session, settings, SystemClock()).check_alerts()
    if summary.checked or summary.expired or summary.failed:
        log.info("price_alerts_checked", **summary.model_dump())
    return summary.triggered + summary.expired
