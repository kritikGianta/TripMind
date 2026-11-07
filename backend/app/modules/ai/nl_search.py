"""Natural-language trip search: "2 of us, Delhi to Goa 20-24 Nov, beach hotel under 60k".

The text is turned into search criteria by a hosted LLM when one is available, otherwise by a
deterministic rule parser. Either way the place names are then resolved against the catalog
(aliases and fuzzy matching), so a city the data does not contain is reported as missing,
never invented. The result only fills a search form; the traveller still runs the search.
"""

from __future__ import annotations

import contextlib
import re
from calendar import month_abbr
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import AI_FALLBACKS
from app.modules.ai.llm import LLMClient
from app.modules.catalog.models import Airport, City
from app.modules.catalog.vocabulary import Vocabulary, normalize_text

Intent = Literal["flights", "stays", "trip"]


class TripIntent(BaseModel):
    """What the LLM must return (and what the rule parser produces)."""

    intent: Intent = "trip"
    origin: str | None = None
    destination: str | None = None
    depart_date: date | None = None
    return_date: date | None = None
    nights: int | None = Field(default=None, ge=1, le=30)
    adults: int = Field(default=1, ge=1, le=9)
    cabin_class: Literal["economy", "business"] | None = None
    priority: Literal["balanced", "cheapest", "fastest", "comfort"] | None = None
    max_budget: int | None = Field(default=None, ge=1)
    min_stars: int | None = Field(default=None, ge=1, le=5)

    @field_validator("adults", mode="before")
    @classmethod
    def _adults(cls, value: object) -> object:
        return 1 if value in (None, "", 0) else value


class PlaceOut(BaseModel):
    city_id: str
    label: str
    airport_code: str | None


class ParsedSearchOut(BaseModel):
    source: str = Field(description="'ai:<provider>' or 'rules'")
    intent: Intent
    origin: PlaceOut | None
    destination: PlaceOut | None
    depart_date: date | None
    return_date: date | None
    adults: int
    cabin_class: str | None
    priority: str | None
    max_budget: int | None
    min_stars: int | None
    missing: list[str]
    unknown_places: list[str]
    summary: str


# ── Rule parser ──────────────────────────────────────────────────────────────────────────────

_MONTHS = {m.lower(): i for i, m in enumerate(month_abbr) if m}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:-|to|\u2013)?\s*(?:(\d{1,2})(?:st|nd|rd|th)?\s*)?"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
)
_MONTH_DAY = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+"
    r"(\d{1,2})(?:st|nd|rd|th)?\b"
)
_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_ADULTS = re.compile(r"\b(\d)\s*(?:adults?|people|persons?|pax|travell?ers?|of us|guests?)\b")
_FAMILY = re.compile(r"\bfamily of (\d)\b")
_NIGHTS = re.compile(r"\b(\d{1,2})\s*nights?\b")
_BUDGET = re.compile(
    r"(?:under|below|budget(?: of)?|max(?:imum)?|up ?to|less than|within)\s*"
    r"(?:rs\.?|inr|₹)?\s*([\d,.]+)\s*(k|thousand|lakh|lac|l)?\b"
)
_STARS = re.compile(r"\b([1-5])\s*[- ]?star")


def _next(day: int, month: int, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def _dates(text: str, today: date) -> list[date]:
    found: list[tuple[int, date]] = []
    for m in _DAY_MONTH.finditer(text):
        month = _MONTHS[m.group(3)[:3]]
        for group in (1, 2):
            if m.group(group) and (d := _next(int(m.group(group)), month, today)):
                found.append((m.start(group), d))
    for m in _MONTH_DAY.finditer(text):
        if d := _next(int(m.group(2)), _MONTHS[m.group(1)[:3]], today):
            found.append((m.start(), d))
    for m in _ISO.finditer(text):
        with contextlib.suppress(ValueError):  # e.g. 2026-02-30
            found.append((m.start(), date(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    relative = {"day after tomorrow": 2, "tomorrow": 1, "today": 0}
    for phrase, offset in relative.items():
        if phrase in text:
            found.append((text.index(phrase), today + timedelta(days=offset)))
            text = text.replace(phrase, " " * len(phrase))
    for i, name in enumerate(_WEEKDAYS):
        if weekday := re.search(rf"\b(?:next|this|on)\s+{name}\b", text):
            ahead = (i - today.weekday()) % 7 or 7
            found.append((weekday.start(), today + timedelta(days=ahead)))
    if weekend := re.search(r"\bthis weekend\b|\bnext weekend\b", text):
        ahead = (5 - today.weekday()) % 7 or 7
        if "next" in weekend.group(0):
            ahead += 7
        found.append((weekend.start(), today + timedelta(days=ahead)))
        found.append((weekend.start() + 1, today + timedelta(days=ahead + 2)))
    unique = sorted({d: pos for pos, d in sorted(found, reverse=True)}.items(), key=lambda x: x[1])
    return [d for d, _ in unique]


def rule_parse(text: str, today: date) -> TripIntent:
    t = " ".join(text.lower().split())
    hotel = re.search(r"\b(hotel|stay|stays|room|rooms|resort|accommodation|nights?)\b", t)
    flight = re.search(r"\b(fly|flight|flights|plane|airfare|return ticket|one way)\b", t)
    intent: Intent = (
        "stays" if hotel and not flight else "flights" if flight and not hotel else "trip"
    )

    adults = 1
    if m := _ADULTS.search(t) or _FAMILY.search(t):
        adults = int(m.group(1))
    elif re.search(r"\b(couple|two of us|me and my (?:wife|husband|partner|friend))\b", t):
        adults = 2
    budget = None
    if m := _BUDGET.search(t):
        value = float(m.group(1).replace(",", ""))
        scale = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lac": 100_000, "l": 100_000}
        budget = int(value * scale.get(m.group(2) or "", 1))
    dates = _dates(t, today)
    nights = (
        int(m.group(1))
        if (m := _NIGHTS.search(t))
        else (7 if "a week" in t else 2 if "weekend" in t and len(dates) < 2 else None)
    )
    return TripIntent(
        intent=intent,
        depart_date=dates[0] if dates else None,
        return_date=dates[1] if len(dates) > 1 else None,
        nights=nights,
        adults=min(max(adults, 1), 9),
        cabin_class="business" if "business class" in t or "business" in t.split() else None,
        priority=(
            "cheapest"
            if re.search(r"\b(cheap|cheapest|budget|low cost)\b", t)
            else "fastest"
            if re.search(r"\b(fast|fastest|quick|shortest)\b", t)
            else "comfort"
            if re.search(r"\b(luxury|comfortable|comfort|premium|nice hotel)\b", t)
            else None
        ),
        max_budget=budget,
        min_stars=int(m.group(1)) if (m := _STARS.search(t)) else None,
    )


# ── Places ───────────────────────────────────────────────────────────────────────────────────


class PlaceResolver:
    """Finds catalog cities in free text, and resolves single names (from the LLM)."""

    def __init__(self, session: Session, vocabulary: Vocabulary) -> None:
        self._cities = list(session.scalars(select(City).where(City.is_active.is_(True))))
        airports = (
            session.execute(
                select(Airport.city_id, Airport.code).where(Airport.is_active.is_(True))
            )
            .tuples()
            .all()
        )
        self._airport = {city_id: code for city_id, code in airports}
        codes = {code.lower(): city_id for city_id, code in airports}
        aliases = vocabulary.city_alias_index()
        self._names: dict[str, City] = {}
        by_id = {c.id: c for c in self._cities}
        for city in self._cities:
            self._names[normalize_text(city.name)] = city
        for alias, canonical in aliases.items():
            if canonical in self._names:
                self._names[alias] = self._names[canonical]
        for code, city_id in codes.items():
            if city_id in by_id:
                self._names.setdefault(code, by_id[city_id])

    def out(self, city: City) -> PlaceOut:
        return PlaceOut(
            city_id=str(city.id), label=city.name, airport_code=self._airport.get(city.id)
        )

    def resolve(self, name: str | None) -> City | None:
        if not name:
            return None
        key = normalize_text(name)
        if key in self._names:
            return self._names[key]
        match = process.extractOne(key, list(self._names), scorer=fuzz.WRatio, score_cutoff=88)
        return self._names[match[0]] if match else None

    def find_in(self, text: str) -> tuple[City | None, City | None]:
        """Origin and destination named in the text, using 'from'/'to'/'in' when present."""
        norm = f" {normalize_text(text)} "
        hits: list[tuple[int, City]] = []
        for name, city in self._names.items():
            if len(name) < 3:
                continue
            for m in re.finditer(rf" {re.escape(name)} ", norm):
                hits.append((m.start(), city))
        hits.sort(key=lambda h: h[0])
        seen: list[tuple[int, City]] = []
        for pos, city in hits:
            if all(city.id != c.id for _, c in seen):
                seen.append((pos, city))
        origin = destination = None
        for pos, city in seen:
            before = norm[max(0, pos - 6) : pos]
            if " from" in before and origin is None:
                origin = city
            elif (" to" in before or " in" in before or "for" in before) and destination is None:
                destination = city
        rest = [c for _, c in seen if c not in (origin, destination)]
        if destination is None and rest:
            destination = rest.pop() if origin is not None or len(rest) == 1 else rest.pop(1)
        if origin is None and rest:
            origin = rest.pop(0)
        return origin, destination


# ── Service ──────────────────────────────────────────────────────────────────────────────────

SYSTEM = """You turn a traveller's message into search criteria for a travel booking site.
Reply with one JSON object only, with these keys:
intent ("flights", "stays" or "trip" = flight and hotel together), origin (city name or null),
destination (city name or null), depart_date and return_date (YYYY-MM-DD or null),
nights (integer or null), adults (integer, default 1), cabin_class ("economy", "business" or null),
priority ("balanced", "cheapest", "fastest", "comfort" or null), max_budget (whole trip, number in
INR, or null), min_stars (1-5 or null).
Rules: resolve relative dates ("next Friday", "this weekend") against today's date. Never invent
values that are not in the message; use null. Use only city names; do not add airports."""


class NaturalLanguageSearch:
    def __init__(
        self,
        session: Session,
        llm: LLMClient,
        vocabulary: Vocabulary,
        today: date,
        window: tuple[date, date] | None,
    ) -> None:
        self._llm = llm
        self._places = PlaceResolver(session, vocabulary)
        self._today = today
        self._window = window

    def parse(self, text: str) -> ParsedSearchOut:
        window = (
            f"Flights exist from {self._window[0]} to {self._window[1]}." if self._window else ""
        )
        ai = self._llm.complete_json(
            feature="nl_search",
            system=SYSTEM,
            schema=TripIntent,
            user=f"Today is {self._today:%A %Y-%m-%d}. {window}\nMessage: {text}",
        )
        # The rule parser always runs: it is deterministic for dates and numbers, and fills
        # anything the model leaves empty (models are inconsistent with "next Friday").
        rules = rule_parse(text, self._today)
        found_origin, found_destination = self._places.find_in(text)
        if ai is None:
            AI_FALLBACKS.labels(feature="nl_search").inc()
            return self._finish(rules, "rules", found_origin, found_destination, [])

        model, source = ai[0], f"ai:{ai[1]}"
        merged = model.model_copy(
            update={
                field: getattr(rules, field)
                for field in (
                    "depart_date",
                    "return_date",
                    "nights",
                    "cabin_class",
                    "priority",
                    "max_budget",
                    "min_stars",
                )
                if getattr(model, field) is None and getattr(rules, field) is not None
            }
        )
        if merged.adults == 1 and rules.adults > 1:
            merged = merged.model_copy(update={"adults": rules.adults})
        origin = self._places.resolve(model.origin) or (None if model.origin else found_origin)
        destination = self._places.resolve(model.destination) or (
            None if model.destination else found_destination
        )
        unknown = [
            n
            for n, c in ((model.origin, origin), (model.destination, destination))
            if n and c is None
        ]
        return self._finish(merged, source, origin, destination, unknown)

    def _finish(
        self,
        intent: TripIntent,
        source: str,
        origin: City | None,
        destination: City | None,
        unknown: list[str],
    ) -> ParsedSearchOut:
        depart, ret = intent.depart_date, intent.return_date
        if depart and depart < self._today:
            depart = None
        if depart and not ret and intent.nights:
            ret = depart + timedelta(days=intent.nights)
        if depart and ret and ret <= depart:
            ret = None
        if intent.intent == "stays" and depart and not ret:
            ret = depart + timedelta(days=intent.nights or 2)
        missing = []
        if intent.intent != "stays" and origin is None:
            missing.append("origin")
        if destination is None:
            missing.append("destination")
        if depart is None:
            missing.append("depart_date")
        if intent.intent == "trip" and ret is None:
            missing.append("return_date")
        label = {"flights": "Flights", "stays": "Stays", "trip": "Flight + stay"}[intent.intent]
        parts = [label]
        if origin or destination:
            parts.append(" → ".join(c.name for c in (origin, destination) if c))
        if depart:
            parts.append(f"{depart:%d %b}" + (f" to {ret:%d %b}" if ret else ""))
        parts.append(f"{intent.adults} adult{'s' if intent.adults > 1 else ''}")
        if intent.max_budget:
            parts.append(f"budget {intent.max_budget:,}")
        return ParsedSearchOut(
            source=source,
            intent=intent.intent,
            origin=self._places.out(origin) if origin else None,
            destination=self._places.out(destination) if destination else None,
            depart_date=depart,
            return_date=ret,
            adults=intent.adults,
            cabin_class=intent.cabin_class,
            priority=intent.priority,
            max_budget=intent.max_budget,
            min_stars=intent.min_stars,
            missing=missing,
            unknown_places=unknown,
            summary=" · ".join(parts),
        )
