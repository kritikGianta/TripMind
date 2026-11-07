"""Quarantine bookkeeping: why a row was rejected, and which normalisations were applied."""

from __future__ import annotations

import enum
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class RejectCode(enum.StrEnum):
    MISSING_REQUIRED = "MISSING_REQUIRED"  # a required value is empty
    INVALID_VALUE = "INVALID_VALUE"  # cannot be read as the expected type or format
    OUT_OF_RANGE = "OUT_OF_RANGE"  # readable but outside the allowed range
    DUPLICATE_KEY = "DUPLICATE_KEY"  # same identity as an earlier row in the same file
    UNKNOWN_REFERENCE = "UNKNOWN_REFERENCE"  # refers to an airport or hotel that does not exist
    INCONSISTENT = "INCONSISTENT"  # fields contradict each other (arrives before it departs)


@dataclass(frozen=True)
class Reject:
    entity: str
    source_file: str
    row_number: int
    code: RejectCode
    field: str | None
    message: str
    raw: dict[str, Any] | None


@dataclass
class RejectLog:
    """Collects rejects and adjustments for one import."""

    rejects: list[Reject] = field(default_factory=list)
    adjustments: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=dict)

    def reject(
        self,
        *,
        entity: str,
        table: str,
        raw: pd.DataFrame,
        rows: pd.Index,
        code: RejectCode,
        field: str | None,
        message: str,
    ) -> None:
        for row in rows:
            record = raw.loc[row].to_dict() if row in raw.index else None
            self.rejects.append(
                Reject(
                    entity=entity,
                    source_file=table,
                    row_number=int(row),
                    code=code,
                    field=field,
                    message=message[:300],
                    raw=_jsonable(record),
                )
            )

    def adjust(self, code: str, count: int = 1, example: str | None = None) -> None:
        if count <= 0:
            return
        self.adjustments[code] += count
        if example is not None:
            bucket = self.examples.setdefault(code, [])
            if len(bucket) < 10:
                bucket.append(example)

    def counts_for(self, entity: str) -> int:
        return sum(1 for r in self.rejects if r.entity == entity)

    def summary(self) -> dict[str, dict[str, int]]:
        result: dict[str, Counter[str]] = {}
        for r in self.rejects:
            result.setdefault(r.entity, Counter())[r.code] += 1
        return {entity: dict(codes) for entity, codes in result.items()}


def _jsonable(record: dict[Any, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    clean: dict[str, Any] = {}
    for key, value in record.items():
        if value is None or isinstance(value, str | int | float | bool | list):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    return clean
