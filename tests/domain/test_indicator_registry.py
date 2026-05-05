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


def test_discovered_indicators_remain_draft_only_without_execution_spec() -> None:
    result = search_indicators("moving average convergence divergence")[0]

    assert executable_indicator_spec("macd") is None
    assert result.key == "macd"
    assert result.support_status == "draft_only"


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
