"""Sort a traveller's message into a support category.

With a trained model (`models/request_classifier/artifacts`, TF-IDF + logistic regression on the
Bitext travel customer-support dataset, its 33 intents grouped into the categories below) the
most likely category is used when the model is confident enough. Otherwise keyword rules decide,
and a message that matches nothing is `other`. Used to route support tickets and by the assistant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.modules.ml.text import TextModel, load_text_model

# Bitext intent -> TripMind category. The notebook uses this exact mapping.
INTENT_CATEGORIES: dict[str, str] = {
    "cancel_flight": "cancellation_refund",
    "cancel_trip": "cancellation_refund",
    "get_refund": "cancellation_refund",
    "check_cancellation_fee": "cancellation_refund",
    "change_flight": "change_booking",
    "change_trip": "change_booking",
    "check_baggage_allowance": "baggage_seats",
    "change_seat": "baggage_seats",
    "choose_seat": "baggage_seats",
    "check_in": "check_in_boarding",
    "get_boarding_pass": "check_in_boarding",
    "print_boarding_pass": "check_in_boarding",
    "check_flight_status": "flight_status",
    "check_arrival_time": "flight_status",
    "check_departure_time": "flight_status",
    "check_flight_insurance_coverage": "insurance",
    "purchase_flight_insurance": "insurance",
    "search_flight_insurance": "insurance",
    "check_trip_insurance_coverage": "insurance",
    "purchase_trip_insurance": "insurance",
    "search_trip_insurance": "insurance",
    "book_flight": "new_booking",
    "book_trip": "new_booking",
    "search_flight": "new_booking",
    "search_trip": "new_booking",
    "check_flight_offers": "new_booking",
    "check_trip_offers": "new_booking",
    "check_flight_prices": "new_booking",
    "check_trip_prices": "new_booking",
    "check_flight_reservation": "existing_booking",
    "check_trip_details": "existing_booking",
    "check_trip_plan": "existing_booking",
    "human_agent": "human_agent",
}
MODEL_CATEGORIES = frozenset(INTENT_CATEGORIES.values())
CATEGORIES = (*sorted(MODEL_CATEGORIES), "other")
LABELS = {
    "baggage_seats": "Baggage and seats",
    "cancellation_refund": "Cancellation or refund",
    "change_booking": "Change a booking",
    "check_in_boarding": "Check-in and boarding",
    "existing_booking": "About my booking",
    "flight_status": "Flight status and times",
    "human_agent": "Talk to a person",
    "insurance": "Travel insurance",
    "new_booking": "New booking or prices",
    "other": "Something else",
}
RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (category, re.compile(pattern, re.IGNORECASE))
    for category, pattern in (
        ("human_agent", r"\b(human|agent|real person|speak to (someone|a person)|call me)\b"),
        ("cancellation_refund", r"\b(cancel\w*|refund\w*|money back|reimburse\w*)\b"),
        ("change_booking", r"\b(change|reschedul\w*|move|modify|different (date|flight|time))\b"),
        ("baggage_seats", r"\b(bag\w*|luggage|suitcase|kg|seat\w*|legroom|meal)\b"),
        ("check_in_boarding", r"\b(check[- ]?in|boarding pass|boarding)\b"),
        ("flight_status", r"\b(delay\w*|status|on time|depart\w*|arriv\w*|late)\b"),
        ("insurance", r"\binsur\w*\b"),
        ("existing_booking", r"\b(my booking|reservation|itinerary|confirmation|reference)\b"),
        ("new_booking", r"\b(book|price|cheap\w*|fare|offer|deal|search|find)\b"),
    )
)


@dataclass(frozen=True)
class Classification:
    category: str
    label: str
    confidence: float
    source: str  # "model:<version>" or "rules"


class RequestClassifier:
    def __init__(self, models_dir: Path, min_confidence: float = 0.45) -> None:
        self._model: TextModel | None = load_text_model(
            models_dir, "request_classifier", MODEL_CATEGORIES
        )
        self._min = min_confidence

    def classify(self, text: str) -> Classification:
        if self._model is not None:
            probs = self._model.predict_proba(text)
            best = max(probs, key=lambda c: probs[c])
            if probs[best] >= self._min:
                return Classification(
                    best, LABELS[best], round(probs[best], 3), self._model.version
                )
        for category, pattern in RULES:
            if pattern.search(text):
                return Classification(category, LABELS[category], 0.0, "rules")
        return Classification("other", LABELS["other"], 0.0, "rules")
