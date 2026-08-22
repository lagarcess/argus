"""DCA metrics measure investment performance, never deposits (#463/#464/#465).

Every expected value here is derived from prices and cash flows alone; no
assertion reads a production metric helper to compute what it should equal.
"""

from __future__ import annotations

from math import sqrt

import numpy as np
import pandas as pd
import pytest
from argus.domain.backtesting.cards import build_result_card
from argus.domain.backtesting.coverage import build_metric_time_basis
from argus.domain.backtesting.execution import _dca_equity_curve
from argus.domain.backtesting.metrics import (
    _annualized_return_pct,
    _flow_adjusted_returns,
    _money_weighted_annual_return_pct,
)
from argus.domain.backtesting.runner import (
    _aggregate_external_flows,
    compute_alpha_metrics,
)
from hypothesis import given, settings
from hypothesis import strategies as st

_CALENDAR_DAYS_PER_YEAR = 365.2425


def _bars(prices: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(prices, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )


def _dca_config(
    index: pd.DatetimeIndex,
    *,
    contribution: float,
    starting_capital: float = 0.0,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, object]:
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": "monthly"},
        "dca_capital": {
            "schema_version": "dca_capital_v1",
            "starting_capital": starting_capital,
            "contribution": contribution,
        },
        "_execution_realism": {
            "enabled": True,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
        },
    }


def _run_dca(
    config: dict[str, object],
    *,
    prices: list[float],
    benchmark_prices: list[float],
    entries: list[bool],
    index: pd.DatetimeIndex,
) -> dict[str, object]:
    strategy_bars = _bars(prices, index)
    benchmark = pd.Series(benchmark_prices, index=index, dtype=float)
    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: strategy_bars,
        build_signals_func=lambda *_: (
            pd.Series(entries, index=index, dtype=bool),
            pd.Series(False, index=index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda *_args, **_kwargs: {
            "equity_curve": (benchmark / benchmark.iloc[0]).tolist(),
        },
    )


def _expected_ledger(
    *,
    prices: list[float],
    entries: list[bool],
    contribution: float,
    starting_capital: float = 0.0,
    fee: float = 0.0,
    slippage: float = 0.0,
) -> tuple[list[float], list[float], list[float]]:
    """Equity, deposits, and flow-adjusted returns from first principles.

    The first funded bar carries the execution jump from deposited cash to
    the post-fill mark (0 without costs); later intervals subtract the
    bar's deposit before the ratio.
    """
    shares = 0.0
    equity: list[float] = []
    flows: list[float] = []
    for position, price in enumerate(prices):
        deposit = contribution if entries[position] else 0.0
        if position == 0:
            deposit += starting_capital
        shares += deposit / (price * (1.0 + slippage) * (1.0 + fee))
        equity.append(shares * price)
        flows.append(deposit)
    adjusted = [equity[0] / flows[0] - 1.0 if flows[0] > 0.0 else 0.0]
    for position in range(1, len(prices)):
        previous = equity[position - 1]
        if previous > 0.0:
            adjusted.append((equity[position] - flows[position]) / previous - 1.0)
        else:
            adjusted.append(0.0)
    return equity, flows, adjusted


def _period_returns(adjusted: list[float]) -> list[float]:
    """The funding jump compounds into the first real bar interval."""
    if len(adjusted) < 2:
        return []
    first = (1.0 + adjusted[0]) * (1.0 + adjusted[1]) - 1.0
    return [first, *adjusted[2:]]


def _sample_std(values: list[float]) -> float:
    return float(np.std(np.array(values), ddof=1))


# --- The audit's worked example (D1), end to end -------------------------


def test_audit_example_risk_metrics_come_from_flow_adjusted_returns() -> None:
    """Nominal equity [100, 80, 180, 144] with deposits [100, 0, 100, 0]."""
    index = pd.bdate_range("2025-01-02", periods=4, tz="UTC")
    metrics = _run_dca(
        _dca_config(index, contribution=100.0),
        prices=[100.0, 80.0, 80.0, 64.0],
        benchmark_prices=[100.0] * 4,
        entries=[True, False, True, False],
        index=index,
    )
    aggregate = metrics["aggregate"]
    performance = aggregate["performance"]

    # Independent arithmetic: the three real bar intervals return
    # [-20%, 0, -20%] (no costs, so the funding jump is zero and no
    # fabricated first observation exists); wealth compounds through
    # [1.0, 0.8, 0.8, 0.64] from the 1.0 pre-trade baseline.
    adjusted = [-0.2, 0.0, -0.2]
    expected_volatility = _sample_std(adjusted) * sqrt(252.0) * 100.0
    expected_sharpe = float(np.mean(adjusted)) / _sample_std(adjusted) * sqrt(252.0)

    assert performance["return_basis"] == "contributions"
    assert performance["total_return_pct"] == pytest.approx(-28.0, abs=0.01)
    assert performance["profit"] == pytest.approx(-56.0, abs=0.01)
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(-36.0, abs=0.01)
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )
    assert aggregate["efficiency"]["sharpe_ratio"] == pytest.approx(
        expected_sharpe, abs=0.01
    )
    assert aggregate["efficiency"]["win_rate"] is None
    assert aggregate["efficiency"]["profit_factor"] is None
    # Losing a third of the money in five days annualizes to the -100% limit.
    assert performance["annualized_return_pct"] == -100.0
    # Nominal dollars stay nominal: the deposit peak remains chart truth.
    assert performance["portfolio_value_range"]["peak_value"] == pytest.approx(180.0)


def test_contribution_at_an_unchanged_price_is_a_zero_performance_interval() -> None:
    index = pd.bdate_range("2025-01-02", periods=4, tz="UTC")
    metrics = _run_dca(
        _dca_config(index, contribution=250.0),
        prices=[50.0, 50.0, 50.0, 50.0],
        benchmark_prices=[100.0] * 4,
        entries=[True, False, True, False],
        index=index,
    )
    aggregate = metrics["aggregate"]

    assert aggregate["risk"]["max_drawdown_pct"] == 0.0
    assert aggregate["risk"]["volatility_pct"] == 0.0
    assert aggregate["efficiency"]["sharpe_ratio"] == 0.0
    assert aggregate["performance"]["total_return_pct"] == 0.0
    assert aggregate["performance"]["annualized_return_pct"] == pytest.approx(
        0.0, abs=0.01
    )


def test_flow_adjusted_drawdown_ignores_an_economically_identical_deposit() -> None:
    """An added mid-window deposit must not dilute the reported drawdown."""
    index = pd.bdate_range("2025-01-02", periods=4, tz="UTC")
    prices = [100.0, 80.0, 80.0, 64.0]
    with_extra_deposit = _run_dca(
        _dca_config(index, contribution=100.0),
        prices=prices,
        benchmark_prices=[100.0] * 4,
        entries=[True, False, True, False],
        index=index,
    )
    single_deposit = _run_dca(
        _dca_config(index, contribution=100.0),
        prices=prices,
        benchmark_prices=[100.0] * 4,
        entries=[True, False, False, False],
        index=index,
    )

    for key in ("max_drawdown_pct", "volatility_pct"):
        assert with_extra_deposit["aggregate"]["risk"][key] == pytest.approx(
            single_deposit["aggregate"]["risk"][key], abs=0.01
        )
    assert with_extra_deposit["aggregate"]["efficiency"]["sharpe_ratio"] == pytest.approx(
        single_deposit["aggregate"]["efficiency"]["sharpe_ratio"], abs=0.01
    )


@pytest.mark.parametrize(
    "prices",
    [
        [100.0, 110.0, 121.0],
        [100.0, 90.0, 81.0],
        [100.0, 100.0, 100.0],
    ],
    ids=["rising", "falling", "flat"],
)
def test_modeled_cost_ledgers_reconcile_from_prices_and_deposits(
    monkeypatch: pytest.MonkeyPatch,
    prices: list[float],
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    fee = 20.0 / 10_000.0
    slippage = 10.0 / 10_000.0
    contribution = 1_000.0
    index = pd.bdate_range("2025-01-02", periods=3, tz="UTC")
    entries = [True, True, False]
    metrics = _run_dca(
        _dca_config(index, contribution=contribution, fee_bps=20.0, slippage_bps=10.0),
        prices=prices,
        benchmark_prices=[100.0] * 3,
        entries=entries,
        index=index,
    )
    aggregate = metrics["aggregate"]

    equity, _, adjusted = _expected_ledger(
        prices=prices,
        entries=entries,
        contribution=contribution,
        fee=fee,
        slippage=slippage,
    )
    # Drawdown reads the wealth path from the 1.0 pre-trade baseline, so the
    # first deposit's execution cost is itself a fall from that baseline.
    wealth = np.cumprod(1.0 + np.array([0.0, *adjusted]))
    expected_drawdown = float(
        (wealth / np.maximum.accumulate(wealth) - 1.0).min() * 100.0
    )
    expected_volatility = _sample_std(_period_returns(adjusted)) * sqrt(252.0) * 100.0
    expected_return = (equity[-1] / (2.0 * contribution) - 1.0) * 100.0

    assert aggregate["performance"]["total_return_pct"] == pytest.approx(
        expected_return, abs=0.01
    )
    assert aggregate["risk"]["max_drawdown_pct"] == pytest.approx(
        expected_drawdown, abs=0.01
    )
    assert aggregate["risk"]["volatility_pct"] == pytest.approx(
        expected_volatility, abs=0.01
    )


# --- Money-weighted annual return (#465) ---------------------------------


def test_money_weighted_rate_prices_the_late_deposit_correctly() -> None:
    """$100 grows to $110 while a late $100 arrives at year end: 10%, not 5%."""
    index = pd.DatetimeIndex(["2025-01-01", "2026-01-01"], tz="UTC")
    flows = pd.Series([100.0, 100.0], index=index, dtype=float)

    rate = _money_weighted_annual_return_pct(
        external_flows=flows,
        ending_value=210.0,
    )

    years = 365.0 / _CALENDAR_DAYS_PER_YEAR
    expected = (1.1 ** (1.0 / years) - 1.0) * 100.0
    assert rate == pytest.approx(expected, abs=0.01)
    # The simple contribution return would say 5%; the invested dollars say 10%.
    assert rate > 9.0


def test_early_and_late_deposits_with_equal_cash_and_ending_value_differ() -> None:
    index = pd.DatetimeIndex(
        ["2025-01-01", "2025-07-02", "2026-01-01"],
        tz="UTC",
    )
    early = _money_weighted_annual_return_pct(
        external_flows=pd.Series([100.0, 100.0, 0.0], index=index, dtype=float),
        ending_value=210.0,
    )
    late = _money_weighted_annual_return_pct(
        external_flows=pd.Series([100.0, 0.0, 100.0], index=index, dtype=float),
        ending_value=210.0,
    )

    assert early is not None and late is not None
    # The earlier the cash arrives, the more dollar-time the same $10 profit
    # is spread over, so the annual rate is lower.
    assert early < late
    # Neither equals the 5% the fixed-capital formula would print.
    assert abs(early - 5.0) > 1.0
    assert abs(late - 5.0) > 1.0


def test_single_deposit_reduces_to_fixed_capital_annualization() -> None:
    index = pd.DatetimeIndex(
        ["2025-01-01", "2025-07-01", "2025-12-31"],
        tz="UTC",
    )
    flows = pd.Series([1_000.0, 0.0, 0.0], index=index, dtype=float)

    money_weighted = _money_weighted_annual_return_pct(
        external_flows=flows,
        ending_value=1_100.0,
    )
    fixed_capital = _annualized_return_pct(
        0.1,
        build_metric_time_basis(
            asset_class="crypto",
            timeframe="1D",
            effective_index=index,
        ),
    )

    assert money_weighted is not None and fixed_capital is not None
    assert money_weighted == pytest.approx(fixed_capital, abs=0.01)


def test_total_loss_reports_the_negative_one_hundred_limit() -> None:
    index = pd.DatetimeIndex(["2025-01-01", "2025-06-01"], tz="UTC")
    flows = pd.Series([500.0, 500.0], index=index, dtype=float)

    assert (
        _money_weighted_annual_return_pct(external_flows=flows, ending_value=0.0)
        == -100.0
    )


def test_unrepresentably_large_rate_is_null_not_zero() -> None:
    index = pd.DatetimeIndex(["2025-01-01", "2025-01-02"], tz="UTC")
    flows = pd.Series([100.0, 0.0], index=index, dtype=float)

    assert (
        _money_weighted_annual_return_pct(
            external_flows=flows,
            ending_value=1e11,
        )
        is None
    )


def test_window_shorter_than_one_cadence_annualizes_its_single_deposit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    fee = 200.0 / 10_000.0
    slippage = 100.0 / 10_000.0
    index = pd.bdate_range("2025-01-02", periods=2, tz="UTC")
    metrics = _run_dca(
        _dca_config(index, contribution=1_000.0, fee_bps=200.0, slippage_bps=100.0),
        prices=[100.0, 101.0],
        benchmark_prices=[100.0, 100.0],
        entries=[True, False],
        index=index,
    )
    performance = metrics["aggregate"]["performance"]

    shares = 1_000.0 / (100.0 * (1.0 + slippage) * (1.0 + fee))
    ending = shares * 101.0
    years = (index[-1] - index[0]).total_seconds() / (
        _CALENDAR_DAYS_PER_YEAR * 24.0 * 3600.0
    )
    expected = ((ending / 1_000.0) ** (1.0 / years) - 1.0) * 100.0

    assert performance["annualized_return_pct"] == pytest.approx(expected, abs=0.01)


# --- The class guard: no schedule can leak deposits into returns ----------


@st.composite
def _contribution_schedules(
    draw: st.DrawFn,
) -> tuple[list[float], list[bool], float, float]:
    length = draw(st.integers(min_value=3, max_value=24))
    prices = draw(
        st.lists(
            st.floats(min_value=1.0, max_value=1_000.0),
            min_size=length,
            max_size=length,
        )
    )
    entries = draw(st.lists(st.booleans(), min_size=length, max_size=length))
    entries[0] = True
    contribution = draw(st.floats(min_value=10.0, max_value=10_000.0))
    seed = draw(st.floats(min_value=0.0, max_value=10_000.0))
    return prices, entries, contribution, seed


@settings(max_examples=100, deadline=None)
@given(case=_contribution_schedules())
def test_no_contribution_schedule_enters_the_return_series(
    case: tuple[list[float], list[bool], float, float],
) -> None:
    """Without costs, performance is the price path for every schedule."""
    prices, entries, contribution, seed = case
    index = pd.bdate_range("2025-01-02", periods=len(prices), tz="UTC")
    close = pd.Series(prices, index=index, dtype=float)
    result = _dca_equity_curve(
        close=close,
        entries=pd.Series(entries, index=index, dtype=bool),
        contribution=contribution,
        starting_capital=seed,
    )

    adjusted = _flow_adjusted_returns(result.equity_curve, result.external_flows)
    price_returns = close.pct_change()

    # Without costs the funding jump is zero to float precision: the deposit
    # buys shares worth exactly what it paid.
    assert float(adjusted.iloc[0]) == pytest.approx(0.0, abs=1e-12)
    np.testing.assert_allclose(
        adjusted.to_numpy()[1:],
        price_returns.to_numpy()[1:],
        rtol=1e-9,
        atol=1e-12,
    )


@settings(max_examples=100, deadline=None)
@given(case=_contribution_schedules())
def test_modeled_costs_only_ever_drag_a_contribution_interval(
    case: tuple[list[float], list[bool], float, float],
) -> None:
    """With costs, a deposit interval loses exactly the modeled cost, never gains."""
    prices, entries, contribution, seed = case
    fee, slippage = 0.002, 0.001
    index = pd.bdate_range("2025-01-02", periods=len(prices), tz="UTC")
    close = pd.Series(prices, index=index, dtype=float)
    result = _dca_equity_curve(
        close=close,
        entries=pd.Series(entries, index=index, dtype=bool),
        contribution=contribution,
        starting_capital=seed,
        fees=fee,
        slippage=slippage,
    )

    adjusted = _flow_adjusted_returns(result.equity_curve, result.external_flows)
    price_returns = close.pct_change()
    cost_keep_ratio = 1.0 / ((1.0 + slippage) * (1.0 + fee))
    for position in range(1, len(prices)):
        previous_equity = float(result.equity_curve.iloc[position - 1])
        deposit = float(result.external_flows.iloc[position])
        expected = (
            float(price_returns.iloc[position])
            - deposit * (1.0 - cost_keep_ratio) / previous_equity
        )
        assert float(adjusted.iloc[position]) == pytest.approx(
            expected, rel=1e-9, abs=1e-12
        )
        assert (
            float(adjusted.iloc[position]) <= float(price_returns.iloc[position]) + 1e-12
        )


# --- Aggregate flow alignment --------------------------------------------


def test_aggregate_flows_roll_dropped_bars_forward_and_preserve_total() -> None:
    full_index = pd.bdate_range("2025-01-02", periods=5, tz="UTC")
    partial_index = full_index[[0, 1, 3, 4]]
    flows_a = pd.Series([100.0, 0.0, 100.0, 0.0, 0.0], index=full_index)
    flows_b = pd.Series([50.0, 0.0, 50.0, 0.0], index=partial_index)

    aggregated = _aggregate_external_flows([flows_a, flows_b], partial_index)

    # Symbol A's bar-3 deposit (dropped from the aggregate index) rolls to
    # the next kept bar instead of disappearing.
    assert aggregated.tolist() == pytest.approx([150.0, 0.0, 150.0, 0.0])
    assert float(aggregated.sum()) == pytest.approx(
        float(flows_a.sum()) + float(flows_b.sum())
    )


# --- The card states the basis (#464) ------------------------------------


@pytest.mark.parametrize(
    ("language", "expected_label"),
    [("en", "Return on contributions"), ("es", "Retorno sobre aportes")],
)
def test_dca_card_return_row_is_named_as_a_contribution_return(
    language: str,
    expected_label: str,
) -> None:
    index = pd.bdate_range("2025-01-02", periods=4, tz="UTC")
    config = _dca_config(index, contribution=100.0)
    metrics = _run_dca(
        config,
        prices=[100.0, 80.0, 80.0, 64.0],
        benchmark_prices=[100.0] * 4,
        entries=[True, False, True, False],
        index=index,
    )

    card = build_result_card(config, metrics, language=language)
    row_keys = [row["key"] for row in card["rows"]]
    assert "contribution_return_pct" in row_keys
    assert "total_return_pct" not in row_keys
    return_row = next(
        row for row in card["rows"] if row["key"] == "contribution_return_pct"
    )
    assert return_row["label"] == expected_label
    assert return_row["value"] == "-28.0%"


def test_fixed_capital_card_keeps_the_total_return_row() -> None:
    index = pd.bdate_range("2025-01-02", periods=3, tz="UTC")
    config = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": index[0].date().isoformat(),
        "end_date": index[-1].date().isoformat(),
        "starting_capital": 1_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
        "_execution_realism": {"enabled": False, "fee_bps": 0.0, "slippage_bps": 0.0},
    }
    bars = _bars([100.0, 105.0, 110.0], index)
    metrics = compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: bars,
        build_signals_func=lambda *_: (
            pd.Series([True, False, False], index=index, dtype=bool),
            pd.Series(False, index=index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda *_args, **_kwargs: {
            "equity_curve": [1.0, 1.0, 1.0],
        },
    )

    assert metrics["aggregate"]["performance"]["return_basis"] == "fixed_capital"
    card = build_result_card(config, metrics)
    row_keys = [row["key"] for row in card["rows"]]
    assert "total_return_pct" in row_keys
    assert "contribution_return_pct" not in row_keys
