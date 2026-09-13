"""A backtest handoff under a computed answer states dollars and converts in prose."""

from __future__ import annotations

from argus.agent_runtime import answer_calculation
from argus.agent_runtime.calculation_rows import market_counterfactual_rows


def _row(arguments: dict, language: str = "en") -> dict:
    rows = market_counterfactual_rows(arguments, language=language)
    assert rows is not None
    return rows["rows"][0]


def _closes(monkeypatch, closes: dict[str, tuple[float, str]]) -> list[str]:
    asked: list[str] = []

    def close(symbol: str) -> tuple[float, str] | None:
        asked.append(symbol)
        return closes.get(symbol)

    monkeypatch.setattr(answer_calculation, "latest_market_close", close)
    return asked


def test_a_dollar_amount_is_offered_as_stated_with_no_lookup(monkeypatch) -> None:
    asked = _closes(monkeypatch, {})

    row = _row({"present_value": 10000, "years": 10, "currency": "USD"})

    assert row["label"] == "Test S&P 500 (SPY) with 10,000 USD over the last 10 years"
    assert row["send_text"] == (
        "Test buying and holding SPY with 10000 USD over the last 10 years"
    )
    assert asked == []


def test_one_year_reads_as_the_last_year_in_both_languages(monkeypatch) -> None:
    _closes(monkeypatch, {})
    arguments = {"present_value": 500, "years": 1, "currency": "USD"}

    assert _row(arguments)["send_text"] == (
        "Test buying and holding SPY with 500 USD over the last year"
    )
    spanish = _row(arguments, "es-419")
    assert spanish["send_text"] == (
        "Prueba comprar y mantener SPY con 500 USD durante el último año"
    )
    assert spanish["label"] == "Probar S&P 500 (SPY) con 500 USD durante el último año"


def test_another_currency_is_converted_at_the_pairs_close_and_the_label_says_so(
    monkeypatch,
) -> None:
    _closes(monkeypatch, {"EURUSD": (1.084, "2026-09-11")})

    row = _row({"present_value": 1000, "years": 5, "currency": "EUR"}, "es-419")

    assert row["label"] == (
        "Probar S&P 500 (SPY) con 1,084 USD (1,000 EUR a 1.084 USD por EUR el "
        "2026-09-11) durante los últimos 5 años"
    )
    assert row["send_text"] == (
        "Prueba comprar y mantener SPY con 1084 USD durante los últimos 5 años"
    )


def test_a_pair_quoted_as_dollars_first_is_inverted(monkeypatch) -> None:
    asked = _closes(monkeypatch, {"USDJPY": (147.0, "2026-09-11")})

    row = _row({"payment": 30000, "periods_per_year": 12, "years": 5, "currency": "JPY"})

    assert row["label"] == (
        "Test S&P 500 (SPY) buying 204 USD every month (30,000 JPY at 0.006803 USD "
        "per JPY on 2026-09-11) over the last 5 years"
    )
    assert (
        row["send_text"] == "Test buying 204 USD of SPY every month over the last 5 years"
    )
    assert asked == ["JPYUSD", "USDJPY"]


def test_a_currency_with_no_close_against_the_dollar_offers_no_test(monkeypatch) -> None:
    asked = _closes(monkeypatch, {})

    for arguments in (
        {"present_value": 100, "periods": 12, "currency": "DOP"},
        {"present_value": 1000, "years": 3, "currency": "EUR"},
    ):
        assert market_counterfactual_rows(arguments, language="es-419") is None

    assert asked == ["EURUSD", "USDEUR"]
