from __future__ import annotations

import pytest
from argus.domain.indicators import (
    detect_executable_indicator_key,
    executable_indicator_spec,
    indicator_assumption_lines,
    normalize_indicator_parameters,
    search_indicators,
)


def test_rsi_has_executable_spec_with_bounds_defaults_and_formatting() -> None:
    spec = executable_indicator_spec("relative strength index")

    assert spec is not None
    assert spec.key == "rsi"
    assert spec.default_period == 14
    assert spec.output_selector == "RSI_{period}"
    assert spec.threshold_min == 0
    assert spec.threshold_max == 100
    assert spec.format_threshold_rule("entry", threshold=25, period=10) == (
        "Buy when RSI(10) drops to 25 or below"
    )
    assert spec.format_threshold_rule("exit", threshold=60, period=10) == (
        "Sell when RSI(10) rises to 60 or above"
    )


def test_sma_and_ema_have_executable_specs_with_warmup_metadata() -> None:
    sma = executable_indicator_spec("simple moving average")
    ema = executable_indicator_spec("ema")

    assert sma is not None
    assert sma.key == "sma"
    assert sma.default_period == 20
    assert sma.warmup_bars == 20
    assert sma.required_columns == ("close",)
    assert sma.category == "trend"

    assert ema is not None
    assert ema.key == "ema"
    assert ema.default_period == 20
    assert ema.warmup_bars == 20
    assert ema.required_columns == ("close",)
    assert ema.category == "trend"


def test_discovered_indicators_remain_draft_only_without_execution_spec() -> None:
    result = search_indicators("average true range")[0]

    assert executable_indicator_spec("atr") is None
    assert result.key == "atr"
    assert result.support_status == "draft_only"


def test_macd_and_bollinger_have_executable_output_schemas() -> None:
    macd = executable_indicator_spec("moving average convergence divergence")
    bbands = executable_indicator_spec("bollinger bands")

    assert macd is not None
    assert macd.key == "macd"
    assert macd.support_status == "executable"
    assert macd.default_parameters["fast"] == 12
    assert macd.default_parameters["slow"] == 26
    assert macd.default_parameters["signal"] == 9
    assert macd.output_roles["macd"] == "MACD_{fast}_{slow}_{signal}"
    assert macd.output_roles["signal"] == "MACDs_{fast}_{slow}_{signal}"

    assert bbands is not None
    assert bbands.key == "bbands"
    assert bbands.support_status == "executable"
    assert bbands.default_parameters["length"] == 20
    assert bbands.default_parameters["std"] == 2.0
    assert bbands.output_roles["lower"] == "BBL_{length}_{std}"
    assert bbands.output_roles["middle"] == "BBM_{length}_{std}"
    assert bbands.output_roles["upper"] == "BBU_{length}_{std}"


def test_normalize_indicator_parameters_accepts_aliases_and_defaults() -> None:
    params = normalize_indicator_parameters(
        "rsi",
        {"rsi_period": "10", "buy_threshold": "25", "sell_threshold": "60"},
    )

    assert params == {
        "indicator": "rsi",
        "indicator_period": 10,
        "entry_threshold": 25.0,
        "exit_threshold": 60.0,
    }
    assert indicator_assumption_lines(params) == [
        "Indicator: RSI(10).",
        "Buy threshold: RSI at or below 25.",
        "Exit threshold: RSI at or above 60.",
    ]
    assert detect_executable_indicator_key("relative strength index below 30") == "rsi"


def test_normalize_indicator_parameters_rejects_out_of_bounds_thresholds() -> None:
    with pytest.raises(ValueError, match="indicator_threshold_out_of_bounds"):
        normalize_indicator_parameters("rsi", {"entry_threshold": 120})
