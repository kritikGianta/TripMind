"""Similar stays: TF-IDF over hotel attributes + cosine similarity (scikit-learn).

Each hotel becomes a bag of tokens: its amenities, its star class, its guest-rating band and its
price band within the city. TF-IDF down-weights what nearly every hotel has (Wi-Fi) and
up-weights distinctive features (beach access, spa), so "similar" means similar in the ways a
traveller notices. Computed on demand from the live catalog, so it works on any dataset without
training. Evaluated in models/similar_hotels/.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class HotelProfile:
    id: uuid.UUID
    amenities: tuple[str, ...]
    star_rating: float | None
    guest_rating: float | None
    nightly_price: float | None  # any single currency within the city


@dataclass(frozen=True)
class Neighbour:
    id: uuid.UUID
    similarity: float
    shared_amenities: tuple[str, ...]


def _tokens(hotel: HotelProfile, price_band: str) -> str:
    parts = [f"amenity_{a}" for a in hotel.amenities]
    if hotel.star_rating:
        parts.append(f"stars_{int(hotel.star_rating)}")
    if hotel.guest_rating is not None:
        parts.append(f"rating_{int(hotel.guest_rating)}")
    parts.append(price_band)
    return " ".join(parts)


def similar_hotels(target: uuid.UUID, hotels: list[HotelProfile], k: int = 4) -> list[Neighbour]:
    if len(hotels) < 2 or all(h.id != target for h in hotels):
        return []
    prices = [h.nightly_price for h in hotels if h.nightly_price]
    edges: list[float] = (
        [float(q) for q in np.quantile(prices, [0.2, 0.4, 0.6, 0.8])] if len(prices) >= 5 else []
    )

    def band(price: float | None) -> str:
        if not price:
            return "price_unknown"
        return f"price_q{int(np.searchsorted(edges, price))}" if len(edges) else "price_any"

    documents = [_tokens(h, band(h.nightly_price)) for h in hotels]
    tokenizer = r"[^ ]+"  # tokens are space-separated and may contain underscores
    matrix = TfidfVectorizer(token_pattern=tokenizer).fit_transform(documents)
    index = next(i for i, h in enumerate(hotels) if h.id == target)
    scores = cosine_similarity(matrix[index], matrix).ravel()
    order = [i for i in np.argsort(-scores) if i != index][:k]
    mine = set(hotels[index].amenities)
    return [
        Neighbour(
            id=hotels[i].id,
            similarity=round(float(scores[i]), 3),
            shared_amenities=tuple(sorted(mine & set(hotels[i].amenities))),
        )
        for i in order
        if scores[i] > 0
    ]
