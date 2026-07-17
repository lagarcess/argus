from __future__ import annotations

from collections import Counter
from datetime import date

import pandas as pd
import pytest
from argus.domain.backtesting.coverage import (
    MarketDataCoverageError,
    apply_coverage_to_config,
    prepare_market_data,
)
from argus.domain.engine import build_result_chart, compute_alpha_metrics


def _bars(*days: str, base: float = 100.0) -> pd.DataFrame:
    index = pd.DatetimeIndex(pd.to_datetime(list(days), utc=True))
    close = pd.Series(
        [base + float(offset) for offset in range(len(index))],
        index=index,
    )
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )


def _config(*symbols: str) -> dict[str, object]:
    return {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": list(symbols),
        "timeframe": "1D",
        "start_date": "2024-01-01",
        "end_date": "2024-01-05",
        "side": "long",
        "starting_capital": 10_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }


def _fetcher(
    frames: dict[str, pd.DataFrame],
    calls: Counter[str] | None = None,
):
    def fetch(
        symbol: str,
        asset_class: str,  # noqa: ARG001
        start_date: date,  # noqa: ARG001
        end_date: date,  # noqa: ARG001
        timeframe: str,  # noqa: ARG001
    ) -> pd.DataFrame:
        if calls is not None:
            calls[symbol] += 1
        return frames[symbol].copy(deep=True)

    return fetch


def test_full_coverage_preserves_requested_window_and_fetches_each_series_once() -> None:
    full = _bars(
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    )
    calls: Counter[str] = Counter()

    prepared = prepare_market_data(
        _config("AAPL", "MSFT"),
        fetch_ohlcv_func=_fetcher({"AAPL": full, "MSFT": full, "SPY": full}, calls),
    )

    assert prepared.outcome == "full_coverage"
    assert prepared.requested_date_range.model_dump() == {
        "start": "2024-01-01",
        "end": "2024-01-05",
    }
    assert prepared.effective_date_range == prepared.requested_date_range
    assert calls == Counter({"AAPL": 1, "MSFT": 1, "SPY": 1})


@pytest.mark.parametrize(
    ("symbol_days", "expected_start", "expected_end"),
    [
        (
            ["2024-01-03", "2024-01-04", "2024-01-05"],
            "2024-01-03",
            "2024-01-05",
        ),
        (
            ["2024-01-01", "2024-01-02", "2024-01-03"],
            "2024-01-01",
            "2024-01-03",
        ),
    ],
)
def test_leading_and_trailing_gaps_produce_one_effective_window(
    symbol_days: list[str],
    expected_start: str,
    expected_end: str,
) -> None:
    full = _bars(
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    )

    prepared = prepare_market_data(
        _config("AAPL"),
        fetch_ohlcv_func=_fetcher({"AAPL": _bars(*symbol_days), "SPY": full}),
    )
    effective_config = apply_coverage_to_config(_config("AAPL"), prepared)

    assert prepared.outcome == "adjusted_coverage"
    assert prepared.effective_date_range.model_dump() == {
        "start": expected_start,
        "end": expected_end,
    }
    assert effective_config["start_date"] == expected_start
    assert effective_config["end_date"] == expected_end
    assert effective_config["requested_date_range"] == {
        "start": "2024-01-01",
        "end": "2024-01-05",
    }
    assert effective_config["effective_date_range"] == {
        "start": expected_start,
        "end": expected_end,
    }


def test_multi_symbol_window_is_intersection_including_benchmark() -> None:
    prepared = prepare_market_data(
        _config("AAPL", "MSFT"),
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": _bars("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"),
                "MSFT": _bars("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"),
                "SPY": _bars("2024-01-01", "2024-01-02", "2024-01-03"),
            }
        ),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2024-01-02",
        "end": "2024-01-03",
    }
    assert all(
        list(frame.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
        for frame in prepared.bars_by_symbol.values()
    )


def test_effective_window_uses_observed_boundaries_for_every_series() -> None:
    all_days = [f"2024-01-{day:02d}" for day in range(1, 21)]
    strategy_days = [
        day
        for day in all_days
        if day not in {"2024-01-03", "2024-01-18"}
    ]
    benchmark_days = [f"2024-01-{day:02d}" for day in range(3, 19)]

    prepared = prepare_market_data(
        {
            **_config("AAPL", "MSFT"),
            "end_date": "2024-01-20",
        },
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": _bars(*strategy_days),
                "MSFT": _bars(*benchmark_days, base=200.0),
                "SPY": _bars(*all_days, base=300.0),
            }
        ),
    )

    assert prepared.effective_date_range.model_dump() == {
        "start": "2024-01-04",
        "end": "2024-01-17",
    }
    assert all(
        frame.index[0].date().isoformat() == "2024-01-04"
        and frame.index[-1].date().isoformat() == "2024-01-17"
        for frame in prepared.bars_by_symbol.values()
    )


def test_sparse_history_is_rejected_with_typed_recovery_code() -> None:
    full = _bars(
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    )

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL", "MSFT"),
            fetch_ohlcv_func=_fetcher(
                {
                    "AAPL": full,
                    "MSFT": _bars("2024-01-01", "2024-01-05"),
                    "SPY": full,
                }
            ),
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_uniformly_sparse_history_is_rejected_against_the_effective_window() -> None:
    endpoints = _bars("2024-01-02", "2024-01-31")

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            {
                **_config("AAPL"),
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            fetch_ohlcv_func=_fetcher({"AAPL": endpoints, "SPY": endpoints}),
        )

    assert exc_info.value.code == "insufficient_common_data"


def test_no_common_window_is_rejected_before_a_runnable_artifact_exists() -> None:
    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL", "MSFT"),
            fetch_ohlcv_func=_fetcher(
                {
                    "AAPL": _bars("2024-01-01", "2024-01-02"),
                    "MSFT": _bars("2024-01-04", "2024-01-05"),
                    "SPY": _bars(
                        "2024-01-01",
                        "2024-01-02",
                        "2024-01-03",
                        "2024-01-04",
                        "2024-01-05",
                    ),
                }
            ),
        )

    assert exc_info.value.code == "no_common_data_window"


def test_approved_effective_window_cannot_silently_change_during_execution() -> None:
    full = _bars(
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    )
    approved = {
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "effective_date_range": {"start": "2024-01-02", "end": "2024-01-05"},
    }

    with pytest.raises(MarketDataCoverageError) as exc_info:
        prepare_market_data(
            _config("AAPL"),
            fetch_ohlcv_func=_fetcher({"AAPL": full, "SPY": full}),
            approved_coverage=approved,
        )

    assert exc_info.value.code == "approved_data_window_unavailable"


def test_metrics_and_chart_share_prepared_bars_without_refetch_or_edge_backfill() -> None:
    full = _bars(
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    )
    calls: Counter[str] = Counter()
    config = _config("AAPL", "MSFT")
    prepared = prepare_market_data(
        config,
        fetch_ohlcv_func=_fetcher(
            {
                "AAPL": full,
                "MSFT": _bars("2024-01-03", "2024-01-04", "2024-01-05", base=200),
                "SPY": full,
            },
            calls,
        ),
    )
    effective_config = apply_coverage_to_config(config, prepared)
    calls_after_preflight = calls.copy()

    metrics = compute_alpha_metrics(
        effective_config,
        prepared_market_data=prepared,
    )
    chart = build_result_chart(
        effective_config,
        prepared_market_data=prepared,
    )

    assert calls == calls_after_preflight
    assert chart["series"][0]["time"] == "2024-01-03"
    assert chart["series"][-1]["time"] == "2024-01-05"
    assert chart["series"][0]["value"] == 10_000.0
    assert (
        metrics["aggregate"]["performance"]["portfolio_value_range"]["lowest_value"]
        >= 10_000.0
    )
    assert effective_config["data_coverage"]["dataset_id"] == prepared.dataset_id
