"""A money amount and the currency it is counted in."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_CURRENCY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount, bool) or not isinstance(self.amount, (int, float)):
            raise TypeError("A money amount is a number")
        if not math.isfinite(self.amount):
            raise ValueError("A money amount is finite")
        if _CURRENCY.fullmatch(self.currency) is None:
            raise ValueError("A currency is an ISO 4217 code")
        object.__setattr__(self, "amount", float(self.amount))

    def with_amount(self, amount: float) -> Money:
        return Money(amount, self.currency)

    def scaled(self, factor: float) -> Money:
        return Money(self.amount * factor, self.currency)

    def __add__(self, other: Money) -> Money:
        return Money(self.amount + self._same(other).amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount - self._same(other).amount, self.currency)

    def _same(self, other: Money) -> Money:
        if not isinstance(other, Money):
            raise TypeError("Money combines only with money")
        if other.currency != self.currency:
            raise ValueError("Money combines only within one currency")
        return other
