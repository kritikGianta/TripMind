"""Column parsers. Each turns a column of raw source values into typed values, vectorised.

A parser never guesses silently: a value that is present but unreadable is reported in
`invalid`, and the row is quarantined with INVALID_VALUE.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pandas as pd

from app.core.money import parse_amount
from app.modules.ingestion.mapping import FieldSpec
from app.modules.ingestion.targets import FieldKind

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
)
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%b %d, %Y",
    "%d.%m.%Y",
)
TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%H.%M")

_TZ_SUFFIX = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$")
_DURATION = re.compile(
    r"^\s*(?:PT)?\s*(?:(?P<h>\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours|H))?\s*"
    r"(?:(?P<m>\d+)\s*(?:m|min|mins|minute|minutes|M))?\s*$"
)
_HHMM = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})$")
_TRUE = {"1", "true", "t", "yes", "y"}
_FALSE = {"0", "false", "f", "no", "n"}


@dataclass
class Parsed:
    values: pd.Series
    invalid: pd.Series  # True where a value was present but could not be read
    format_used: str | None = None
    extra: dict[str, pd.Series] = field(default_factory=dict)


def is_missing(value: Any) -> bool:
    """None, NaN, NA and NaT all mean "no value" (pandas 3 uses NaN for missing strings)."""
    if value is None or isinstance(value, list):
        return value is None
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _present(raw: pd.Series) -> pd.Series:
    return raw.notna()


def _as_text(raw: pd.Series) -> pd.Series:
    return raw.map(lambda v: None if is_missing(v) else str(v)).astype("object")


def _apply_map(raw: pd.Series, mapping: dict[str, Any] | None) -> pd.Series:
    if not mapping:
        return raw
    lookup = {str(k).strip().lower(): v for k, v in mapping.items()}
    return raw.map(lambda v: None if is_missing(v) else lookup.get(str(v).strip().lower(), v))


def _best_format(text: pd.Series, formats: tuple[str, ...]) -> str | None:
    sample = text.dropna().head(500)
    if sample.empty:
        return formats[0]
    best, best_hits = None, 0
    for fmt in formats:
        hits = int(pd.to_datetime(sample, format=fmt, errors="coerce").notna().sum())
        if hits > best_hits:
            best, best_hits = fmt, hits
            if hits == len(sample):
                break
    return best


def parse_str(raw: pd.Series, spec: FieldSpec, max_length: int | None) -> Parsed:
    text = _as_text(raw)
    invalid = pd.Series(False, index=raw.index)
    if max_length:
        invalid = text.str.len().gt(max_length).fillna(False).astype(bool)
    return Parsed(text.where(~invalid, None), invalid)


def parse_code(raw: pd.Series, spec: FieldSpec, max_length: int | None) -> Parsed:
    parsed = parse_str(raw, spec, max_length)
    parsed.values = parsed.values.map(
        lambda v: None if is_missing(v) else re.sub(r"\s+", "", v).upper()
    )
    return parsed


def parse_float(raw: pd.Series, spec: FieldSpec) -> Parsed:
    text = _as_text(raw).str.replace(",", "", regex=False)
    values = pd.to_numeric(text, errors="coerce")
    invalid = _present(raw) & values.isna()
    if spec.scale is not None:
        values = values * spec.scale
    return Parsed(values.astype("Float64"), invalid)


def parse_int(raw: pd.Series, spec: FieldSpec) -> Parsed:
    parsed = parse_float(raw, spec)
    numbers = parsed.values
    fractional = numbers.notna() & (numbers.round() != numbers)
    invalid = parsed.invalid | fractional.fillna(False).astype(bool)
    values = numbers.where(~invalid).round().astype("Int64")
    return Parsed(values, invalid)


def parse_money(raw: pd.Series, spec: FieldSpec) -> Parsed:
    def one(value: object) -> Decimal | None:
        amount = parse_amount(value)
        if amount is not None and spec.scale is not None:
            amount = amount * Decimal(str(spec.scale))
        return amount

    values = raw.map(one)
    invalid = _present(raw) & values.isna()
    return Parsed(values.astype("object"), invalid)


def parse_datetime(raw: pd.Series, spec: FieldSpec) -> Parsed:
    text = _as_text(raw)
    # Values with an explicit UTC offset are absolute instants; keep them separately.
    has_offset = text.str.contains(_TZ_SUFFIX, na=False)
    aware = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")
    if has_offset.any():
        aware = pd.to_datetime(text.where(has_offset), errors="coerce", utc=True, format="ISO8601")
    fmt = spec.format or _best_format(text.where(~has_offset), DATETIME_FORMATS)
    naive = pd.to_datetime(text.where(~has_offset), format=fmt, errors="coerce")
    invalid = _present(raw) & naive.isna() & aware.isna()
    return Parsed(naive, invalid, format_used=fmt, extra={"utc": aware})


def parse_date(raw: pd.Series, spec: FieldSpec) -> Parsed:
    text = _as_text(raw)
    fmt = spec.format or _best_format(text, DATE_FORMATS)
    values = pd.to_datetime(text, format=fmt, errors="coerce").dt.normalize()
    return Parsed(values, _present(raw) & values.isna(), format_used=fmt)


def parse_time(raw: pd.Series, spec: FieldSpec) -> Parsed:
    """Time of day as a Timedelta since midnight."""
    text = _as_text(raw)
    fmt = spec.format or _best_format(text, TIME_FORMATS)
    stamps = pd.to_datetime(text, format=fmt, errors="coerce")
    values = stamps - stamps.dt.normalize()
    return Parsed(values, _present(raw) & values.isna(), format_used=fmt)


def _duration_minutes(value: object) -> float | None:
    if is_missing(value):
        return None
    text = str(value).strip()
    try:
        return float(text)  # bare numbers are minutes
    except ValueError:
        pass
    clock = _HHMM.match(text)
    if clock:
        return int(clock["h"]) * 60 + int(clock["m"])
    match = _DURATION.match(text)
    if not match or not (match["h"] or match["m"]):
        return None
    return float(match["h"] or 0) * 60 + int(match["m"] or 0)


def parse_duration(raw: pd.Series, spec: FieldSpec) -> Parsed:
    minutes = pd.to_numeric(raw.map(_duration_minutes), errors="coerce")
    if spec.scale is not None:
        minutes = minutes * spec.scale
    invalid = _present(raw) & minutes.isna()
    return Parsed(minutes.round().astype("Int64"), invalid)


def parse_bool(raw: pd.Series, spec: FieldSpec) -> Parsed:
    def one(value: object) -> bool | None:
        if is_missing(value):
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        return None

    values = raw.map(one)
    return Parsed(values.astype("boolean"), _present(raw) & values.isna())


def parse_list(raw: pd.Series, spec: FieldSpec) -> Parsed:
    delimiter = spec.split or ","

    def one(value: object) -> list[str] | None:
        if is_missing(value):
            return None
        items = value if isinstance(value, list) else str(value).split(delimiter)
        cleaned = [str(i).strip() for i in items if str(i).strip()]
        return cleaned or None

    return Parsed(raw.map(one), pd.Series(False, index=raw.index))


_PARSERS: dict[FieldKind, Callable[[pd.Series, FieldSpec], Parsed]] = {
    "int": parse_int,
    "float": parse_float,
    "money": parse_money,
    "datetime": parse_datetime,
    "date": parse_date,
    "time": parse_time,
    "duration": parse_duration,
    "bool": parse_bool,
    "list": parse_list,
}


def parse_column(
    raw: pd.Series, spec: FieldSpec, kind: FieldKind, max_length: int | None = None
) -> Parsed:
    if spec.value is not None:
        raw = pd.Series([spec.value] * len(raw), index=raw.index, dtype="object")
    raw = _apply_map(raw, spec.map)
    if kind == "str":
        parsed = parse_str(raw, spec, max_length)
    elif kind == "code":
        parsed = parse_code(raw, spec, max_length)
    else:
        parsed = _PARSERS[kind](raw, spec)
    if spec.default is not None:
        default = parse_column(
            pd.Series([spec.default], dtype="object"),
            FieldSpec(value=spec.default, format=spec.format),
            kind,
            max_length,
        ).values.iloc[0]
        missing = parsed.values.isna() & ~parsed.invalid
        if missing.any():
            parsed.values = parsed.values.astype("object").where(~missing, default)
    return parsed
