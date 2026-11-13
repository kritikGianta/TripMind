"""Quick request (stretch feature S1): read a short sentence with rules, no AI, and fill the form.

    "2 adults and a 6 year old from Bengaluru to Japan on 10 April for 6 nights under 3.5 lakh"
    -> departure BLR, Japan, 2027-04-10, 6 nights, 2 adults, child ages [6], budget 350000

Places are matched against the catalog (departure cities, countries and their cities), so a
place the data does not have is never invented. Whatever cannot be read stays as it was in the
form, and the answer says what was understood and what is still missing.
"""

from __future__ import annotations

import re
from datetime import date
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
ALIASES = {"bangalore": "Bengaluru", "bombay": "Mumbai", "madras": "Chennai", "uae": "United Arab Emirates", "uk": "United Kingdom", "england": "United Kingdom"}  # fmt: skip


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


def parse(text: str, cat: Catalog) -> dict[str, Any]:
    raw = text.strip()
    t = " " + re.sub(r"\s+", " ", raw.lower()) + " "
    for word, name in ALIASES.items():
        t = re.sub(rf"\b{word}\b", name.lower(), t)
    fields: dict[str, Any] = {}
    understood: list[str] = []

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
    # Start date.
    if start := _date(t, cat.first_night):
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
    # Adults: "2 adults", "couple", "two of us", "solo".
    if m := re.search(rf"\b{NUM}\s+(adults?|grown-?ups?|people|persons|of us)\b", t):
        fields["adults"] = _num(m[1])
    elif re.search(r"\b(couple|my (wife|husband|partner) and (i|me))\b", t):
        fields["adults"] = 2
    elif re.search(r"\b(solo|alone|just me)\b", t):
        fields["adults"] = 1
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
    return {"fields": fields, "understood": understood, "missing": missing}
