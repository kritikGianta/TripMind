"""Promo codes from config/promotions.yaml, validated and priced on the server."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.errors import ValidationFailed


class Promotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z0-9]{3,24}$")
    description: str
    percent_off: float | None = Field(default=None, gt=0, le=100)
    amount_off: int | None = Field(default=None, gt=0, description="Display currency, major")
    max_discount: int | None = Field(default=None, gt=0)
    applies_to: Literal["any", "flight", "hotel"] = "any"
    min_nights: int | None = Field(default=None, ge=1)
    first_booking_only: bool = False
    requires_flight_and_hotel: bool = False
    valid_until: date | None = None

    @model_validator(mode="after")
    def _one_discount(self) -> Promotion:
        if (self.percent_off is None) == (self.amount_off is None):
            raise ValueError("set exactly one of percent_off or amount_off")
        return self


class PromotionsFile(BaseModel):
    promotions: list[Promotion] = Field(default_factory=list)


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict[str, Promotion]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {p.code: p for p in PromotionsFile.model_validate(data).promotions}


def load_promotions(config_dir: Path) -> dict[str, Promotion]:
    path = config_dir / "promotions.yaml"
    return _load(str(path), path.stat().st_mtime) if path.exists() else {}


class PromoInvalid(ValidationFailed):
    code = "PROMO_INVALID"
    message = "This promo code can't be used."


def discount_for(
    promo: Promotion,
    *,
    items: list[tuple[str, int, int]],  # (kind, display_minor, nights or 0)
    today: date,
    has_confirmed_booking: bool,
    already_used: bool,
) -> tuple[int, list[int]]:
    """Total discount in minor units and its split across the items (same order)."""
    if promo.valid_until and today > promo.valid_until:
        raise PromoInvalid(f"{promo.code} expired on {promo.valid_until:%d %b %Y}.")
    if already_used:
        raise PromoInvalid(f"You've already used {promo.code}.", code="PROMO_ALREADY_USED")
    if promo.first_booking_only and has_confirmed_booking:
        raise PromoInvalid(f"{promo.code} is for your first booking only.")
    kinds = {kind for kind, _, _ in items}
    if promo.requires_flight_and_hotel and not {"flight", "hotel"} <= kinds:
        raise PromoInvalid(f"{promo.code} needs a flight and a stay in the same booking.")
    eligible = [
        i
        for i, (kind, _, nights) in enumerate(items)
        if (promo.applies_to in ("any", kind))
        and (promo.min_nights is None or (kind == "hotel" and nights >= promo.min_nights))
    ]
    if not eligible:
        raise PromoInvalid(f"Nothing in this booking qualifies for {promo.code}.")
    base = sum(items[i][1] for i in eligible)
    if promo.percent_off is not None:
        discount = int(base * promo.percent_off / 100)
    else:
        discount = (promo.amount_off or 0) * 100
    if promo.max_discount is not None:
        discount = min(discount, promo.max_discount * 100)
    discount = min(discount, base)
    split = [0] * len(items)
    remaining = discount
    for n, i in enumerate(eligible):
        share = remaining if n == len(eligible) - 1 else discount * items[i][1] // base
        split[i] = share
        remaining -= share
    return discount, split
