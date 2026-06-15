from __future__ import annotations

import inspect
from datetime import date

import pandas as pd
import pytest
from argus.domain import engine
from argus.domain.market_data.assets import ResolvedAsset


def _make_bars(
    prices: list[float], *, start: str = "2025-01-01", freq: str = "D"
) -> pd.DataFrame:
    index = pd.date_range(start=start, periods=len(prices), freq=freq, tz="UTC")
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close * 0.995,
            "high": close * 1.005,
            "low": close * 0.99,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


@pytest.fixture(autouse=True)
def _patch_asset_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_asset(symbol: str) -> ResolvedAsset:
        candidate = symbol.strip().upper().replace("-", "/")
        compact = candidate.replace("/", "")

        if compact in {"AAPL", "TSLA", "MSFT", "NVDA", "SPY"}:
            return ResolvedAsset(
                canonical_symbol=compact,
                asset_class="equity",
                name=f"{compact} Inc",
                raw_symbol=compact,
            )
        if compact in {"BTC", "ETH", "SOL", "USDC", "USDT"}:
            return ResolvedAsset(
                canonical_symbol=compact,
                asset_class="crypto",
                name=compact,
                raw_symbol=compact,
            )
        if compact in {"EURUSD", "USDJPY"}:
            return ResolvedAsset(
                canonical_symbol=compact,
                asset_class="currency_pair",
                name=compact,
                raw_symbol=compact,
            )
        if compact.endswith("USD") and len(compact) > 3:
            compact = compact[:-3]
        if compact in {"BTC", "ETH", "SOL"}:
            return ResolvedAsset(
                canonical_symbol=compact,
                asset_class="crypto",
                name=compact,
                raw_symbol=compact,
            )
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(engine, "resolve_asset", fake_resolve_asset)


@pytest.fixture(autouse=True)
def _patch_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = {
        "AAPL": _make_bars([100, 102, 104, 106, 108, 110, 112]),
        "MSFT": _make_bars([100, 101, 102, 103, 104, 106, 108]),
        "SPY": _make_bars([100, 101, 102, 103, 104, 105, 106]),
        "BTC": _make_bars([100, 103, 104, 108, 110, 111, 113]),
        "EURUSD": _make_bars([100, 100.5, 99.5, 101, 102, 101.5, 103]),
    }

    def fake_fetch_ohlcv(
        symbol: str,
        asset_class: engine.AssetClass,  # noqa: ARG001
        start_date: date,  # noqa: ARG001
        end_date: date,  # noqa: ARG001
        timeframe: str,  # noqa: ARG001
    ) -> pd.DataFrame:
        if symbol not in bars:
            raise ValueError("market_data_unavailable")
        return bars[symbol].copy()

    def fake_fetch_price_series(
        symbol: str,
        asset_class: engine.AssetClass,
        start_date: date,
        end_date: date,
        timeframe: str,
    ) -> pd.Series:
        return fake_fetch_ohlcv(
            symbol=symbol,
            asset_class=asset_class,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )["close"]

    monkeypatch.setattr(engine, "fetch_ohlcv", fake_fetch_ohlcv)
    monkeypatch.setattr(engine, "fetch_price_series", fake_fetch_price_series)


def test_compute_alpha_metrics_uses_vectorbt_path_not_sha_mock() -> None:
    source = inspect.getsource(engine.compute_alpha_metrics)
    assert "sha256" not in source
    assert "hashlib" not in source
    assert "Portfolio.from_signals" in source


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("1d", "1D"),
        ("1D", "1D"),
        ("1h", "1h"),
        ("1H", "1h"),
        ("2H", "2h"),
        ("4hour", "4h"),
        ("6h", "6h"),
        ("12HOUR", "12h"),
    ],
)
def test_normalize_backtest_config_timeframe_variants(
    timeframe: str, expected: str
) -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": timeframe,
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )
    assert config["timeframe"] == expected


def test_currency_pair_config_uses_same_pair_as_default_benchmark() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "currency_pair",
            "symbols": ["EUR/USD"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "parameters": {},
        }
    )

    assert config["asset_class"] == "currency_pair"
    assert config["symbols"] == ["EURUSD"]
    assert config["benchmark_symbol"] == "EURUSD"
    metrics = engine.compute_alpha_metrics(config)
    assert metrics["aggregate"]["performance"]["total_return_pct"] > 0


def test_validate_backtest_config_rejects_stablecoins() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "crypto",
            "symbols": ["USDT"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "BTC",
            "parameters": {},
        }
    )
    with pytest.raises(ValueError, match="stablecoin_not_supported"):
        engine.validate_backtest_config(config)


def test_validate_backtest_config_rejects_custom_parameters() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {"rsi_length": 21},
        }
    )
    with pytest.raises(ValueError, match="unsupported_parameters"):
        engine.validate_backtest_config(config)


def test_validate_backtest_config_distinguishes_chronology_and_future_dates() -> None:
    base_config = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }

    with pytest.raises(ValueError, match="invalid_chronological_date_range"):
        engine.validate_backtest_config(
            {
                **base_config,
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",
            }
        )

    with pytest.raises(ValueError, match="future_end_date"):
        engine.validate_backtest_config(
            {
                **base_config,
                "start_date": "2026-01-01",
                "end_date": "2099-12-31",
            }
        )


def test_validate_backtest_config_accepts_custom_rsi_thresholds() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {
                "rsi_period": 10,
                "buy_threshold": 25,
                "sell_threshold": 60,
            },
        }
    )

    engine.validate_backtest_config(config)

    assert config["parameters"]["indicator"] == "rsi"
    assert config["parameters"]["indicator_period"] == 10
    assert config["parameters"]["entry_threshold"] == 25.0
    assert config["parameters"]["exit_threshold"] == 60.0


def test_validate_backtest_config_rejects_out_of_bounds_indicator_threshold() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {"entry_threshold": 120},
        }
    )

    with pytest.raises(ValueError, match="indicator_threshold_out_of_bounds"):
        engine.validate_backtest_config(config)


def test_validate_backtest_config_allows_equity_history_beyond_three_years() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2020, 1, 1),
            "end_date": date(2024, 1, 10),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )

    engine.validate_backtest_config(config)


def test_validate_backtest_config_rejects_equity_history_before_alpaca_window() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2015, 12, 31),
            "end_date": date(2016, 1, 15),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )

    with pytest.raises(ValueError) as excinfo:
        engine.validate_backtest_config(config)
    assert str(excinfo.value) == "provider_history_start_unavailable"


def test_validate_backtest_config_rejects_currency_pair_windows_by_kraken_candles() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "currency_pair",
            "symbols": ["EURUSD"],
            "timeframe": "1h",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 2, 15),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "EURUSD",
            "parameters": {},
        }
    )

    with pytest.raises(ValueError) as excinfo:
        engine.validate_backtest_config(config)
    assert str(excinfo.value) == "kraken_ohlc_window_exceeded"


def test_build_benchmark_curve_aligns_and_normalizes() -> None:
    target_index = pd.date_range("2025-01-01", periods=7, freq="D", tz="UTC")
    curve = engine.build_benchmark_curve(
        {
            "asset_class": "equity",
            "benchmark_symbol": "SPY",
            "start_date": "2025-01-01",
            "end_date": "2025-01-07",
            "timeframe": "1D",
        },
        target_index,
    )
    assert curve["symbol"] == "SPY"
    assert len(curve["equity_curve"]) == 7
    assert curve["equity_curve"][0] == pytest.approx(1.0, abs=1e-6)


def test_build_benchmark_curve_rejects_late_start_without_future_backfill() -> None:
    target_index = pd.date_range("2025-01-01", periods=7, freq="D", tz="UTC")
    late_benchmark = pd.Series(
        [100.0, 101.0, 102.0],
        index=pd.date_range("2025-01-03", periods=3, freq="D", tz="UTC"),
    )

    with pytest.raises(ValueError) as excinfo:
        engine.build_benchmark_curve(
            {
                "asset_class": "equity",
                "benchmark_symbol": "SPY",
                "start_date": "2025-01-01",
                "end_date": "2025-01-07",
                "timeframe": "1D",
            },
            target_index,
            fetch_price_series_func=lambda **_: late_benchmark,
        )

    assert str(excinfo.value) == "benchmark_data_unavailable"


def test_build_benchmark_curve_rejects_sparse_benchmark_observations() -> None:
    target_index = pd.date_range("2025-01-01", periods=10, freq="D", tz="UTC")
    sparse_benchmark = pd.Series(
        [100.0, 102.0],
        index=pd.DatetimeIndex([target_index[0], target_index[-1]]),
    )

    with pytest.raises(ValueError) as excinfo:
        engine.build_benchmark_curve(
            {
                "asset_class": "equity",
                "benchmark_symbol": "SPY",
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "timeframe": "1D",
            },
            target_index,
            fetch_price_series_func=lambda **_: sparse_benchmark,
        )

    assert str(excinfo.value) == "benchmark_data_unavailable"


def test_buy_and_hold_metrics_match_total_return_benchmark_and_profit() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )

    metrics = engine.compute_alpha_metrics(config)
    performance = metrics["aggregate"]["performance"]

    assert performance["total_return_pct"] == pytest.approx(12.0, abs=0.05)
    assert performance["benchmark_return_pct"] == pytest.approx(6.0, abs=0.05)
    assert performance["delta_vs_benchmark_pct"] == pytest.approx(6.0, abs=0.05)
    assert performance["profit"] == pytest.approx(1200.0, abs=1)


def test_max_drawdown_uses_peak_inside_selected_period() -> None:
    equity = pd.Series([100.0, 150.0, 120.0, 180.0])

    assert engine._max_drawdown_pct(equity) == pytest.approx(-20.0)


def test_dca_metrics_use_actual_invested_cash_flows() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 100,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {"dca_cadence": "daily"},
        }
    )

    metrics = engine.compute_alpha_metrics(config)

    assert metrics["aggregate"]["efficiency"]["total_trades"] == 7
    assert metrics["aggregate"]["performance"]["profit"] == pytest.approx(40.68, abs=0.1)


def test_multi_symbol_aggregate_uses_equal_weight_capital() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL", "MSFT"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )

    metrics = engine.compute_alpha_metrics(config)

    assert metrics["aggregate"]["performance"]["total_return_pct"] == pytest.approx(
        10.0,
        abs=0.05,
    )
    assert set(metrics["by_symbol"]) == {"AAPL", "MSFT"}


def test_indicator_signals_use_user_selected_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-01-01", periods=16, freq="D", tz="UTC")
    bars = pd.DataFrame({"close": list(range(100, 116))}, index=index)
    monkeypatch.setattr(
        engine,
        "_resolve_indicator_series",
        lambda data, *, indicator, period, fallback_col="close": pd.Series(
            [35, 24, 29, 61, 50, *([50] * 11)],
            index=data.index,
        ),
    )

    entries, exits = engine._build_signals(
        {
            "template": "rsi_mean_reversion",
            "parameters": {
                "indicator": "rsi",
                "indicator_period": 2,
                "entry_threshold": 25,
                "exit_threshold": 60,
            },
        },
        bars,
    )

    assert entries.iloc[:5].tolist() == [False, True, False, False, False]
    assert not entries.iloc[5:].any()
    assert exits.iloc[:5].tolist() == [False, False, False, True, False]
    assert not exits.iloc[5:].any()


def test_compute_alpha_metrics_preserves_contract_shape_multi_symbol() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL", "MSFT"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )
    engine.validate_backtest_config(config)

    metrics = engine.compute_alpha_metrics(config)

    assert set(metrics) == {"aggregate", "by_symbol"}
    assert set(metrics["by_symbol"]) == {"AAPL", "MSFT"}
    assert metrics["aggregate"]["performance"]["total_return_pct"] != 0
    assert metrics["aggregate"]["efficiency"]["total_trades"] >= 2


def test_build_result_chart_uses_aggregate_portfolio_curve() -> None:
    config = engine.normalize_backtest_config(
        {
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL", "MSFT"],
            "timeframe": "1D",
            "start_date": date(2025, 1, 2),
            "end_date": date(2025, 1, 7),
            "side": "long",
            "starting_capital": 10000,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "SPY",
            "parameters": {},
        }
    )

    chart = engine.build_result_chart(config)

    assert chart["kind"] == "portfolio_equity"
    assert chart["attribution"] == "TradingView Lightweight Charts"
    assert len(chart["series"]) >= 2
    assert chart["series"][0]["value"] == 10000
    assert chart["markers"][0]["type"] == "entry"
    assert chart["markers"][0]["label"] == "Buy AAPL, MSFT"


def test_build_result_card_actions_by_symbol_count() -> None:
    config = {
        "template": "rsi_mean_reversion",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-01-07",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }
    metrics = {
        "aggregate": {
            "performance": {
                "total_return_pct": 5.0,
                "delta_vs_benchmark_pct": 1.0,
                "profit": 500.0,
            },
            "risk": {"max_drawdown_pct": 2.0},
            "efficiency": {"win_rate": 0.6, "total_trades": 10},
        }
    }

    # Case 1: Single symbol
    card = engine.build_result_card(config, metrics)
    assert card["asset_class"] == "equity"
    row_keys = [row["key"] for row in card["rows"]]
    assert row_keys[:4] == [
        "cash_value",
        "total_return_pct",
        "benchmark_delta",
        "max_drawdown_pct",
    ]
    assert "win_rate" in row_keys
    actions = [a["type"] for a in card["actions"]]
    assert actions == ["show_breakdown", "save_strategy", "refine_strategy"]
    assert card["actions"][0]["label"] == "Explain result"
    assert card["actions"][0]["labelKey"] == "chat.result_card.explain_result"
    assert card["actions"][1]["label"] == "Save"
    assert card["actions"][1]["labelKey"] == "chat.result_card.save"
    assert card["actions"][2]["label"] == "Refine idea"
    assert card["actions"][2]["labelKey"] == "chat.result_card.refine_idea"
    labels = [row["label"] for row in card["rows"][:4]]
    assert labels == [
        "Ending value",
        "Total return",
        "Compared with SPY",
        "Worst drop",
    ]
    assert card["assumptions"] == [
        "Long-only",
        "Equal weight",
        "No fees/slippage",
        "Benchmark: SPY",
    ]
    assert card["benchmark_note"] is None

    # Case 2: Multi-symbol (between 2 and 4)
    config["symbols"] = ["AAPL", "MSFT"]
    card = engine.build_result_card(config, metrics)
    actions = [a["type"] for a in card["actions"]]
    assert actions == ["show_breakdown", "save_strategy", "refine_strategy"]
    assert card["actions"][1]["label"] == "Save"

    # Case 3: Max symbols (5)
    config["symbols"] = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]
    card = engine.build_result_card(config, metrics)
    actions = [a["type"] for a in card["actions"]]
    assert actions == ["show_breakdown", "save_strategy", "refine_strategy"]
    assert all(action["presentation"] == "result" for action in card["actions"])

    # Verify Spanish labels
    card = engine.build_result_card(config, metrics, language="es-419")
    assert card["actions"][1]["label"] == "Guardar"
    assert card["actions"][1]["labelKey"] == "chat.result_card.save"


def test_build_result_card_dca_assumptions_name_recurring_contribution() -> None:
    config = {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["NVDA"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
        "side": "long",
        "starting_capital": 500,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "monthly"},
        "recurring_contribution": 500,
        "starting_principal": 0.0,
    }
    metrics = {
        "aggregate": {
            "performance": {
                "total_return_pct": 5.0,
                "delta_vs_benchmark_pct": 1.0,
                "profit": 300.0,
            },
            "risk": {"max_drawdown_pct": -4.0},
            "efficiency": {"win_rate": 0.0, "total_trades": 12},
        }
    }

    card = engine.build_result_card(config, metrics)
    assert card["assumptions"] == [
        "Recurring contribution: $500 monthly",
        "Starting principal: $0",
        "Long-only",
        "Equal weight",
        "No fees/slippage",
        "Benchmark: SPY",
    ]
    assert not any("Starting capital" in item for item in card["assumptions"])

    spanish_card = engine.build_result_card(config, metrics, language="es-419")
    assert spanish_card["assumptions"] == [
        "Aporte recurrente: $500 mensual",
        "Capital inicial: $0",
        "Solo largo",
        "Peso igual",
        "Sin comisiones/deslizamiento",
        "Referencia: SPY",
    ]


def test_build_result_card_hides_win_rate_when_no_meaningful_closed_trades() -> None:
    config = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-01-07",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }
    metrics = {
        "aggregate": {
            "performance": {
                "total_return_pct": 5.0,
                "delta_vs_benchmark_pct": 1.0,
                "profit": 500.0,
            },
            "risk": {"max_drawdown_pct": 2.0},
            "efficiency": {"win_rate": 1.0, "total_trades": 1},
        }
    }

    card = engine.build_result_card(config, metrics)

    assert [row["key"] for row in card["rows"]] == [
        "cash_value",
        "total_return_pct",
        "benchmark_delta",
        "max_drawdown_pct",
    ]


def test_validate_template_parameters_rejects_unknown():
    config = {
        "template": "rsi_mean_reversion",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"unknown_param": 123},
    }
    with pytest.raises(ValueError, match="unsupported_parameters"):
        engine.validate_backtest_config(config)


def test_validate_template_parameters_rejects_invalid_value():
    config = {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "hourly"},  # Only daily/weekly/monthly allowed
    }
    with pytest.raises(ValueError, match="unsupported_parameter_value_dca_cadence"):
        engine.validate_backtest_config(config)


def test_validate_template_parameters_accepts_valid():
    config = {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2025-01-01",
        "end_date": "2025-01-05",
        "side": "long",
        "starting_capital": 10000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "weekly"},
    }
    # Should not raise
    engine.validate_backtest_config(config)
