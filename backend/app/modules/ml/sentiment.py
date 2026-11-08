"""Review sentiment and aspect highlights.

With a trained model (`models/review_sentiment/artifacts`, TF-IDF + logistic regression on public
hotel reviews: 1-2 stars negative, 3 neutral, 4-5 positive) each review and each sentence is
scored by it. Without one, a small word list with negation handling is used and the result says
`rules`. Aspects (location, staff, cleanliness, ...) are found by keywords per sentence, so a
summary can say "location: 9 of 10 mentions positive".
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.modules.ml.text import TextModel, load_text_model

Label = Literal["positive", "neutral", "negative"]
CLASSES = frozenset({"positive", "neutral", "negative"})

POSITIVE = frozenset(
    (
        "amazing",
        "awesome",
        "beautiful",
        "best",
        "brilliant",
        "clean",
        "comfortable",
        "comfy",
        "convenient",
        "cosy",
        "cozy",
        "delicious",
        "delightful",
        "excellent",
        "fabulous",
        "fantastic",
        "fast",
        "friendly",
        "gorgeous",
        "great",
        "helpful",
        "hospitable",
        "ideal",
        "immaculate",
        "impressive",
        "love",
        "loved",
        "lovely",
        "nice",
        "outstanding",
        "peaceful",
        "perfect",
        "pleasant",
        "polite",
        "quiet",
        "recommend",
        "recommended",
        "relaxing",
        "reliable",
        "roomy",
        "spacious",
        "spotless",
        "stunning",
        "superb",
        "tasty",
        "value",
        "welcoming",
        "wonderful",
        "worth",
    )
)
NEGATIVE = frozenset(
    (
        "awful",
        "bad",
        "bland",
        "broken",
        "cold",
        "cramped",
        "dated",
        "dirty",
        "disappointed",
        "disappointing",
        "disgusting",
        "dropping",
        "expensive",
        "filthy",
        "horrible",
        "noisy",
        "old",
        "overpriced",
        "poor",
        "rude",
        "shabby",
        "slow",
        "small",
        "smelly",
        "stained",
        "terrible",
        "tired",
        "unclean",
        "unfriendly",
        "unhelpful",
        "unpleasant",
        "worst",
    )
)
NEGATORS = frozenset(
    (
        "not",
        "no",
        "never",
        "nobody",
        "hardly",
        "barely",
        "didn't",
        "don't",
        "wasn't",
        "weren't",
        "isn't",
    )
)
ASPECTS: dict[str, tuple[str, ...]] = {
    "location": ("location", "located", "centre", "center", "walk", "nearby", "close to", "far"),
    "staff": ("staff", "reception", "front desk", "service", "manager", "helped", "concierge"),
    "cleanliness": ("clean", "dirty", "spotless", "filthy", "smell", "stain", "hygiene"),
    "room": ("room", "bed", "shower", "bathroom", "air conditioning", "spacious", "balcony"),
    "food": ("breakfast", "restaurant", "food", "dinner", "buffet", "meal"),
    "value": ("value", "price", "worth", "overpriced", "expensive", "cheap", "money"),
    "wifi": ("wifi", "wi-fi", "internet"),
    "noise": ("noise", "noisy", "quiet", "loud", "walls", "peaceful"),
}
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_WORDS = re.compile(r"[a-z']+")


@dataclass(frozen=True)
class Sentiment:
    label: Label
    score: float  # -1 (negative) .. 1 (positive)


def _rules(text: str) -> Sentiment:
    words = _WORDS.findall(text.lower())
    total = 0.0
    hits = 0
    for i, word in enumerate(words):
        polarity = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if not polarity:
            continue
        if any(w in NEGATORS for w in words[max(0, i - 3) : i]):
            polarity = -polarity
        total += polarity
        hits += 1
    score = total / hits if hits else 0.0
    label: Label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return Sentiment(label, round(score, 3))


class SentimentScorer:
    def __init__(self, models_dir: Path) -> None:
        self._model: TextModel | None = load_text_model(models_dir, "review_sentiment", CLASSES)

    @property
    def source(self) -> str:
        return self._model.version if self._model else "rules"

    def score(self, text: str) -> Sentiment:
        if self._model is None:
            return _rules(text)
        probs = self._model.predict_proba(text)
        label = max(probs, key=lambda c: probs[c])
        return Sentiment(label, round(probs["positive"] - probs["negative"], 3))  # type: ignore[arg-type]

    def aspects(self, text: str) -> dict[str, Label]:
        """Aspect -> sentiment of the sentences that mention it (last mention wins a tie)."""
        found: dict[str, list[float]] = defaultdict(list)
        for sentence in filter(None, (s.strip() for s in _SENTENCES.split(text))):
            lowered = sentence.lower()
            mentioned = [a for a, words in ASPECTS.items() if any(w in lowered for w in words)]
            if not mentioned:
                continue
            score = self.score(sentence).score
            for aspect in mentioned:
                found[aspect].append(score)
        return {
            aspect: "positive"
            if sum(s) / len(s) > 0.2
            else "negative"
            if sum(s) / len(s) < -0.2
            else "neutral"
            for aspect, s in found.items()
        }
