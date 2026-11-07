"""Price ledgers and currency conversion (plan v2, G11).

A ledger lists what a price is made of. Amounts the data does not contain (taxes and fees in the
demo dataset) appear as explicit "not included" lines, so a total is never presented as more
complete than it is. Converted amounts use static, labelled rates from `config/rules.yaml`.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.money import from_minor_units, to_minor_units


class PricingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_currency: str = "INR"
    fx_rates: dict[str, Decimal] = Field(default_factory=lambda: {"INR": Decimal(1)})
    fx_note: str = "Converted with fixed demo rates, not live exchange rates."
    taxes_included_in_data: bool = False


class SearchRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_connection_minutes: int = Field(default=60, ge=20)
    max_connection_minutes: int = Field(default=360, ge=60)
    max_results: int = Field(default=200, ge=10)
    max_hotel_nights: int = Field(default=30, ge=1)


@lru_cache(maxsize=8)
def _rules_document(path: str, mtime: float) -> dict[str, object]:
    file = Path(path)
    return (yaml.safe_load(file.read_text(encoding="utf-8")) or {}) if file.exists() else {}


def _section(config_dir: Path, name: str) -> object:
    path = config_dir / "rules.yaml"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _rules_document(str(path), mtime).get(name) or {}


def load_pricing_rules(config_dir: Path) -> PricingRules:
    return PricingRules.model_validate(_section(config_dir, "pricing"))


def load_search_rules(config_dir: Path) -> SearchRules:
    return SearchRules.model_validate(_section(config_dir, "search"))


class MoneyOut(BaseModel):
    amount_minor: int
    currency: str


LineKind = Literal["fare", "room", "taxes_and_fees"]


class LedgerLine(BaseModel):
    label: str
    kind: LineKind
    amount: MoneyOut | None = Field(description="None when the data does not contain the amount")
    note: str | None = None


class PriceLedger(BaseModel):
    lines: list[LedgerLine]
    total: MoneyOut | None = Field(description="Sum of the known lines, in the supplier currency")
    display_total: MoneyOut | None = Field(description="Total converted to the display currency")
    converted: bool = Field(description="True when display_total used a conversion rate")
    complete: bool = Field(description="False when some lines are not included in the data")
    fx_note: str | None = None


class Converter:
    def __init__(self, rules: PricingRules) -> None:
        self.rules = rules
        self.display_currency = rules.display_currency

    def to_display(self, amount_minor: int, currency: str) -> MoneyOut | None:
        if currency == self.display_currency:
            return MoneyOut(amount_minor=amount_minor, currency=currency)
        rate = self.rules.fx_rates.get(currency)
        if rate is None:
            return None
        major = from_minor_units(amount_minor, currency) * rate
        return MoneyOut(
            amount_minor=to_minor_units(major, self.display_currency),
            currency=self.display_currency,
        )

    def ledger(self, lines: list[LedgerLine]) -> PriceLedger:
        """Total the known lines. Mixed currencies are totalled in the display currency only."""
        if not self.rules.taxes_included_in_data:
            lines = [
                *lines,
                LedgerLine(
                    label="Taxes and fees",
                    kind="taxes_and_fees",
                    amount=None,
                    note="Not included in the supplied data",
                ),
            ]
        priced = [line for line in lines if line.kind != "taxes_and_fees"]
        amounts = [line.amount for line in priced if line.amount is not None]
        complete = all(line.amount is not None for line in lines)
        if not amounts or len(amounts) != len(priced):
            return PriceLedger(
                lines=lines, total=None, display_total=None, converted=False, complete=False
            )
        currencies = {a.currency for a in amounts}
        total: MoneyOut | None = None
        if len(currencies) == 1:
            currency = currencies.pop()
            total = MoneyOut(amount_minor=sum(a.amount_minor for a in amounts), currency=currency)
            display = self.to_display(total.amount_minor, currency)
        else:
            converted_parts = [self.to_display(a.amount_minor, a.currency) for a in amounts]
            display = (
                None
                if any(c is None for c in converted_parts)
                else MoneyOut(
                    amount_minor=sum(c.amount_minor for c in converted_parts if c is not None),
                    currency=self.display_currency,
                )
            )
        converted = display is not None and (
            total is None or total.currency != self.display_currency
        )
        return PriceLedger(
            lines=lines,
            total=total,
            display_total=display,
            converted=converted,
            complete=complete,
            fx_note=self.rules.fx_note if converted else None,
        )
