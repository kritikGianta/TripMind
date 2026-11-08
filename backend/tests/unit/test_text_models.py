"""Text models: JSON export reproduces scikit-learn exactly; rules work without a model."""

from __future__ import annotations

from pathlib import Path

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from app.modules.ml.request_classifier import INTENT_CATEGORIES, LABELS, RequestClassifier
from app.modules.ml.sentiment import SentimentScorer
from app.modules.ml.text import load_text_model
from app.modules.ml.text_export import export_tfidf_logreg

CORPUS = [
    ("The room was spotless and the staff were lovely", "positive"),
    ("Great location, friendly staff, would recommend", "positive"),
    ("Excellent breakfast and a comfortable bed", "positive"),
    ("Dirty bathroom and rude staff at reception", "negative"),
    ("Terrible noise all night, never again", "negative"),
    ("Overpriced and the room was small and tired", "negative"),
    ("It was fine for one night, nothing special", "neutral"),
    ("Average hotel, okay location, ordinary room", "neutral"),
    ("Decent stay but breakfast could be better", "neutral"),
]


def _fit(tmp: Path, labels: list[str], name: str) -> tuple[TfidfVectorizer, LogisticRegression]:
    texts = [t for t, _ in CORPUS]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    model = LogisticRegression(max_iter=500, C=5.0).fit(vectorizer.fit_transform(texts), labels)
    export_tfidf_logreg(
        vectorizer, model, tmp / name / "artifacts", name=name, dataset="test", metrics={"f1": 1}
    )
    return vectorizer, model


@pytest.mark.parametrize(
    "probe",
    ["Staff were lovely and the room spotless", "rude staff, dirty room", "unknown words only"],
)
def test_exported_model_matches_sklearn(tmp_path: Path, probe: str) -> None:
    vectorizer, model = _fit(tmp_path, [label for _, label in CORPUS], "review_sentiment")
    served = load_text_model(tmp_path, "review_sentiment", frozenset(model.classes_))
    assert served is not None and served.version.startswith("model:")
    expected = dict(
        zip(model.classes_, model.predict_proba(vectorizer.transform([probe]))[0], strict=True)
    )
    got = served.predict_proba(probe)
    assert got.keys() == expected.keys()
    assert all(abs(got[c] - expected[c]) < 1e-4 for c in expected)


def test_binary_model_matches_sklearn(tmp_path: Path) -> None:
    labels = ["good" if label == "positive" else "bad" for _, label in CORPUS]
    vectorizer, model = _fit(tmp_path, labels, "binary")
    served = load_text_model(tmp_path, "binary", frozenset({"good", "bad"}))
    assert served is not None
    probe = "friendly staff and a great location"
    expected = model.predict_proba(vectorizer.transform([probe]))[0]
    got = served.predict_proba(probe)
    assert abs(got["good"] - expected[list(model.classes_).index("good")]) < 1e-4


def test_model_with_other_classes_is_refused(tmp_path: Path) -> None:
    _fit(tmp_path, [label for _, label in CORPUS], "request_classifier")
    assert RequestClassifier(tmp_path).classify("cancel my flight").source == "rules"


def test_sentiment_uses_the_trained_model(tmp_path: Path) -> None:
    _fit(tmp_path, [label for _, label in CORPUS], "review_sentiment")
    scorer = SentimentScorer(tmp_path)
    assert scorer.source.startswith("model:")
    assert scorer.score("rude staff and a dirty bathroom").label == "negative"


def test_sentiment_rules_without_a_model(tmp_path: Path) -> None:
    scorer = SentimentScorer(tmp_path)
    assert scorer.source == "rules"
    assert scorer.score("Lovely staff and a spotless room.").label == "positive"
    assert scorer.score("The room was dirty and the staff rude.").label == "negative"
    assert scorer.score("The staff were not friendly.").label == "negative"  # negation
    assert scorer.score("We arrived on Tuesday.").label == "neutral"
    aspects = scorer.aspects(
        "Perfect location, easy to get around. The bathroom was dirty. Breakfast was delicious."
    )
    assert aspects == {
        "location": "positive",
        "cleanliness": "negative",
        "room": "negative",
        "food": "positive",
    }


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("I want my money back for the cancelled trip", "cancellation_refund"),
        ("Can I move my flight to Friday?", "change_booking"),
        ("How many kg of luggage can I bring", "baggage_seats"),
        ("Where do I get my boarding pass", "check_in_boarding"),
        ("Is flight AI 101 delayed?", "flight_status"),
        ("Let me speak to a real person please", "human_agent"),
        ("hello there", "other"),
    ],
)
def test_request_rules(tmp_path: Path, text: str, category: str) -> None:
    result = RequestClassifier(tmp_path).classify(text)
    assert (result.category, result.source) == (category, "rules")


def test_every_category_has_a_label() -> None:
    assert set(INTENT_CATEGORIES.values()) | {"other"} == set(LABELS)
    assert len(INTENT_CATEGORIES) == 33  # every Bitext travel intent is mapped
