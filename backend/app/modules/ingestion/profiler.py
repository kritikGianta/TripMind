"""Dataset profiler: describe every file and draft a mapping for an unseen dataset.

On finale day: profile the official ZIP, review the drafted YAML (every guess is commented with
its confidence), save it under config/mappings/, then import.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import yaml
from rapidfuzz import fuzz

from app.modules.ingestion.parsing import DATE_FORMATS, DATETIME_FORMATS, TIME_FORMATS
from app.modules.ingestion.rules import normalize_text
from app.modules.ingestion.sources import DatasetSource, Table, iter_tables
from app.modules.ingestion.targets import ENTITY_ORDER, TARGETS, TargetEntity

_SAMPLE = 500
_NUMBER = re.compile(r"^-?[\d,]*\.?\d+$")


def _infer_kind(values: pd.Series) -> tuple[str, str | None]:
    sample = values.dropna().astype(str).head(_SAMPLE)
    if sample.empty:
        return "empty", None
    if sample.str.match(_NUMBER).mean() > 0.95:
        numbers = pd.to_numeric(sample.str.replace(",", ""), errors="coerce")
        return ("integer" if (numbers.dropna() % 1 == 0).all() else "number"), None
    for kind, formats in (
        ("datetime", DATETIME_FORMATS),
        ("date", DATE_FORMATS),
        ("time", TIME_FORMATS),
    ):
        for fmt in formats:
            if pd.to_datetime(sample, format=fmt, errors="coerce").notna().mean() > 0.95:
                return kind, fmt
    if sample.str.lower().isin({"true", "false", "yes", "no", "y", "n", "0", "1"}).mean() > 0.95:
        return "boolean", None
    return "text", None


def profile_table(table: Table) -> dict[str, Any]:
    frame = table.frame
    columns = []
    for name in frame.columns:
        values = frame[name]
        kind, fmt = _infer_kind(values)
        non_null = int(values.notna().sum())
        hashable = values.dropna().map(lambda v: str(v))
        columns.append(
            {
                "name": name,
                "kind": kind,
                "format": fmt,
                "non_null": non_null,
                "null_pct": round(100 * (1 - non_null / len(frame)), 1) if len(frame) else 0.0,
                "distinct": int(hashable.nunique()),
                "samples": [str(v)[:60] for v in hashable.unique()[:3]],
            }
        )
    return {"file": table.name, "rows": len(frame), "encoding": table.encoding, "columns": columns}


def profile_source(source: DatasetSource) -> list[tuple[Table, dict[str, Any]]]:
    return [(table, profile_table(table)) for table in iter_tables(source)]


def _column_score(column: str, synonyms: tuple[str, ...]) -> int:
    norm = normalize_text(column).replace(" ", "_")
    if norm in synonyms:
        return 100
    return int(max((fuzz.ratio(norm, s) for s in synonyms), default=0))


def _match_columns(target: TargetEntity, profile: dict[str, Any]) -> dict[str, tuple[str, int]]:
    """Best source column per target field (each column used at most once)."""
    candidates = sorted(
        (
            (_column_score(col["name"], field.synonyms), field.name, col["name"])
            for field in target.fields
            for col in profile["columns"]
        ),
        reverse=True,
    )
    chosen: dict[str, tuple[str, int]] = {}
    used: set[str] = set()
    for score, field_name, column in candidates:
        if score < 85 or field_name in chosen or column in used:
            continue
        chosen[field_name] = (column, score)
        used.add(column)
    return chosen


def _entity_fit(target: TargetEntity, matches: dict[str, tuple[str, int]]) -> float:
    required = [f.name for f in target.fields if f.required]
    hit = sum(1 for name in required if name in matches)
    return hit / len(required) + 0.01 * len(matches)


def suggest_mapping(profiles: list[dict[str, Any]], dataset: str) -> str:
    """Draft a mapping YAML. Unsure choices are marked with comments for review."""
    entities: dict[str, Any] = {}
    notes: list[str] = []
    taken: set[str] = set()
    for entity in ENTITY_ORDER:
        target = TARGETS[entity]
        scored = []
        for profile in profiles:
            if profile["file"] in taken:
                continue
            matches = _match_columns(target, profile)
            scored.append((_entity_fit(target, matches), profile, matches))
        if not scored:
            continue
        fit, profile, matches = max(scored, key=lambda item: item[0])
        if fit < 1.0:  # not every required field found: skip rather than guess
            missing = [f.name for f in target.fields if f.required and f.name not in matches]
            notes.append(f"{entity}: no file has columns for {', '.join(missing)}")
            continue
        taken.add(profile["file"])
        kinds = {c["name"]: c for c in profile["columns"]}
        fields: dict[str, Any] = {}
        for name, (column, score) in matches.items():
            field = target.require(name)
            spec: dict[str, Any] = {"column": column}
            fmt = kinds[column].get("format")
            if field.kind in {"datetime", "date", "time"} and fmt:
                spec["format"] = fmt
            if field.kind == "list":
                spec["split"] = _guess_delimiter(kinds[column]["samples"])
            fields[name] = spec if len(spec) > 1 else column
            if score < 100:
                notes.append(f"{entity}.{name} <- '{column}' (similarity {score}, please check)")
        entities[entity] = {"file": profile["file"].split("/")[-1], "fields": fields}

    body = yaml.safe_dump(
        {"dataset": dataset, "origin": "provided", "entities": entities},
        sort_keys=False,
        allow_unicode=True,
    )
    header = [
        "# Draft mapping generated by the TripMind profiler. Review before importing.",
        "# Field names on the left are TripMind fields; values are your column names.",
    ] + [f"# - {n}" for n in notes]
    return "\n".join(header) + "\n" + body


def _guess_delimiter(samples: list[str]) -> str:
    joined = "".join(samples)
    for delimiter in ("|", ";", ","):
        if delimiter in joined:
            return delimiter
    return ","
