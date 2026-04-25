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
        if compact.endswith("USD") and len(compact) > 3:
            compact = compact[:-3]

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
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(engine, "resolve_asset", fake_resolve_asset)


@pytest.fixture(autouse=True)
def _patch_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = {
        "AAPL": _make_bars([100, 102, 104, 106, 108, 110, 112]),
        "MSFT": _make_bars([100, 101, 102, 103, 104, 106, 108]),
        "SPY": _make_bars([100, 101, 102, 103, 104, 105, 106]),
        "BTC": _make_bars([100, 103, 104, 108, 110, 111, 113]),
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


def test_validate_backtest_config_rejects_lookback_over_three_years() -> None:
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
    with pytest.raises(ValueError, match="invalid_lookback_window"):
        engine.validate_backtest_config(config)


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
