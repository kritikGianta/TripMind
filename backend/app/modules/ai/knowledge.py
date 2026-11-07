"""Help knowledge for the assistant, and BM25 retrieval over it.

Two sources:
- Policy articles generated from the live configuration (rules.yaml, promotions.yaml), so an
  answer about holds, refunds or promo codes always matches what the system actually enforces.
- How-to articles in docs/help/*.md, split into one chunk per `## ` section.

BM25 needs no model or API quota, so retrieval works with every AI provider switched off.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.modules.bookings.promotions import load_promotions
from app.modules.bookings.service import BookingRules
from app.modules.loyalty.module import load_loyalty_rules
from app.modules.recovery.service import RecoveryRules
from app.modules.search.pricing import load_pricing_rules, rules_section

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "i",
    "my",
    "me",
    "do",
    "does",
    "can",
    "how",
    "what",
    "when",
    "will",
    "it",
    "be",
    "with",
    "if",
    "at",
    "you",
    "your",
    "we",
    "our",
    "this",
    "that",
    "from",
    "by",
    "as",
    "about",
    "get",
}


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    text: str
    source: str  # "policy:<name>" or "docs/help/<file>"


def tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP]


def _policy_chunks(config_dir: Path) -> list[Chunk]:
    b = BookingRules.model_validate(rules_section(config_dir, "bookings"))
    r = RecoveryRules.model_validate(rules_section(config_dir, "recovery"))
    pricing = load_pricing_rules(config_dir)
    loyalty = load_loyalty_rules(config_dir)
    promos = load_promotions(config_dir)
    after = (
        f"{b.flight_refund_percent_after_window}% of the fare is refunded"
        if b.flight_refund_percent_after_window
        else "flights are not refunded"
    )
    tiers = ", ".join(
        f"{name} from {floor} points"
        for name, floor in sorted(loyalty.tiers.items(), key=lambda t: t[1])
    )
    promo_lines = " ".join(
        f"{p.code}: {p.description}"
        + (f" (valid until {p.valid_until:%d %b %Y})" if p.valid_until else "")
        + "."
        for p in promos.values()
    )
    return [
        Chunk(
            "policy-holds",
            "Holds and payment",
            f"When you check out, seats and rooms are held for {b.hold_minutes} minutes while "
            "you pay. Nothing is charged until payment succeeds. If the hold expires, the "
            "seats and rooms are released and you need to search again. A declined card keeps "
            "the hold, so you can try another card before it expires. Payments in this demo "
            "are simulated: card 4242 4242 4242 4242 succeeds and 4000 0000 0000 0002 is "
            "declined. Only the card brand and last four digits are stored.",
            "policy:bookings",
        ),
        Chunk(
            "policy-cancel-flights",
            "Cancelling a flight",
            f"You can cancel a flight for a full refund within "
            f"{b.flight_free_cancellation_hours} hours of booking. After that, {after}. "
            "Once a flight has departed it cannot be refunded. This is TripMind's demo policy "
            "because the supplied data has no airline fare rules. Cancel from the booking "
            "page; you see the refund before you confirm.",
            "policy:bookings",
        ),
        Chunk(
            "policy-cancel-stays",
            "Cancelling a stay",
            "Refundable rooms are refunded in full until "
            f"{b.hotel_free_cancellation_hours_before_check_in} hours before check-in. "
            "Non-refundable rooms are not refunded. Each room shows its terms before you book. "
            "You can cancel one part of a booking, for example the stay, and keep the flight.",
            "policy:bookings",
        ),
        Chunk(
            "policy-disruptions",
            "Flight cancelled or delayed by the airline",
            "If the airline cancels your flight or a hotel cannot provide your room, TripMind "
            "notifies you and offers options: another flight or room at no extra cost, or a "
            "full refund of that part. Delays shorter than "
            f"{r.significant_delay_minutes // 60} hours are notified; longer delays also offer "
            "rebooking or a refund. Only the affected part changes; the rest of your trip "
            "stays booked. You always choose; nothing is changed without you.",
            "policy:recovery",
        ),
        Chunk(
            "policy-prices",
            "Prices, taxes and currencies",
            "Prices come from the supplied data. Taxes and fees are not in the data, so they "
            "are shown as not included and the real total would be higher. Prices are shown "
            "in the supplier's currency; totals are converted to "
            f"{pricing.display_currency} with fixed demo rates, not live exchange rates. "
            "A price is re-checked before anything is held; if it changed, you see the new "
            "price first.",
            "policy:pricing",
        ),
        Chunk(
            "policy-loyalty",
            "Loyalty points",
            f"You earn {loyalty.points_per_100} point for every 100 "
            f"{pricing.display_currency} you pay. Refunds take back the points they earned. "
            f"Tiers: {tiers}. See your balance on the Account page.",
            "policy:loyalty",
        ),
        Chunk(
            "policy-promos",
            "Promo codes",
            "Enter a promo code at checkout; the discount is checked and priced by TripMind "
            f"and shown in the price summary. Current codes: {promo_lines} Each code can be "
            "used once per traveller.",
            "policy:promotions",
        ),
    ]


def _doc_chunks(docs_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")) if docs_dir.exists() else []:
        sections = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]
        for i, section in enumerate(sections):
            title, _, body = section.partition("\n")
            chunks.append(
                Chunk(
                    f"{path.stem}-{i}",
                    title.strip(),
                    " ".join(body.split()),
                    f"docs/help/{path.name}",
                )
            )
    return chunks


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._docs = [tokens(f"{c.title} {c.title} {c.text}") for c in chunks]
        self._avg = sum(len(d) for d in self._docs) / max(len(self._docs), 1)
        df: Counter[str] = Counter(t for d in self._docs for t in set(d))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        terms = tokens(query)
        scored = []
        for chunk, doc in zip(self.chunks, self._docs, strict=True):
            counts = Counter(doc)
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf:
                    score += (
                        self._idf.get(term, 0)
                        * tf
                        * 2.2
                        / (tf + 1.2 * (0.25 + 0.75 * len(doc) / self._avg))
                    )
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda item: -item[1])[:k]


@lru_cache(maxsize=4)
def _cached(config_dir: str, docs_dir: str, stamp: float) -> KnowledgeBase:
    return KnowledgeBase(_policy_chunks(Path(config_dir)) + _doc_chunks(Path(docs_dir)))


def knowledge_base(config_dir: Path) -> KnowledgeBase:
    docs = config_dir.parent / "docs" / "help"
    if not docs.exists():  # in the container, docs are mounted next to config
        docs = config_dir / "help"
    files = [*config_dir.glob("*.yaml"), *(docs.glob("*.md") if docs.exists() else [])]
    stamp = max((f.stat().st_mtime for f in files), default=0.0)
    return _cached(str(config_dir), str(docs), stamp)
