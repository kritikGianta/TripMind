"""Serving for small text classifiers (TF-IDF + logistic regression) exported as JSON.

Loads `models/<name>/artifacts/model.json` plus `model_card.json`, written by
`text_export.export_tfidf_logreg`. Used only when both files exist, the card is valid and the
model's classes are the ones the caller expects; otherwise callers use their rules.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from pydantic import ValidationError

from app.modules.ml.registry import ModelCard
from app.modules.ml.text_export import FORMAT

log = structlog.get_logger(__name__)


class TextModel:
    def __init__(self, card: ModelCard, payload: dict[str, Any]) -> None:
        self.card = card
        self.classes: list[str] = list(payload["classes"])
        self._lowercase = bool(payload["lowercase"])
        self._token = re.compile(payload["token_pattern"])
        self._ngrams = tuple(int(n) for n in payload["ngram_range"])
        self._sublinear = bool(payload["sublinear_tf"])
        self._norm = payload["norm"]
        self._vocabulary: dict[str, int] = payload["vocabulary"]
        self._idf = np.asarray(payload["idf"], dtype=np.float64)
        self._coef = np.asarray(payload["coef"], dtype=np.float64)
        self._intercept = np.asarray(payload["intercept"], dtype=np.float64)

    @property
    def version(self) -> str:
        return f"model:{self.card.version}"

    def _terms(self, text: str) -> list[str]:
        tokens = self._token.findall(text.lower() if self._lowercase else text)
        low, high = self._ngrams
        terms: list[str] = []
        for n in range(low, high + 1):
            terms.extend(" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1))
        return terms

    def _vector(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        counts = Counter(t for t in self._terms(text) if t in self._vocabulary)
        if not counts:
            return np.empty(0, dtype=np.int64), np.empty(0)
        index = np.fromiter((self._vocabulary[t] for t in counts), dtype=np.int64)
        tf = np.fromiter(counts.values(), dtype=np.float64)
        if self._sublinear:
            tf = 1.0 + np.log(tf)
        values = tf * self._idf[index]
        if self._norm == "l2":
            values = values / math.sqrt(float(values @ values))
        return index, values

    def predict_proba(self, text: str) -> dict[str, float]:
        index, values = self._vector(text)
        logits = self._coef[:, index] @ values + self._intercept
        if len(self.classes) == 2 and logits.shape[0] == 1:  # binary: one row of weights
            p = 1.0 / (1.0 + math.exp(-float(logits[0])))
            return {self.classes[0]: 1.0 - p, self.classes[1]: p}
        shifted = np.exp(logits - logits.max())
        probs = shifted / shifted.sum()
        return {c: float(p) for c, p in zip(self.classes, probs, strict=True)}


@lru_cache(maxsize=16)
def _load(card_path: str, model_path: str, mtimes: tuple[float, float]) -> TextModel | None:
    try:
        card = ModelCard.model_validate(json.loads(Path(card_path).read_text(encoding="utf-8")))
        payload = json.loads(Path(model_path).read_text(encoding="utf-8"))
    except (ValueError, ValidationError) as exc:
        log.warning("text_model_invalid", path=card_path, error=type(exc).__name__)
        return None
    if payload.get("format") != FORMAT or card.features != [FORMAT]:
        log.warning("text_model_format_mismatch", model=card.name)
        return None
    return TextModel(card, payload)


def load_text_model(models_dir: Path, name: str, classes: frozenset[str]) -> TextModel | None:
    directory = models_dir / name / "artifacts"
    card_path, model_path = directory / "model_card.json", directory / "model.json"
    if not (card_path.exists() and model_path.exists()):
        return None
    model = _load(
        str(card_path), str(model_path), (card_path.stat().st_mtime, model_path.stat().st_mtime)
    )
    if model is not None and set(model.classes) != classes:
        log.warning("text_model_classes_mismatch", model=name, found=model.classes)
        return None
    return model
