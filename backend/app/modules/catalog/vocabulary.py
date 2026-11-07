"""Canonical vocabularies (config/vocabulary.yaml) and name normalisation.

Shared by ingestion (to normalise supplied values) and search (to match what travellers type).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


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


def load_vocabulary(config_dir: Path) -> Vocabulary:
    path = config_dir / "vocabulary.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return Vocabulary.model_validate(document or {})
