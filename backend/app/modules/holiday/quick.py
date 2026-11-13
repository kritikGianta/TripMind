"""Quick request (stretch feature S1): read a short sentence with rules, no AI, and fill the form.

    "2 adults and a 6 year old from Bengaluru to Japan on 10 April for 6 nights under 3.5 lakh"
    -> departure BLR, Japan, 2027-04-10, 6 nights, 2 adults, child ages [6], budget 350000

Places are matched against the catalog (departure cities, countries and their cities), so a
place the data does not have is never invented. Whatever cannot be read stays as it was in the
form, and the answer says what was understood and what is still missing.
"""

from __future__ import annotations

import difflib
import re
from datetime import date, timedelta
from typing import Any

from app.modules.holiday.engine import Catalog

WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}  # fmt: skip
MONTHS = {
    m: i
    for i, names in enumerate(
        [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
         ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
         ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
         ("dec", "december")],
        start=1,
    )
    for m in names
}  # fmt: skip
NUM = r"(\d+|" + "|".join(WORDS) + r")"
ALIASES = {"bangalore": "Bengaluru", "banglore": "Bengaluru", "bangalor": "Bengaluru", "bengalore": "Bengaluru", "bangaluru": "Bengaluru", "blore": "Bengaluru", "new delhi": "Delhi", "dilli": "Delhi", "chenai": "Chennai", "mumabi": "Mumbai","bombay": "Mumbai", "madras": "Chennai", "uae": "United Arab Emirates", "uk": "United Kingdom", "england": "United Kingdom"}  # fmt: skip


def _num(token: str) -> int:
    return int(token) if token.isdigit() else WORDS[token]


def _date(text: str, after: date) -> date | None:
    """10 April 2027, April 10, 10 apr, 10/04/2027, 2027-04-10. Without a year: the next one."""
    if m := re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b", text):
        year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return date(year, int(m[2]), int(m[1]))
    month = "|".join(sorted(MONTHS, key=len, reverse=True))
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month})\b\.?(?:\s*,?\s*(\d{{4}}))?", text)
    m2 = re.search(rf"\b({month})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:\s*,?\s*(\d{{4}}))?", text)
    if m:
        day, mon, written = int(m[1]), MONTHS[m[2]], m[3]
    elif m2:
        day, mon, written = int(m2[2]), MONTHS[m2[1]], m2[3]
    else:
        return None
    try:
        found = date(int(written) if written else after.year, mon, day)
        if not written and found < after:
            found = date(after.year + 1, mon, day)
        return found
    except ValueError:
        return None


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PEOPLE = r"(?:friends?|wife|husband|partner|brother|sister|mom|mum|mother|dad|father|colleagues?|cousins?|girlfriend|boyfriend|fiancee?)"
# Common words that must never be "corrected" into a place name.
STOP = {"from", "with", "going", "trip", "nights", "night", "days", "budget", "under", "friend", "friends", "family", "tomorrow", "today", "holiday", "week", "weekend", "there", "where", "next", "this"}  # fmt: skip


def _relative(t: str, today: date) -> date | None:
    """today, tomorrow, day after tomorrow, in 5 days, next week, this weekend, next friday."""
    if re.search(r"\bday after tomorrow\b", t):
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw|tmr)\b", t):
        return today + timedelta(days=1)
    if re.search(r"\b(today|tonight)\b", t):
        return today
    if m := re.search(rf"\bin\s+{NUM}\s+(days?|weeks?)\b", t):
        return today + timedelta(days=_num(m[1]) * (7 if m[2].startswith("week") else 1))
    if re.search(r"\bnext week\b", t):
        return today + timedelta(days=7 - today.weekday())  # next Monday
    if m := re.search(r"\b(this |next )?weekend\b", t):
        ahead = (5 - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead + (7 if m[1] == "next " else 0))
    if m := re.search(rf"\b(?:on|this|next)\s+({'|'.join(WEEKDAYS)})\b", t):
        ahead = (WEEKDAYS.index(m[1]) - today.weekday()) % 7 or 7
        return today + timedelta(days=ahead)
    return None


def _fix_spelling(t: str, names: list[str]) -> str:
    """Bring close misspellings of known places to the right name (banglore -> bengaluru)."""
    known = {n for n in names if " " not in n}
    out = []
    for w in t.split(" "):
        if len(w) >= 4 and w not in known and w not in STOP:
            close = difflib.get_close_matches(w, known, n=1, cutoff=0.75)
            w = close[0] if close else w
        out.append(w)
    return " ".join(out)


def _people(t: str) -> int | None:
    """2 adults, we are 3, 3 of us, group of 4, me and my friend, with 2 friends, couple, solo."""
    if m := re.search(rf"\b{NUM}\s+(adults?|grown-?ups?|people|persons|of us|travell?ers)\b", t):
        return _num(m[1])
    if m := re.search(rf"\b(?:we are|we're|group of|party of)\s+{NUM}\b", t):
        return _num(m[1])
    if m := re.search(rf"\b(?:me|i)\s+(?:and|with|&)\s+(?:my\s+)?{NUM}\s+{PEOPLE}\b", t):
        return _num(m[1]) + 1
    if m := re.search(rf"\bwith\s+(?:my\s+)?{NUM}\s+{PEOPLE}\b", t):
        return _num(m[1]) + 1
    if re.search(
        rf"\b(couple|honeymoon|(?:me|i)\s+(?:and|&)\s+(?:my|a)\s+{PEOPLE}|(?:my|a)\s+{PEOPLE}\s+and\s+(?:i|me)|with\s+(?:my|a)\s+{PEOPLE})\b",
        t,
    ):
        return 2
    if re.search(r"\b(solo|alone|just me|by myself)\b", t):
        return 1
    return None


def parse(text: str, cat: Catalog, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    t = re.sub(r"[^\w\s,./&₹-]", " ", text.strip().lower())
    t = " " + re.sub(r"\s+", " ", t).strip() + " "
    for word, name in ALIASES.items():
        t = re.sub(rf"\b{word}\b", name.lower(), t)
    places = [c.lower() for c in cat.departures.values()]
    places += [n.lower() for country, cities in cat.countries.items() for n in (country, *cities)]
    t = _fix_spelling(t, places)
    fields: dict[str, Any] = {}
    understood: list[str] = []
    notes: list[str] = []

    # Departure city: "from Bengaluru" or an airport code (BLR).
    for code, city in cat.departures.items():
        if re.search(rf"\b(from\s+)?({city.lower()}|{code.lower()})\b", t):
            fields["departure_airport"] = code
            understood.append(f"from {city}")
            break
    # Destination: a country name, or one of its cities (Kyoto -> Japan).
    for country, cities in cat.countries.items():
        names = [country.lower(), *(c.lower() for c in cities)]
        if any(re.search(rf"\b{re.escape(n)}\b", t) for n in names):
            fields["country"] = country
            understood.append(f"to {country}")
            break
    else:
        # A destination we do not have: say so instead of guessing.
        m = re.search(r"\b(?:to|visit|visiting)\s+([a-z]+(?: [a-z]+)?)", t)
        place = m[1].split(" ")[0] if m else ""
        if place and place not in STOP and place not in WORDS and place not in places:
            notes.append(
                f"{place.title()} is not in our holiday data. Holidays go to "
                + ", ".join(sorted(cat.countries))
                + "."
            )
    # Start date: "10 April", "10/04/2027", or "tomorrow", "next friday", "in 2 weeks".
    if start := _date(t, max(today, cat.first_night)) or _relative(t, today):
        fields["start_date"] = start.isoformat()
        understood.append(f"landing {start:%d %b %Y}")
    # Nights: "6 nights", "7 days" (6 nights), "a week".
    if m := re.search(rf"\b{NUM}\s+nights?\b", t):
        fields["nights"] = _num(m[1])
    elif m := re.search(rf"\b{NUM}\s+days?\b", t):
        fields["nights"] = max(_num(m[1]) - 1, 1)
    elif re.search(r"\b(a|one)\s+week\b", t):
        fields["nights"] = 7
    if "nights" in fields:
        understood.append(f"{fields['nights']} nights")
    # Adults: "2 adults", "we are 3", "me and my friend", "couple", "solo".
    if (adults := _people(t)) is not None:
        fields["adults"] = adults
    if "adults" in fields:
        understood.append(f"{fields['adults']} adults")
    # Children: "a 6 year old", "kids aged 6 and 9", "child 4".
    ages = [int(a) for a in re.findall(r"\b(\d{1,2})[- ]?(?:years?|yrs?)[- ]?old\b", t)]
    if not ages and (
        m := re.search(
            r"\b(?:kids?|child(?:ren)?)\s+(?:aged?\s+)?(\d{1,2}(?:\s*(?:,|and)\s*\d{1,2})*)\b", t
        )
    ):
        ages = [int(a) for a in re.findall(r"\d{1,2}", m[1])]
    ages = [a for a in ages if 0 <= a <= 17]
    if ages:
        fields["child_ages"] = ages
        understood.append(f"children aged {', '.join(map(str, ages))}")
    elif re.search(r"\bno (kids|children)\b", t):
        fields["child_ages"] = []
    # Budget: "3.5 lakh", "2L", "350k", "under 3,50,000", "budget 300000", "rs 2 lakh".
    if m := re.search(r"(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|l)\b", t):
        fields["budget_inr"] = round(float(m[1]) * 100_000)
    elif m := re.search(r"(\d+(?:\.\d+)?)\s*k\b", t):
        fields["budget_inr"] = round(float(m[1]) * 1_000)
    elif m := re.search(
        r"(?:budget|under|within|upto|up to|max|rs\.?|inr|₹)\s*(?:of\s*)?([\d,]{4,})", t
    ):
        fields["budget_inr"] = int(m[1].replace(",", ""))
    if "budget_inr" in fields:
        understood.append(f"budget {fields['budget_inr']:,} INR")

    labels = {"departure_airport": "departure city", "country": "destination country",
              "start_date": "start date", "nights": "nights", "adults": "adults",
              "budget_inr": "budget"}  # fmt: skip
    missing = [label for key, label in labels.items() if key not in fields]
    if start:
        first, last = cat.first_night, cat.last_departure
        if not first <= start <= last:
            notes.append(f"Holidays can start from {first:%d %b %Y} to {last:%d %b %Y}.")
    return {"fields": fields, "understood": understood, "missing": missing, "notes": notes}
