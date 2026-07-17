from __future__ import annotations

import warnings
from collections import Counter
from typing import Any

import pandas as pd
import pytest
from argus.domain.backtesting.coverage import _dataset_id
from argus.domain.engine import _build_signals
from argus.domain.engine_launch.adapter import (
    _provider_metadata,
    _resolve_request_symbols,
    run_launch_backtest,
)
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)
from argus.domain.engine_launch.results import user_safe_failure_message
from argus.domain.engine_launch.strategies import validate_launch_supported


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


@pytest.mark.parametrize(
    "strategy_type",
    [
        "buy_and_hold",
        "dca_accumulation",
        "indicator_threshold",
        "signal_strategy",
    ],
)
def test_launch_validation_rejects_unsupported_timeframe_for_every_strategy(
    strategy_type: str,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type=strategy_type,
        symbol="AAPL",
        symbols=["AAPL"],
        asset_class="equity",
        timeframe="5m",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10_000.0,
        position_size=None,
        cadence="monthly" if strategy_type == "dca_accumulation" else None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    with pytest.raises(ValueError, match="unsupported_timeframe"):
        validate_launch_supported(request)


def test_approved_launch_uses_one_prepared_dataset_for_metrics_and_chart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Counter[str] = Counter()
    index = pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"], utc=True)
    close = pd.Series([100.0, 101.0, 102.0], index=index)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )

    def fake_fetch(symbol: str, **_: Any) -> pd.DataFrame:
        calls[symbol] += 1
        return bars.copy(deep=True)

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_ohlcv",
        fake_fetch,
    )
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="AAPL",
        symbols=["AAPL"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2024-01-03", "end": "2024-01-05"},
        requested_date_range={"start": "2024-01-01", "end": "2024-01-05"},
        coverage_preflight={
            "outcome": "adjusted_coverage",
            "requested_date_range": {
                "start": "2024-01-01",
                "end": "2024-01-05",
            },
            "effective_date_range": {
                "start": "2024-01-03",
                "end": "2024-01-05",
            },
            "preflight_id": _dataset_id({"AAPL": bars, "SPY": bars}),
        },
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10_000,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert calls == Counter({"AAPL": 1, "SPY": 1})
    resolved = result.envelope.resolved_parameters
    assert resolved["requested_date_range"] == {
        "start": "2024-01-01",
        "end": "2024-01-05",
    }
    assert resolved["effective_date_range"] == {
        "start": "2024-01-03",
        "end": "2024-01-05",
    }
    assert resolved["engine_config"]["data_coverage"]["dataset_id"].startswith("sha256:")
    assert result.result_card is not None
    assert result.result_card["chart"]["series"][0]["time"] == "2024-01-03"
    assert result.result_card["chart"]["series"][-1]["time"] == "2024-01-05"

    from argus.domain.backtest_run_builder import build_backtest_run_from_result

    run = build_backtest_run_from_result(
        conversation_id="conversation-effective-window",
        result_card=result.result_card,
        envelope=result.envelope.model_dump(mode="python"),
        run_id_factory=lambda: "run-effective-window",
        classify_symbol_func=lambda _symbol: type(
            "ResolvedAsset", (), {"asset_class": "equity"}
        )(),
        default_benchmark_func=lambda _asset_class, _symbols: "SPY",
    )
    assert run is not None
    assert run.config_snapshot["requested_date_range"] == {
        "start": "2024-01-01",
        "end": "2024-01-05",
    }
    assert run.config_snapshot["effective_date_range"] == {
        "start": "2024-01-03",
        "end": "2024-01-05",
    }


def test_approved_launch_reuses_canonical_benchmark_alias_without_duplicate_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: Counter[str] = Counter()
    index = pd.to_datetime(
        ["2024-01-03", "2024-01-04", "2024-01-05"],
        utc=True,
    )
    close = pd.Series([100.0, 101.0, 102.0], index=index)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )

    def fake_fetch(symbol: str, **_: Any) -> pd.DataFrame:
        calls[symbol] += 1
        return bars.copy(deep=True)

    def classify_stub(symbol: str):
        canonical = "BTC" if symbol in {"BTC", "BTC/USD"} else symbol
        return type(
            "ResolvedAsset",
            (),
            {
                "canonical_symbol": canonical,
                "asset_class": "crypto",
                "symbol": canonical,
            },
        )()

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        classify_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_ohlcv",
        fake_fetch,
    )
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="ETH",
        symbols=["ETH"],
        asset_class="crypto",
        timeframe="1D",
        date_range={"start": "2024-01-03", "end": "2024-01-05"},
        requested_date_range={"start": "2024-01-03", "end": "2024-01-05"},
        coverage_preflight={
            "outcome": "full_coverage",
            "requested_date_range": {
                "start": "2024-01-03",
                "end": "2024-01-05",
            },
            "effective_date_range": {
                "start": "2024-01-03",
                "end": "2024-01-05",
            },
            "preflight_id": _dataset_id({"ETH": bars, "BTC": bars}),
        },
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1_000,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="BTC/USD",
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["benchmark_symbol"] == "BTC"
    assert calls == Counter({"ETH": 1, "BTC": 1})


def test_approved_launch_preserves_transient_market_data_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = {"start": "2024-01-01", "end": "2024-01-05"}
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="AAPL",
        symbols=["AAPL"],
        asset_class="equity",
        timeframe="1D",
        date_range=requested,
        requested_date_range=requested,
        coverage_preflight={
            "outcome": "full_coverage",
            "requested_date_range": requested,
            "effective_date_range": requested,
            "preflight_id": "sha256:approved-window",
        },
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=10_000,
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
        "argus.domain.engine_launch.adapter.fetch_ohlcv",
        lambda **_: (_ for _ in ()).throw(ValueError("provider timeout")),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "failed_upstream"
    assert result.envelope.failure_category == "upstream_dependency_error"
    assert result.envelope.failure_reason == "market_data_unavailable"


@pytest.mark.parametrize(
    "failure_category",
    [
        "missing_required_input",
        "parameter_validation_error",
        "upstream_dependency_error",
        "unexpected_failure",
    ],
)
def test_user_safe_failure_messages_do_not_expose_draft_language(
    failure_category: str,
) -> None:
    message = user_safe_failure_message(
        failure_reason=None,
        failure_category=failure_category,
    )

    assert "draft" not in message.lower()
    assert "setup" in message.lower() or "detail" in message.lower()


def test_launch_request_supports_signal_strategy_with_rule_spec() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "gt",
                    "right": {"kind": "indicator", "key": "ema", "period": 20},
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "lt",
                    "right": {"kind": "indicator", "key": "ema", "period": 20},
                }
            ]
        },
    }

    request = LaunchBacktestRequest(
        strategy_type="signal_strategy",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        rule_spec=rule_spec,
        sizing_mode="capital_amount",
        capital_amount=10000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    assert request.strategy_type == "signal_strategy"
    assert request.rule_spec == rule_spec


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
        cadence="biweekly",
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    assert request.cadence == "biweekly"

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


def test_provider_metadata_distinguishes_market_data_sources() -> None:
    assert _provider_metadata(asset_class="equity", timeframe="1D") == {
        "provider": "alpaca",
        "asset_class": "equity",
        "timeframe": "1D",
        "feed": "iex",
    }
    assert _provider_metadata(asset_class="currency_pair", timeframe="1h") == {
        "provider": "kraken",
        "asset_class": "currency_pair",
        "timeframe": "1h",
    }
    crypto_metadata = _provider_metadata(asset_class="crypto", timeframe="1D")
    assert crypto_metadata["provider"] == "alpaca"
    assert crypto_metadata["fallback_provider"] == "kraken"
    assert crypto_metadata["source_policy"] == "alpaca_crypto_with_kraken_fallback"


def test_launch_request_explicit_asset_class_still_uses_provider_canonical_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="BTC/USD",
        symbols=["btc/usd"],
        asset_class="crypto",
        timeframe="1D",
        date_range={"start": "2026-01-01", "end": "2026-06-03"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    def classify_symbol_stub(symbol: str):
        assert symbol == "BTC/USD"
        return type(
            "ResolvedAsset",
            (),
            {
                "canonical_symbol": "BTC",
                "asset_class": "crypto",
                "symbol": "BTC",
            },
        )()

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        classify_symbol_stub,
    )

    symbols, asset_class = _resolve_request_symbols(request)

    assert symbols == ["BTC"]
    assert asset_class == "crypto"


def test_launch_request_explicit_asset_class_rejects_provider_class_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="CVX",
        symbols=["CVX"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2026-01-01", "end": "2026-06-03"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="SPY",
    )

    def classify_symbol_stub(symbol: str):
        return type(
            "ResolvedAsset",
            (),
            {
                "canonical_symbol": symbol,
                "asset_class": "crypto",
                "symbol": symbol,
            },
        )()

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        classify_symbol_stub,
    )

    with pytest.raises(ValueError, match="asset_class_conflict"):
        _resolve_request_symbols(request)


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
        lambda config, **_: {
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


def test_buy_and_hold_adapter_propagates_explicit_benchmark_to_card_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="AAPL",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="QQQ",
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
        lambda config, **_: {
            "aggregate": {
                "performance": {
                    "profit": 350.0,
                    "total_return_pct": 35.0,
                    "benchmark_return_pct": 26.9,
                    "delta_vs_benchmark_pct": 8.1,
                },
                "risk": {"max_drawdown_pct": -15.5},
                "efficiency": {"total_trades": 1, "win_rate": 1.0},
            },
            "by_symbol": {
                "AAPL": {
                    "performance": {
                        "total_return_pct": 35.0,
                        "benchmark_return_pct": 26.9,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_chart",
        lambda config: None,
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["benchmark_symbol"] == "QQQ"
    assert result.envelope.benchmark_metrics["symbol"] == "QQQ"
    assert result.result_card is not None
    assert result.result_card["rows"][0]["value"] == "$1,000 -> $1,350"
    assert result.result_card["rows"][2]["label"] == "Compared with QQQ"
    assert result.result_card["rows"][2]["value"] == "Beat by 8.1 percentage points"
    assert "Benchmark: QQQ" in result.result_card["assumptions"]
    assert result.explanation_context is not None
    assert result.explanation_context["benchmark_symbol"] == "QQQ"


def test_launch_envelope_carries_replayable_engine_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="AAPL",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="QQQ",
    )
    seen_configs: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )

    def fake_compute_alpha_metrics(config: dict[str, Any], **_: Any) -> dict[str, Any]:
        seen_configs.append(dict(config))
        return {
            "aggregate": {
                "performance": {
                    "profit": 350.0,
                    "total_return_pct": 35.0,
                    "benchmark_return_pct": 26.9,
                    "delta_vs_benchmark_pct": 8.1,
                },
                "risk": {"max_drawdown_pct": -15.5},
                "efficiency": {"total_trades": 1, "win_rate": 1.0},
            },
            "by_symbol": {
                "AAPL": {
                    "performance": {
                        "total_return_pct": 35.0,
                        "benchmark_return_pct": 26.9,
                    }
                }
            },
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        fake_compute_alpha_metrics,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_chart",
        lambda config: None,
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert seen_configs
    assert result.envelope.resolved_parameters["engine_config"] == seen_configs[0]


def test_launch_adapter_propagates_execution_realism_to_engine_config_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    request = LaunchBacktestRequest.model_validate(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "AAPL",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 1000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "_execution_realism": {
                "enabled": True,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
            },
        }
    )
    seen_configs: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )

    def fake_compute_alpha_metrics(config: dict[str, Any], **_: Any) -> dict[str, Any]:
        seen_configs.append(dict(config))
        return {
            "aggregate": {
                "performance": {
                    "profit": 350.0,
                    "total_return_pct": 35.0,
                    "benchmark_return_pct": 26.9,
                    "delta_vs_benchmark_pct": 8.1,
                },
                "risk": {"max_drawdown_pct": -15.5},
                "efficiency": {"total_trades": 1, "win_rate": 1.0},
            },
            "by_symbol": {
                "AAPL": {
                    "performance": {
                        "total_return_pct": 35.0,
                        "benchmark_return_pct": 26.9,
                    }
                }
            },
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        fake_compute_alpha_metrics,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_chart",
        lambda config: None,
    )

    result = run_launch_backtest(request)

    assert request.execution_realism == {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }
    assert seen_configs[0]["_execution_realism"] == {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }
    assert result.envelope.resolved_parameters["engine_config"] == seen_configs[0]


def test_persisted_config_snapshot_replays_key_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timezone

    from argus.domain.backtest_run_builder import build_backtest_run_from_result
    from argus.domain.engine import compute_alpha_metrics

    index = pd.date_range("2025-01-01", periods=7, freq="D", tz="UTC")
    bars_by_symbol = {
        "AAPL": pd.DataFrame(
            {"close": [100.0, 102.0, 104.0, 103.0, 106.0, 109.0, 111.0]},
            index=index,
        ),
        "SPY": pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 102.5, 103.0, 104.0, 105.0]},
            index=index,
        ),
    }

    def fake_fetch_ohlcv(**kwargs: Any) -> pd.DataFrame:
        symbol = str(kwargs["symbol"]).strip().upper()
        return bars_by_symbol[symbol].copy(deep=True)

    def fake_fetch_price_series(**kwargs: Any) -> pd.Series:
        symbol = str(kwargs["symbol"]).strip().upper()
        return bars_by_symbol[symbol]["close"].copy(deep=True)

    def fake_classify_symbol(symbol: str):
        normalized = symbol.strip().upper()
        return type(
            "ResolvedAsset",
            (),
            {
                "canonical_symbol": normalized,
                "asset_class": "equity",
                "symbol": normalized,
            },
        )()

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        fake_classify_symbol,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_ohlcv",
        fake_fetch_ohlcv,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.fetch_price_series",
        fake_fetch_price_series,
    )

    result = run_launch_backtest(
        LaunchBacktestRequest(
            strategy_type="buy_and_hold",
            symbol="AAPL",
            timeframe="1D",
            date_range={"start": "2025-01-01", "end": "2025-01-07"},
            entry_rule=None,
            exit_rule=None,
            sizing_mode="capital_amount",
            capital_amount=1000.0,
            position_size=None,
            cadence=None,
            parameters={},
            risk_rules=[],
            benchmark_symbol="SPY",
        )
    )

    assert result.envelope.execution_status == "succeeded"
    assert result.result_card is not None
    run = build_backtest_run_from_result(
        conversation_id="conversation-replay",
        result_card=result.result_card,
        envelope=result.envelope.model_dump(mode="python"),
        run_id_factory=lambda: "run-replay",
        now_func=lambda: datetime(2026, 6, 16, tzinfo=timezone.utc),
        classify_symbol_func=fake_classify_symbol,
        default_benchmark_func=lambda _asset_class, _symbols: "SPY",
    )
    assert run is not None

    replayed = compute_alpha_metrics(
        run.config_snapshot["engine_config"],
        fetch_ohlcv_func=fake_fetch_ohlcv,
        fetch_price_series_func=fake_fetch_price_series,
    )

    original_performance = run.metrics["aggregate"]["performance"]
    replayed_performance = replayed["aggregate"]["performance"]
    for metric_key in (
        "total_return_pct",
        "benchmark_return_pct",
        "delta_vs_benchmark_pct",
    ):
        assert replayed_performance[metric_key] == pytest.approx(
            original_performance[metric_key],
        )
    assert (
        replayed["aggregate"]["efficiency"]["total_trades"]
        == (run.metrics["aggregate"]["efficiency"]["total_trades"])
    )


def test_buy_and_hold_adapter_uses_canonical_benchmark_for_all_result_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="BTC",
        timeframe="1D",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=1000.0,
        position_size=None,
        cadence=None,
        parameters={},
        risk_rules=[],
        benchmark_symbol="ETHUSD",
    )

    def classify_stub(symbol: str):
        normalized = "ETH" if symbol == "ETHUSD" else symbol
        return type(
            "ResolvedAsset",
            (),
            {
                "canonical_symbol": normalized,
                "asset_class": "crypto",
                "symbol": normalized,
            },
        )()

    seen_configs: list[dict[str, object]] = []

    def fake_result_card(config, metrics, language="en", chart=None):
        del metrics, language, chart
        seen_configs.append(config)
        benchmark = str(config["benchmark_symbol"])
        return {
            "title": "BTC Buy and Hold",
            "assumptions": [f"Benchmark: {benchmark}"],
            "rows": [
                {"label": "Ending value", "value": "$1,000 -> $1,100"},
                {"label": "Total return", "value": "+10.0%"},
                {"label": f"Compared with {benchmark}", "value": "Beat by 1.0 point"},
                {"label": "Worst drop", "value": "-5.0%"},
            ],
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        classify_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config, **_: {
            "aggregate": {
                "performance": {
                    "profit": 100.0,
                    "total_return_pct": 10.0,
                    "benchmark_return_pct": 9.0,
                    "delta_vs_benchmark_pct": 1.0,
                },
                "risk": {"max_drawdown_pct": -5.0},
            },
            "by_symbol": {
                "BTC": {
                    "performance": {
                        "total_return_pct": 10.0,
                        "benchmark_return_pct": 9.0,
                    }
                }
            },
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        fake_result_card,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_chart",
        lambda config: None,
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert seen_configs[0]["benchmark_symbol"] == "ETH"
    assert result.envelope.resolved_parameters["benchmark_symbol"] == "ETH"
    assert result.envelope.benchmark_metrics["symbol"] == "ETH"
    assert result.result_card is not None
    assert result.result_card["rows"][2]["label"] == "Compared with ETH"
    assert result.explanation_context is not None
    assert result.explanation_context["benchmark_symbol"] == "ETH"


def test_buy_and_hold_adapter_preserves_multi_symbol_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="SBUX",
        symbols=["SBUX", "CMG"],
        timeframe="1D",
        date_range={"start": "2026-01-01", "end": "2026-05-04"},
        entry_rule=None,
        exit_rule=None,
        sizing_mode="capital_amount",
        capital_amount=100000.0,
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
        lambda config, **_: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 25.0,
                    "benchmark_return_pct": 5.1,
                    "delta_vs_benchmark_pct": 19.9,
                },
                "risk": {"max_drawdown_pct": -14.5},
                "efficiency": {"win_rate": 0.54},
            },
            "by_symbol": {
                "SBUX": {"performance": {"benchmark_return_pct": 5.1}},
                "CMG": {"performance": {"benchmark_return_pct": 5.1}},
            },
        },
    )

    seen_configs: list[dict[str, object]] = []

    def fake_build_result_card(config, metrics, language="en"):
        seen_configs.append(config)
        return {
            "title": "SBUX, CMG Buy and Hold",
            "symbols": config["symbols"],
            "strategy_label": "Buy and Hold",
            "assumptions": ["Universe: SBUX, CMG."],
            "rows": [],
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        fake_build_result_card,
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert seen_configs[0]["symbols"] == ["SBUX", "CMG"]
    assert result.envelope.resolved_strategy["asset_universe"] == ["SBUX", "CMG"]
    assert result.result_card is not None
    assert result.result_card["symbols"] == ["SBUX", "CMG"]
    assert result.explanation_context is not None
    assert result.explanation_context["symbols"] == ["SBUX", "CMG"]


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
        lambda config, **_: {
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
        lambda config, **_: {
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


def test_adapter_accepts_registry_bounded_indicator_threshold_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )
    captured: dict[str, object] = {}

    def compute_metrics_stub(config: dict[str, object], **_: Any) -> dict[str, object]:
        captured["config"] = config
        return {
            "aggregate": {
                "performance": {
                    "total_return_pct": 11.0,
                    "benchmark_return_pct": 7.5,
                }
            },
            "by_symbol": {},
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        compute_metrics_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA RSI Mean Reversion",
            "assumptions": [],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["indicator"] == "rsi"
    assert result.envelope.resolved_parameters["entry_threshold"] == 25.0
    assert result.envelope.resolved_parameters["exit_threshold"] == 60.0
    assert (
        "Only the confirmed RSI threshold rule was simulated; no extra filters were added."
        in result.envelope.caveats
    )
    assert not any(
        "executable indicator registry" in caveat for caveat in result.envelope.caveats
    )
    assert captured["config"]["parameters"]["entry_threshold"] == 25.0
    assert "rule_spec" in captured["config"]["parameters"]


def test_adapter_uses_indicator_period_from_threshold_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={
            "indicator": "rsi",
            "operator": "below",
            "period": 7,
            "threshold": 25,
        },
        exit_rule={
            "indicator": "rsi",
            "operator": "above",
            "period": 7,
            "threshold": 60,
        },
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
    captured: dict[str, object] = {}

    def compute_metrics_stub(config: dict[str, object], **_: Any) -> dict[str, object]:
        captured["config"] = config
        return {
            "aggregate": {
                "performance": {
                    "total_return_pct": 11.0,
                    "benchmark_return_pct": 7.5,
                }
            },
            "by_symbol": {},
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        compute_metrics_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA RSI Mean Reversion",
            "assumptions": [],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.envelope.resolved_parameters["indicator_period"] == 7
    assert captured["config"]["parameters"]["indicator_period"] == 7
    assert (
        captured["config"]["parameters"]["rule_spec"]["entry"]["conditions"][0]["left"][
            "period"
        ]
        == 7
    )


def test_adapter_adds_no_trade_note_to_signal_result_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="indicator_threshold",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={"indicator": "rsi", "operator": "below", "threshold": 20},
        exit_rule={"indicator": "rsi", "operator": "above", "threshold": 60},
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
        lambda config, **_: {
            "aggregate": {
                "performance": {
                    "total_return_pct": 0.0,
                    "benchmark_return_pct": 8.9,
                },
                "efficiency": {"total_trades": 0},
            },
            "by_symbol": {},
        },
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA RSI Mean Reversion",
            "assumptions": [],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "succeeded"
    assert result.result_card is not None
    assert (
        "No entry trades were executed; the strategy stayed in cash because the "
        "entry condition did not trigger in that window."
    ) in result.result_card["assumptions"]


def test_adapter_maps_common_crossover_payload_to_rule_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="signal_strategy",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bullish",
        },
        exit_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 20,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bearish",
        },
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
    captured: dict[str, object] = {}

    def compute_metrics_stub(config: dict[str, object], **_: Any) -> dict[str, object]:
        captured["config"] = config
        return {
            "aggregate": {
                "performance": {
                    "total_return_pct": 11.0,
                    "benchmark_return_pct": 7.5,
                }
            },
            "by_symbol": {},
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        compute_metrics_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.build_result_card",
        lambda config, metrics, language="en": {
            "title": "TSLA Signal Strategy",
            "assumptions": [],
            "rows": [],
        },
    )

    result = run_launch_backtest(request)

    config = captured["config"]
    rule_spec = config["parameters"]["rule_spec"]
    assert result.envelope.execution_status == "succeeded"
    assert config["template"] == "signal_strategy"
    assert rule_spec["entry"]["conditions"][0]["operator"] == "cross_above"
    assert rule_spec["exit"]["conditions"][0]["operator"] == "cross_below"


def test_adapter_classifies_rule_warmup_failure_as_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="signal_strategy",
        symbol="TSLA",
        timeframe="1D",
        date_range={"start": "2024-01-01", "end": "2024-01-10"},
        entry_rule=None,
        exit_rule=None,
        rule_spec={
            "entry": {
                "conditions": [
                    {
                        "left": {"kind": "indicator", "key": "rsi", "period": 14},
                        "operator": "lte",
                        "right": 30,
                    }
                ]
            },
            "exit": {
                "conditions": [
                    {
                        "left": {"kind": "indicator", "key": "rsi", "period": 14},
                        "operator": "gte",
                        "right": 55,
                    }
                ]
            },
        },
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
        lambda config, **_: (_ for _ in ()).throw(
            ValueError("indicator_data_insufficient")
        ),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "blocked_invalid_input"
    assert result.envelope.failure_category == "parameter_validation_error"
    assert result.envelope.failure_reason == "indicator_data_insufficient"


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


def test_adapter_explains_symbol_level_equity_data_window_unavailability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = LaunchBacktestRequest(
        strategy_type="buy_and_hold",
        symbol="SNDK",
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

    def classify_symbol_stub(symbol: str):
        return type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )()

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        classify_symbol_stub,
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        lambda config, **_: (_ for _ in ()).throw(ValueError("market_data_unavailable")),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "failed_upstream"
    assert result.envelope.failure_category == "upstream_dependency_error"
    assert result.envelope.failure_reason == "market_data_unavailable"
    assert result.envelope.resolved_strategy["asset_universe"] == ["SNDK"]
    assert result.envelope.resolved_parameters["date_range"] == {
        "start": "2024-01-01",
        "end": "2024-12-31",
    }
    assert result.envelope.provider_metadata["asset_class"] == "equity"
    assert result.envelope.provider_metadata["symbols"] == ["SNDK"]
    assert result.envelope.provider_metadata["date_range"] == {
        "start": "2024-01-01",
        "end": "2024-12-31",
    }

    message = user_safe_failure_message(
        failure_reason=result.envelope.failure_reason,
        failure_category=result.envelope.failure_category,
    )
    assert "price history" in message.lower()
    assert "date" in message.lower()
    assert "provider" not in message.lower()
    assert "alpaca" not in message.lower()


def test_adapter_maps_benchmark_coverage_failure_to_upstream_dependency(
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
        lambda config, **_: (_ for _ in ()).throw(
            ValueError("benchmark_data_unavailable")
        ),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "failed_upstream"
    assert result.envelope.failure_category == "upstream_dependency_error"
    assert result.envelope.failure_reason == "benchmark_data_unavailable"


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
        lambda config, **_: {
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
    assert result.envelope.assumptions == result.result_card["assumptions"]
    assert result.explanation_context is not None
    assert result.explanation_context["strategy_type"] == "dca_accumulation"


def test_dca_adapter_separates_recurring_contribution_from_starting_principal(
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
    observed_config: dict[str, Any] = {}

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )

    def fake_metrics(config: dict[str, Any], **_: Any) -> dict[str, Any]:
        observed_config.update(config)
        return {
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
        }

    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.compute_alpha_metrics",
        fake_metrics,
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
    assert observed_config["starting_capital"] == 500.0
    assert observed_config["recurring_contribution"] == 500.0
    assert observed_config["starting_principal"] == 0.0
    assert observed_config["parameters"] == {"dca_cadence": "monthly"}
    assert result.envelope.resolved_parameters["capital_amount"] == 500.0
    assert result.envelope.resolved_parameters["recurring_contribution"] == 500.0
    assert result.envelope.resolved_parameters["starting_principal"] == 0.0


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
        lambda config, **_: {
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
    assert result.envelope.caveats[0] == "Daily data only."
    assert result.envelope.caveats[-1].startswith(
        "Recurring entries use the first available daily price"
    )


def test_build_signals_supports_quarterly_dca_cadence() -> None:
    index = pd.to_datetime(
        [
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
            "2024-05-01",
            "2024-06-01",
            "2024-07-01",
            "2024-08-01",
            "2024-09-01",
        ]
    )
    data = pd.DataFrame({"close": [100, 101, 102, 103, 104, 105, 106, 107]}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "quarterly"},
    }

    entries, exits = _build_signals(config, data)

    assert entries.tolist() == [True, False, True, False, False, True, False, False]
    assert exits.tolist() == [False] * len(index)


def test_build_signals_monthly_dca_does_not_warn_for_timezone_index() -> None:
    index = pd.date_range("2024-01-02", periods=4, freq="MS", tz="UTC")
    data = pd.DataFrame({"close": [100, 101, 102, 103]}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "monthly"},
    }

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message="Converting to PeriodArray/Index representation will drop timezone information.",
            category=UserWarning,
        )
        entries, exits = _build_signals(config, data)

    assert entries.tolist() == [True, True, True, True]
    assert exits.tolist() == [False] * len(index)


def test_build_signals_preserves_rule_template_branches_after_rsi() -> None:
    index = pd.date_range("2024-01-01", periods=80, freq="D")
    data = pd.DataFrame(
        {"close": [100 + step for step in range(len(index))]},
        index=index,
    )
    config = {"template": "moving_average_crossover", "parameters": {}}

    entries, exits = _build_signals(config, data)

    assert len(entries) == len(index)
    assert len(exits) == len(index)


def test_launch_classifies_malformed_execution_realism_as_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    request = LaunchBacktestRequest.model_validate(
        {
            "strategy_type": "buy_and_hold",
            "symbol": "AAPL",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 1000.0,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "_execution_realism": {
                "enabled": True,
                "fee_bps": -10.0,
                "slippage_bps": 5.0,
            },
        }
    )
    monkeypatch.setattr(
        "argus.domain.engine_launch.adapter.classify_symbol",
        lambda symbol: type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )(),
    )

    result = run_launch_backtest(request)

    assert result.envelope.execution_status == "blocked_invalid_input"
    assert result.envelope.failure_category == "parameter_validation_error"
    assert result.envelope.failure_reason == "invalid_execution_realism_fee_bps"
