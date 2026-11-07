from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.search.pricing import MoneyOut
from app.modules.search.schemas import FlightOfferOut

DisruptionKindIn = Literal["flight_cancelled", "flight_delayed", "room_unavailable"]


class DisruptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: DisruptionKindIn
    flight_id: uuid.UUID | None = None
    room_type_id: uuid.UUID | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    delay_minutes: Annotated[int | None, Field(ge=15, le=24 * 60)] = None
    reason: Annotated[str, Field(min_length=3, max_length=200)] = "Operational reasons"

    @model_validator(mode="after")
    def _target(self) -> DisruptionIn:
        if self.kind == "room_unavailable":
            if not (self.room_type_id and self.starts_on and self.ends_on):
                raise ValueError("room_unavailable needs room_type_id, starts_on and ends_on")
            if self.ends_on <= self.starts_on:
                raise ValueError("ends_on must be after starts_on")
        elif self.flight_id is None:
            raise ValueError("flight disruptions need flight_id")
        if self.kind == "flight_delayed" and not self.delay_minutes:
            raise ValueError("flight_delayed needs delay_minutes")
        return self


class DisruptionOut(BaseModel):
    id: uuid.UUID
    kind: str
    target: str
    reason: str
    delay_minutes: int | None
    affected_items: int
    created_at: datetime


class DisruptionListOut(BaseModel):
    items: list[DisruptionOut]


class BookedFlightOut(BaseModel):
    flight_id: uuid.UUID
    flight_number: str
    route: str
    departure_local: datetime
    cabin_class: str
    booked_seats: int
    disruption: str | None


class BookedFlightListOut(BaseModel):
    items: list[BookedFlightOut]


class RecoveryOptionOut(BaseModel):
    id: str
    type: Literal["rebook_flight", "rebook_room", "refund", "keep"]
    title: str
    description: str
    offer: FlightOfferOut | None = None
    room: dict[str, Any] | None = None
    extra_cost: MoneyOut
    refund: MoneyOut | None = None
    notes: list[str] = Field(default_factory=list)


class RecoveryCaseOut(BaseModel):
    id: uuid.UUID
    status: str
    resolution: str | None
    booking_id: uuid.UUID
    booking_reference: str
    trip_id: uuid.UUID
    item_id: uuid.UUID
    item_title: str
    disruption_kind: str
    disruption_reason: str
    summary: str
    impact: list[str]
    options: list[RecoveryOptionOut]
    chosen_option_id: str | None
    created_at: datetime
    resolved_at: datetime | None


class RecoveryCaseListOut(BaseModel):
    items: list[RecoveryCaseOut]


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: Annotated[str, Field(min_length=1, max_length=120)]
