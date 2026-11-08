"""The worker's job list: (name, interval in seconds, function). Each function opens its own
session, does idempotent work, commits, and returns how many records it changed."""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings
from app.core.features import load_feature_flags
from app.modules.bookings.jobs import expire_holds_once
from app.modules.privacy.module import purge_once
from app.modules.search.preferences import load_preference_rules, train_preferences_once
from app.modules.watchlist.jobs import check_price_alerts_once
from app.modules.watchlist.service import alert_check_interval_seconds

Job = tuple[str, float, Callable[[Settings], int]]


def jobs(settings: Settings) -> list[Job]:
    """The jobs to run, honouring feature flags and the intervals set in config."""
    flags = load_feature_flags(settings)
    selected: list[Job] = [("purge_expired_data", 24 * 3600.0, purge_once)]
    if flags.enabled("bookings"):
        selected.append(("expire_holds", 30, expire_holds_once))
    if flags.enabled("watchlist"):
        selected.append(
            ("check_price_alerts", alert_check_interval_seconds(settings), check_price_alerts_once)
        )
    if flags.enabled("personalization"):
        minutes = load_preference_rules(settings).retrain_minutes
        selected.append(("train_preferences", minutes * 60.0, train_preferences_once))
    return selected
