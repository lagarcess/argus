"""The benchmark curve is honest at its edges and records what it rests on.

Review round on PR #526: a forward-filled price is never an executable fill
price, so the first and last target bars must be real observations for every
template, not only the DCA router; a curve that cannot say which bars are
observed is refused rather than trusted; and the stored metrics carry the
benchmark coverage and deferred-fill count the comparison rests on.
"""

from __future__ import annotations

import pandas as pd
import pytest
from argus.domain import engine
from argus.domain.backtesting.execution import _dca_equity_curve
from argus.domain.backtesting.runner import (
    _align_benchmark_series,
    build_benchmark_curve,
    compute_alpha_metrics,
)

FEE = 10.0 / 10_000.0
SLIPPAGE = 5.0 / 10_000.0

INDEX5 = pd.bdate_range("2025-01-06", periods=5, tz="UTC")
DAY_BEFORE = pd.Timestamp("2025-01-03", tz="UTC")
DAY_AFTER = pd.Timestamp("2025-01-13", tz="UTC")


def _bars(prices: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": 1e3},
        index=index,
    )


def _config(template: str) -> dict[str, object]:
    config: dict[str, object] = {
        "template": template,
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": INDEX5[0].date().isoformat(),
        "end_date": INDEX5[-1].date().isoformat(),
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
        "_execution_realism": {"enabled": True, "fee_bps": 10.0, "slippage_bps": 5.0},
    }
    if template == "dca_accumulation":
        config["parameters"] = {"dca_cadence": "daily"}
        config["dca_capital"] = {
            "schema_version": "dca_capital_v1",
            "starting_capital": 0.0,
            "contribution": 100.0,
        }
    else:
        config["starting_capital"] = 10_000.0
    return config


def _signals(template: str):
    def build(_config: dict[str, object], data: pd.DataFrame):
        entries = pd.Series(template == "dca_accumulation", index=data.index, dtype=bool)
        if template != "dca_accumulation":
            entries.iloc[0] = True
        return entries, pd.Series(False, index=data.index, dtype=bool)

    return build


def _run(
    template: str,
    *,
    benchmark_series: pd.Series,
    bars_by_symbol: dict[str, pd.DataFrame] | None = None,
    config: dict[str, object] | None = None,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    bars_by_symbol = bars_by_symbol or {"AAPL": _bars([100.0] * 5, INDEX5)}
    return compute_alpha_metrics(
        config or _config(template),
        fetch_ohlcv_func=lambda *, symbol, **_: bars_by_symbol[symbol],
        build_signals_func=_signals(template),
        build_benchmark_curve_func=lambda cfg, idx: build_benchmark_curve(
            cfg, idx, fetch_price_series_func=lambda **_: benchmark_series
        ),
    )


# A benchmark observed the session before the window and absent on the
# window's first bar: range covers, coverage is exactly 0.8, bar 0 is not real.
LEADING_GAP = pd.Series(
    [50.0, 100.0, 100.0, 100.0, 100.0],
    index=pd.DatetimeIndex([DAY_BEFORE, *INDEX5[1:]]),
    dtype=float,
)
TRAILING_GAP = pd.Series(
    [100.0, 100.0, 100.0, 100.0, 50.0],
    index=pd.DatetimeIndex([*INDEX5[:4], DAY_AFTER]),
    dtype=float,
)


# --- Unobserved endpoints are rejected for every template -----------------


@pytest.mark.parametrize("template", ["buy_and_hold", "dca_accumulation"])
@pytest.mark.parametrize(
    "benchmark_series", [LEADING_GAP, TRAILING_GAP], ids=["leading", "trailing"]
)
def test_unobserved_endpoint_is_rejected_not_filled(
    template: str,
    benchmark_series: pd.Series,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # At 8b40e288 the leading gap produced benchmark_return_pct 99.7 for
    # buy_and_hold: a whole-position fill at a forward-filled 50 on a
    # benchmark that never traded below 100 inside the window.
    with pytest.raises(ValueError, match="benchmark_data_unavailable"):
        _run(template, benchmark_series=benchmark_series, monkeypatch=monkeypatch)


@pytest.mark.parametrize(
    "benchmark_series", [LEADING_GAP, TRAILING_GAP], ids=["leading", "trailing"]
)
def test_alignment_requires_an_observation_at_both_target_endpoints(
    benchmark_series: pd.Series,
) -> None:
    with pytest.raises(ValueError, match="benchmark_data_unavailable"):
        _align_benchmark_series(benchmark_series, INDEX5)


def test_interior_gap_is_still_accepted_and_anchored_on_an_observed_bar() -> None:
    interior_gap = pd.Series(
        [90.0, 100.0, 102.0, 103.0], index=INDEX5[[0, 1, 3, 4]], dtype=float
    )
    curve = build_benchmark_curve(
        _config("dca_accumulation"),
        INDEX5,
        fetch_price_series_func=lambda **_: interior_gap,
    )
    # The payload's bar-0 value and the router's bar-0 price are one fact.
    assert curve["observed_mask"][0] is True
    assert curve["observed_mask"][-1] is True
    assert curve["equity_curve"][0] == 1.0
    assert curve["observed_mask"] == [True, True, False, True, True]
    assert curve["coverage"] == {
        "observed_points": 4,
        "target_points": 5,
        "observed_ratio": 0.8,
    }


# --- A curve that cannot say which bars are real is refused ----------------


def test_curve_without_an_observed_mask_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    with pytest.raises(ValueError, match="benchmark_curve_incomplete"):
        compute_alpha_metrics(
            _config("dca_accumulation"),
            fetch_ohlcv_func=lambda **_: _bars([100.0] * 5, INDEX5),
            build_signals_func=_signals("dca_accumulation"),
            build_benchmark_curve_func=lambda *_a, **_k: {"equity_curve": [1.0] * 5},
        )


@pytest.mark.parametrize("template", ["buy_and_hold", "dca_accumulation"])
def test_curve_length_mismatch_is_a_typed_refusal(
    template: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    with pytest.raises(ValueError, match="benchmark_data_unavailable"):
        compute_alpha_metrics(
            _config(template),
            fetch_ohlcv_func=lambda **_: _bars([100.0] * 5, INDEX5),
            build_signals_func=_signals(template),
            build_benchmark_curve_func=lambda *_a, **_k: {
                "equity_curve": [1.0] * 6,
                "observed_mask": [True] * 6,
                "coverage": {"observed_points": 6, "target_points": 6},
            },
        )


# --- The seed is a deposit like any other through the fill router ---------


def test_seed_deposit_defers_with_the_same_router_as_a_contribution() -> None:
    index = pd.bdate_range("2025-01-06", periods=4, tz="UTC")
    close = pd.Series([1.0, 1.5, 2.0, 2.5], index=index, dtype=float)
    result = _dca_equity_curve(
        close=close,
        entries=pd.Series(False, index=index, dtype=bool),
        contribution=0.0,
        starting_capital=10_000.0,
        observed=pd.Series([False, True, True, True], index=index, dtype=bool),
    )
    # Cash idles through the unobserved bar, buys at 1.5, then rides to 2.5.
    assert result.equity_curve.tolist() == pytest.approx(
        [10_000.0, 10_000.0, 10_000.0 * 2.0 / 1.5, 10_000.0 * 2.5 / 1.5]
    )
    assert result.deferred_fill_count == 1
    assert result.external_flows.tolist() == [10_000.0, 0.0, 0.0, 0.0]
    assert result.invested_capital == 10_000.0


def test_engine_facade_forwards_the_observed_mask() -> None:
    index = pd.bdate_range("2025-01-06", periods=3, tz="UTC")
    result = engine._dca_equity_curve(
        close=pd.Series([1.0, 2.0, 2.0], index=index, dtype=float),
        entries=pd.Series([True, True, False], index=index, dtype=bool),
        contribution=100.0,
        observed=pd.Series([True, False, True], index=index, dtype=bool),
    )
    assert result.deferred_fill_count == 1


# --- The stored run says what the comparison rests on ---------------------


def test_stored_metrics_carry_benchmark_coverage_and_deferred_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interior_gap = pd.Series(
        [100.0, 100.0, 200.0, 200.0], index=INDEX5[[0, 1, 3, 4]], dtype=float
    )
    metrics = _run(
        "dca_accumulation", benchmark_series=interior_gap, monkeypatch=monkeypatch
    )
    expected = {
        "observed_points": 4,
        "target_points": 5,
        "observed_ratio": 0.8,
        "deferred_fill_count": 1,
    }
    assert metrics["by_symbol"]["AAPL"]["performance"]["benchmark_coverage"] == expected
    assert metrics["aggregate"]["performance"]["benchmark_coverage"] == expected


def test_fully_observed_benchmark_records_no_deferred_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dense = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=INDEX5, dtype=float)
    for template in ("buy_and_hold", "dca_accumulation"):
        metrics = _run(template, benchmark_series=dense, monkeypatch=monkeypatch)
        assert metrics["aggregate"]["performance"]["benchmark_coverage"] == {
            "observed_points": 5,
            "target_points": 5,
            "observed_ratio": 1.0,
            "deferred_fill_count": 0,
        }


def test_aggregate_coverage_sums_every_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interior_gap = pd.Series(
        [100.0, 100.0, 200.0, 200.0], index=INDEX5[[0, 1, 3, 4]], dtype=float
    )
    config = _config("dca_accumulation")
    config["symbols"] = ["AAPL", "MSFT"]
    metrics = _run(
        "dca_accumulation",
        benchmark_series=interior_gap,
        bars_by_symbol={
            "AAPL": _bars([100.0] * 5, INDEX5),
            "MSFT": _bars([50.0] * 5, INDEX5),
        },
        config=config,
        monkeypatch=monkeypatch,
    )
    assert metrics["aggregate"]["performance"]["benchmark_coverage"] == {
        "observed_points": 8,
        "target_points": 10,
        "observed_ratio": 0.8,
        "deferred_fill_count": 2,
    }
