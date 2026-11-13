"""Sort a traveller's message into a support category with keyword rules (no model, no AI).

The first rule that matches decides, in the order below, so "talk to a person" wins over
everything and a cancellation wins over a generic booking question. A message that matches
nothing is `other`; an agent can always re-file the ticket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
CATEGORIES = tuple(LABELS)

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
    source: str  # always "rules"


def classify(text: str) -> Classification:
    for category, pattern in RULES:
        if pattern.search(text):
            return Classification(category, LABELS[category], "rules")
    return Classification("other", LABELS["other"], "rules")
