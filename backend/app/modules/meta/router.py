"""Health, readiness and feature flags.

Readiness checks only what the API needs to serve traffic: a reachable database whose schema is at
the latest migration. Dataset state is deliberately excluded (plan v2, G2), so the stack can start
before any data is imported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import Settings
from app.core.deps import get_feature_flags, get_kv_store, get_settings_dep
from app.core.features import FeatureFlags
from app.core.kv import KeyValueStore
from app.db.session import get_session

router = APIRouter(tags=["meta"])

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _migration_head() -> str | None:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessCheck(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class ReadinessOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: list[ReadinessCheck]


class FeaturesOut(BaseModel):
    features: dict[str, bool]


@router.get("/health", response_model=HealthOut, summary="Liveness: the process is serving")
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessOut,
    responses={503: {"model": ReadinessOut}},
    summary="Readiness: database reachable and schema migrated",
)
def ready(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    store: KeyValueStore = Depends(get_kv_store),
) -> JSONResponse:
    checks: list[ReadinessCheck] = []
    try:
        session.execute(text("SELECT 1"))
        checks.append(ReadinessCheck(name="database", ok=True))
        current = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        head = _migration_head()
        checks.append(
            ReadinessCheck(
                name="migrations",
                ok=current == head,
                detail=None if current == head else f"at {current}, expected {head}",
            )
        )
    except SQLAlchemyError as exc:
        checks.append(ReadinessCheck(name="database", ok=False, detail=type(exc).__name__))

    ok = all(c.ok for c in checks)
    if settings.redis_url:
        # Reported, but not required: without Redis the API keeps serving (no shared cache or
        # shared rate limits), so an outage must not take every replica out of rotation.
        reachable = store.ping()
        checks.append(
            ReadinessCheck(
                name="redis",
                ok=reachable,
                detail=None if reachable else "degraded: shared state off",
            )
        )
    body = ReadinessOut(status="ready" if ok else "not_ready", checks=checks)
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())


@router.get("/meta/features", response_model=FeaturesOut, summary="Enabled feature flags")
def features(flags: FeatureFlags = Depends(get_feature_flags)) -> FeaturesOut:
    return FeaturesOut(features=flags.as_dict())
