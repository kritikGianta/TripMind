"""Money in integer minor units (plan v2, G5).

Amounts are stored as integers in the currency's smallest unit (paise, cents, fils) together with
an ISO 4217 code. This keeps arithmetic exact and behaves identically on PostgreSQL and SQLite.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ISO 4217 currencies whose minor unit is not 2 digits. Everything else uses 2.
_EXPONENTS: dict[str, int] = {
    "BHD": 3,
    "CLP": 0,
    "IDR": 0,  # IDR has an official exponent of 2, but no sub-unit is used in practice
    "ISK": 0,
    "JOD": 3,
    "JPY": 0,
    "KRW": 0,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
    "UGX": 0,
    "VND": 0,
}

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_NON_NUMERIC = re.compile(r"[^\d.\-]")


def currency_exponent(currency: str) -> int:
    return _EXPONENTS.get(currency.upper(), 2)


def parse_amount(raw: object) -> Decimal | None:
    """Parse '₹4,999.50', '4999.5' or 4999.5 into a Decimal. Returns None if not a number."""
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int | float):
        if raw != raw:  # NaN
            return None
        return Decimal(str(raw))
    text = _NON_NUMERIC.sub("", str(raw))
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_minor_units(amount: Decimal, currency: str) -> int:
    exponent = currency_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    return int((amount.quantize(quantum, rounding=ROUND_HALF_UP)).scaleb(exponent))


def from_minor_units(amount_minor: int, currency: str) -> Decimal:
    return Decimal(amount_minor).scaleb(-currency_exponent(currency))
