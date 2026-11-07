"""Synthetic traffic for dashboards and the About page's measured numbers.

Each virtual user signs in with demo access, then loops: search flights, search stays and, now
and then, hold and pay for a flight. Results are labelled synthetic wherever they are shown.

    cd backend
    uv run python scripts/loadtest.py --base-url http://localhost:8000 --users 8 --duration 60

Point it at the API port (8000). Every virtual user presents its own client address in
X-Forwarded-For, which the API trusts because in production it only sits behind the web proxy;
without it, all users would share one per-IP rate limit and mostly measure the limiter.
"""

from __future__ import annotations

import argparse
import random
import statistics
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta

import httpx

ROUTES = [
    ("DEL", "BOM"),
    ("BOM", "BLR"),
    ("DEL", "GOI"),
    ("BLR", "HYD"),
    ("MAA", "DEL"),
    ("CCU", "BOM"),
    ("DEL", "DXB"),
    ("BOM", "SIN"),
    ("HYD", "JAI"),
    ("BLR", "COK"),
]
CITIES = ["Mumbai", "Delhi", "Goa", "Bengaluru", "Jaipur", "Dubai", "Kochi"]
CARD = {
    "card_number": "4242424242424242",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvc": "123",
    "cardholder_name": "Load Test",
}


class Stats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.latency: dict[str, list[float]] = defaultdict(list)
        self.status: Counter[str] = Counter()
        self.outcomes: Counter[str] = Counter()

    def record(self, name: str, seconds: float, status: int) -> None:
        with self.lock:
            self.latency[name].append(seconds)
            self.status[f"{status // 100}xx"] += 1

    def outcome(self, name: str) -> None:
        with self.lock:
            self.outcomes[name] += 1


def call(
    client: httpx.Client, stats: Stats, name: str, method: str, url: str, **kwargs: object
) -> httpx.Response:
    start = time.perf_counter()
    response = client.request(method, url, **kwargs)  # type: ignore[arg-type]
    stats.record(name, time.perf_counter() - start, response.status_code)
    return response


def user(base: str, index: int, until: float, first_day: date, stats: Stats) -> None:
    headers = {"X-Forwarded-For": f"10.42.{index // 250}.{index % 250 + 1}"}
    with httpx.Client(base_url=f"{base}/api/v1", headers=headers, timeout=30) as client:
        call(client, stats, "demo_login", "POST", "/auth/demo-login", json={"role": "traveler"})
        cities = {}
        for name in CITIES:
            items = client.get("/locations", params={"q": name, "kind": "city"}).json()["items"]
            if items:
                cities[name] = items[0]["value"]
        rng = random.Random(index)
        while time.time() < until:
            origin, destination = rng.choice(ROUTES)
            day = first_day + timedelta(days=rng.randint(1, 20))
            adults = rng.choice([1, 1, 2])
            flights = call(
                client,
                stats,
                "flight_search",
                "GET",
                "/flights/search",
                params={
                    "origin": origin,
                    "destination": destination,
                    "departure_date": day.isoformat(),
                    "adults": adults,
                },
            )
            city = rng.choice(list(cities.values()))
            call(
                client,
                stats,
                "hotel_search",
                "GET",
                "/hotels/search",
                params={
                    "city": city,
                    "check_in": day.isoformat(),
                    "check_out": (day + timedelta(days=rng.randint(1, 4))).isoformat(),
                },
            )
            if flights.status_code == 200 and rng.random() < 0.25:
                offers = [o for o in flights.json()["outbound"]["offers"] if o["bookable"]]
                if offers:
                    offer = rng.choice(offers[:5])
                    hold = call(
                        client,
                        stats,
                        "booking_hold",
                        "POST",
                        "/bookings",
                        json={
                            "items": [
                                {"kind": "flight", "offer_id": offer["id"], "adults": adults}
                            ],
                            "travellers": [
                                {"first_name": "Load", "last_name": f"User{i}"}
                                for i in range(adults)
                            ],
                            "contact": {"email": f"load{index}@example.com"},
                        },
                        headers={"Idempotency-Key": uuid.uuid4().hex},
                    )
                    stats.outcome(f"hold_{hold.status_code}")
                    if hold.status_code == 201:
                        paid = call(
                            client,
                            stats,
                            "payment",
                            "POST",
                            f"/bookings/{hold.json()['id']}/payments",
                            json=CARD,
                            headers={"Idempotency-Key": uuid.uuid4().hex},
                        )
                        stats.outcome(f"payment_{paid.status_code}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=8)
    parser.add_argument("--duration", type=int, default=60, help="seconds")
    args = parser.parse_args()

    summary = httpx.get(f"{args.base_url}/api/v1/datasets/current", timeout=10).json()
    window = summary.get("travel_window") or {}
    first_day = max(
        date.fromisoformat(window.get("first_departure", date.today().isoformat())), date.today()
    )
    stats = Stats()
    until = time.time() + args.duration
    threads = [
        threading.Thread(target=user, args=(args.base_url, i, until, first_day, stats))
        for i in range(args.users)
    ]
    started = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - started

    total = sum(len(v) for v in stats.latency.values())
    print(
        f"Synthetic load: {args.users} users, {elapsed:.0f} s, {total} requests "
        f"({total / elapsed:.1f} req/s). Status: {dict(stats.status)}"
    )
    for name, values in sorted(stats.latency.items()):
        values.sort()
        p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
        print(
            f"  {name:<14} n={len(values):<5} p50={statistics.median(values) * 1000:6.0f} ms  "
            f"p95={p95 * 1000:6.0f} ms"
        )
    print(f"  outcomes: {dict(stats.outcomes)}")


if __name__ == "__main__":
    main()
