"""Calculation rows under an answer: the market counterfactual and the offer.

A research answer whose calculation needs figures only the reader knows offers
it as its first row; tapping it asks for those figures and keeps the cited ones.

The market counterfactual is offered under a computed answer, never run by itself.

A plan computed at a stated rate invites one honest comparison: what the same
amount did in the market over the same number of years. The row carries the
user's own amount and horizon into a runnable test of the calculation's asset,
or the S&P 500 proxy when it names none, in the shape every Try next row has,
and runs only when tapped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from argus.agent_runtime.asset_identity import asset_label_parts, label_from_parts
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENTS_ROW_CAP,
    NEXT_EXPERIMENTS_VERSION,
)

MARKET_COUNTERFACTUAL_KIND = "calculation_market_counterfactual"
CALCULATION_OFFER_KIND = "calculation_offer"
_OFFER_LABEL_KEY = "chat.next_experiments.labels.calculation_offer"
_OFFER_LABELS = {
    "en": "Work it out with your own figures",
    "es-419": "Calcúlalo con tus propios números",
}
MARKET_PROXY = {"symbol": "SPY", "name": "S&P 500", "asset_class": "equity"}
# A label_key the catalogs deliberately lack, so the backend label renders.
_DYNAMIC_LABEL_KEY = "chat.next_experiments.labels.research_dynamic"
# Argument names that carry the amount the user starts with, by kind.
_AMOUNT_FIELDS = ("present_value", "start_value", "amount", "assets")
MAX_COUNTERFACTUAL_YEARS = 30


def market_counterfactual_rows(
    arguments: Mapping[str, Any],
    *,
    language: str,
    subject: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """One row when the calculation states an amount and a horizon in whole years.

    A starting amount becomes a buy-and-hold test; a periodic payment with
    no starting amount becomes a monthly-buy test of the same payment. The
    asset is the calculation's own subject when it has one, else the market."""
    years = _years(arguments)
    amount = _amount(arguments)
    payment = _monthly_payment(arguments)
    if years is None or (amount is None and payment is None):
        return None
    currency = str(arguments.get("currency") or "")
    spanish = language.startswith("es")
    asset = dict(subject) if subject else MARKET_PROXY
    symbol = asset["symbol"]
    if amount is not None:
        stated = _money(amount, currency, grouped=True)
        plain = _money(amount, currency, grouped=False)
        tail = (
            f" con {stated} durante los últimos {years} años"
            if spanish
            else f" with {stated} over the last {years} years"
        )
        send_text = (
            f"Prueba comprar y mantener {symbol} con {plain} durante los últimos {years} años"
            if spanish
            else f"Test buying and holding {symbol} with {plain} over the last {years} years"
        )
    else:
        assert payment is not None
        stated = _money(payment, currency, grouped=True)
        plain = _money(payment, currency, grouped=False)
        tail = (
            f" comprando {stated} cada mes durante los últimos {years} años"
            if spanish
            else f" buying {stated} every month over the last {years} years"
        )
        send_text = (
            f"Prueba comprar {plain} de {symbol} cada mes durante los últimos {years} años"
            if spanish
            else f"Test buying {plain} of {symbol} every month over the last {years} years"
        )
    parts = [
        {"type": "text", "value": "Probar " if spanish else "Test "},
        *asset_label_parts([asset]),
        {"type": "text", "value": tail},
    ]
    return {
        "version": NEXT_EXPERIMENTS_VERSION,
        "rows": [
            {
                "kind": MARKET_COUNTERFACTUAL_KIND,
                "label": label_from_parts(parts),
                "label_parts": parts,
                "label_key": _DYNAMIC_LABEL_KEY,
                "send_text": send_text,
            }
        ],
    }


def _money(amount: float, currency: str, *, grouped: bool) -> str:
    figure = f"{amount:,.0f}" if grouped else f"{amount:.0f}"
    return f"{figure} {currency}".strip()


def _monthly_payment(arguments: Mapping[str, Any]) -> float | None:
    if arguments.get("periods_per_year", 12) != 12:
        return None
    for name in ("payment", "contribution"):
        value = arguments.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
    return None


def _amount(arguments: Mapping[str, Any]) -> float | None:
    for name in _AMOUNT_FIELDS:
        value = arguments.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
    return None


def _years(arguments: Mapping[str, Any]) -> int | None:
    for name in ("years", "horizon_years"):
        value = arguments.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _whole_years(float(value))
    periods = arguments.get("periods")
    per_year = arguments.get("periods_per_year", 12)
    if (
        isinstance(periods, (int, float))
        and isinstance(per_year, (int, float))
        and not isinstance(periods, bool)
        and per_year
    ):
        return _whole_years(float(periods) / float(per_year))
    return None


def _whole_years(value: float) -> int | None:
    years = round(value)
    if years < 1 or abs(value - years) > 1e-6 or years > MAX_COUNTERFACTUAL_YEARS:
        return None
    return years


def with_calculation_offer(
    rows: dict[str, Any] | None, *, language: str
) -> dict[str, Any]:
    """The offer first among an answer's rows, within the row bound."""
    label = _OFFER_LABELS["es-419" if str(language or "").startswith("es") else "en"]
    offer = {
        "kind": CALCULATION_OFFER_KIND,
        "label": label,
        "label_key": _OFFER_LABEL_KEY,
        "send_text": label,
    }
    offered = [offer, *((rows or {}).get("rows") or [])]
    return {
        **(rows or {"version": NEXT_EXPERIMENTS_VERSION}),
        "rows": offered[:NEXT_EXPERIMENTS_ROW_CAP],
    }
