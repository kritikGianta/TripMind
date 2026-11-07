"""Ingestion end to end: generator -> ZIP -> mapping -> validation -> publish -> reports."""

from __future__ import annotations

import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import seed
from app.core.clock import FrozenClock
from app.core.config import Settings
from app.core.errors import Conflict, ValidationFailed
from app.core.request_context import RequestMeta
from app.models import AuditLog, Flight, Hotel, HotelAmenity, ImportReject, ImportRun, RoomType
from app.modules.catalog.models import Airport, City
from app.modules.ingestion.models import ImportStatus
from app.modules.ingestion.service import Actor, ImportService
from app.modules.ingestion.sources import DirectorySource, ZipSource

API = "/api/v1"
ACTOR = Actor(user_id=None, via="cli", meta=RequestMeta(ip_address=None, user_agent="test"))
UPLOAD_HEADERS = {"X-Requested-With": "tripmind"}


def zip_source(path: Path) -> ZipSource:
    return ZipSource(path.read_bytes(), name=path.name, max_members=50, max_uncompressed_mb=200)


def service(session: Session, settings: Settings, clock: FrozenClock) -> ImportService:
    return ImportService(session, settings, clock)


def count(session: Session, model: Any, active: bool | None = True) -> int:
    query = select(func.count()).select_from(model)
    if active is not None:
        query = query.where(model.is_active.is_(active))
    return int(session.scalar(query) or 0)


def config_with_mapping(tmp_path: Path, settings: Settings, name: str, body: str) -> Settings:
    config = tmp_path / "config"
    (config / "mappings").mkdir(parents=True)
    for file in ("rules.yaml", "vocabulary.yaml", "features.yaml"):
        shutil.copy(settings.config_dir / file, config / file)
    (config / "mappings" / f"{name}.yaml").write_text(body, encoding="utf-8")
    return settings.model_copy(update={"config_dir": config})


# ── Publish, quarantine and re-import ──────────────────────────────────────


def test_synthetic_import_publishes_and_quarantines(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path
) -> None:
    run = service(db_session, settings, clock).run_import(
        zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR
    )
    assert run.status == ImportStatus.PUBLISHED
    counts = run.entity_counts or {}
    assert counts["airports"]["inserted"] == 25
    assert counts["flights"]["accepted"] == count(db_session, Flight)
    assert counts["hotels"]["accepted"] == count(db_session, Hotel)
    assert count(db_session, City) >= 20

    # Every deliberate defect type is quarantined with its own reason code.
    summary = run.reject_summary or {}
    assert set(summary["flights"]) == {
        "INVALID_VALUE",
        "MISSING_REQUIRED",
        "UNKNOWN_REFERENCE",
        "INCONSISTENT",
        "OUT_OF_RANGE",
        "DUPLICATE_KEY",
    }
    stored = db_session.scalars(select(ImportReject).where(ImportReject.import_run_id == run.id))
    first = next(iter(stored))
    assert first.row_number >= 2 and first.raw is not None and first.source_file.endswith(".csv")

    # Normalisations are reported, not hidden.
    adjustments = (run.adjustments or {})["counts"]
    assert adjustments["TIMEZONE_ASSUMED"] >= 1
    assert adjustments["FARE_MISSING_BROWSE_ONLY"] >= 1
    assert (run.profile or {})["travel_window"] == {
        "first_departure": "2026-11-13",
        "last_departure": "2026-11-15",
    }
    # Amenities were normalised through the vocabulary ("Free WiFi" -> wifi).
    assert db_session.scalar(
        select(func.count()).select_from(HotelAmenity).where(HotelAmenity.amenity == "wifi")
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "data.import")
        )
        == 1
    )


def test_reimport_is_idempotent_with_stable_ids(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path
) -> None:
    svc = service(db_session, settings, clock)
    svc.run_import(zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR)
    ids = set(db_session.scalars(select(Flight.id)))
    again = svc.run_import(
        zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR
    )
    for entity, c in (again.entity_counts or {}).items():
        assert c["inserted"] == 0 and c["updated"] == 0 and c["retired"] == 0, entity
    assert set(db_session.scalars(select(Flight.id))) == ids


def test_dry_run_validates_without_publishing(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path
) -> None:
    run = service(db_session, settings, clock).run_import(
        zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=True, actor=ACTOR
    )
    assert run.status == ImportStatus.VALIDATED
    assert count(db_session, Flight, active=None) == 0
    assert (run.reject_summary or {})["flights"]


def test_rows_missing_from_a_new_import_are_retired_with_dependants(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path, tmp_path: Path
) -> None:
    svc = service(db_session, settings, clock)
    svc.run_import(zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR)

    with zipfile.ZipFile(demo_zip) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    lines = members["hotels.csv"].decode().splitlines()
    removed_id = lines[1].split(",")[0]
    members["hotels.csv"] = ("\n".join([lines[0], *lines[2:]]) + "\n").encode()
    smaller = tmp_path / "smaller.zip"
    with zipfile.ZipFile(smaller, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    run = svc.run_import(
        zip_source(smaller), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR
    )
    counts = run.entity_counts or {}
    assert counts["hotels"]["retired"] == 1
    assert counts["room_types"]["retired"] >= 1  # cascaded: its rooms referenced a missing hotel
    hotel = db_session.scalar(select(Hotel).where(Hotel.source_key == removed_id))
    assert hotel is not None and not hotel.is_active and hotel.retired_at is not None
    assert count(db_session, RoomType, active=True) and not db_session.scalar(
        select(func.count())
        .select_from(RoomType)
        .where(RoomType.hotel_id == hotel.id, RoomType.is_active.is_(True))
    )


def test_a_wrong_mapping_blocks_publishing(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path, tmp_path: Path
) -> None:
    # Mapping review counts (hundreds) as the 0-10 rating puts nearly every hotel out of range.
    body = (settings.config_dir / "mappings" / "synthetic-v1.yaml").read_text()
    body = body.replace("guest_rating: {column: rating, scale: 2}", "guest_rating: reviews")
    custom = config_with_mapping(tmp_path, settings, "wrong", body)
    run = service(db_session, custom, clock).run_import(
        zip_source(demo_zip), mapping_name="wrong", dry_run=False, actor=ACTOR
    )
    assert run.status == ImportStatus.BLOCKED
    assert "hotels" in (run.error or "")
    assert count(db_session, Flight, active=None) == 0  # nothing published, not even flights


def test_missing_column_fails_with_a_clear_error(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path, tmp_path: Path
) -> None:
    body = (settings.config_dir / "mappings" / "synthetic-v1.yaml").read_text()
    custom = config_with_mapping(
        tmp_path, settings, "typo", body.replace("code: iata", "code: iata_code")
    )
    with pytest.raises(ValidationFailed) as error:
        service(db_session, custom, clock).run_import(
            zip_source(demo_zip), mapping_name="typo", dry_run=False, actor=ACTOR
        )
    assert error.value.code == "MAPPING_COLUMN_MISSING"
    assert "iata" in error.value.details["available"]  # type: ignore[index]
    run = db_session.scalars(select(ImportRun)).one()
    assert run.status == ImportStatus.FAILED and "iata_code" in (run.error or "")


def test_only_one_import_runs_at_a_time(
    db_session: Session, settings: Settings, clock: FrozenClock, demo_zip: Path
) -> None:
    db_session.add(
        ImportRun(
            dataset="x",
            mapping_name="x",
            origin="provided",
            source_name="x",
            source_sha256="0" * 64,
            status="running",
            started_at=clock.now(),
            triggered_via="cli",
        )
    )
    db_session.commit()
    with pytest.raises(Conflict) as error:
        service(db_session, settings, clock).run_import(
            zip_source(demo_zip), mapping_name="synthetic-v1", dry_run=False, actor=ACTOR
        )
    assert error.value.code == "IMPORT_IN_PROGRESS"


# ── Times, references and derived rows ─────────────────────────────────────

TIME_MAPPING = """
dataset: times
entities:
  airports:
    file: airports.csv
    fields: {code: code, name: name, city: city, country: country, timezone: tz}
  flights:
    file: flights.csv
    fields:
      flight_number: number
      airline_code: carrier
      origin: from
      destination: to
      departure_date: date
      departure_clock: dep
      arrival_clock: arr
      duration_minutes: duration
      fare: fare
  hotels:
    file: hotels.csv
    fields: {name: name, city: city, country: country, nightly_rate: price, currency: currency}
"""


def write_times_dataset(root: Path) -> None:
    root.mkdir()
    (root / "airports.csv").write_text(
        "code,name,city,country,tz\n"
        "DEL,Indira Gandhi International Airport,New Delhi,IN,Asia/Kolkata\n"
        "LHR,London Heathrow Airport,London,GB,Europe/London\n"
        "BOM,Mumbai Airport,Mumbai,IN,\n"
    )
    (root / "flights.csv").write_text(
        "number,carrier,from,to,date,dep,arr,duration,fare\n"
        "101,TM,DEL,LHR,2026-11-13,23:30,05:10,,52000\n"  # arrives next day (clock rollover)
        "102,TM,Delhi,BOM,2026-11-13,06:00,,2h 10m,\n"  # city name, duration only, no fare
        "103,TM,DEL,DEL,2026-11-13,06:00,08:00,,4000\n"  # same airport
    )
    (root / "hotels.csv").write_text(
        "name,city,country,price,currency\n"
        "Harbour Inn,Bombay,IN,4500,INR\n"  # alias of Mumbai
        "Lake House,Londn,GB,120.50,GBP\n"  # misspelt, fuzzy-matched
    )


def test_local_times_timezones_references_and_derived_rooms(
    db_session: Session, settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    write_times_dataset(tmp_path / "times")
    custom = config_with_mapping(tmp_path, settings, "times", TIME_MAPPING)
    rules = custom.config_dir / "rules.yaml"  # 1 bad row in 3 is above the default 20% limit
    rules.write_text(rules.read_text().replace("max_reject_ratio: 0.2", "max_reject_ratio: 0.5"))
    run = service(db_session, custom, clock).run_import(
        DirectorySource(tmp_path / "times"), mapping_name="times", dry_run=False, actor=ACTOR
    )
    assert run.status == ImportStatus.PUBLISHED
    assert (run.reject_summary or {}) == {"flights": {"INCONSISTENT": 1}}

    london = db_session.scalars(select(Flight).where(Flight.flight_number == "TM101")).one()
    assert london.departure_at.replace(tzinfo=UTC) == datetime(2026, 11, 13, 18, 0, tzinfo=UTC)
    assert london.arrival_local == datetime(2026, 11, 14, 5, 10)  # London local, next day
    assert london.duration_minutes == 11 * 60 + 10
    assert london.fare_minor == 5_200_000 and london.currency == "INR"

    mumbai = db_session.scalars(select(Flight).where(Flight.flight_number == "TM102")).one()
    assert mumbai.duration_minutes == 130 and mumbai.fare_minor is None  # browse-only
    bom = db_session.scalars(select(Airport).where(Airport.code == "BOM")).one()
    assert bom.timezone == "Asia/Kolkata" and bom.timezone_assumed

    # "New Delhi" (alias of Delhi), "Bombay" (alias of Mumbai), "Londn" (fuzzy) all resolve.
    assert count(db_session, City) == 3
    hotel = db_session.scalars(select(Hotel).where(Hotel.name == "Lake House")).one()
    assert hotel.city_name == "London"
    room = db_session.scalars(select(RoomType).where(RoomType.hotel_id == hotel.id)).one()
    assert room.origin == "derived" and room.nightly_rate_minor == 12050
    assert (run.adjustments or {})["counts"]["CITY_FUZZY_MATCH"] == 1


# ── Admin API ──────────────────────────────────────────────────────────────


def sign_in(client: TestClient, role: str) -> None:
    seed()
    assert client.post(f"{API}/auth/demo-login", json={"role": role}).status_code == 200


def upload(client: TestClient, path: Path, **form: str) -> Any:
    with path.open("rb") as handle:
        return client.post(
            f"{API}/admin/imports",
            files={"file": (path.name, handle, "application/zip")},
            data={"mapping": "synthetic-v1", **form},
            headers=UPLOAD_HEADERS,
        )


def test_imports_require_an_admin(client: TestClient, demo_zip: Path) -> None:
    assert upload(client, demo_zip).status_code == 401
    sign_in(client, "traveler")
    assert upload(client, demo_zip).status_code == 403


def test_uploads_require_the_client_header(client: TestClient, demo_zip: Path) -> None:
    sign_in(client, "admin")
    with demo_zip.open("rb") as handle:
        response = client.post(
            f"{API}/admin/imports",
            files={"file": ("d.zip", handle)},
            data={"mapping": "synthetic-v1"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CLIENT_HEADER_MISSING"


def test_admin_import_flow_and_public_summary(client: TestClient, demo_zip: Path) -> None:
    assert client.get(f"{API}/datasets/current").json() == {
        "status": "empty",
        "dataset": None,
        "origin": None,
        "published_at": None,
        "is_demo_data": False,
        "counts": {},
        "by_origin": {},
        "travel_window": None,
    }
    sign_in(client, "admin")
    assert client.get(f"{API}/admin/imports/mappings").json()["mappings"] == ["synthetic-v1"]

    created = upload(client, demo_zip)
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["status"] == "published" and report["rejects_total"] > 0

    listing = client.get(f"{API}/admin/imports").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == report["id"]
    detail = client.get(f"{API}/admin/imports/{report['id']}").json()
    assert {f["entity"] for f in detail["files"]} == {"airports", "flights", "hotels", "room_types"}
    rejects = client.get(
        f"{API}/admin/imports/{report['id']}/rejects",
        params={"entity": "flights", "code": "UNKNOWN_REFERENCE"},
    ).json()
    assert rejects["total"] >= 1 and rejects["items"][0]["raw"]["to"] == "XYZ"

    summary = client.get(f"{API}/datasets/current").json()
    assert summary["status"] == "loaded" and summary["is_demo_data"] is True
    assert summary["travel_window"] == {
        "first_departure": "2026-11-13",
        "last_departure": "2026-11-15",
    }
    assert summary["counts"]["airports"] == 25


def test_profile_endpoint_drafts_a_valid_mapping(client: TestClient, demo_zip: Path) -> None:
    sign_in(client, "admin")
    with demo_zip.open("rb") as handle:
        response = client.post(
            f"{API}/admin/imports/profile",
            files={"file": ("d.zip", handle)},
            data={"dataset": "finale"},
            headers=UPLOAD_HEADERS,
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert {f["file"] for f in body["files"]} >= {"airports.csv", "flights.csv"}
    from app.modules.ingestion.mapping import parse_mapping

    drafted = parse_mapping(body["suggested_mapping"])
    assert set(drafted.entities) >= {"airports", "flights", "hotels"}
    assert drafted.entities["airports"].fields["code"].column == "iata"


def test_bad_archives_are_rejected(client: TestClient, tmp_path: Path) -> None:
    sign_in(client, "admin")
    bogus = tmp_path / "bogus.zip"
    bogus.write_bytes(b"not a zip")
    response = upload(client, bogus)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOURCE_INVALID"
    unknown = upload(client, bogus, mapping="../../etc/passwd")
    assert unknown.status_code in (404, 422)
