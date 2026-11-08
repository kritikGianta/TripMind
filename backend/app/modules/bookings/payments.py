"""Payment simulator (no real money moves; plan v2 scope).

Behaves like a card processor's test mode: the card number decides the outcome. Card numbers are
checked (Luhn, expiry) and then discarded; only the brand and last four digits are stored.

    4242 4242 4242 4242  succeeds
    4000 0000 0000 0002  declined
    4000 0000 0000 9995  insufficient funds
    any other valid number succeeds
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date

from app.core.errors import ValidationFailed

# Provider reference on the record kept for a free change or extra, so a retry with the same
# Idempotency-Key is recognised. Not shown to travellers as a payment.
NO_CHARGE = "no_charge"

DECLINES = {
    "4000000000000002": "CARD_DECLINED",
    "4000000000009995": "INSUFFICIENT_FUNDS",
}


@dataclass(frozen=True)
class PaymentResult:
    succeeded: bool
    brand: str
    last4: str
    failure_code: str | None
    reference: str


def _luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        digit = int(ch)
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _brand(number: str) -> str:
    if number.startswith("4"):
        return "visa"
    if number[:2] in {"51", "52", "53", "54", "55"} or "2221" <= number[:4] <= "2720":
        return "mastercard"
    if number[:2] in {"34", "37"}:
        return "amex"
    if number[:2] in {"60", "65", "81", "82"}:
        return "rupay"
    return "card"


def charge(card_number: str, expiry_month: int, expiry_year: int, today: date) -> PaymentResult:
    number = "".join(ch for ch in card_number if ch.isdigit())
    if len(number) < 12 or not _luhn_ok(number):
        raise ValidationFailed("The card number is not valid.", code="CARD_INVALID")
    if (expiry_year, expiry_month) < (today.year, today.month):
        raise ValidationFailed("The card has expired.", code="CARD_EXPIRED")
    failure = DECLINES.get(number)
    return PaymentResult(
        succeeded=failure is None,
        brand=_brand(number),
        last4=number[-4:],
        failure_code=failure,
        reference=f"sim_{secrets.token_hex(10)}",
    )
