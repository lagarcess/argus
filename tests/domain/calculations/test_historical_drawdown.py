"""Historical risk uses provider closes, never an answer's numbers."""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest
from argus.domain.calculations.historical_drawdown import (
    HistoricalDrawdownArguments,
    get_historical_drawdown_declaration,
)
from argus.domain.market_data import historical_drawdown as history
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.tool_contracts import ToolCall
from pydantic import ValidationError

START = date(2024, 1, 2)
END = date(2024, 1, 8)
DATES = pd.bdate_range(START, END, tz="UTC")


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    resolve = Mock(return_value=ResolvedAsset("BTC", "crypto", "Bitcoin", "BTC/USD"))
    fetch = Mock(return_value=pd.Series([100, 120, 90, 60, 110], index=DATES))
    monkeypatch.setattr(history, "resolve_asset", resolve)
    monkeypatch.setattr("argus.domain.market_data.provider.fetch_price_series", fetch)
    monkeypatch.setattr(history, "new_york_today", lambda: date(2026, 9, 14))
    return resolve, fetch


def arguments(**changes):
    return {
        "symbol": "BTC",
        "start_date": START.isoformat(),
        "end_date": END.isoformat(),
        **changes,
    }


def test_reports_worst_peak_to_trough_with_actual_window_and_market_source(provider):
    declaration = get_historical_drawdown_declaration()
    outcome = declaration.invoke_sync(arguments())
    assert outcome.status == "succeeded", outcome
    result = outcome.result
    assert result["max_drawdown_pct"] == pytest.approx(-50)
    assert result["peak_date"] == DATES[1].date().isoformat()
    assert result["trough_date"] == DATES[3].date().isoformat()
    assert result["observed_start_date"] == START.isoformat()
    assert result["observed_end_date"] == END.isoformat()
    assert result["observations"] == len(DATES)
    assert result["source"] == "argus_market_data"
    card = declaration.result_card(
        call=ToolCall(
            tool_name=declaration.name, call_id="drawdown", arguments=arguments()
        ),
        outcome=outcome,
        artifact_id="risk",
    )
    assert card.presentation.answer.value == -50
    assert card.presentation.answer.source.kind == "market_data"
    assert card.presentation.answer.source.date == END.isoformat()
    assert not any(item.editable for item in card.presentation.inputs)
    assert declaration.policy.execution == "provider"
    assert declaration.policy.external_calls == 1
    provider[1].assert_called_once_with(
        symbol="BTC", asset_class="crypto", start_date=START, end_date=END, timeframe="1D"
    )


def test_shorter_available_window_is_reported_without_claiming_all_history(provider):
    provider[1].return_value = provider[1].return_value.iloc[1:-1]
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments())
    assert outcome.status == "succeeded"
    assert outcome.result["observed_start_date"] == DATES[1].date().isoformat()
    assert outcome.result["observed_end_date"] == DATES[-2].date().isoformat()
    assert outcome.result["requested_start_date"] == START.isoformat()


@pytest.mark.parametrize("values", [[100, 100, 100, 100, 100], [100, 110, 120, 130, 140]])
def test_no_drop_has_zero_drawdown_and_no_invented_drawdown_dates(provider, values):
    provider[1].return_value = pd.Series(values, index=DATES)
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments())
    assert outcome.status == "succeeded"
    assert outcome.result["max_drawdown_pct"] == 0
    assert outcome.result["peak_date"] is None
    assert outcome.result["trough_date"] is None


@pytest.mark.parametrize(
    "values", [[], [100], [100, 0], [100, -5], [100, float("nan")], [100, float("inf")]]
)
def test_insufficient_or_invalid_prices_cannot_be_a_zero_risk_answer(provider, values):
    provider[1].return_value = pd.Series(values, index=DATES[: len(values)], dtype=float)
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments())
    assert outcome.status == "unavailable"
    assert outcome.result is None


def test_provider_outage_has_no_numerical_answer(provider):
    provider[1].side_effect = ValueError("market_data_unavailable")
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments())
    assert outcome.status == "unavailable"
    assert outcome.result is None


@pytest.mark.parametrize(
    "changes", [{"end_date": "2027-01-01"}, {"end_date": "2024-01-01"}]
)
def test_invalid_window_does_not_fetch(provider, changes):
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments(**changes))
    assert outcome.status == "invalid"
    provider[1].assert_not_called()


def test_default_window_is_bounded_and_excludes_today(provider):
    outcome = get_historical_drawdown_declaration().invoke_sync(
        arguments(start_date=None, end_date=None)
    )
    assert outcome.status == "succeeded"
    assert outcome.result["default_window"] is True
    requested = provider[1].call_args.kwargs
    assert requested["end_date"] == date(2026, 9, 13)
    assert requested["start_date"] == date(2021, 9, 13)


def test_model_or_research_price_arrays_are_not_accepted():
    with pytest.raises(ValidationError):
        HistoricalDrawdownArguments.model_validate(arguments(prices=[100, 50]))


def test_historical_provider_calculation_has_no_automatic_decision_kernel():
    from argus.domain.computations import kernel_for

    assert kernel_for("historical_drawdown") is None


def test_synthetic_fixture_never_becomes_historical_risk(provider, monkeypatch):
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments())
    assert outcome.status == "unavailable"
    provider[0].assert_not_called()
    provider[1].assert_not_called()


def test_provider_currency_pair_window_limit_fails_before_fetch(provider):
    provider[0].return_value = ResolvedAsset(
        "EURUSD", "currency_pair", "Euro / Dollar", "EURUSD"
    )
    outcome = get_historical_drawdown_declaration().invoke_sync(
        arguments(start_date=None, end_date=None)
    )
    assert outcome.status == "unavailable"
    assert outcome.failure.code == "kraken_ohlc_window_exceeded"
    provider[1].assert_not_called()


def test_declaration_is_in_the_answer_catalog():
    from argus.domain.calculations import get_calculation_declarations

    assert "historical_drawdown" in {item.name for item in get_calculation_declarations()}


def test_missing_symbol_is_invalid_without_provider_work(provider):
    request = arguments()
    request.pop("symbol")
    outcome = get_historical_drawdown_declaration().invoke_sync(request)
    assert outcome.status == "invalid"
    provider[0].assert_not_called()
    provider[1].assert_not_called()


def test_equity_history_records_the_shared_providers_split_adjusted_close_basis(provider):
    provider[0].return_value = ResolvedAsset("AAPL", "equity", "Apple", "AAPL")
    outcome = get_historical_drawdown_declaration().invoke_sync(arguments(symbol="AAPL"))
    assert outcome.status == "succeeded"
    assert outcome.result["price_basis"] == "split_adjusted_close"


def test_drawdown_has_no_currency_input_or_conversion_claim():
    schema = HistoricalDrawdownArguments.model_json_schema()
    assert set(schema["properties"]) == {"sources", "symbol", "start_date", "end_date"}
    assert schema["additionalProperties"] is False
    assert get_historical_drawdown_declaration().policy.ends_answer is True
    with pytest.raises(ValidationError):
        HistoricalDrawdownArguments.model_validate({**arguments(), "currency": "DOP"})
