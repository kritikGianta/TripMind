"""Model registry: loads trained artifacts from `models/<name>/artifacts/` with their model card.

Every model ships as two files: the artifact (LightGBM text model, never a pickle, so loading it
cannot execute code) and `model_card.json` describing the data, features, metrics and library
versions. A model is used only when both exist, the card's feature list matches what the
serving code computes, and its feature flag is on. Otherwise callers use their rule-based
fallback; nothing in a traveller flow depends on a model being present.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field, ValidationError

log = structlog.get_logger(__name__)


class ModelCard(BaseModel):
    name: str
    version: str
    trained_at: datetime
    framework: str
    framework_version: str
    dataset: str
    features: list[str]
    metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class LoadedModel:
    def __init__(self, card: ModelCard, booster: Any) -> None:
        self.card = card
        self.booster = booster

    def predict(self, rows: list[dict[str, float]]) -> list[float]:
        import numpy as np

        matrix = np.array([[float(row[f]) for f in self.card.features] for row in rows])
        return [float(v) for v in self.booster.predict(matrix)]


def _load(directory: Path, expected: tuple[str, ...]) -> LoadedModel | None:
    card_path, model_path = directory / "model_card.json", directory / "model.txt"
    if not (card_path.exists() and model_path.exists()):
        return None
    try:
        card = ModelCard.model_validate(json.loads(card_path.read_text(encoding="utf-8")))
    except (ValueError, ValidationError) as exc:
        log.warning("model_card_invalid", path=str(card_path), error=type(exc).__name__)
        return None
    if tuple(card.features) != expected:
        log.warning(
            "model_features_mismatch", model=card.name, expected=list(expected), found=card.features
        )
        return None
    import lightgbm  # imported lazily: only when a model artifact is present

    booster = lightgbm.Booster(model_file=str(model_path))
    log.info(
        "model_loaded",
        model=card.name,
        version=card.version,
        trained_at=card.trained_at.isoformat(),
    )
    return LoadedModel(card, booster)


@lru_cache(maxsize=16)
def _cached(directory: str, expected: tuple[str, ...], stamp: float) -> LoadedModel | None:
    return _load(Path(directory), expected)


def load_model(models_dir: Path, name: str, expected: tuple[str, ...]) -> LoadedModel | None:
    """The model in `models_dir/<name>/artifacts`, reloaded when its files change."""
    directory = models_dir / name / "artifacts"
    files = [directory / "model.txt", directory / "model_card.json"]
    stamp = max((f.stat().st_mtime for f in files if f.exists()), default=0.0)
    return _cached(str(directory), expected, stamp)
