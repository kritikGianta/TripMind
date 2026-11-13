"""Extend the official data pack with more dates, in exactly the same schema.

The official pack has flights and rooms for 1-20 April 2027 only. This writes `flights.json` and
`availability.json` (same fields as the pack) for every other day from `start` to `end`, so
TripMind can be used for trips from today onwards. Everything else (airports, hotels, rooms,
transfers, attractions, destinations) is the official pack, unchanged.

How the extra rows are made (seeded, so the output is always the same):
- Flights: each day, about two flights per route, copied from that route's official flights
  (same airline, flight number style, local times, duration, stops), with the price moved by up
  to +-15% (+10% on Fridays and Sundays) and 1-9 seats left. IDs look like `FX-20261115-001`.
- Availability: every room type, every night, 0 to the most rooms the official pack ever shows
  for it, with a few full nights.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

OFFICIAL_FIRST, OFFICIAL_LAST = date(2027, 4, 1), date(2027, 4, 20)
FLIGHTS_PER_ROUTE_PER_DAY = 2


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def generate(
    pack_dir: Path, out_dir: Path, start: date, end: date, seed: int = 7
) -> dict[str, int]:
    rng = random.Random(seed)  # noqa: S311 - seeded synthetic data, not security
    folder = pack_dir / "data" / "catalog"
    flights = json.loads((folder / "flights.json").read_text(encoding="utf-8"))
    availability = json.loads((folder / "availability.json").read_text(encoding="utf-8"))
    days = [d for d in _days(start, end) if not OFFICIAL_FIRST <= d <= OFFICIAL_LAST]

    by_route: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for f in flights:
        by_route[(f["from"], f["to"])].append(f)
    new_flights: list[dict[str, Any]] = []
    for day in days:
        n = 0
        for route in sorted(by_route):
            templates = by_route[route]
            for t in rng.sample(templates, min(FLIGHTS_PER_ROUTE_PER_DAY, len(templates))):
                dep = datetime.fromisoformat(t["departure_local"])
                arr = datetime.fromisoformat(t["arrival_local"])
                shift = day - dep.date()
                bump = 1.10 if day.weekday() in (4, 6) else 1.0
                price = (
                    round(t["price_per_seat"]["amount"] * rng.uniform(0.85, 1.15) * bump / 50) * 50
                )
                n += 1
                new_flights.append(
                    {
                        **t,
                        "flight_id": f"FX-{day:%Y%m%d}-{n:03d}",
                        "departure_local": (dep + shift).isoformat(),
                        "arrival_local": (arr + shift).isoformat(),
                        "price_per_seat": {"amount": price, "currency": "INR"},
                        "seats_left": rng.randint(1, 9),
                    }
                )

    most: dict[str, int] = defaultdict(int)
    for a in availability:
        most[a["room_id"]] = max(most[a["room_id"]], a["rooms_left"])
    new_availability = [
        {
            "room_id": room,
            "date": day.isoformat(),
            "rooms_left": 0 if rng.random() < 0.05 else rng.randint(1, max(1, top)),
        }
        for room, top in sorted(most.items())
        for day in days
    ]

    target = out_dir / "data" / "catalog"
    target.mkdir(parents=True, exist_ok=True)
    (target / "flights.json").write_text(json.dumps(new_flights, indent=1), encoding="utf-8")
    (target / "availability.json").write_text(json.dumps(new_availability), encoding="utf-8")
    return {"flights": len(new_flights), "availability": len(new_availability), "days": len(days)}
