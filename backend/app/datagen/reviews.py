"""Synthetic guest reviews for the demo dataset.

Each review mentions two or three aspects of the stay; whether each remark is good or bad follows
the review's rating, which is drawn around the hotel's guest rating. The text is SYNTHETIC and only
exists so review screens and the sentiment pipeline have something to show. The sentiment model is
trained on public review data, never on these sentences.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

REVIEW_COLUMNS = (
    "review_id",
    "hotel_id",
    "rating",
    "title",
    "review",
    "traveller_type",
    "review_date",
)

PHRASES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "location": (
        (
            "The location was excellent, close to everything.",
            "Perfect location, easy to get around.",
        ),
        (
            "The location was far from the main sights.",
            "Hard to find and a long way from the centre.",
        ),
    ),
    "staff": (
        (
            "Staff were friendly and helpful.",
            "The front desk team went out of their way to help us.",
        ),
        (
            "Staff were rude and slow at check-in.",
            "Nobody helped when we had a problem with the room.",
        ),
    ),
    "cleanliness": (
        ("The room was spotless.", "Very clean throughout the hotel."),
        ("The bathroom was dirty.", "The room was not clean when we arrived."),
    ),
    "room": (
        ("The room was spacious and comfortable.", "Comfortable bed and a great shower."),
        ("The room was small and tired.", "The air conditioning did not work properly."),
    ),
    "food": (
        ("Breakfast had plenty of choice.", "The restaurant food was delicious."),
        ("Breakfast was cold and limited.", "The food was overpriced and bland."),
    ),
    "value": (
        ("Good value for the price.", "Worth the money for what you get."),
        ("Overpriced for what you get.", "Not worth the money."),
    ),
    "wifi": (
        ("Wi-Fi was fast and reliable.", "Internet worked well for video calls."),
        ("Wi-Fi kept dropping.", "The internet was too slow to work."),
    ),
    "noise": (
        ("Quiet at night, we slept well.", "Peaceful and quiet rooms."),
        ("Very noisy at night from the street.", "Thin walls, we could hear everything next door."),
    ),
}
TITLES = {
    "good": ("Lovely stay", "Would come back", "Great value", "Excellent hotel"),
    "mixed": ("Decent but could be better", "Okay for a short stay", "Mixed experience"),
    "bad": ("Disappointing", "Not as described", "Would not stay again"),
}
TRAVELLER_TYPES = ("couple", "family", "solo", "business", "friends")


def reviews_for(hotels: list[dict[str, Any]], *, seed: int, start: date) -> list[dict[str, Any]]:
    # A separate random stream, so adding reviews never changes the rest of the dataset.
    rng = random.Random(seed * 7919 + 17)
    rows: list[dict[str, Any]] = []
    for hotel in hotels:
        try:
            base = float(hotel["rating"])
        except (TypeError, ValueError):
            continue  # a deliberately corrupted hotel row: no reviews for it
        for _ in range(rng.randint(3, 8)):
            rating = min(5, max(1, round(rng.gauss(base, 0.8))))
            tone = "good" if rating >= 4 else "bad" if rating <= 2 else "mixed"
            sentences = []
            for aspect in rng.sample(sorted(PHRASES), rng.randint(2, 3)):
                good, bad = PHRASES[aspect]
                positive = (
                    (tone == "good" and rng.random() < 0.9)
                    or (tone == "mixed" and rng.random() < 0.5)
                    or (tone == "bad" and rng.random() < 0.15)
                )
                sentences.append(rng.choice(good if positive else bad))
            rows.append(
                {
                    "review_id": f"RV{len(rows) + 1:07d}",
                    "hotel_id": hotel["hotel_id"],
                    "rating": rating,
                    "title": rng.choice(TITLES[tone]),
                    "review": " ".join(sentences),
                    "traveller_type": rng.choice(TRAVELLER_TYPES),
                    "review_date": (start - timedelta(days=rng.randint(10, 400))).isoformat(),
                }
            )
    return rows
