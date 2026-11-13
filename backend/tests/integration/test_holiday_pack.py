"""Loading the official data pack into the catalog."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.core.config import Settings
from app.models import (
    Airport,
    AirportServedCity,
    Attraction,
    City,
    CityLink,
    Flight,
    Hotel,
    RoomNightInventory,
    RoomType,
    Transfer,
)
from app.modules.catalog.models import DataOrigin, catalog_id
from app.modules.holiday.pack import load_pack
from app.modules.inventory.service import InventoryService, nights

API = "/api/v1"


def count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_every_record_of_the_pack_is_loaded(db_session: Session, holiday_pack: None) -> None:
    # The record counts the data dictionary gives, file by file.
    assert count(db_session, Flight) == 469
    assert count(db_session, Hotel) == 49
    assert count(db_session, RoomType) == 125
    assert count(db_session, RoomNightInventory) == 2500
    assert count(db_session, Transfer) == 66
    assert count(db_session, Attraction) == 56
    assert count(db_session, Airport) == 10
    departures = db_session.scalars(select(City.name).where(City.is_departure.is_(True))).all()
    assert sorted(departures) == ["Bengaluru", "Chennai", "Delhi", "Mumbai"]


def test_records_keep_their_meaning(db_session: Session, holiday_pack: None) -> None:
    flight = db_session.get(Flight, catalog_id("flights", "FL-711"))
    assert flight is not None and flight.source_key == "FL-711"
    assert flight.seat_capacity == 9 and flight.fare_minor == 25200 * 100
    # 06:30 in Bengaluru (UTC+05:30) is 01:00 UTC; local time is kept as given.
    assert flight.departure_local == datetime(2027, 4, 3, 6, 30)
    assert flight.departure_at.replace(tzinfo=UTC) == datetime(2027, 4, 3, 1, 0, tzinfo=UTC)

    room = db_session.get(RoomType, catalog_id("room_types", "RM-TYO-001-A"))
    assert room is not None and (room.max_adults, room.max_children) == (2, 0)
    assert room.nightly_rate_minor == 6440 * 100 and room.room_kind == "TWIN"

    kix = db_session.scalar(select(Airport).where(Airport.code == "KIX"))
    assert kix is not None
    served = db_session.scalars(
        select(City.name)
        .join(AirportServedCity, AirportServedCity.city_id == City.id)
        .where(AirportServedCity.airport_id == kix.id)
    ).all()
    assert sorted(served) == ["Kyoto", "Osaka"]
    assert count(db_session, CityLink) >= 8  # Japan's cities all connect; Dubai <-> Abu Dhabi


def test_rooms_exist_only_on_listed_nights_and_reservations_survive_a_reload(
    db_session: Session, holiday_pack: None, settings: Settings, clock: FrozenClock
) -> None:
    room = db_session.get(RoomType, catalog_id("room_types", "RM-TYO-001-A"))
    assert room is not None
    inventory = InventoryService(db_session)
    stay = nights(date(2027, 4, 10), date(2027, 4, 12))
    listed = db_session.scalars(
        select(RoomNightInventory.capacity).where(
            RoomNightInventory.room_type_id == room.id, RoomNightInventory.night.in_(stay)
        )
    ).all()
    assert inventory.rooms_free([room], stay)[room.id] == min(listed)
    assert inventory.rooms_free([room], [date(2027, 4, 25)])[room.id] == 0  # outside the data

    # Reserve one room on 10 April, reload the pack: the reservation still counts.
    row = db_session.get(RoomNightInventory, (room.id, date(2027, 4, 10)))
    assert row is not None and row.capacity >= 1
    row.reserved = 1
    db_session.commit()
    load_pack(db_session, settings.holiday_data_dir, clock.now())
    again = db_session.get(RoomNightInventory, (room.id, date(2027, 4, 10)))
    assert again is not None and again.reserved == 1


def test_loading_twice_changes_nothing(
    db_session: Session, holiday_pack: None, settings: Settings, clock: FrozenClock
) -> None:
    before = {f.id: f.row_hash for f in db_session.scalars(select(Flight))}
    load_pack(db_session, settings.holiday_data_dir, clock.now())
    after = {f.id: f.row_hash for f in db_session.scalars(select(Flight))}
    assert before == after and count(db_session, CityLink) == count(db_session, CityLink)


def test_earlier_data_is_retired(
    db_session: Session, catalog: None, settings: Settings, clock: FrozenClock
) -> None:
    load_pack(db_session, settings.holiday_data_dir, clock.now())
    live = db_session.scalars(select(Flight.origin).where(Flight.is_active.is_(True))).all()
    assert live and set(live) == {DataOrigin.PROVIDED.value}


def test_stay_search_uses_the_pack(client: TestClient, holiday_pack: None) -> None:
    found = client.get(f"{API}/locations", params={"q": "Kyoto", "kind": "city"}).json()
    body = client.get(
        f"{API}/hotels/search",
        params={
            "city": found["items"][0]["value"],
            "check_in": "2027-04-11",
            "check_out": "2027-04-14",
        },
    ).json()
    assert body["total"] > 0
    assert all(r["cheapest_room"]["fits_party"] for r in body["results"])
