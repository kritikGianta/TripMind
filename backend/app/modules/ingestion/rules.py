"""Ingestion rules and vocabularies, loaded from `config/rules.yaml` and `config/vocabulary.yaml`.

Rules are the decisions the finale data may force us to change (default timezone, thresholds,
fallback capacities) without touching code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.catalog.vocabulary import Vocabulary, load_vocabulary, normalize_text, slugify

__all__ = [
    "IngestionRules",
    "Vocabulary",
    "is_valid_timezone",
    "load_rules",
    "load_vocabulary",
    "normalize_text",
    "slugify",
]


class IngestionRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_timezone: str = "Asia/Kolkata"
    default_currency: str = "INR"
    default_cabin_class: str = "economy"
    default_seat_capacity: int = Field(default=180, ge=1)
    default_rooms_per_type: int = Field(default=10, ge=1)
    default_max_occupancy: int = Field(default=2, ge=1)
    default_room_name: str = "Standard Room"
    max_flight_duration_minutes: int = Field(default=20 * 60, ge=60)
    duration_mismatch_minutes: int = Field(default=90, ge=0)
    city_match_threshold: int = Field(default=90, ge=50, le=100)
    # An entity with more rejected rows than this share blocks the import (likely a bad mapping).
    max_reject_ratio: float = Field(default=0.2, ge=0, le=1)
    max_stored_rejects: int = Field(default=5000, ge=0)
    max_upload_mb: int = Field(default=100, ge=1)
    max_uncompressed_mb: int = Field(default=1024, ge=1)
    max_archive_members: int = Field(default=200, ge=1)
    # Flight schedules are expanded at most this many days ahead of the import date.
    schedule_horizon_days: int = Field(default=90, ge=1, le=400)

    @field_validator("default_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError(f"unknown timezone {value!r}")
        return value


@lru_cache(maxsize=1024)
def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def load_rules(config_dir: Path) -> IngestionRules:
    path = config_dir / "rules.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return IngestionRules.model_validate((document or {}).get("ingestion") or {})
