"""Flight schedules: rows that describe a repeating flight become dated flights.

A schedule row says "SF 238 DEL-GOI departs 06:05 on these weekdays between these dates" instead
of listing every date. Supported operating-day notations (case-insensitive):

    daily | weekdays | weekends | 1234567 (ISO, Monday = 1) | 135 | Mon,Wed,Fri | Mon-Fri
    x67 (every day except Saturday and Sunday; airline notation)

Expansion starts at the later of the schedule's first day and today, stops at its last day, and
never goes further than `schedule_horizon_days` ahead (rules.yaml). Every generated flight keeps
a link to its source row, so a problem is reported once against the line in the file.
"""

from __future__ import annotations

import re
from collections.abc import Hashable
from datetime import date, timedelta
from typing import Any

import pandas as pd

from app.modules.ingestion.extract import EntityFrame
from app.modules.ingestion.rejects import RejectCode, RejectLog

_NAMES = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7}


def parse_operating_days(value: object) -> frozenset[int] | None:
    """ISO weekdays (1 = Monday) the flight operates, or None if the text is not understood."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return frozenset(range(1, 8))  # no column value: every day
    text = str(value).strip().lower()
    if text in {"daily", "everyday", "every day", "all", "1234567"}:
        return frozenset(range(1, 8))
    if text == "weekdays":
        return frozenset(range(1, 6))
    if text == "weekends":
        return frozenset({6, 7})
    if re.fullmatch(r"x[1-7]+", text):
        return frozenset(range(1, 8)) - {int(c) for c in text[1:]}
    if re.fullmatch(r"[1-7]+", text):
        return frozenset(int(c) for c in text)
    if m := re.fullmatch(r"([a-z]{3})[a-z]*\s*-\s*([a-z]{3})[a-z]*", text):
        start, end = _NAMES.get(m.group(1)), _NAMES.get(m.group(2))
        if start and end and start <= end:
            return frozenset(range(start, end + 1))
        return None
    parts = [p[:3] for p in re.split(r"[\s,/;]+", text) if p]
    if parts and all(p in _NAMES for p in parts):
        return frozenset(_NAMES[p] for p in parts)
    return None


def expand_schedules(frame: EntityFrame, log: RejectLog, *, today: date, horizon_days: int) -> int:
    """Replace schedule rows in `frame.data` with one row per operating date. Returns how many
    flights were generated."""
    data = frame.data
    if "valid_from" not in data or not data["valid_from"].notna().any():
        return 0
    scheduled = data[data["valid_from"].notna()]
    dated = data[data["valid_from"].isna()]

    days = scheduled["operating_days"].map(parse_operating_days)
    frame.drop(
        days[days.isna()].index,
        log,
        RejectCode.INVALID_VALUE,
        "operating_days",
        "operating days not understood (use daily, 1234567, Mon,Wed,Fri, x67 ...)",
    )
    scheduled = scheduled.loc[scheduled.index.intersection(frame.data.index)]
    ends = pd.to_datetime(scheduled["valid_to"])
    starts = pd.to_datetime(scheduled["valid_from"])
    backwards = ends.notna() & (ends < starts)
    frame.drop(
        backwards[backwards].index,
        log,
        RejectCode.INCONSISTENT,
        "valid_to",
        "the schedule ends before it starts",
    )
    scheduled = scheduled.loc[scheduled.index.intersection(frame.data.index)]

    horizon_end = today + timedelta(days=horizon_days)
    operating_by_row: dict[Hashable, frozenset[int]] = days.to_dict()
    pieces: list[dict[Hashable, Any]] = []
    sources: list[int] = []
    for source_row, row in scheduled.iterrows():
        operating: frozenset[int] = operating_by_row[source_row]
        first = max(pd.Timestamp(row["valid_from"]).date(), today)
        last = pd.Timestamp(row["valid_to"]).date() if pd.notna(row["valid_to"]) else horizon_end
        day = first
        while day <= min(last, horizon_end):
            if day.isoweekday() in operating:
                piece = row.to_dict()
                piece["departure_date"] = pd.Timestamp(day)
                pieces.append(piece)
                sources.append(int(str(source_row)))
            day += timedelta(days=1)
    if not pieces and scheduled.empty:
        return 0

    # Generated rows get new index labels above the file's row numbers; row_map points each one
    # back to the line it came from, so rejects and counts stay per source row.
    start = int(max(frame.raw.index.max(), data.index.max())) + 1
    expanded = pd.DataFrame(pieces, index=pd.RangeIndex(start, start + len(pieces)))
    for label, source in zip(expanded.index, sources, strict=True):
        frame.row_map[int(label)] = source
    frame.data = pd.concat([dated, expanded]) if len(dated) else expanded
    log.adjust(
        "SCHEDULE_EXPANDED",
        len(pieces),
        example=f"{len(scheduled)} schedule rows -> {len(pieces)} dated flights",
    )
    return len(pieces)
