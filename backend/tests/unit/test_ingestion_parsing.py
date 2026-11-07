from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ValidationFailed
from app.core.money import from_minor_units, parse_amount, to_minor_units
from app.modules.ingestion.mapping import FieldSpec, parse_mapping
from app.modules.ingestion.parsing import is_missing, parse_column
from app.modules.ingestion.rules import Vocabulary, normalize_text


def col(*values: object) -> pd.Series:
    return pd.Series(list(values), dtype="object")


# ── Money ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "currency", "minor"),
    [
        ("4,999.50", "INR", 499950),
        ("₹ 4999", "INR", 499900),
        ("0.285", "USD", 29),  # half-up, no binary float error
        ("1500", "JPY", 1500),  # zero-decimal currency
        ("12.3456", "KWD", 12346),  # three-decimal currency
    ],
)
def test_money_is_stored_in_exact_minor_units(raw: str, currency: str, minor: int) -> None:
    amount = parse_amount(raw)
    assert amount is not None
    assert to_minor_units(amount, currency) == minor


def test_minor_units_round_trip() -> None:
    assert from_minor_units(499950, "INR") == Decimal("4999.50")
    assert parse_amount("on request") is None
    assert parse_amount(float("nan")) is None


# ── Column parsers ─────────────────────────────────────────────────────────


def test_missing_values_are_never_stringified() -> None:
    for value in (None, np.nan, pd.NA, pd.NaT, float("nan")):
        assert is_missing(value)
    parsed = parse_column(col("DEL", np.nan, None), FieldSpec(column="x"), "code")
    assert parsed.values.iloc[0] == "DEL"
    assert parsed.values.iloc[1:].isna().all()  # not the string "NAN"
    assert not parsed.invalid.any()


def test_datetime_format_is_inferred_and_bad_values_are_flagged() -> None:
    parsed = parse_column(
        col("13/11/2026 06:05", "14/11/2026 23:40", "31/02/2026 10:00", None),
        FieldSpec(column="x"),
        "datetime",
    )
    assert parsed.format_used == "%d/%m/%Y %H:%M"
    assert parsed.values.iloc[0] == pd.Timestamp("2026-11-13 06:05")
    assert parsed.invalid.tolist() == [False, False, True, False]


def test_datetime_with_offset_is_kept_as_an_instant() -> None:
    parsed = parse_column(col("2026-11-13T06:05:00+05:30"), FieldSpec(column="x"), "datetime")
    assert parsed.extra["utc"].iloc[0] == pd.Timestamp("2026-11-13 00:35", tz="UTC")
    assert not parsed.invalid.any()


@pytest.mark.parametrize(
    ("raw", "minutes"),
    [("2h 50m", 170), ("PT2H50M", 170), ("02:50", 170), ("170", 170), ("45m", 45), ("3h", 180)],
)
def test_duration_formats(raw: str, minutes: int) -> None:
    parsed = parse_column(col(raw), FieldSpec(column="x"), "duration")
    assert int(parsed.values.iloc[0]) == minutes


def test_numbers_scale_map_default_and_invalid() -> None:
    rating = parse_column(col("4.5", "x"), FieldSpec(column="r", scale=2), "float")
    assert float(rating.values.iloc[0]) == 9.0
    assert rating.invalid.tolist() == [False, True]

    stops = parse_column(
        col("non-stop", "1 stop"), FieldSpec(column="s", map={"non-stop": 0, "1 stop": 1}), "int"
    )
    assert stops.values.tolist() == [0, 1]

    seats = parse_column(col(None, "2.5"), FieldSpec(column="s", default=180), "int")
    assert seats.values.iloc[0] == 180
    assert seats.invalid.tolist() == [False, True]  # fractional seats are not silently rounded


def test_lists_booleans_and_times() -> None:
    amenities = parse_column(
        col("Free WiFi| Pool |", None), FieldSpec(column="a", split="|"), "list"
    )
    assert amenities.values.iloc[0] == ["Free WiFi", "Pool"]
    refundable = parse_column(col("Y", "no", "maybe"), FieldSpec(column="r"), "bool")
    assert refundable.values.tolist()[:2] == [True, False]
    assert refundable.invalid.tolist() == [False, False, True]
    check_in = parse_column(col("2:30 PM"), FieldSpec(column="c"), "time")
    assert check_in.values.iloc[0] == pd.Timedelta(hours=14, minutes=30)


def test_code_max_length_is_enforced() -> None:
    parsed = parse_column(col("toolongcode"), FieldSpec(column="c"), "code", max_length=8)
    assert parsed.invalid.tolist() == [True]


# ── Mapping and vocabulary ─────────────────────────────────────────────────


def test_mapping_shorthand_and_validation() -> None:
    mapping = parse_mapping(
        "dataset: d\nentities:\n  airports:\n    file: a.csv\n"
        "    fields: {code: iata, name: n, city: c}\n"
    )
    assert mapping.entities["airports"].fields["code"].column == "iata"

    with pytest.raises(ValidationFailed) as error:
        parse_mapping(
            "dataset: d\nentities:\n  airports:\n    file: a.csv\n"
            "    fields: {code: iata, name: n, colour: c}\n"
        )
    messages = str(error.value.details)
    assert "colour is not a known field" in messages
    assert "city is required" in messages


def test_room_types_need_hotels_in_the_same_mapping() -> None:
    with pytest.raises(ValidationFailed):
        parse_mapping(
            "dataset: d\nentities:\n  room_types:\n    file: r.csv\n"
            "    fields: {hotel_key: h, name: n}\n"
        )


def test_vocabulary_matching_ignores_case_accents_and_punctuation() -> None:
    vocabulary = Vocabulary(
        amenities={"wifi": ["free wi-fi"]}, city_aliases={"Bengaluru": ["Bangalore"]}
    )
    assert vocabulary.amenity_index()[normalize_text("FREE Wi-Fi!")] == "wifi"
    assert vocabulary.city_alias_index()["bangalore"] == "bengaluru"
    assert normalize_text("São  Paulo") == "sao paulo"
