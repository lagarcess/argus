from __future__ import annotations

from math import sqrt
from typing import Any

import numpy as np
import pandas as pd


def _compute_profit_factor(returns: pd.Series) -> float:
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    if losses == 0:
        return 10.0 if gains > 0 else 0.0
    return float(gains / abs(losses))


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
    total_return: float, periods: int, periods_per_year: float
) -> float:
    if periods <= 1:
        return total_return * 100.0
    years = periods / periods_per_year
    if years <= 0:
        return total_return * 100.0
    annualized = (1 + total_return) ** (1 / years) - 1
    return annualized * 100.0


def _compute_metrics(
    *,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    allocation_capital: float,
    periods_per_year: float,
    trade_count: int,
) -> dict[str, Any]:
    strategy_equity = (1.0 + strategy_returns).cumprod()
    benchmark_equity = (1.0 + benchmark_returns).cumprod()

    total_return = float(strategy_equity.iloc[-1] - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    volatility_pct = float(strategy_returns.std() * sqrt(periods_per_year) * 100.0)

    active = strategy_returns[strategy_returns != 0]
    win_rate = float((active > 0).mean()) if not active.empty else 0.0

    return {
        "performance": {
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(total_return_pct - benchmark_return_pct, 2),
            "profit": round(allocation_capital * total_return, 2),
            "annualized_return_pct": round(
                _annualized_return_pct(
                    total_return, len(strategy_returns), periods_per_year
                ),
                2,
            ),
        },
        "risk": {
            "max_drawdown_pct": round(_max_drawdown_pct(strategy_equity), 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2),
            "total_trades": trade_count,
            "profit_factor": round(_compute_profit_factor(strategy_returns), 2),
            "sharpe_ratio": round(_compute_sharpe(strategy_returns, periods_per_year), 2),
        },
    }


def _compute_metrics_from_equity(
    *,
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    invested_capital: float,
    periods_per_year: float,
    trade_count: int,
) -> dict[str, Any]:
    strategy_returns = strategy_equity.pct_change().fillna(0.0)
    total_return = float(strategy_equity.iloc[-1] / invested_capital - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] / invested_capital - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    volatility_pct = float(strategy_returns.std() * sqrt(periods_per_year) * 100.0)
    active = strategy_returns[strategy_returns != 0]
    win_rate = float((active > 0).mean()) if not active.empty else 0.0

    return {
        "performance": {
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(total_return_pct - benchmark_return_pct, 2),
            "profit": round(strategy_equity.iloc[-1] - invested_capital, 2),
            "annualized_return_pct": round(
                _annualized_return_pct(
                    total_return, len(strategy_returns), periods_per_year
                ),
                2,
            ),
        },
        "risk": {
            "max_drawdown_pct": round(_max_drawdown_pct(strategy_equity), 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2),
            "total_trades": trade_count,
            "profit_factor": round(_compute_profit_factor(strategy_returns), 2),
            "sharpe_ratio": round(_compute_sharpe(strategy_returns, periods_per_year), 2),
        },
    }
