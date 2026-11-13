"""More destinations, written in exactly the official pack's schema (synthetic data).

Adds countries, cities, airports, hotels, room types, nightly availability, airport and
city-to-city transfers, attractions and daily flights from the four Indian departure cities.
Landmark names are real; hotels, prices, times and availability are invented (seeded).
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

INDIA = {"BLR": "Bengaluru", "DEL": "Delhi", "BOM": "Mumbai", "MAA": "Chennai"}

# country code, name, timezone, price level (1 = cheap), cities:
#   (city, airport code, airport name, lat, lng, minutes from India, areas, attractions)
# attraction: (name, category, open_from, open_until, visit minutes, price INR, closed weekday)
WORLD: list[dict[str, Any]] = [
    {
        "code": "TH",
        "name": "Thailand",
        "tz": "Asia/Bangkok",
        "level": 0.6,
        "cities": [
            (
                "Bangkok",
                "BKK",
                "Suvarnabhumi Airport",
                13.69,
                100.75,
                250,
                ["Sukhumvit", "Riverside", "Silom"],
                [
                    ("Grand Palace", "PALACE", "08:30", "15:30", 150, 1250, None),
                    ("Wat Arun", "TEMPLE", "08:00", "18:00", 60, 250, None),
                    ("Wat Pho", "TEMPLE", "08:00", "18:30", 90, 500, None),
                    ("Chatuchak Weekend Market", "MARKET", "09:00", "18:00", 180, 0, "MON"),
                    ("Jim Thompson House", "MUSEUM", "10:00", "18:00", 75, 500, None),
                    ("Chao Phraya River Cruise", "CRUISE", "16:00", "22:00", 120, 1800, None),
                    ("Lumphini Park", "PARK", "04:30", "21:00", 60, 0, None),
                    ("SEA LIFE Bangkok Ocean World", "AQUARIUM", "10:00", "20:00", 120, 2300, None),
                ],
            ),
            (
                "Phuket",
                "HKT",
                "Phuket International Airport",
                8.11,
                98.31,
                270,
                ["Patong", "Kata"],
                [
                    ("Big Buddha", "TEMPLE", "08:00", "19:30", 60, 0, None),
                    ("Patong Beach", "BEACH", "06:00", "20:00", 180, 0, None),
                    ("Phi Phi Islands Day Trip", "TOUR", "07:00", "18:00", 540, 4500, None),
                    ("Old Phuket Town", "HERITAGE", "09:00", "20:00", 120, 0, None),
                    ("Phuket FantaSea", "SHOW", "17:30", "23:30", 180, 4200, "THU"),
                    ("Kata Viewpoint", "VIEWPOINT", "06:00", "19:00", 45, 0, None),
                ],
            ),
            (
                "Chiang Mai",
                "CNX",
                "Chiang Mai International Airport",
                18.77,
                98.96,
                330,
                ["Old City", "Nimman"],
                [
                    ("Wat Phra That Doi Suthep", "TEMPLE", "06:00", "18:00", 120, 80, None),
                    ("Elephant Nature Park", "WILDLIFE", "08:00", "17:00", 420, 6500, None),
                    ("Sunday Walking Street", "MARKET", "16:00", "23:00", 150, 0, None),
                    ("Wat Chedi Luang", "TEMPLE", "06:00", "18:00", 60, 100, None),
                    ("Doi Inthanon National Park", "NATURE", "06:00", "18:00", 480, 700, None),
                    ("Chiang Mai Night Bazaar", "MARKET", "18:00", "24:00", 120, 0, None),
                ],
            ),
        ],
        "links": [
            ("Bangkok", "Chiang Mai", "TRAIN", 660, 1600),
            ("Bangkok", "Phuket", "INTERCITY_BUS", 720, 1400),
        ],
    },
    {
        "code": "SG",
        "name": "Singapore",
        "tz": "Asia/Singapore",
        "level": 1.1,
        "cities": [
            (
                "Singapore",
                "SIN",
                "Changi Airport",
                1.36,
                103.99,
                300,
                ["Marina Bay", "Orchard", "Sentosa"],
                [
                    ("Gardens by the Bay", "GARDEN", "05:00", "24:00", 150, 1800, None),
                    ("Marina Bay Sands SkyPark", "VIEWPOINT", "10:00", "22:00", 60, 2000, None),
                    (
                        "Universal Studios Singapore",
                        "THEME_PARK",
                        "10:00",
                        "19:00",
                        420,
                        5200,
                        None,
                    ),
                    ("Singapore Zoo", "ZOO", "08:30", "18:00", 240, 2800, None),
                    ("Night Safari", "ZOO", "19:15", "24:00", 180, 3300, None),
                    ("S.E.A. Aquarium", "AQUARIUM", "10:00", "17:00", 150, 2400, None),
                    ("Chinatown Heritage Centre", "MUSEUM", "09:00", "20:00", 75, 1000, "MON"),
                    ("Sentosa Beaches", "BEACH", "07:00", "22:00", 180, 0, None),
                ],
            ),
        ],
        "links": [],
    },
    {
        "code": "ID",
        "name": "Indonesia",
        "tz": "Asia/Makassar",
        "level": 0.7,
        "cities": [
            (
                "Bali",
                "DPS",
                "Ngurah Rai International Airport",
                -8.75,
                115.17,
                480,
                ["Seminyak", "Ubud", "Kuta"],
                [
                    ("Uluwatu Temple", "TEMPLE", "07:00", "19:00", 120, 450, None),
                    ("Tegallalang Rice Terraces", "NATURE", "08:00", "18:00", 120, 300, None),
                    ("Sacred Monkey Forest Sanctuary", "WILDLIFE", "09:00", "18:00", 90, 450, None),
                    ("Tanah Lot", "TEMPLE", "07:00", "19:00", 90, 400, None),
                    ("Mount Batur Sunrise Trek", "TOUR", "02:00", "11:00", 480, 3500, None),
                    ("Waterbom Bali", "THEME_PARK", "09:00", "18:00", 300, 3000, None),
                    ("Seminyak Beach", "BEACH", "06:00", "20:00", 180, 0, None),
                ],
            ),
        ],
        "links": [],
    },
    {
        "code": "FR",
        "name": "France",
        "tz": "Europe/Paris",
        "level": 1.8,
        "cities": [
            (
                "Paris",
                "CDG",
                "Charles de Gaulle Airport",
                49.01,
                2.55,
                600,
                ["Le Marais", "Saint-Germain", "Montmartre"],
                [
                    ("Eiffel Tower", "LANDMARK", "09:30", "23:00", 150, 2600, None),
                    ("Louvre Museum", "MUSEUM", "09:00", "18:00", 240, 2000, "TUE"),
                    ("Musee d'Orsay", "MUSEUM", "09:30", "18:00", 150, 1500, "MON"),
                    ("Montmartre and Sacre-Coeur", "LANDMARK", "06:00", "22:30", 120, 0, None),
                    ("Seine River Cruise", "CRUISE", "10:00", "22:00", 75, 1600, None),
                    ("Disneyland Paris", "THEME_PARK", "09:30", "21:00", 480, 8200, None),
                    ("Palace of Versailles", "PALACE", "09:00", "17:30", 240, 2000, "MON"),
                    ("Arc de Triomphe", "LANDMARK", "10:00", "22:30", 60, 1200, None),
                ],
            ),
            (
                "Nice",
                "NCE",
                "Nice Cote d'Azur Airport",
                43.66,
                7.21,
                720,
                ["Promenade", "Vieux Nice"],
                [
                    ("Promenade des Anglais", "WALK", "00:00", "24:00", 90, 0, None),
                    ("Castle Hill", "VIEWPOINT", "08:30", "20:00", 90, 0, None),
                    ("Musee Matisse", "MUSEUM", "10:00", "18:00", 90, 1100, "TUE"),
                    ("Cours Saleya Market", "MARKET", "06:00", "13:30", 75, 0, "MON"),
                    ("Monaco Day Trip", "TOUR", "08:00", "19:00", 480, 4500, None),
                    ("Eze Village", "HERITAGE", "09:00", "19:00", 180, 600, None),
                ],
            ),
        ],
        "links": [("Paris", "Nice", "TRAIN", 330, 6500)],
    },
    {
        "code": "GB",
        "name": "United Kingdom",
        "tz": "Europe/London",
        "level": 1.9,
        "cities": [
            (
                "London",
                "LHR",
                "Heathrow Airport",
                51.47,
                -0.45,
                600,
                ["Westminster", "Kensington", "Covent Garden"],
                [
                    ("Tower of London", "CASTLE", "09:00", "17:30", 180, 3500, None),
                    ("British Museum", "MUSEUM", "10:00", "17:00", 180, 0, None),
                    ("London Eye", "VIEWPOINT", "10:00", "20:30", 60, 3800, None),
                    (
                        "Buckingham Palace Changing of the Guard",
                        "PALACE",
                        "10:45",
                        "12:00",
                        60,
                        0,
                        None,
                    ),
                    ("Natural History Museum", "MUSEUM", "10:00", "17:50", 150, 0, None),
                    ("Warner Bros. Studio Tour", "TOUR", "09:00", "20:00", 300, 5600, None),
                    ("Westminster Abbey", "CHURCH", "09:30", "15:30", 90, 3000, "SUN"),
                    ("Thames River Cruise", "CRUISE", "10:00", "18:00", 60, 2000, None),
                ],
            ),
            (
                "Edinburgh",
                "EDI",
                "Edinburgh Airport",
                55.95,
                -3.37,
                780,
                ["Old Town", "New Town"],
                [
                    ("Edinburgh Castle", "CASTLE", "09:30", "17:00", 150, 2300, None),
                    ("Royal Mile", "HERITAGE", "00:00", "24:00", 90, 0, None),
                    ("Arthur's Seat", "NATURE", "06:00", "20:00", 150, 0, None),
                    ("National Museum of Scotland", "MUSEUM", "10:00", "17:00", 120, 0, None),
                    ("Holyrood Palace", "PALACE", "09:30", "16:30", 90, 2100, "TUE"),
                    ("Loch Ness Day Tour", "TOUR", "08:00", "20:00", 660, 6500, None),
                ],
            ),
        ],
        "links": [("London", "Edinburgh", "TRAIN", 270, 6800)],
    },
]

HOTEL_WORDS = [
    "Grand",
    "Harbour",
    "Garden",
    "Lotus",
    "Crown",
    "Royal",
    "Park",
    "Central",
    "Pearl",
    "Vista",
]
HOTEL_KINDS = ["Hotel", "Suites", "Residence", "Inn", "Resort"]
IMAGES = [
    "HOTEL-BUSINESS-1",
    "HOTEL-BUSINESS-2",
    "HOTEL-FAMILY-1",
    "HOTEL-LUXURY-1",
    "HOTEL-LUXURY-2",
    "HOTEL-TWIN-1",
    "HOTEL-TWIN-2",
]
ROOMS = [  # kind, name, max adults, max children, price factor
    ("SINGLE", "Single Room", 1, 0, 0.7),
    ("TWIN", "Twin Room", 2, 0, 1.0),
    ("DOUBLE", "Double Room", 2, 1, 1.1),
    ("FAMILY", "Family Room", 2, 2, 1.5),
]
AIRLINES = [("AirVeda", "AV"), ("SkyIndia", "SI"), ("Garuda Wings", "GW"), ("EuroStar Air", "EA")]


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def generate_world(start: date, end: date, seed: int = 11) -> dict[str, Any]:
    """Rows for every pack file, in the official schema."""
    rng = random.Random(seed)  # noqa: S311 - seeded synthetic data, not security
    days = _days(start, end)
    out: dict[str, Any] = {
        "destinations": {"countries": []},
        "airports": [],
        "flights": [],
        "hotels": [],
        "rooms": [],
        "availability": [],
        "transfers": [],
        "attractions": [],
    }
    flight_no = 0
    for country in WORLD:
        level, tz = country["level"], country["tz"]
        cities, links = [], []
        for city, code, airport, lat, lng, minutes, areas, sights in country["cities"]:
            cities.append({"name": city, "airports": [code]})
            out["airports"].append(
                {
                    "code": code,
                    "name": airport,
                    "city": city,
                    "country": country["code"],
                    "timezone": tz,
                    "lat": lat,
                    "lng": lng,
                    "serves_cities": [city],
                }
            )
            prefix = code
            # Airport transfers: a taxi to each area and one bus for the whole city.
            for area in areas:
                out["transfers"].append(
                    {
                        "transfer_id": f"TR-{code}-{area[:3].upper()}-TAXI",
                        "type": "AIRPORT_TAXI",
                        "name": f"{airport} taxi to {area}",
                        "airport": code,
                        "city": city,
                        "area": area,
                        "from_point": code,
                        "to_point": f"{area} area hotels",
                        "max_passengers": 4,
                        "service_from": "00:00",
                        "service_until": "24:00",
                        "duration_minutes": rng.randint(30, 70),
                        "pricing": "PER_VEHICLE",
                        "price": {
                            "amount": round(1800 * level / 10) * 10 + rng.randint(0, 40) * 10,
                            "currency": "INR",
                        },
                    }
                )
            out["transfers"].append(
                {
                    "transfer_id": f"TR-{code}-CITY-BUS",
                    "type": "AIRPORT_BUS",
                    "name": f"{airport} express bus to {city}",
                    "airport": code,
                    "city": city,
                    "area": None,
                    "from_point": code,
                    "to_point": f"{city} hotels",
                    "max_passengers": 99,
                    "service_from": "05:30",
                    "service_until": "23:30",
                    "duration_minutes": rng.randint(50, 90),
                    "pricing": "PER_PERSON",
                    "price": {"amount": round(450 * level), "currency": "INR"},
                    "child_price": {"amount": round(225 * level), "currency": "INR"},
                }
            )
            # Hotels: three per area (3, 4 and 5 stars), each with 2-3 room types.
            for a_i, area in enumerate(areas):
                for stars in (3, 4, 5):
                    h_id = f"HTL-{prefix}-{a_i}{stars}"
                    name = f"{rng.choice(HOTEL_WORDS)} {area} {rng.choice(HOTEL_KINDS)}"
                    out["hotels"].append(
                        {
                            "hotel_id": h_id,
                            "name": name,
                            "aliases": [],
                            "city": city,
                            "area": area,
                            "lat": round(lat + rng.uniform(-0.05, 0.05), 4),
                            "lng": round(lng + rng.uniform(-0.05, 0.05), 4),
                            "rating": round(rng.uniform(6.8, 9.5), 1),
                            "stars": stars,
                            "check_in_from": "14:00",
                            "check_out_until": "11:00",
                            "family_friendly": rng.random() < 0.7,
                            "image": f"images/hotels/{rng.choice(IMAGES)}.jpg",
                        }
                    )
                    kinds = rng.sample(ROOMS, 3) if stars > 3 else rng.sample(ROOMS, 2)
                    for r_i, (kind, room_name, adults, children, factor) in enumerate(kinds):
                        r_id = f"RM-{prefix}-{a_i}{stars}-{'ABC'[r_i]}"
                        price = (
                            round(
                                2200
                                * level
                                * (1 + (stars - 3) * 0.6)
                                * factor
                                * rng.uniform(0.9, 1.15)
                                / 10
                            )
                            * 10
                        )
                        out["rooms"].append(
                            {
                                "room_id": r_id,
                                "hotel_id": h_id,
                                "room_type": kind,
                                "name": room_name,
                                "max_adults": adults,
                                "max_children": children,
                                "price_per_night": {"amount": price, "currency": "INR"},
                                "refundable": rng.random() < 0.5,
                            }
                        )
                        top = rng.randint(4, 9)
                        for day in days:
                            out["availability"].append(
                                {
                                    "room_id": r_id,
                                    "date": day.isoformat(),
                                    "rooms_left": 0 if rng.random() < 0.04 else rng.randint(1, top),
                                }
                            )
            # Attractions.
            for s_i, (name, category, opens, closes, visit, price, closed_day) in enumerate(
                sights, start=1
            ):
                week = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                out["attractions"].append(
                    {
                        "attraction_id": f"ATT-{prefix}-{s_i:03d}",
                        "name": name,
                        "name_ja": None,
                        "city": city,
                        "category": category,
                        "lat": round(lat + rng.uniform(-0.08, 0.08), 4),
                        "lng": round(lng + rng.uniform(-0.08, 0.08), 4),
                        "open_days": [d for d in week if d != closed_day],
                        "open_from": opens,
                        "open_until": closes,
                        "aliases": [],
                        "visit_minutes": visit,
                        "child_friendly": category not in ("MUSEUM", "CHURCH"),
                        "accessible": category != "NATURE",
                        "price_per_person": {"amount": price, "currency": "INR"},
                        **(
                            {"child_price": {"amount": round(price * 0.5), "currency": "INR"}}
                            if price
                            else {}
                        ),
                        "image": None,
                    }
                )
            # Daily flights from each Indian city: an evening flight out, a morning flight home.
            for home in INDIA:
                airline, code2 = rng.choice(AIRLINES)
                base = round((9000 + minutes * 40) * max(level, 0.8))
                for day in days:
                    # Two flights each way a day: morning and evening.
                    for direction, dep_clock in (
                        ("out", (8, 15)),
                        ("out", (21, 30)),
                        ("home", (10, 15)),
                        ("home", (19, 40)),
                    ):
                        flight_no += 1
                        if direction == "out":
                            src, dst, src_tz, dst_tz = home, code, "Asia/Kolkata", tz
                        else:
                            src, dst, src_tz, dst_tz = code, home, tz, "Asia/Kolkata"
                        dep = datetime.combine(day, datetime.min.time()).replace(
                            hour=dep_clock[0], minute=dep_clock[1]
                        )
                        arr_utc = dep.replace(tzinfo=ZoneInfo(src_tz)) + timedelta(minutes=minutes)
                        arr = arr_utc.astimezone(ZoneInfo(dst_tz)).replace(tzinfo=None)
                        price = (
                            round(
                                base
                                * rng.uniform(0.85, 1.2)
                                * (1.1 if day.weekday() in (4, 6) else 1)
                                / 50
                            )
                            * 50
                        )
                        out["flights"].append(
                            {
                                "flight_id": f"FW-{flight_no:06d}",
                                "airline": airline,
                                "flight_number": f"{code2} {100 + flight_no % 900}",
                                "from": src,
                                "to": dst,
                                "departure_local": dep.isoformat(),
                                "arrival_local": arr.isoformat(),
                                "stops": 1 if minutes > 400 else 0,
                                "duration_minutes": minutes,
                                "price_per_seat": {"amount": price, "currency": "INR"},
                                "seats_left": rng.randint(2, 9),
                                "cabin": "ECONOMY",
                            }
                        )
        # City-to-city transfers, both directions.
        for a, b, kind, minutes_between, price in country["links"]:
            for x, y in ((a, b), (b, a)):
                t_id = f"TR-{x[:3].upper()}-{y[:3].upper()}-01"
                out["transfers"].append(
                    {
                        "transfer_id": t_id,
                        "type": kind,
                        "name": f"{kind.replace('_', ' ').title()} {x} to {y}",
                        "airport": None,
                        "city": None,
                        "area": None,
                        "from_city": x,
                        "to_city": y,
                        "from_point": f"{x} station",
                        "to_point": f"{y} station",
                        "max_passengers": 99,
                        "service_from": "06:00",
                        "service_until": "22:00",
                        "frequency_minutes": 60,
                        "duration_minutes": minutes_between,
                        "pricing": "PER_PERSON",
                        "price": {"amount": price, "currency": "INR"},
                        "child_price": {"amount": round(price * 0.5), "currency": "INR"},
                    }
                )
                links.append({"from_city": x, "to_city": y, "transfer_ids": [t_id]})
        out["destinations"]["countries"].append(
            {
                "code": country["code"],
                "name": country["name"],
                "timezone": tz,
                "cities": cities,
                "links": links,
            }
        )
    return out
