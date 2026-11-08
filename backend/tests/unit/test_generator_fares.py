"""Demo fares follow public Indian fare levels, and stay inside the anomaly detector's limit."""

from __future__ import annotations

import csv
import io
import math
import zipfile
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from app.datagen.generator import GeneratorOptions, _domestic_booking_curve, generate
from app.modules.ingestion.anomalies import MIN_RELATIVE_JUMP

START = date(2026, 11, 8)


def _flights(path: Path) -> list[dict[str, str]]:
    generate(path, GeneratorOptions(seed=7, start=START, days=30, hotels_scale=0.1, dirty_rate=0))
    with zipfile.ZipFile(path) as archive:
        return list(csv.DictReader(io.StringIO(archive.read("flights.csv").decode())))


def test_booking_curve_is_flat_within_fifteen_days() -> None:
    assert _domestic_booking_curve(0) == _domestic_booking_curve(15) == 1.85
    assert _domestic_booking_curve(16) == 1.0


def test_domestic_fares_rise_near_departure_and_stay_realistic(tmp_path: Path) -> None:
    rows = _flights(tmp_path / "d.zip")
    route = [r for r in rows if (r["from"], r["to"], r["cabin"]) == ("DEL", "BOM", "Economy")]
    cutoff = (START + timedelta(days=15)).isoformat()
    near = median(float(r["fare"]) for r in route if r["departure"][:10] <= cutoff)
    far = median(float(r["fare"]) for r in route if r["departure"][:10] > cutoff)
    assert 1.6 < near / far < 2.1
    assert 2_000 < far < 4_500  # advance Delhi-Mumbai economy, in rupees
    business = median(
        float(r["fare"])
        for r in rows
        if (r["from"], r["to"], r["cabin"]) == ("DEL", "BOM", "Business")
        and r["departure"][:10] > cutoff
    )
    assert business > 4 * far


def test_genuine_fares_do_not_reach_the_anomaly_threshold(tmp_path: Path) -> None:
    groups: dict[tuple[str, str, str], list[float]] = {}
    for row in _flights(tmp_path / "d.zip"):
        groups.setdefault((row["from"], row["to"], row["cabin"]), []).append(float(row["fare"]))
    for fares in groups.values():
        middle = median(fares)
        assert max(abs(math.log(f / middle)) for f in fares) < MIN_RELATIVE_JUMP
