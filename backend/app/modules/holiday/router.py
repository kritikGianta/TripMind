"""Build My Holiday API. No sign-in needed: a package and a reservation number are enough."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.deps import get_clock, rate_limit
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, get_optional_user
from app.modules.auth.models import User
from app.modules.holiday.quick import parse
from app.modules.holiday.service import (
    AlternativeOut,
    BuildOut,
    ChangeIn,
    HolidayRequestIn,
    HolidayService,
    OptionsOut,
    PackageOut,
)

router = APIRouter(prefix="/holiday", tags=["holiday"])


def _service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> HolidayService:
    return HolidayService(session, clock)


class QuickIn(BaseModel):
    text: str = Field(min_length=3, max_length=300)


class QuickOut(BaseModel):
    fields: dict[str, Any] = Field(description="Form fields read from the sentence")
    understood: list[str]
    missing: list[str]


@router.post(
    "/parse",
    response_model=QuickOut,
    summary="Quick request: read a sentence with rules (no AI) and fill the form (S1)",
)
def parse_request(body: QuickIn, service: HolidayService = Depends(_service)) -> QuickOut:
    return QuickOut(**parse(body.text, service.cat))


@router.get("/options", response_model=OptionsOut, summary="Departure cities and countries (M1)")
def options(service: HolidayService = Depends(_service)) -> OptionsOut:
    return service.options()


@router.post(
    "/packages",
    response_model=BuildOut,
    dependencies=[Depends(rate_limit("holiday.build", limit=30, window_seconds=60))],
    summary="Build the cheapest, fastest and best-rated packages for a request (M2, G4, M8)",
)
def build(
    body: HolidayRequestIn,
    service: HolidayService = Depends(_service),
    user: User | None = Depends(get_optional_user),
) -> BuildOut:
    return service.build(body, user.id if user else None)


@router.get(
    "/reservations",
    response_model=list[PackageOut],
    summary="My confirmed holidays (shown in My Trips)",
)
def my_reservations(
    service: HolidayService = Depends(_service), user: User = Depends(get_current_user)
) -> list[PackageOut]:
    return service.mine(user.id)


@router.get("/packages/{package_id}", response_model=PackageOut, summary="One package")
def get_package(package_id: uuid.UUID, service: HolidayService = Depends(_service)) -> PackageOut:
    return service.out(service.get(package_id))


@router.get(
    "/packages/{package_id}/alternatives",
    response_model=list[AlternativeOut],
    summary="Change options with the price difference (G2)",
)
def alternatives(
    package_id: uuid.UUID,
    kind: Literal["hotel", "flight", "attraction"],
    key: str | None = None,
    service: HolidayService = Depends(_service),
) -> list[AlternativeOut]:
    return service.alternatives(package_id, kind, key)


@router.post(
    "/packages/{package_id}/changes",
    response_model=PackageOut,
    summary="Change a hotel or flight, add or remove an attraction; every rule is checked (M6)",
)
def change(
    package_id: uuid.UUID, body: ChangeIn, service: HolidayService = Depends(_service)
) -> PackageOut:
    return service.change(package_id, body)


@router.post(
    "/packages/{package_id}/confirm",
    response_model=PackageOut,
    summary="Confirm: reserve the seats and rooms and get a 10-digit reservation number (M7, S2)",
)
def confirm(
    package_id: uuid.UUID,
    service: HolidayService = Depends(_service),
    user: User | None = Depends(get_optional_user),
) -> PackageOut:
    return service.confirm(package_id, user.id if user else None)


@router.get(
    "/reservations/{reference}",
    response_model=PackageOut,
    summary="Open a reservation by its number (M7)",
)
def reservation(reference: str, service: HolidayService = Depends(_service)) -> PackageOut:
    return service.reservation(reference)


@router.get("/packages/{package_id}/export", summary="Download as JSON, shared trip format (M5)")
def export(package_id: uuid.UUID, service: HolidayService = Depends(_service)) -> JSONResponse:
    body: dict[str, Any] = service.export(package_id)
    return JSONResponse(
        body,
        headers={"Content-Disposition": f'attachment; filename="holiday-{package_id}.json"'},
    )
