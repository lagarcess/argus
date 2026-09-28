"""Currency acceptance and exact minor-unit arithmetic.

The tender set is ``home_country.currency_codes()`` and the exponent is CLDR
through babel. babel answers 2 for codes it does not know, so membership is
checked first. Amounts never pass through float, and input is never rounded.
"""

from __future__ import annotations

from babel.numbers import get_currency_precision

from argus.domain.home_country import currency_codes
from argus.domain.recording.errors import RecordingInputError


def normalize_currency(value: str) -> str:
    """Return the accepted ISO 4217 code or raise ``currency_unsupported``."""

    code = (value or "").strip().upper()
    if code not in currency_codes():
        raise RecordingInputError(
            "currency_unsupported", f"{value!r} is not a supported currency"
        )
    return code


def currency_exponent(currency: str) -> int:
    return get_currency_precision(normalize_currency(currency))


def parse_minor_units(text: str, currency: str) -> int:
    """Parse a dot-decimal string into signed minor units without rounding."""

    digits = currency_exponent(currency)
    unsigned = (text or "").strip()
    negative = unsigned.startswith("-")
    if negative:
        unsigned = unsigned[1:]
    whole, dot, fraction = unsigned.partition(".")
    if not _ascii_digits(whole) or (dot and not _ascii_digits(fraction)):
        raise RecordingInputError("amount_invalid", f"{text!r} is not a decimal amount")
    if len(fraction) > digits:
        raise RecordingInputError(
            "amount_precision",
            f"{text!r} has more than {digits} fraction digits for {currency}",
        )
    minor = int(whole) * 10**digits + int(fraction.ljust(digits, "0") or "0")
    return -minor if negative else minor


def format_minor_units(minor: int, currency: str) -> str:
    """Render signed minor units as the dot-decimal string the wire carries."""

    digits = currency_exponent(currency)
    sign = "-" if minor < 0 else ""
    magnitude = abs(minor)
    if digits == 0:
        return f"{sign}{magnitude}"
    whole, fraction = divmod(magnitude, 10**digits)
    return f"{sign}{whole}.{fraction:0{digits}d}"


def _ascii_digits(text: str) -> bool:
    return text.isascii() and text.isdigit()
