from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
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
    invested value are 0.0, except the first funded bar: its value is the
    execution jump from the pre-trade cash baseline to the post-fill mark,
    ``E[fs] / cumulative_flows[fs] - 1``, which is the modeled entry cost
    and 0.0 without costs (#468).
    """
    flows = external_flows.reindex(strategy_equity.index).fillna(0.0).astype(float)
    previous = strategy_equity.shift(1)
    adjusted = (strategy_equity - flows) / previous - 1.0
    adjusted = adjusted.where(previous > 0.0, 0.0).fillna(0.0)
    cumulative_flows = flows.cumsum()
    funded = (cumulative_flows > 0.0).to_numpy()
    if funded.any():
        first_funded = int(funded.argmax())
        if not bool(previous.iloc[first_funded] > 0.0):
            adjusted.iloc[first_funded] = float(
                strategy_equity.iloc[first_funded] / cumulative_flows.iloc[first_funded]
                - 1.0
            )
    return adjusted


@dataclass(frozen=True)
class BaselineAnchoredSeries:
    """The one metric series shape both capital templates share (#468).

    ``period_returns`` carries one flow-adjusted return per bar interval
    from the first funded bar, with the funding bar's execution jump
    compounded into the first interval, so entry costs count exactly once
    at bar-interval duration. ``drawdown_path`` is the wealth path anchored
    at the 1.0 pre-trade baseline and keeps the funded bar's post-fill mark.
    """

    period_returns: pd.Series
    drawdown_path: pd.Series


def _baseline_anchored_series(
    strategy_equity: pd.Series,
    external_flows: pd.Series,
) -> BaselineAnchoredSeries:
    adjusted = _flow_adjusted_returns(strategy_equity, external_flows)
    flows = external_flows.reindex(strategy_equity.index).fillna(0.0).astype(float)
    funded = (flows.cumsum() > 0.0).to_numpy()
    if not funded.any():
        return BaselineAnchoredSeries(
            period_returns=pd.Series(dtype=float),
            drawdown_path=pd.Series([1.0], dtype=float),
        )
    first_funded = int(funded.argmax())
    jump = float(adjusted.iloc[first_funded])
    period_returns = adjusted.iloc[first_funded + 1 :].copy()
    if len(period_returns) > 0:
        period_returns.iloc[0] = (1.0 + jump) * (
            1.0 + float(period_returns.iloc[0])
        ) - 1.0
    wealth = (1.0 + adjusted.iloc[first_funded:]).cumprod()
    drawdown_path = pd.Series(
        np.concatenate([[1.0], wealth.to_numpy(dtype=float)]),
        dtype=float,
    )
    return BaselineAnchoredSeries(
        period_returns=period_returns,
        drawdown_path=drawdown_path,
    )


def _dispersion_metrics(
    period_returns: pd.Series,
    periods_per_year: float,
) -> tuple[float | None, float | None]:
    """Volatility percent and Sharpe from real return intervals only.

    Sample dispersion needs at least two intervals; with fewer, both values
    are null rather than a fabricated zero.
    """
    if len(period_returns) < 2:
        return None, None
    volatility_pct = float(period_returns.std() * sqrt(periods_per_year) * 100.0)
    return abs(volatility_pct), _compute_sharpe(period_returns, periods_per_year)


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
    the baseline-anchored flow-adjusted series, the headline return is a
    simple ratio on contributed cash, and the annual rate is money-weighted
    over the dated flows. Nominal equity still owns ending value, profit,
    and the chart.
    """
    anchored = _baseline_anchored_series(strategy_equity, external_flows)
    contribution_return_pct = (
        float(strategy_equity.iloc[-1] / invested_capital - 1.0) * 100.0
    )
    benchmark_return_pct = (
        float(benchmark_equity.iloc[-1] / invested_capital - 1.0) * 100.0
    )
    volatility_pct, sharpe_ratio = _dispersion_metrics(
        anchored.period_returns,
        time_basis.periods_per_year,
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
            "max_drawdown_pct": round(_max_drawdown_pct(anchored.drawdown_path), 2),
            "volatility_pct": (
                round(volatility_pct, 2) if volatility_pct is not None else None
            ),
        },
        "efficiency": {
            # An accumulation plan never closes a position, so closed-trade
            # statistics are absent rather than zero.
            "win_rate": None,
            "total_trades": trade_count,
            "profit_factor": None,
            "sharpe_ratio": (
                round(sharpe_ratio, 2) if sharpe_ratio is not None else None
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
    """Metrics for a run funded by one bankroll on the first bar.

    The bankroll is a single external flow at bar 0, so the risk series is
    the same baseline-anchored shape the contributions path uses: drawdown
    starts at the pre-trade capital, a first-bar execution cost is the
    first period's loss, and no fabricated zero return exists.
    """
    external_flows = pd.Series(0.0, index=strategy_equity.index, dtype=float)
    if len(external_flows) > 0:
        external_flows.iloc[0] = invested_capital
    anchored = _baseline_anchored_series(strategy_equity, external_flows)
    total_return = float(strategy_equity.iloc[-1] / invested_capital - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] / invested_capital - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    volatility_pct, sharpe_ratio = _dispersion_metrics(
        anchored.period_returns,
        time_basis.periods_per_year,
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
            "max_drawdown_pct": round(_max_drawdown_pct(anchored.drawdown_path), 2),
            "volatility_pct": (
                round(volatility_pct, 2) if volatility_pct is not None else None
            ),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2) if win_rate is not None else None,
            "total_trades": trade_count,
            "profit_factor": (
                round(profit_factor, 2) if profit_factor is not None else None
            ),
            "sharpe_ratio": (
                round(sharpe_ratio, 2) if sharpe_ratio is not None else None
            ),
        },
    }
