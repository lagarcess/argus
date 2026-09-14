"""Calculation rows under an answer: the market counterfactual and the offer.

A research answer whose calculation needs figures only the reader knows offers
it as its first row; tapping it asks for those figures and keeps the cited ones.

The market counterfactual is offered under a computed answer, never run by itself.

A plan computed at a stated rate invites one honest comparison: what the same
amount did in the market over the same number of years. The row carries the
user's own amount and horizon into a runnable test of the calculation's asset,
or the S&P 500 proxy when it names none, in the shape every Try next row has,
and runs only when tapped. A loan is not money the reader could have invested,
and a plan that starts with an amount and also adds deposits is neither one lump
sum nor one monthly buy, so neither offers a row. A backtest runs in dollars, so
an amount in another currency is converted at Argus's own latest close for the
pair, and the label states the rate and its date.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from loguru import logger

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
# The reader's own money, by calculation kind: the argument holding the amount
# they start with, and the one holding what they add each period, if any. A kind
# not listed, such as a loan's effective rate, offers no test.
_READER_MONEY: dict[str, tuple[str, str | None]] = {
    "expense_ratio": ("assets", None),
    "growth_projection": ("start_value", "contribution"),
    "time_value": ("present_value", "payment"),
    "valuation_scenarios": ("amount", None),
}
MAX_COUNTERFACTUAL_YEARS = 30
# Logged when a calculation's currency has no close against the dollar, so the
# backtest handoff is withheld rather than run in the wrong currency.
NO_DOLLAR_RATE_REASON_CODE = "market_counterfactual_no_dollar_rate"


def market_counterfactual_rows(
    card: Mapping[str, Any],
    *,
    language: str,
    subjects: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any] | None:
    """One row when a computed card states the reader's own amount and a horizon
    in whole years.

    A starting amount becomes a buy-and-hold test; a monthly payment with no
    starting amount becomes a monthly-buy test of the same payment. The amount is
    one the reader stated, never a looked-up or assumed figure. A loan offers no
    row, and neither does a plan with both a starting amount and deposits, stated
    or solved. The asset is the card's own symbol, named as the answer's subjects
    name it, else the market. The test runs in dollars: another currency is
    converted at the pair's latest close, and with no close against the dollar
    there is no row."""
    arguments = card.get("arguments") or {}
    money = _READER_MONEY.get(str(card.get("tool_name") or ""))
    if money is None or arguments.get("direction") == "borrow":
        return None
    start, deposit = money
    solved = (card.get("outcome") or {}).get("result") or {}
    amount = _positive(arguments.get(start))
    starts = amount is not None or _positive(solved.get(start)) is not None
    if (
        starts
        and deposit is not None
        and (
            _positive(arguments.get(deposit)) is not None
            or _positive(solved.get(deposit)) is not None
        )
    ):
        return None
    years = _years(arguments)
    payment = _monthly_payment(arguments, deposit)
    if amount is not None and not _stated(card, start):
        amount = None
    if payment is not None and deposit is not None and not _stated(card, deposit):
        payment = None
    if years is None or (amount is None and payment is None):
        return None
    currency = str(arguments.get("currency") or "USD").strip().upper()
    rate = dollar_rate(currency)
    stated_amount = amount if amount is not None else payment
    assert stated_amount is not None
    if rate is None or round(stated_amount * rate[0]) < 1:
        logger.info(
            "Market counterfactual withheld: no dollar amount currency={}",
            currency,
            failure_classification=NO_DOLLAR_RATE_REASON_CODE,
        )
        return None
    dollars = stated_amount * rate[0]
    spanish = language.startswith("es")
    asset = _asset(arguments, subjects)
    symbol = asset["symbol"]
    period = _last_years(years, spanish=spanish)
    stated = _money(dollars, "USD", grouped=True)
    plain = _money(dollars, "USD", grouped=False)
    conversion = _conversion(stated_amount, currency, rate, spanish=spanish)
    if amount is not None:
        tail = (
            f" con {stated}{conversion} {period}"
            if spanish
            else f" with {stated}{conversion} {period}"
        )
        send_text = (
            f"Prueba comprar y mantener {symbol} con {plain} {period}"
            if spanish
            else f"Test buying and holding {symbol} with {plain} {period}"
        )
    else:
        tail = (
            f" comprando {stated} cada mes{conversion} {period}"
            if spanish
            else f" buying {stated} every month{conversion} {period}"
        )
        send_text = (
            f"Prueba comprar {plain} de {symbol} cada mes {period}"
            if spanish
            else f"Test buying {plain} of {symbol} every month {period}"
        )
    parts = [
        {"type": "text", "value": "Probar " if spanish else "Test "},
        *asset_label_parts([dict(asset)]),
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
    """The amount to the cent, with no cents shown when it is whole, so the test
    runs with the capital the calculation used."""
    cents = round(amount, 2)
    decimals = 0 if cents == round(cents) else 2
    figure = f"{cents:,.{decimals}f}" if grouped else f"{cents:.{decimals}f}"
    return f"{figure} {currency}".strip()


def dollar_rate(currency: str) -> tuple[float, str] | None:
    """US dollars per unit of a currency and the close's date, from Argus's own
    market data; a dollar is 1. None when no pair with the dollar is carried."""
    from argus.domain.market_data.assets import FIAT_CODES

    if currency == "USD":
        return 1.0, ""
    if currency not in FIAT_CODES:
        return None
    from argus.agent_runtime.answer_calculation import latest_market_close

    direct = latest_market_close(f"{currency}USD")
    if direct is not None and direct[0] > 0:
        return direct
    inverse = latest_market_close(f"USD{currency}")
    if inverse is not None and inverse[0] > 0:
        return 1.0 / inverse[0], inverse[1]
    return None


def _conversion(
    amount: float, currency: str, rate: tuple[float, str], *, spanish: bool
) -> str:
    """The amount as stated, the rate and its date; nothing for dollars."""
    if currency == "USD":
        return ""
    per_unit, as_of = rate
    original = _money(amount, currency, grouped=True)
    if spanish:
        return f" ({original} a {per_unit:.4g} USD por {currency} el {as_of})"
    return f" ({original} at {per_unit:.4g} USD per {currency} on {as_of})"


def _last_years(years: int, *, spanish: bool) -> str:
    if spanish:
        return (
            "durante el último año" if years == 1 else f"durante los últimos {years} años"
        )
    return "over the last year" if years == 1 else f"over the last {years} years"


def _monthly_payment(arguments: Mapping[str, Any], field: str | None) -> float | None:
    if field is None or arguments.get("periods_per_year", 12) != 12:
        return None
    return _positive(arguments.get(field))


def _positive(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _stated(card: Mapping[str, Any], field: str) -> bool:
    """Whether the card shows this input as a figure the reader stated."""
    inputs = (card.get("presentation") or {}).get("inputs") or []
    source = next(
        (fact.get("source") or {} for fact in inputs if fact.get("name") == field), {}
    )
    return source.get("kind") == "user"


def _asset(
    arguments: Mapping[str, Any], subjects: Sequence[Mapping[str, str]]
) -> Mapping[str, str]:
    """The card's own security, named as the answer's subjects name it; the
    market proxy when the card names none."""
    symbol = str(arguments.get("symbol") or "").strip().upper()
    if not symbol:
        return MARKET_PROXY
    return next(
        (
            subject
            for subject in subjects
            if str(subject.get("symbol") or "").strip().upper() == symbol
        ),
        {"symbol": symbol, "name": ""},
    )


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
