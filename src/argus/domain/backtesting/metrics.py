from __future__ import annotations

from collections.abc import Sequence
from math import expm1, isfinite, log1p, sqrt
from typing import Any

import numpy as np
import pandas as pd

from argus.domain.backtesting.coverage import MetricTimeBasis

_CALENDAR_DAYS_PER_YEAR = 365.2425
_SECONDS_PER_YEAR = _CALENDAR_DAYS_PER_YEAR * 24.0 * 60.0 * 60.0
# Annual rates past this bound have no product meaning; the metric is null,
# matching the fixed-capital overflow convention.
_MAX_ANNUAL_RATE = 1e9


def _compute_profit_factor(closed_trade_pnls: Sequence[float]) -> float | None:
    gains = sum(pnl for pnl in closed_trade_pnls if pnl > 0.0)
    losses = sum(pnl for pnl in closed_trade_pnls if pnl < 0.0)
    if losses == 0.0:
        return None
    return float(gains / abs(losses))


def _closed_trade_win_rate(closed_trade_pnls: Sequence[float]) -> float | None:
    if not closed_trade_pnls:
        return None
    winning_trades = sum(1 for pnl in closed_trade_pnls if pnl > 0.0)
    return float(winning_trades / len(closed_trade_pnls))


def _compute_sharpe(returns: pd.Series, periods_per_year: float) -> float:
    std = returns.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float((returns.mean() / std) * sqrt(periods_per_year))


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min() * 100.0)


def portfolio_value_summary(equity_curve: pd.Series) -> dict[str, Any] | None:
    values = equity_curve.dropna().astype(float)
    if values.empty:
        return None
    return {
        "peak_value": round(float(values.max()), 2),
        "lowest_value": round(float(values.min()), 2),
        "currency": "USD",
        "source": "strategy_portfolio_equity_close",
    }


def _annualized_return_pct(
    total_return: float,
    time_basis: MetricTimeBasis,
) -> float | None:
    if not isfinite(total_return) or total_return < -1.0:
        return None
    if total_return == -1.0:
        return -100.0
    if time_basis.elapsed_years is None:
        return total_return * 100.0
    if time_basis.elapsed_years <= 0:
        return total_return * 100.0
    try:
        annualized_pct = expm1(log1p(total_return) / time_basis.elapsed_years) * 100.0
    except OverflowError:
        return None
    return float(annualized_pct) if isfinite(annualized_pct) else None


def _rounded_annualized_return_pct(
    total_return: float,
    time_basis: MetricTimeBasis,
) -> float | None:
    annualized = _annualized_return_pct(total_return, time_basis)
    return round(annualized, 2) if annualized is not None else None


def _flow_adjusted_returns(
    strategy_equity: pd.Series,
    external_flows: pd.Series,
) -> pd.Series:
    """Investment performance per interval, with deposits subtracted.

    ``r[t] = (E[t] - F[t]) / E[t-1] - 1``. Intervals that begin with no
    invested value are 0.0, as is the first interval (the pre-trade
    baseline belongs to #468 for every template).
    """
    flows = external_flows.reindex(strategy_equity.index).fillna(0.0).astype(float)
    previous = strategy_equity.shift(1)
    adjusted = (strategy_equity - flows) / previous - 1.0
    return adjusted.where(previous > 0.0, 0.0).fillna(0.0)


def _money_weighted_annual_return_pct(
    *,
    external_flows: pd.Series,
    ending_value: float,
) -> float | None:
    """The annual rate the deposited dollars earned: a dated-cash-flow IRR.

    Each deposit compounds from its own bar timestamp to the final bar, so
    the rate solves ``sum(flow * (1 + r) ** years_to_end) = ending_value``.
    Deposits followed by one terminal value have a single sign change, so
    the root is unique when it exists. When no rate above -100% can
    reproduce the ending value the limit -100.0 is reported, and a rate too
    large to mean anything is None, matching the fixed-capital overflow
    convention.
    """
    flows = external_flows.dropna().astype(float)
    flows = flows[flows > 0.0]
    if flows.empty or len(external_flows.index) == 0:
        return None
    if not isfinite(ending_value) or ending_value < 0.0:
        return None
    terminal = pd.Timestamp(external_flows.index[-1])
    years = np.array(
        [
            (terminal - pd.Timestamp(timestamp)).total_seconds() / _SECONDS_PER_YEAR
            for timestamp in flows.index
        ],
        dtype=float,
    )
    if float(years.max()) <= 0.0:
        return None
    amounts = flows.to_numpy(dtype=float)

    def grown(rate: float) -> float:
        return float(np.sum(amounts * (1.0 + rate) ** years))

    terminal_dated_deposits = float(amounts[years <= 0.0].sum())
    if ending_value <= terminal_dated_deposits:
        return -100.0
    low, high = -1.0 + 1e-12, 1.0
    while grown(high) < ending_value:
        high *= 2.0
        if high > _MAX_ANNUAL_RATE:
            return None
    for _ in range(200):
        mid = (low + high) / 2.0
        if grown(mid) < ending_value:
            low = mid
        else:
            high = mid
    rate_pct = ((low + high) / 2.0) * 100.0
    return float(rate_pct) if isfinite(rate_pct) else None


def _compute_metrics(
    *,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    allocation_capital: float,
    time_basis: MetricTimeBasis,
    trade_count: int,
    closed_trade_pnls: Sequence[float],
) -> dict[str, Any]:
    strategy_equity = (1.0 + strategy_returns).cumprod()
    benchmark_equity = (1.0 + benchmark_returns).cumprod()

    total_return = float(strategy_equity.iloc[-1] - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    volatility_pct = float(
        strategy_returns.std() * sqrt(time_basis.periods_per_year) * 100.0
    )
    win_rate = _closed_trade_win_rate(closed_trade_pnls)
    profit_factor = _compute_profit_factor(closed_trade_pnls)

    return {
        "performance": {
            "return_basis": "fixed_capital",
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(total_return_pct - benchmark_return_pct, 2),
            "profit": round(allocation_capital * total_return, 2),
            "annualized_return_pct": _rounded_annualized_return_pct(
                total_return,
                time_basis,
            ),
        },
        "risk": {
            "max_drawdown_pct": round(_max_drawdown_pct(strategy_equity), 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2) if win_rate is not None else None,
            "total_trades": trade_count,
            "profit_factor": (
                round(profit_factor, 2) if profit_factor is not None else None
            ),
            "sharpe_ratio": round(
                _compute_sharpe(strategy_returns, time_basis.periods_per_year),
                2,
            ),
        },
    }


def _compute_dca_metrics(
    *,
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    external_flows: pd.Series,
    invested_capital: float,
    time_basis: MetricTimeBasis,
    trade_count: int,
) -> dict[str, Any]:
    """Metrics for a run funded by dated deposits rather than one bankroll.

    Deposits are cash arriving, not performance: risk and efficiency read
    flow-adjusted returns, the headline return is a simple ratio on
    contributed cash, and the annual rate is money-weighted over the dated
    flows. Nominal equity still owns ending value, profit, and the chart.
    """
    adjusted_returns = _flow_adjusted_returns(strategy_equity, external_flows)
    wealth_index = (1.0 + adjusted_returns).cumprod()
    contribution_return_pct = (
        float(strategy_equity.iloc[-1] / invested_capital - 1.0) * 100.0
    )
    benchmark_return_pct = (
        float(benchmark_equity.iloc[-1] / invested_capital - 1.0) * 100.0
    )
    volatility_pct = float(
        adjusted_returns.std() * sqrt(time_basis.periods_per_year) * 100.0
    )
    annualized = _money_weighted_annual_return_pct(
        external_flows=external_flows,
        ending_value=float(strategy_equity.iloc[-1]),
    )

    return {
        "performance": {
            "return_basis": "contributions",
            "total_return_pct": round(contribution_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(
                contribution_return_pct - benchmark_return_pct, 2
            ),
            "profit": round(strategy_equity.iloc[-1] - invested_capital, 2),
            "annualized_return_pct": (
                round(annualized, 2) if annualized is not None else None
            ),
        },
        "risk": {
            "max_drawdown_pct": round(_max_drawdown_pct(wealth_index), 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            # An accumulation plan never closes a position, so closed-trade
            # statistics are absent rather than zero.
            "win_rate": None,
            "total_trades": trade_count,
            "profit_factor": None,
            "sharpe_ratio": round(
                _compute_sharpe(adjusted_returns, time_basis.periods_per_year),
                2,
            ),
        },
    }


def _compute_metrics_from_equity(
    *,
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    invested_capital: float,
    time_basis: MetricTimeBasis,
    trade_count: int,
    closed_trade_pnls: Sequence[float],
) -> dict[str, Any]:
    strategy_returns = strategy_equity.pct_change().fillna(0.0)
    total_return = float(strategy_equity.iloc[-1] / invested_capital - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] / invested_capital - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    volatility_pct = float(
        strategy_returns.std() * sqrt(time_basis.periods_per_year) * 100.0
    )
    win_rate = _closed_trade_win_rate(closed_trade_pnls)
    profit_factor = _compute_profit_factor(closed_trade_pnls)

    return {
        "performance": {
            "return_basis": "fixed_capital",
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(total_return_pct - benchmark_return_pct, 2),
            "profit": round(strategy_equity.iloc[-1] - invested_capital, 2),
            "annualized_return_pct": _rounded_annualized_return_pct(
                total_return,
                time_basis,
            ),
        },
        "risk": {
            "max_drawdown_pct": round(_max_drawdown_pct(strategy_equity), 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2) if win_rate is not None else None,
            "total_trades": trade_count,
            "profit_factor": (
                round(profit_factor, 2) if profit_factor is not None else None
            ),
            "sharpe_ratio": round(
                _compute_sharpe(strategy_returns, time_basis.periods_per_year),
                2,
            ),
        },
    }
