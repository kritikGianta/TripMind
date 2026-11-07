"""Search over a real import of the synthetic dataset (3 travel days from 13 Nov 2026)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from app.core.deps import get_feature_flags
from app.core.features import FeatureFlags
from app.modules.search.pricing import Converter, LedgerLine, MoneyOut, PricingRules

API = "/api/v1"
DAY = "2026-11-13"


def city_id(client: TestClient, name: str) -> str:
    items = client.get(f"{API}/locations", params={"q": name, "kind": "city"}).json()["items"]
    return str(items[0]["value"])


def flights(client: TestClient, **params: Any) -> Any:
    query = {"origin": "DEL", "destination": "BOM", "departure_date": DAY, **params}
    return client.get(f"{API}/flights/search", params=query)


def display_total(offer: dict[str, Any]) -> int:
    return int(offer["price"]["display_total"]["amount_minor"])


# ── Locations ──────────────────────────────────────────────────────────────


def test_locations_match_codes_names_and_aliases(client: TestClient, catalog: None) -> None:
    airports = client.get(f"{API}/locations", params={"q": "del"}).json()["items"]
    assert airports[0]["code"] == "DEL"
    cities = client.get(f"{API}/locations", params={"q": "Bangalore", "kind": "city"}).json()
    assert cities["items"][0]["name"] == "Bengaluru"
    fuzzy = client.get(f"{API}/locations", params={"q": "Mumbia", "kind": "city"}).json()
    assert fuzzy["items"][0]["name"] == "Mumbai"


# ── Flights ────────────────────────────────────────────────────────────────


def test_flight_search_returns_priced_offers_with_honest_ledgers(
    client: TestClient, catalog: None
) -> None:
    response = flights(client, adults=2)
    assert response.status_code == 200, response.text
    body = response.json()
    offers = body["outbound"]["offers"]
    assert offers and body["inbound"] is None
    for offer in offers:
        assert offer["legs"][0]["origin"]["code"] == "DEL"
        assert offer["legs"][-1]["destination"]["code"] == "BOM"
        assert offer["legs"][0]["departure_local"].startswith(DAY)
    priced = next(o for o in offers if o["bookable"])
    fare_line, taxes = priced["price"]["lines"][0], priced["price"]["lines"][-1]
    assert "x 2 adults" in fare_line["label"]
    assert fare_line["amount"]["amount_minor"] == priced["legs"][0]["fare"]["amount_minor"] * 2
    assert taxes["kind"] == "taxes_and_fees" and taxes["amount"] is None
    assert priced["price"]["complete"] is False  # never presented as all-inclusive


def test_connections_are_legal(client: TestClient, catalog: None) -> None:
    body = flights(client, destination="GOI").json()
    connections = [o for o in body["outbound"]["offers"] if len(o["legs"]) == 2]
    assert connections, "expected at least one one-stop itinerary to Goa"
    for offer in connections:
        first, second = offer["legs"]
        assert first["destination"]["code"] == second["origin"]["code"]
        gap = (
            datetime.fromisoformat(second["departure_at"])
            - datetime.fromisoformat(first["arrival_at"])
        ).total_seconds() / 60
        assert 60 <= gap <= 360 and offer["layovers"][0]["minutes"] == int(gap)


def test_flight_filters_sort_and_facets(client: TestClient, catalog: None) -> None:
    everything = flights(client).json()["outbound"]
    stops = {f["value"]: f["count"] for f in everything["facets"]["stops"]}
    assert stops["0"] > 0

    direct = flights(client, max_stops=0, sort="cheapest").json()["outbound"]
    assert direct["total"] == stops["0"]
    prices = [display_total(o) for o in direct["offers"] if o["bookable"]]
    assert prices == sorted(prices)

    airline = everything["facets"]["airlines"][0]["value"]
    only = flights(client, airlines=[airline]).json()["outbound"]["offers"]
    assert only and all(leg["airline_code"] == airline for o in only for leg in o["legs"])

    mornings = flights(client, departure_windows=["morning"]).json()["outbound"]["offers"]
    assert all(6 <= int(o["legs"][0]["departure_local"][11:13]) < 12 for o in mornings)


def test_return_search_and_date_rules(client: TestClient, catalog: None) -> None:
    body = flights(client, return_date="2026-11-15").json()
    assert body["inbound"]["offers"][0]["legs"][0]["origin"]["code"] == "BOM"

    past = flights(client, departure_date="2026-11-01")
    assert past.status_code == 422 and past.json()["error"]["code"] == "DATE_IN_PAST"
    backwards = flights(client, return_date="2026-11-12")
    assert backwards.json()["error"]["code"] == "RETURN_BEFORE_DEPARTURE"

    outside = flights(client, departure_date="2026-12-20").json()
    assert outside["outbound"]["total"] == 0
    assert "13 Nov 2026 to 15 Nov 2026" in outside["notices"][0]

    unknown = flights(client, origin="XYZ")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "LOCATION_NOT_FOUND"


def test_search_respects_feature_flags(client: TestClient, catalog: None) -> None:
    client.app.dependency_overrides[get_feature_flags] = lambda: FeatureFlags(  # type: ignore[attr-defined]
        {"flight_search": False, "hotel_search": True}
    )
    response = flights(client)
    assert response.status_code == 404 and response.json()["error"]["code"] == "FEATURE_DISABLED"


# ── Hotels ─────────────────────────────────────────────────────────────────


def hotels(client: TestClient, city: str, **params: Any) -> Any:
    query = {"city": city, "check_in": "2026-11-20", "check_out": "2026-11-23", **params}
    return client.get(f"{API}/hotels/search", params=query)


def test_hotel_search_prices_the_whole_stay(client: TestClient, catalog: None) -> None:
    delhi = city_id(client, "Delhi")
    body = hotels(client, delhi, guests=3, sort="price").json()
    assert body["nights"] == 3 and body["results"]
    for result in body["results"]:
        room = result["cheapest_room"]
        assert room["fits_party"] and room["max_occupancy"] >= 3
        if room["nightly_rate"]:
            line = room["price"]["lines"][0]
            assert line["amount"]["amount_minor"] == room["nightly_rate"]["amount_minor"] * 3
    priced = [
        r["cheapest_room"]["nightly_rate"]["amount_minor"] for r in body["results"] if r["bookable"]
    ]
    assert priced == sorted(priced)


def test_hotel_filters(client: TestClient, catalog: None) -> None:
    delhi = city_id(client, "Delhi")
    everything = hotels(client, delhi).json()
    amenity = everything["facets"]["amenities"][-1]["value"]
    filtered = hotels(client, delhi, amenities=[amenity], stars=[4, 5]).json()["results"]
    assert all(amenity in r["amenities"] and int(r["star_rating"]) in (4, 5) for r in filtered)
    refundable = hotels(client, delhi, free_cancellation=True).json()["results"]
    assert all(r["cheapest_room"]["refundable"] for r in refundable)


def test_foreign_currency_is_converted_and_labelled(client: TestClient, catalog: None) -> None:
    result = hotels(client, city_id(client, "London")).json()["results"][0]
    price = result["cheapest_room"]["price"]
    assert price["total"]["currency"] == "GBP"
    assert price["display_total"]["currency"] == "INR" and price["converted"] is True
    assert "not live" in price["fx_note"]


def test_hotel_detail_and_stay_rules(client: TestClient, catalog: None) -> None:
    delhi = city_id(client, "Delhi")
    hotel_id = hotels(client, delhi).json()["results"][0]["id"]
    detail = client.get(
        f"{API}/hotels/{hotel_id}",
        params={"check_in": "2026-11-20", "check_out": "2026-11-22", "guests": 4},
    ).json()
    assert detail["stay"]["nights"] == 2 and detail["rooms"]
    assert all(
        r["fits_party"] == (r["max_occupancy"] >= 4)
        for r in detail["rooms"]
        if r["total_rooms"] >= 1
    )

    too_long = hotels(client, delhi, check_out="2026-12-30")
    assert too_long.json()["error"]["code"] == "STAY_TOO_LONG"
    missing = client.get(f"{API}/hotels/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


# ── Pricing unit ───────────────────────────────────────────────────────────


def test_mixed_currency_ledger_totals_in_display_currency() -> None:
    converter = Converter(
        PricingRules(display_currency="INR", fx_rates={"INR": Decimal(1), "AED": Decimal("22.7")})
    )
    ledger = converter.ledger(
        [
            LedgerLine(
                label="DXB-BOM", kind="fare", amount=MoneyOut(amount_minor=100000, currency="AED")
            ),
            LedgerLine(
                label="BOM-GOI", kind="fare", amount=MoneyOut(amount_minor=400000, currency="INR")
            ),
        ]
    )
    assert ledger.total is None  # no single supplier currency
    assert ledger.display_total == MoneyOut(amount_minor=2_270_000 + 400_000, currency="INR")
    assert ledger.converted and ledger.fx_note
