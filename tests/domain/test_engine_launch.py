from __future__ import annotations

import pytest
import pandas as pd

from argus.domain.engine import _build_signals
from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)


def test_launch_request_supports_three_strategy_types() -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    dca_request = LaunchBacktestRequest(
        strategy_type="dca_accumulation",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=500.0,
        position_size=None,
        cadence="monthly",
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    threshold_request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={"indicator": "rsi", "operator": "below", "threshold": 30},
        exit_rule={"indicator": "rsi", "operator": "above", "threshold": 55},
        sizing_mode="position_size",
        capital_amount=None,
        position_size=10.0,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    assert request.strategy_type == "buy_and_hold"
    assert request.cadence is None
    assert dca_request.strategy_type == "dca_accumulation"
    assert dca_request.cadence == "monthly"
    assert threshold_request.strategy_type == "indicator_threshold"


def test_launch_request_requires_matching_sizing_field() -> None:
    with pytest.raises(ValueError, match="capital_amount_required"):
        LaunchBacktestRequest(
            strategy_type="buy_and_hold",
            symbol="TSLA",
            timeframe="1D",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            entry_rule=None,
            exit_rule=None,
            sizing_mode="capital_amount",
            capital_amount=None,
            position_size=None,
            cadence=None,
            parameters={},
            risk_rules=[],
            benchmark_symbol="SPY",
        )

    with pytest.raises(ValueError, match="capital_amount_not_applicable"):
        LaunchBacktestRequest(
            strategy_type="buy_and_hold",
            symbol="TSLA",
            timeframe="1D",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            entry_rule=None,
            exit_rule=None,
            sizing_mode="position_size",
            capital_amount=10000.0,
            position_size=10.0,
            cadence=None,
            parameters={},
            risk_rules=[],
            benchmark_symbol="SPY",
        )


def test_launch_request_limits_cadence_to_dca() -> None:
    with pytest.raises(ValueError, match="cadence_required"):
        LaunchBacktestRequest(
            strategy_type="dca_accumulation",
            symbol="TSLA",
            timeframe="1D",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            entry_rule=None,
            exit_rule=None,
            sizing_mode="capital_amount",
            capital_amount=500.0,
            position_size=None,
            cadence=None,
            parameters={},
            risk_rules=[],
            benchmark_symbol="SPY",
        )

    with pytest.raises(ValueError, match="cadence_not_applicable"):
        LaunchBacktestRequest(
            strategy_type="buy_and_hold",
            symbol="TSLA",
            timeframe="1D",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            entry_rule=None,
            exit_rule=None,
            sizing_mode="capital_amount",
            capital_amount=10000.0,
            position_size=None,
            cadence="weekly",
            parameters={},
            risk_rules=[],
            benchmark_symbol="SPY",
        )


def test_launch_envelope_carries_card_and_explanation_fields() -> None:
    envelope = LaunchExecutionEnvelope(
        execution_status="succeeded",
        resolved_strategy={"strategy_type": "buy_and_hold", "symbol": "TSLA"},
        resolved_parameters={"timeframe": "1D"},
        metrics={"total_return_pct": 12.5},
        benchmark_metrics={"total_return_pct": 9.2},
        assumptions=["Starting capital: $10,000."],
        caveats=["Daily bars only."],
        artifact_references=[],
        provider_metadata={"provider": "alpaca"},
    )

    assert envelope.execution_status == "succeeded"
    assert envelope.metrics["total_return_pct"] == 12.5
    assert envelope.provider_metadata["provider"] == "alpaca"


def test_buy_and_hold_adapter_returns_envelope_card_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 12.5,
                    "benchmark_return_pct": 9.2,
                }
            },
            "by_symbol": {
                "TSLA": {
                    "performance": {
                        "total_return_pct": 12.5,
                        "benchmark_return_pct": 9.2,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA Buy and Hold",
            "assumptions": ["Starting capital: $10,000."],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_strategy["strategy_type"] == "buy_and_hold"
    assert result.envelope.benchmark_metrics["symbol"] == "SPY"
    assert result.result_card is not None
    assert result.result_card["title"] == "TSLA Buy and Hold"
    assert result.explanation_context is not None
    assert result.explanation_context["strategy_type"] == "buy_and_hold"


def test_buy_and_hold_adapter_converts_position_size_to_capital(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="position_size",
        capital_amount=None,
        position_size=10.0,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_price_series",
        lambda **_: pd.Series([100.0, 101.0]),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 5.0,
                    "benchmark_return_pct": 4.0,
                }
            },
            "by_symbol": {
                "TSLA": {
                    "performance": {
                        "total_return_pct": 5.0,
                        "benchmark_return_pct": 4.0,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA Buy and Hold",
            "assumptions": ["Position sized from opening price."],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["capital_amount"] == 1000.0
    assert result.envelope.resolved_parameters["position_size"] == 10.0


def test_indicator_threshold_adapter_returns_envelope_card_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={"indicator": "rsi", "operator": "below", "threshold": 30},
        exit_rule={"indicator": "rsi", "operator": "above", "threshold": 55},
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 11.0,
                    "benchmark_return_pct": 7.5,
                }
            },
            "by_symbol": {
                "TSLA": {
                    "performance": {
                        "total_return_pct": 11.0,
                        "benchmark_return_pct": 7.5,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA RSI Mean Reversion",
            "assumptions": ["Starting capital: $10,000."],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_strategy["strategy_type"] == "indicator_threshold"
    assert result.envelope.resolved_strategy["entry_rule"] == request.entry_rule
    assert result.envelope.resolved_parameters["template"] == "rsi_mean_reversion"
    assert result.result_card is not None
    assert result.result_card["title"] == "TSLA RSI Mean Reversion"
    assert result.explanation_context is not None
    assert result.explanation_context["strategy_type"] == "indicator_threshold"


def test_adapter_blocks_unsupported_risk_rules() -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[{"type": "stop_loss", "threshold_pct": 5}],
        benchmark_symbol="SPY",
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "blocked_unsupported"
    assert result.envelope.failure_category == "unsupported_capability"
    assert result.envelope.failure_reason == "unsupported_risk_rules"
    assert result.result_card is None


def test_adapter_blocks_unsupported_indicator_threshold_shape() -> None:
    request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={"indicator": "rsi", "operator": "below", "threshold": 25},
        exit_rule={"indicator": "rsi", "operator": "above", "threshold": 60},
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "blocked_unsupported"
    assert result.envelope.failure_category == "unsupported_capability"
    assert result.envelope.failure_reason == "unsupported_indicator_threshold"


def test_adapter_maps_market_data_failure_to_upstream_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="position_size",
        capital_amount=None,
        position_size=10.0,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_price_series",
        lambda **_: (_ for _ in ()).throw(ValueError("market_data_unavailable")),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "failed_upstream"
    assert result.envelope.failure_category == "upstream_dependency_error"


def test_dca_adapter_returns_envelope_card_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="dca_accumulation",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=500.0,
        position_size=None,
        cadence="monthly",
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 8.5,
                    "benchmark_return_pct": 6.0,
                }
            },
            "by_symbol": {
                "TSLA": {
                    "performance": {
                        "total_return_pct": 8.5,
                        "benchmark_return_pct": 6.0,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA DCA Accumulation",
            "assumptions": ["Recurring allocation: $500."],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_strategy["strategy_type"] == "dca_accumulation"
    assert result.envelope.resolved_parameters["cadence"] == "monthly"
    assert result.result_card is not None
    assert result.result_card["title"] == "TSLA DCA Accumulation"
    assert result.explanation_context is not None
    assert result.explanation_context["strategy_type"] == "dca_accumulation"


def test_dca_adapter_supports_quarterly_cadence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="dca_accumulation",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=500.0,
        position_size=None,
        cadence="quarterly",
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 7.0,
                    "benchmark_return_pct": 5.5,
                }
            },
            "by_symbol": {
                "TSLA": {
                    "performance": {
                        "total_return_pct": 7.0,
                        "benchmark_return_pct": 5.5,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA DCA Accumulation",
            "assumptions": ["Recurring allocation: $500."],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["cadence"] == "quarterly"
    assert result.envelope.caveats[-1].startswith(
        "Recurring entries use the first available bar"
    )


def test_build_signals_supports_quarterly_dca_cadence() -> None:
    index = pd.date_range("2024-01-02", periods=8, freq="MS")
    data = pd.DataFrame({"close": [100, 101, 102, 103, 104, 105, 106, 107]}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "quarterly"},
    }

    entries, exits = _build_signals(config, data)

    assert entries.tolist() == [True, False, False, True, False, False, True, False]
    assert exits.tolist() == [False] * len(index)
