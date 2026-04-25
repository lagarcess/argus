from __future__ import annotations

import inspect

import pandas as pd
import pytest

from argus.domain import engine


def _daily_index() -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC")


def test_compute_alpha_metrics_no_sha_pseudorandom_path() -> None:
    source = inspect.getsource(engine.compute_alpha_metrics)
    assert "sha256" not in source
    assert "hashlib" not in source


def test_compute_alpha_metrics_uses_series_driven_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _daily_index()
    market_data = {
        "AAPL": pd.Series([100.0, 103.0, 106.0, 109.0, 112.0], index=index),
        "SPY": pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=index),
    }

    def fake_fetch(
        symbol: str,
        asset_class: engine.AssetClass,  # noqa: ARG001
        start_date,  # noqa: ANN001,ARG001
        end_date,  # noqa: ANN001,ARG001
        timeframe: str,  # noqa: ARG001
    ) -> pd.Series:
        return market_data[symbol]

    monkeypatch.setattr(engine, "fetch_price_series", fake_fetch)

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
        "parameters": {},
    }

    metrics = engine.compute_alpha_metrics(config)

    assert metrics["aggregate"]["performance"]["total_return_pct"] == pytest.approx(
        12.0, abs=0.01
    )
    assert metrics["aggregate"]["performance"]["benchmark_return_pct"] == pytest.approx(
        4.0, abs=0.01
    )
    assert metrics["aggregate"]["performance"]["delta_vs_benchmark_pct"] == pytest.approx(
        8.0, abs=0.01
    )
    assert metrics["by_symbol"]["AAPL"]["efficiency"]["total_trades"] >= 1


def test_build_benchmark_curve_aligns_to_target_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_index = pd.date_range("2025-02-01", periods=4, freq="D", tz="UTC")
    benchmark_index = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-02-01T00:00:00Z"),
            pd.Timestamp("2025-02-03T00:00:00Z"),
            pd.Timestamp("2025-02-04T00:00:00Z"),
        ]
    )

    def fake_fetch(
        symbol: str,  # noqa: ARG001
        asset_class: engine.AssetClass,  # noqa: ARG001
        start_date,  # noqa: ANN001,ARG001
        end_date,  # noqa: ANN001,ARG001
        timeframe: str,  # noqa: ARG001
    ) -> pd.Series:
        return pd.Series([200.0, 210.0, 220.0], index=benchmark_index)

    monkeypatch.setattr(engine, "fetch_price_series", fake_fetch)

    config = {
        "asset_class": "crypto",
        "benchmark_symbol": "BTC",
        "start_date": "2025-02-01",
        "end_date": "2025-02-04",
        "timeframe": "1D",
    }

    curve = engine.build_benchmark_curve(config, target_index)

    assert curve["symbol"] == "BTC"
    assert len(curve["equity_curve"]) == len(target_index)
    assert curve["equity_curve"][0] == pytest.approx(1.0, abs=1e-6)
    assert curve["total_return_pct"] == pytest.approx(10.0, abs=0.01)
