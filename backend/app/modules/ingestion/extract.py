"""Extract: read each mapped file, parse its columns into typed target fields, and quarantine rows
that are missing required values, unreadable or out of range.

Entity-specific rules (references, times, keys) run afterwards in `resolve.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.modules.ingestion.mapping import DatasetMapping, EntityMapping
from app.modules.ingestion.parsing import parse_column
from app.modules.ingestion.rejects import RejectCode, RejectLog
from app.modules.ingestion.sources import DatasetSource, SourceError, find_member, read_table
from app.modules.ingestion.targets import ENTITY_ORDER, TARGETS, EntityName, TargetEntity


@dataclass
class EntityFrame:
    entity: EntityName
    table: str
    raw: pd.DataFrame  # source rows as read, indexed by row number
    data: pd.DataFrame  # typed target fields for rows still accepted
    rows_read: int
    encoding: str | None = None

    def drop(
        self,
        rows: pd.Index | pd.Series,
        log: RejectLog,
        code: RejectCode,
        field: str | None,
        message: str,
    ) -> None:
        """Quarantine rows (by index label or boolean mask) and remove them from `data`."""
        if isinstance(rows, pd.Series):
            rows = rows[rows.fillna(False).astype(bool)].index
        rows = rows.intersection(self.data.index)
        if rows.empty:
            return
        log.reject(
            entity=self.entity,
            table=self.table,
            raw=self.raw,
            rows=rows,
            code=code,
            field=field,
            message=message,
        )
        self.data = self.data.drop(index=rows)


def _check_columns(
    entity: EntityName, mapping: EntityMapping, table_name: str, columns: list[str]
) -> None:
    available = set(columns)
    missing = sorted(
        spec.column
        for spec in mapping.fields.values()
        if spec.column is not None and spec.column not in available
    )
    if missing:
        raise SourceError(
            f"{table_name} ({entity}) has no column(s) {', '.join(missing)}.",
            code="MAPPING_COLUMN_MISSING",
            details={
                "entity": entity,
                "file": table_name,
                "missing": missing,
                "available": sorted(available),
            },
        )


def extract_entity(
    source: DatasetSource,
    entity: EntityName,
    mapping: EntityMapping,
    log: RejectLog,
) -> EntityFrame:
    target: TargetEntity = TARGETS[entity]
    member = find_member(source, mapping.file)
    if member is None:
        raise SourceError(
            f"No file matching '{mapping.file}' for {entity}.",
            code="MAPPING_FILE_MISSING",
            details={"entity": entity, "pattern": mapping.file, "files": source.members()},
        )
    table = read_table(
        source,
        member,
        fmt=mapping.format,
        delimiter=mapping.delimiter,
        sheet=mapping.sheet,
        json_path=mapping.json_path,
    )
    _check_columns(entity, mapping, member, list(table.frame.columns))

    raw = table.frame
    frame = EntityFrame(
        entity=entity,
        table=member,
        raw=raw,
        data=pd.DataFrame(index=raw.index),
        rows_read=len(raw),
        encoding=table.encoding,
    )

    for name, spec in mapping.fields.items():
        field = target.require(name)  # mapping validation guarantees the field exists
        column = (
            raw[spec.column] if spec.column else pd.Series(None, index=raw.index, dtype="object")
        )
        parsed = parse_column(column, spec, field.kind, field.max_length)
        if parsed.format_used and spec.format is None and parsed.values.notna().any():
            log.adjust("FORMAT_INFERRED", example=f"{entity}.{name}: {parsed.format_used}")
        frame.data[name] = parsed.values
        for suffix, values in parsed.extra.items():
            frame.data[f"{name}__{suffix}"] = values
        frame.drop(
            parsed.invalid,
            log,
            RejectCode.INVALID_VALUE,
            name,
            f"'{name}' could not be read as {field.kind}"
            + (f" ({field.max_length} characters max)" if field.max_length else ""),
        )

    # Fields not in the mapping exist as empty columns, so later stages can rely on them.
    for field in target.fields:
        if field.name not in frame.data:
            frame.data[field.name] = pd.Series(None, index=frame.data.index, dtype="object")

    for field in target.fields:
        values = frame.data[field.name]
        if field.required:
            frame.drop(
                values.isna(),
                log,
                RejectCode.MISSING_REQUIRED,
                field.name,
                f"'{field.name}' is required",
            )
            values = frame.data[field.name]
        if field.min_value is not None or field.max_value is not None:
            numeric = pd.to_numeric(values, errors="coerce")
            never = pd.Series(False, index=numeric.index)
            low = numeric.lt(field.min_value) if field.min_value is not None else never
            high = numeric.gt(field.max_value) if field.max_value is not None else never
            frame.drop(
                low | high,
                log,
                RejectCode.OUT_OF_RANGE,
                field.name,
                f"'{field.name}' must be between {field.min_value} and {field.max_value}",
            )

    for group in target.any_of:
        present = frame.data[list(group)].notna().any(axis=1)
        frame.drop(
            ~present,
            log,
            RejectCode.MISSING_REQUIRED,
            "|".join(group),
            f"one of {', '.join(group)} is required",
        )
    return frame


def extract(
    source: DatasetSource, mapping: DatasetMapping, log: RejectLog
) -> dict[EntityName, EntityFrame]:
    return {
        entity: extract_entity(source, entity, mapping.entities[entity], log)
        for entity in ENTITY_ORDER
        if entity in mapping.entities
    }
