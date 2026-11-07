"""Feature flags.

Defaults live in `config/features.yaml`; an environment variable `FEATURE_<NAME>` overrides a
single flag. Flags are read once at start-up and exposed to the frontend via `/meta/features`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import yaml

from app.core.config import Settings

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class FeatureFlags:
    flags: Mapping[str, bool]

    def enabled(self, name: str) -> bool:
        return self.flags.get(name, False)

    def as_dict(self) -> dict[str, bool]:
        return dict(self.flags)


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"FEATURE_{name.upper()} must be a boolean, got {raw!r}")


def load_feature_flags(
    settings: Settings, environ: Mapping[str, str] | None = None
) -> FeatureFlags:
    env = os.environ if environ is None else environ
    path: Path = settings.config_dir / "features.yaml"
    defaults: dict[str, bool] = {}
    if path.exists():
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        defaults = {str(k): bool(v) for k, v in (document.get("features") or {}).items()}

    resolved = dict(defaults)
    for name in defaults:
        override = env.get(f"FEATURE_{name.upper()}")
        if override is not None:
            resolved[name] = _parse_bool(name, override)

    if settings.is_production and resolved.get("demo_login"):
        raise ValueError("The demo_login feature must be disabled in production")

    return FeatureFlags(MappingProxyType(resolved))
