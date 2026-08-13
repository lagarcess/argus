from __future__ import annotations

from collections.abc import Sequence
from math import expm1, isfinite, log1p, sqrt
from typing import Any

import numpy as np
import pandas as pd

from argus.domain.backtesting.coverage import MetricTimeBasis


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
