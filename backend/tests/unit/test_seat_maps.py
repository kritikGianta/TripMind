"""Seat maps derived from aircraft type, cabin and capacity."""

from __future__ import annotations

from pathlib import Path

from app.modules.bookings.extras import build_cabin, load_ancillary_rules

RULES = load_ancillary_rules(Path(__file__).resolve().parents[3] / "config").seat_maps


def test_narrowbody_economy() -> None:
    cabin = build_cabin(RULES, "Airbus A320neo", "economy", 186)
    seats = [s for row in cabin.rows for s in row]
    assert cabin.layout == "narrowbody" and cabin.groups == ["ABC", "DEF"]
    assert len(seats) == 186 and len(cabin.rows) == 31
    a, b, c = cabin.rows[9][:3]  # row 10
    assert (a.position, b.position, c.position) == ("window", "middle", "aisle")
    assert cabin.rows[0][0].zone == "front" and cabin.rows[0][1].price == RULES.prices.front
    exit_rows = {s.row for s in seats if s.zone == "extra_legroom"}
    assert exit_rows == {12, 13}
    assert cabin.seat("10B") is not None and cabin.seat("10B").price == 0  # type: ignore[union-attr]
    assert cabin.seat("32A") is None and cabin.seat("10G") is None


def test_widebody_and_turboprop_layouts() -> None:
    wide = build_cabin(RULES, "Boeing 787-9", "economy", 268)
    assert wide.groups == ["ABC", "DEF", "GHK"]
    assert sum(len(r) for r in wide.rows) == 268 and len(wide.rows[-1]) == 268 % 9
    business = build_cabin(RULES, "Boeing 787-9", "business", 28)
    assert business.groups == ["A", "DG", "K"]
    assert {s.zone for r in business.rows for s in r} == {"included"}
    assert {s.position for s in business.rows[0]} == {"window", "aisle"}
    turbo = build_cabin(RULES, "ATR 72-600", "economy", 70)
    assert turbo.layout == "turboprop" and turbo.groups == ["AC", "DF"]


def test_unknown_aircraft_falls_back_to_capacity() -> None:
    assert build_cabin(RULES, None, "economy", 300).layout == "widebody"
    assert build_cabin(RULES, "", "economy", 60).layout == "turboprop"
    assert build_cabin(RULES, "Mystery jet", "economy", 150).layout == "narrowbody"
    assert build_cabin(RULES, None, "economy", 0).rows == []
