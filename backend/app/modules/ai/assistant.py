"""Help assistant grounded in TripMind's own knowledge and the traveller's trips.

Retrieval-augmented: the best-matching help chunks (BM25) and a summary of the signed-in
traveller's trips are the only facts the model may use; it must cite the chunks. Trip summaries
carry titles, dates and statuses, never names, emails or payment details. The assistant can
suggest pages to open but never books, pays, cancels or changes anything.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.metrics import AI_FALLBACKS
from app.modules.ai.knowledge import Chunk, KnowledgeBase
from app.modules.ai.llm import LLMClient, extract_json
from app.modules.auth.models import User
from app.modules.bookings.models import Booking, BookingItem, Trip
from app.modules.ml.request_classifier import RequestClassifier
from app.modules.recovery.models import RecoveryCase

_INTERNAL_LINK = re.compile(r"^/[a-z0-9/_\-?=&.%]*$", re.I)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AssistantRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)


class Action(BaseModel):
    label: str = Field(max_length=60)
    href: str = Field(max_length=200)


class Citation(BaseModel):
    title: str
    source: str


class AssistantOut(BaseModel):
    answer: str
    citations: list[Citation]
    actions: list[Action]
    source: str = Field(description="'ai:<provider>' or 'rules'")
    topic: str | None = Field(
        default=None, description="Support category of the question (request classifier)"
    )


class _Reply(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)
    sources: list[int] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)


SYSTEM = """You are TripMind's help assistant on a travel booking site.
Answer the traveller's last message using ONLY the numbered help articles and the trip summary
provided. If they do not contain the answer, say you don't know and suggest contacting support.
Never invent prices, availability, policies or booking details. You cannot book, pay, cancel or
change anything; tell the traveller which page to use instead. Keep answers short and plain.
Reply with one JSON object: {"answer": string, "sources": [article numbers you used],
"actions": [{"label": short button text, "href": one of the site paths listed}]}."""

PAGES = ("/flights", "/stays", "/plan", "/trips", "/account", "/support")
# Topics where a person may need to act: offer to open a support request, pre-filed.
SUPPORT_TOPICS = frozenset({"human_agent", "cancellation_refund", "change_booking"})


def trip_summary(session: Session, user: User | None) -> str:
    if user is None:
        return "The traveller is not signed in."
    lines = []
    trips = session.scalars(
        select(Trip).where(Trip.user_id == user.id).order_by(Trip.starts_on.desc()).limit(5)
    )
    for trip in trips:
        bookings = session.scalars(select(Booking).where(Booking.trip_id == trip.id))
        parts = []
        for b in bookings:
            items = session.scalars(select(BookingItem).where(BookingItem.booking_id == b.id))
            what = ", ".join(f"{i.kind} '{i.title}' ({i.status})" for i in items)
            parts.append(f"booking {b.reference} is {b.status}: {what}; page /bookings/{b.id}")
        lines.append(
            f"- {trip.title}, {trip.starts_on} to {trip.ends_on}, page /trips/{trip.id}. "
            + " ".join(parts)
        )
    open_cases = (
        session.scalar(
            select(func.count())
            .select_from(RecoveryCase)
            .where(RecoveryCase.user_id == user.id, RecoveryCase.status == "open")
        )
        or 0
    )
    if open_cases:
        lines.append(f"- {open_cases} disruption(s) need the traveller's decision (see My Trips).")
    return "Trips:\n" + "\n".join(lines) if lines else "The traveller has no trips yet."


class Assistant:
    def __init__(
        self,
        session: Session,
        llm: LLMClient,
        knowledge: KnowledgeBase,
        classifier: RequestClassifier | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._knowledge = knowledge
        self._classifier = classifier

    def answer(self, request: AssistantRequest, user: User | None) -> AssistantOut:
        out = self._answer(request, user)
        if self._classifier is None:
            return out
        topic = self._classifier.classify(request.messages[-1].content).category
        out.topic = topic
        href = f"/support/new?topic={topic}"
        if (
            user is not None
            and topic in SUPPORT_TOPICS
            and all(a.href != href for a in out.actions)
        ):
            out.actions = [*out.actions[:2], Action(label="Contact support", href=href)]
        return out

    def _answer(self, request: AssistantRequest, user: User | None) -> AssistantOut:
        question = request.messages[-1].content
        recent = " ".join(m.content for m in request.messages[-3:] if m.role == "user")
        hits = [chunk for chunk, _ in self._knowledge.search(recent, k=4)]
        articles = "\n".join(f"[{i + 1}] {c.title}: {c.text}" for i, c in enumerate(hits))
        context = (
            f"Help articles:\n{articles or '(none matched)'}\n\n"
            f"{trip_summary(self._session, user)}\n\nSite paths: {', '.join(PAGES)} "
            "and the trip and booking pages listed above."
        )
        history = [{"role": m.role, "content": m.content} for m in request.messages[-6:]]
        history[-1] = {"role": "user", "content": f"{context}\n\nTraveller: {question}"}
        result = self._llm.complete(
            feature="assistant", system=SYSTEM, messages=history, json_mode=True
        )
        if result is not None:
            try:
                reply = _Reply.model_validate(extract_json(result.text))
                return self._out(reply, hits, f"ai:{result.provider}")
            except ValueError:
                pass
        AI_FALLBACKS.labels(feature="assistant").inc()
        return self._fallback(hits)

    def _out(self, reply: _Reply, hits: list[Chunk], source: str) -> AssistantOut:
        cited = [hits[i - 1] for i in dict.fromkeys(reply.sources) if 1 <= i <= len(hits)]
        actions = [a for a in reply.actions if _INTERNAL_LINK.match(a.href)][:3]
        return AssistantOut(
            answer=reply.answer.strip(),
            citations=[Citation(title=c.title, source=c.source) for c in cited],
            actions=actions,
            source=source,
        )

    def _fallback(self, hits: list[Chunk]) -> AssistantOut:
        if not hits:
            return AssistantOut(
                answer="I couldn't find that in TripMind's help. Try asking about searching, "
                "bookings, cancellations, refunds, promo codes or disruptions.",
                citations=[],
                actions=[Action(label="My Trips", href="/trips")],
                source="rules",
            )
        best = hits[0]
        return AssistantOut(
            answer=f"{best.title}: {best.text}",
            citations=[Citation(title=best.title, source=best.source)],
            actions=[],
            source="rules",
        )
