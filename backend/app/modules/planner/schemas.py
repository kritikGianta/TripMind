"""Connected-trip planner API contract."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.search.pricing import MoneyOut
from app.modules.search.schemas import FlightOfferOut, HotelResultOut

Priority = Literal["balanced", "cheapest", "fastest", "comfort"]
OptionState = Literal["saved", "dismissed", "none"]


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Annotated[str, Field(min_length=2, max_length=64, description="Airport code or city")]
    destination_city_id: uuid.UUID
    depart_date: date
    return_date: date
    adults: Annotated[int, Field(ge=1, le=9)] = 1
    priority: Priority = "balanced"
    min_stars: Annotated[int | None, Field(ge=1, le=5)] = None
    max_budget: Annotated[int | None, Field(ge=1, description="Whole trip, display currency")] = (
        None
    )


class ScoresOut(BaseModel):
    price: float
    time: float
    stay: float
    convenience: float
    total: float


class CheckOut(BaseModel):
    name: str
    status: Literal["ok", "info", "warn", "risk"]
    message: str


class ConfidenceOut(BaseModel):
    level: Literal["high", "medium", "low"]
    summary: str
    checks: list[CheckOut]


class StayPlanOut(BaseModel):
    check_in: date
    check_out: date
    nights: int
    rooms: int
    guests: int


class BundleOut(BaseModel):
    id: str
    rank: int
    outbound: FlightOfferOut
    inbound: FlightOfferOut
    hotel: HotelResultOut
    stay: StayPlanOut
    total: MoneyOut
    complete: bool
    scores: ScoresOut
    explanation: list[str]
    confidence: ConfidenceOut
    state: OptionState = "none"


class PlanOut(BaseModel):
    id: uuid.UUID
    title: str
    request: PlanRequest
    weights: dict[str, float]
    generated_at: datetime
    options: list[BundleOut]
    notices: list[str]


class PlanSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    depart_date: date
    return_date: date
    adults: int
    priority: str
    options: int
    saved: int
    generated_at: datetime


class PlanListOut(BaseModel):
    items: list[PlanSummaryOut]


class OptionStateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: OptionState
