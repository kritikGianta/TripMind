"""Ingestion rules and vocabularies, loaded from `config/rules.yaml` and `config/vocabulary.yaml`.

Rules are the decisions the finale data may force us to change (default timezone, thresholds,
fallback capacities) without touching code.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("default_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError(f"unknown timezone {value!r}")
        return value


class Vocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cabin_classes: dict[str, list[str]] = Field(default_factory=dict)
    amenities: dict[str, list[str]] = Field(default_factory=dict)
    boards: dict[str, list[str]] = Field(default_factory=dict)
    city_aliases: dict[str, list[str]] = Field(default_factory=dict)

    def _lookup(self, table: dict[str, list[str]]) -> dict[str, str]:
        index: dict[str, str] = {}
        for canonical, aliases in table.items():
            for alias in [canonical, *aliases]:
                index[normalize_text(alias)] = canonical
        return index

    def cabin_index(self) -> dict[str, str]:
        return self._lookup(self.cabin_classes)

    def amenity_index(self) -> dict[str, str]:
        return self._lookup(self.amenities)

    def board_index(self) -> dict[str, str]:
        return self._lookup(self.boards)

    def city_alias_index(self) -> dict[str, str]:
        """Normalised alias -> normalised canonical city name."""
        return {k: normalize_text(v) for k, v in self._lookup(self.city_aliases).items()}


_SPACES = re.compile(r"[^a-z0-9]+")


def normalize_text(value: str) -> str:
    """Case-, accent- and punctuation-insensitive form used for matching names."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return _SPACES.sub(" ", ascii_only.lower()).strip()


def slugify(value: str) -> str:
    return normalize_text(value).replace(" ", "_")


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


def load_vocabulary(config_dir: Path) -> Vocabulary:
    path = config_dir / "vocabulary.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return Vocabulary.model_validate(document or {})
