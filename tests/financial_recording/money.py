"""Currency authority adapter and exact decimal parsing into integer minor units.

babel (CLDR) is the currency authority. Amounts never pass through float.
"""

from fractions import Fraction

from babel.numbers import get_currency_precision, list_currencies

KNOWN_CURRENCIES = frozenset(list_currencies())


class InvalidInput(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def exponent(currency: str) -> int:
    # babel answers 2 for codes it does not know, so membership is checked first.
    if currency not in KNOWN_CURRENCIES:
        raise InvalidInput("currency_unsupported", repr(currency))
    return get_currency_precision(currency)


def parse_minor(text: str, currency: str) -> int:
    digits = exponent(currency)
    unsigned = text.strip()
    negative = unsigned.startswith("-")
    if negative:
        unsigned = unsigned[1:]
    whole, dot, fraction = unsigned.partition(".")
    if not _ascii_digits(whole) or (dot and not _ascii_digits(fraction)):
        raise InvalidInput("amount_invalid", repr(text))
    if len(fraction) > digits:
        raise InvalidInput(
            "amount_precision",
            f"{text!r} exceeds {digits} fraction digits for {currency}",
        )
    minor = int(whole) * 10**digits + int(fraction.ljust(digits, "0") or "0")
    return -minor if negative else minor


def round_half_up(value: Fraction) -> int:
    magnitude = int(abs(value) + Fraction(1, 2))
    return magnitude if value >= 0 else -magnitude


def _ascii_digits(text: str) -> bool:
    return text.isascii() and text.isdigit()
