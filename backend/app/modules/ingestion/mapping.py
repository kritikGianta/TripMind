"""Dataset mappings: how the columns of a supplied dataset become TripMind catalog fields.

One YAML file per dataset in `config/mappings/`. Swapping the demo data for the finale data means
writing a new mapping (the profiler drafts one) and importing the new ZIP; no code changes.

    dataset: synthetic-v1
    origin: synthetic                # provided | synthetic
    entities:
      airports:
        file: airports.csv           # glob, matched case-insensitively inside the ZIP
        fields:
          code: iata                 # shorthand for {column: iata}
          guest_rating: {column: rating, scale: 2}
          amenities: {column: amenities, split: "|"}
          departure_local: {column: departure, format: "%Y-%m-%d %H:%M"}
          currency: {value: INR}     # constant
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.errors import NotFound, ValidationFailed
from app.modules.ingestion.targets import TARGETS, EntityName

_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str | None = None
    value: Any = None
    default: Any = None
    format: str | None = None
    split: str | None = None
    scale: float | None = None
    map: dict[str, Any] | None = Field(default=None, description="Source value -> target value")

    @model_validator(mode="after")
    def _source(self) -> FieldSpec:
        if self.column is None and self.value is None:
            raise ValueError("a field needs either 'column' or 'value'")
        if self.column is not None and self.value is not None:
            raise ValueError("use 'column' or 'value', not both")
        return self


class EntityMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    format: Literal["auto", "csv", "tsv", "json", "jsonl", "xlsx"] = "auto"
    sheet: str | None = None
    json_path: str | None = Field(
        default=None, description="Key holding the records in a JSON object"
    )
    delimiter: str | None = None
    fields: dict[str, FieldSpec]

    @field_validator("fields", mode="before")
    @classmethod
    def _shorthand(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: ({"column": v} if isinstance(v, str) else v) for k, v in value.items()}
        return value


class DatasetMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    origin: Literal["provided", "synthetic"] = "provided"
    description: str | None = None
    entities: dict[EntityName, EntityMapping]

    @model_validator(mode="after")
    def _known_fields(self) -> DatasetMapping:
        problems: list[str] = []
        for entity_name, entity in self.entities.items():
            target = TARGETS[entity_name]
            for name in entity.fields:
                if target.get(name) is None:
                    problems.append(f"{entity_name}.{name} is not a known field")
            for required in (f.name for f in target.fields if f.required):
                if required not in entity.fields:
                    problems.append(f"{entity_name}.{required} is required but not mapped")
            for group in target.any_of:
                if not any(name in entity.fields for name in group):
                    problems.append(f"{entity_name} needs one of: {', '.join(group)}")
        if "room_types" in self.entities and "hotels" not in self.entities:
            problems.append("room_types can only be imported together with hotels")
        if problems:
            raise ValueError("; ".join(problems))
        return self


def mappings_dir(config_dir: Path) -> Path:
    return config_dir / "mappings"


def list_mappings(config_dir: Path) -> list[str]:
    directory = mappings_dir(config_dir)
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def parse_mapping(document: str, *, source: str = "mapping") -> DatasetMapping:
    try:
        data = yaml.safe_load(document)
        return DatasetMapping.model_validate(data)
    except yaml.YAMLError as exc:
        raise ValidationFailed(f"{source} is not valid YAML.", code="MAPPING_INVALID") from exc
    except ValidationError as exc:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
        ]
        raise ValidationFailed(
            f"{source} is not a valid dataset mapping.",
            code="MAPPING_INVALID",
            details={"fields": errors},
        ) from exc


def load_mapping(config_dir: Path, name: str) -> DatasetMapping:
    if not _NAME.match(name):
        raise NotFound("Unknown mapping.", code="MAPPING_NOT_FOUND")
    path = mappings_dir(config_dir) / f"{name}.yaml"
    if not path.is_file():
        raise NotFound(f"Mapping '{name}' does not exist.", code="MAPPING_NOT_FOUND")
    return parse_mapping(path.read_text(encoding="utf-8"), source=f"config/mappings/{name}.yaml")
