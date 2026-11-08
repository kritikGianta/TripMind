"""Flight schedules: repeating schedule rows import as the same dated flights."""

from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.core.config import Settings
from app.core.request_context import RequestMeta
from app.datagen.generator import GeneratorOptions, generate
from app.models import Flight, ImportReject
from app.modules.ingestion.schedules import parse_operating_days
from app.modules.ingestion.service import Actor, ImportService
from app.modules.ingestion.sources import DirectorySource, ZipSource

ACTOR = Actor(user_id=None, via="cli", meta=RequestMeta(None, None))


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("daily", {1, 2, 3, 4, 5, 6, 7}),
        ("135", {1, 3, 5}),
        ("x67", {1, 2, 3, 4, 5}),
        ("Mon, Wed, Fri", {1, 3, 5}),
        ("Monday-Thursday", {1, 2, 3, 4}),
        ("weekends", {6, 7}),
        (None, {1, 2, 3, 4, 5, 6, 7}),
    ],
)
def test_operating_day_notations(text: str | None, days: set[int]) -> None:
    assert parse_operating_days(text) == frozenset(days)


def test_unknown_notation_is_rejected() -> None:
    assert parse_operating_days("every other tuesday") is None
    assert parse_operating_days("8") is None


def _import(
    session: Session, settings: Settings, clock: FrozenClock, path: Path, mapping: str
) -> None:
    source = ZipSource(path.read_bytes(), name=path.name, max_members=50, max_uncompressed_mb=200)
    run = ImportService(session, settings, clock).run_import(
        source, mapping_name=mapping, dry_run=False, actor=ACTOR
    )
    assert run.status == "published", run.error


def test_schedules_import_as_the_same_dated_flights(
    db_session: Session, settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    options = dict(seed=5, start=date(2026, 11, 13), days=4, hotels_scale=0.2, dirty_rate=0.0)
    generate(tmp_path / "dated.zip", GeneratorOptions(**options))
    generate(tmp_path / "schedules.zip", GeneratorOptions(**options, flight_format="schedules"))

    _import(db_session, settings, clock, tmp_path / "dated.zip", "synthetic-v1")
    dated = {
        (f.flight_number, f.departure_local, f.cabin_class, f.fare_minor is not None)
        for f in db_session.scalars(select(Flight).where(Flight.is_active.is_(True)))
    }
    _import(db_session, settings, clock, tmp_path / "schedules.zip", "synthetic-schedules")
    db_session.expire_all()
    expanded = {
        (f.flight_number, f.departure_local, f.cabin_class, f.fare_minor is not None)
        for f in db_session.scalars(select(Flight).where(Flight.is_active.is_(True)))
    }
    assert expanded == dated and len(expanded) > 100


def test_expanded_flights_are_searchable(
    client: TestClient, db_session: Session, settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    generate(
        tmp_path / "s.zip",
        GeneratorOptions(
            seed=5, start=date(2026, 11, 13), days=3, hotels_scale=0.2, flight_format="schedules"
        ),
    )
    _import(db_session, settings, clock, tmp_path / "s.zip", "synthetic-schedules")
    offers = client.get(
        "/api/v1/flights/search",
        params={"origin": "DEL", "destination": "BOM", "departure_date": "2026-11-14"},
    ).json()
    assert offers["outbound"]["offers"]


def test_bad_schedule_row_is_reported_once(
    db_session: Session, settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "airports.csv").write_text(
        "iata,airport_name,city,country,lat,lon,tz\n"
        "DEL,Indira Gandhi International Airport,Delhi,IN,28.55,77.10,Asia/Kolkata\n"
        "BOM,Chhatrapati Shivaji Maharaj International Airport,Mumbai,IN,19.09,72.87,Asia/Kolkata\n"
    )
    (data / "flight_schedules.csv").write_text(
        "airline,airline_code,flight_no,from,to,dep,arr,duration,days,valid_from,valid_to,cabin,"
        "fare,currency,aircraft,seats\n"
        "Test Air,TA,TA 1,DEL,BOM,06:00,08:10,2h 10m,daily,2026-11-13,2026-11-19,Economy,"
        "4000,INR,A320,180\n"
        "Test Air,TA,TA 2,DEL,BOM,09:00,11:10,2h 10m,sometimes,2026-11-13,2026-11-19,Economy,"
        "4000,INR,A320,180\n"
        "Test Air,TA,TA 3,DEL,XYZ,10:00,12:10,2h 10m,daily,2026-11-13,2026-11-19,Economy,"
        "4000,INR,A320,180\n"
    )
    generate(tmp_path / "h.zip", GeneratorOptions(days=1, hotels_scale=0.1, dirty_rate=0))
    with zipfile.ZipFile(tmp_path / "h.zip") as archive:
        for name in ("hotels.csv", "rooms.csv"):
            (data / name).write_bytes(archive.read(name))
    config = tmp_path / "config"
    shutil.copytree(settings.config_dir, config)
    rules = config / "rules.yaml"
    rules.write_text(rules.read_text().replace("max_reject_ratio: 0.2", "max_reject_ratio: 0.9"))
    run = ImportService(
        db_session, settings.model_copy(update={"config_dir": config}), clock
    ).run_import(
        DirectorySource(data), mapping_name="synthetic-schedules", dry_run=False, actor=ACTOR
    )
    assert run.status == "published", run.error
    assert (run.entity_counts or {})["flights"]["inserted"] == 7  # TA 1, every day for a week
    rejects = list(
        db_session.scalars(
            select(ImportReject).where(
                ImportReject.import_run_id == run.id, ImportReject.entity == "flights"
            )
        )
    )
    by_row = {(r.row_number, r.code) for r in rejects}
    assert by_row == {(3, "INVALID_VALUE"), (4, "UNKNOWN_REFERENCE")}  # one each, per file line
