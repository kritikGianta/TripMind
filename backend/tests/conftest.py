"""Test fixtures.

API tests run the real Alembic migrations against a throwaway database, so the schema under test is
exactly what production gets. By default this is SQLite; set TEST_DATABASE_URL to run the same
suite against PostgreSQL (CI does both).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import FrozenClock
from app.core.config import Settings, get_settings
from app.core.deps import get_clock, get_rate_limiter, get_settings_dep
from app.core.rate_limit import InMemoryRateLimiter
from app.datagen.generator import GeneratorOptions, generate
from app.db.session import get_session
from app.main import create_app
from app.models import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_SECRET = "test-secret-that-is-long-enough-for-hs256-signing-0123456789"


@pytest.fixture(scope="session")
def database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"


@pytest.fixture(scope="session")
def settings(database_url: str, tmp_path_factory: pytest.TempPathFactory) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        jwt_secret=TEST_SECRET,  # type: ignore[arg-type]
        log_json=False,
        log_level="WARNING",
        background_jobs=False,
        # Empty on purpose: tests must not depend on which models have been trained locally.
        models_dir=tmp_path_factory.mktemp("no_models"),
    )


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    os.environ["DATABASE_URL"] = settings.database_url
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    eng = create_engine(settings.database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with factory() as session:
        yield session
    # Each test starts from empty tables (schema is kept). Children first, so FKs never block.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))  # noqa: S608 - names from metadata


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 11, 7, 9, 0, tzinfo=UTC))


@pytest.fixture
def limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


@pytest.fixture
def client(
    settings: Settings,
    engine: Engine,
    db_session: Session,
    clock: FrozenClock,
    limiter: InMemoryRateLimiter,
) -> Iterator[TestClient]:
    app = create_app(settings)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def _session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def demo_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small synthetic dataset: 3 travel days from 13 Nov 2026, a quarter of the hotels."""
    path = tmp_path_factory.mktemp("data") / "synthetic.zip"
    generate(path, GeneratorOptions(seed=11, start=date(2026, 11, 13), days=3, hotels_scale=0.25))
    return path


@pytest.fixture
def catalog(db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path) -> None:
    """The synthetic dataset imported through the real pipeline."""
    from app.core.request_context import RequestMeta
    from app.modules.ingestion.service import Actor, ImportService
    from app.modules.ingestion.sources import ZipSource

    source = ZipSource(
        demo_zip.read_bytes(), name="demo.zip", max_members=50, max_uncompressed_mb=200
    )
    ImportService(db_session, settings, clock).run_import(
        source,
        mapping_name="synthetic-v1",
        dry_run=False,
        actor=Actor(user_id=None, via="cli", meta=RequestMeta(None, None)),
    )
