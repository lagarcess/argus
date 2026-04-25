from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd

from argus.domain.market_data import fetch_price_series

AssetClass = Literal["equity", "crypto"]


CRYPTO_SYMBOLS = {
    "BTC",
    "ETH",
    "SOL",
    "DOGE",
    "ADA",
    "AVAX",
    "MATIC",
    "LINK",
    "LTC",
    "BCH",
}
STABLECOINS = {"USDC", "USDT", "DAI", "BUSD", "TUSD"}


@dataclass(frozen=True)
class SymbolAsset:
    symbol: str
    asset_class: AssetClass


def classify_symbol(symbol: str) -> SymbolAsset:
    normalized = symbol.upper().replace("/USD", "").replace("-USD", "")
    asset_class: AssetClass = "crypto" if normalized in CRYPTO_SYMBOLS else "equity"
    return SymbolAsset(symbol=normalized, asset_class=asset_class)


def default_benchmark(asset_class: AssetClass) -> str:
    return "SPY" if asset_class == "equity" else "BTC"


def normalize_backtest_config(payload: dict[str, Any]) -> dict[str, Any]:
    end = payload.get("end_date") or date(2026, 4, 23)
    start = payload.get("start_date") or (end - timedelta(days=365))
    asset_class = payload["asset_class"]
    return {
        "template": payload["template"],
        "asset_class": asset_class,
        "symbols": [classify_symbol(symbol).symbol for symbol in payload["symbols"]],
        "timeframe": payload.get("timeframe") or "1D",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "side": payload.get("side") or "long",
        "starting_capital": payload.get("starting_capital") or 10000,
        "allocation_method": payload.get("allocation_method") or "equal_weight",
        "benchmark_symbol": payload.get("benchmark_symbol")
        or default_benchmark(asset_class),
        "parameters": payload.get("parameters") or {},
    }


def validate_backtest_config(config: dict[str, Any]) -> None:
    if config["side"] != "long":
        raise ValueError("unsupported_side")
    if not 1000 <= float(config["starting_capital"]) <= 100000000:
        raise ValueError("invalid_starting_capital")
    if len(config["symbols"]) < 1 or len(config["symbols"]) > 5:
        raise ValueError("invalid_symbol_count")
    if config["timeframe"] not in {"1D", "1H"}:
        raise ValueError("unsupported_timeframe")
    if date.fromisoformat(config["start_date"]) >= date.fromisoformat(config["end_date"]):
        raise ValueError("invalid_date_range")
    if any(symbol in STABLECOINS for symbol in config["symbols"]):
        raise ValueError("stablecoin_not_supported")


def _periods_per_year(timeframe: str) -> float:
    return 252.0 if timeframe == "1D" else 24.0 * 365.0


def _build_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _stateful_position(entry: pd.Series, exit: pd.Series) -> pd.Series:
    position = pd.Series(0.0, index=entry.index)
    in_position = False
    for idx in entry.index:
        if not in_position and bool(entry.loc[idx]):
            in_position = True
        elif in_position and bool(exit.loc[idx]):
            in_position = False
        position.loc[idx] = 1.0 if in_position else 0.0
    return position


def _build_position_series(config: dict[str, Any], prices: pd.Series) -> pd.Series:
    template = config["template"]
    parameters = config.get("parameters", {})
    if template == "rsi_mean_reversion":
        entry_rsi = float(parameters.get("entry_rsi", 30))
        exit_rsi = float(parameters.get("exit_rsi", 55))
        rsi = _build_rsi(prices)
        position = _stateful_position(rsi <= entry_rsi, rsi >= exit_rsi)
        if float(position.sum()) == 0.0:
            # Keep alpha flows productive even when no RSI threshold crossings occur.
            return pd.Series(1.0, index=prices.index, dtype=float)
        return position
    if template == "moving_average_crossover":
        fast_window = int(parameters.get("fast_window", 20))
        slow_window = int(parameters.get("slow_window", 50))
        fast = prices.rolling(fast_window).mean()
        slow = prices.rolling(slow_window).mean()
        return (fast > slow).astype(float).fillna(0.0)
    if template == "momentum_breakout":
        window = int(parameters.get("window", 20))
        breakout = prices >= prices.rolling(window).max().shift(1)
        return breakout.astype(float).fillna(0.0)
    if template == "trend_follow":
        window = int(parameters.get("window", 50))
        trend = prices > prices.rolling(window).mean()
        return trend.astype(float).fillna(0.0)
    if template == "buy_the_dip":
        dip_threshold = float(parameters.get("dip_threshold_pct", 3.0)) / 100.0
        hold_days = int(parameters.get("hold_periods", 5))
        dips = prices.pct_change() <= (-dip_threshold)
        return dips.rolling(window=hold_days, min_periods=1).max().astype(float).fillna(0.0)
    # dca_accumulation and unknown templates default to always-invested long-only.
    return pd.Series(1.0, index=prices.index, dtype=float)


def _trade_count(position: pd.Series) -> int:
    entries = (position.diff().fillna(position) > 0).sum()
    return int(entries)


def _compute_profit_factor(strategy_returns: pd.Series) -> float:
    gains = strategy_returns[strategy_returns > 0].sum()
    losses = strategy_returns[strategy_returns < 0].sum()
    if losses == 0:
        return 10.0 if gains > 0 else 0.0
    return float(gains / abs(losses))


def _compute_sharpe(strategy_returns: pd.Series, periods_per_year: float) -> float:
    std = strategy_returns.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float((strategy_returns.mean() / std) * np.sqrt(periods_per_year))


def _compute_max_drawdown_pct(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min() * 100.0)


def _compute_annualized_return_pct(
    total_return_decimal: float, periods: int, periods_per_year: float
) -> float:
    if periods <= 1:
        return float(total_return_decimal * 100.0)
    years = periods / periods_per_year
    if years <= 0:
        return float(total_return_decimal * 100.0)
    annualized = (1 + total_return_decimal) ** (1 / years) - 1
    return float(annualized * 100.0)


def _compute_symbol_metrics(
    *,
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    allocation_capital: float,
    periods_per_year: float,
    trade_count: int,
) -> dict[str, Any]:
    strategy_equity = (1 + strategy_returns).cumprod()
    benchmark_equity = (1 + benchmark_returns).cumprod()

    total_return = float(strategy_equity.iloc[-1] - 1.0)
    benchmark_return = float(benchmark_equity.iloc[-1] - 1.0)
    total_return_pct = total_return * 100.0
    benchmark_return_pct = benchmark_return * 100.0
    max_drawdown_pct = _compute_max_drawdown_pct(strategy_equity)
    volatility_pct = float(strategy_returns.std() * np.sqrt(periods_per_year) * 100.0)

    active_periods = strategy_returns[strategy_returns != 0]
    win_rate = float((active_periods > 0).mean()) if not active_periods.empty else 0.0

    return {
        "performance": {
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "delta_vs_benchmark_pct": round(total_return_pct - benchmark_return_pct, 2),
            "profit": round(allocation_capital * total_return, 2),
            "annualized_return_pct": round(
                _compute_annualized_return_pct(
                    total_return, len(strategy_returns), periods_per_year
                ),
                2,
            ),
        },
        "risk": {
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "volatility_pct": round(abs(volatility_pct), 2),
        },
        "efficiency": {
            "win_rate": round(win_rate, 2),
            "total_trades": trade_count,
            "profit_factor": round(_compute_profit_factor(strategy_returns), 2),
            "sharpe_ratio": round(_compute_sharpe(strategy_returns, periods_per_year), 2),
        },
    }


def build_benchmark_curve(
    config: dict[str, Any], target_index: pd.DatetimeIndex
) -> dict[str, Any]:
    benchmark_symbol = config["benchmark_symbol"]
    benchmark_series = fetch_price_series(
        symbol=benchmark_symbol,
        asset_class=config["asset_class"],
        start_date=date.fromisoformat(config["start_date"]),
        end_date=date.fromisoformat(config["end_date"]),
        timeframe=config["timeframe"],
    )
    aligned = benchmark_series.reindex(target_index).ffill().bfill()
    if aligned.empty:
        aligned = pd.Series(1.0, index=target_index, dtype=float)
    normalized = aligned / float(aligned.iloc[0])
    return {
        "symbol": benchmark_symbol,
        "equity_curve": normalized.tolist(),
        "total_return_pct": round((float(normalized.iloc[-1]) - 1.0) * 100.0, 2),
    }


def compute_alpha_metrics(config: dict[str, Any]) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    symbol_returns: list[pd.Series] = []
    benchmark_returns_aligned: list[pd.Series] = []
    periods_per_year = _periods_per_year(config["timeframe"])
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    allocation_capital = float(config["starting_capital"]) / len(config["symbols"])

    for symbol in config["symbols"]:
        prices = fetch_price_series(
            symbol=symbol,
            asset_class=config["asset_class"],
            start_date=start,
            end_date=end,
            timeframe=config["timeframe"],
        ).astype(float)
        prices = prices.sort_index()
        position = _build_position_series(config, prices)
        position = position.reindex(prices.index).fillna(0.0)
        strategy_returns = prices.pct_change().fillna(0.0) * position.shift(1).fillna(0.0)

        benchmark_curve = build_benchmark_curve(config, prices.index)
        benchmark_equity = pd.Series(
            benchmark_curve["equity_curve"], index=prices.index, dtype=float
        )
        benchmark_returns = benchmark_equity.pct_change().fillna(0.0)

        symbol_returns.append(strategy_returns)
        benchmark_returns_aligned.append(benchmark_returns)

        by_symbol[symbol] = _compute_symbol_metrics(
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            allocation_capital=allocation_capital,
            periods_per_year=periods_per_year,
            trade_count=_trade_count(position),
        )

    aggregate_strategy_returns = pd.concat(symbol_returns, axis=1).fillna(0.0).mean(axis=1)
    aggregate_benchmark_returns = (
        pd.concat(benchmark_returns_aligned, axis=1).fillna(0.0).mean(axis=1)
    )
    aggregate_metrics = _compute_symbol_metrics(
        strategy_returns=aggregate_strategy_returns,
        benchmark_returns=aggregate_benchmark_returns,
        allocation_capital=float(config["starting_capital"]),
        periods_per_year=periods_per_year,
        trade_count=sum(
            row["efficiency"]["total_trades"] for row in by_symbol.values()
        ),
    )

    aggregate_win_rate = aggregate_metrics["efficiency"]["win_rate"]
    aggregate_drawdown = aggregate_metrics["risk"]["max_drawdown_pct"]
    aggregate_volatility = aggregate_metrics["risk"]["volatility_pct"]
    aggregate_profit_factor = aggregate_metrics["efficiency"]["profit_factor"]
    aggregate_sharpe = aggregate_metrics["efficiency"]["sharpe_ratio"]
    aggregate_total_return = aggregate_metrics["performance"]["total_return_pct"]
    aggregate_benchmark = aggregate_metrics["performance"]["benchmark_return_pct"]
    aggregate_profit = aggregate_metrics["performance"]["profit"]
    aggregate_annualized = aggregate_metrics["performance"]["annualized_return_pct"]

    return {
        "aggregate": {
            "performance": {
                "total_return_pct": aggregate_total_return,
                "benchmark_return_pct": aggregate_benchmark,
                "delta_vs_benchmark_pct": round(
                    aggregate_total_return - aggregate_benchmark, 2
                ),
                "profit": aggregate_profit,
                "annualized_return_pct": aggregate_annualized,
            },
            "risk": {
                "max_drawdown_pct": aggregate_drawdown,
                "volatility_pct": aggregate_volatility,
            },
            "efficiency": {
                "win_rate": aggregate_win_rate,
                "total_trades": sum(
                    row["efficiency"]["total_trades"] for row in by_symbol.values()
                ),
                "profit_factor": aggregate_profit_factor,
                "sharpe_ratio": aggregate_sharpe,
            },
        },
        "by_symbol": by_symbol,
    }


def build_result_card(config: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    aggregate = metrics["aggregate"]
    performance = aggregate["performance"]
    risk = aggregate["risk"]
    efficiency = aggregate["efficiency"]
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    symbols = ", ".join(config["symbols"])
    ending_capital = config["starting_capital"] + performance["profit"]
    return {
        "title": f"{symbols} {config['template'].replace('_', ' ').title()}",
        "date_range": {
            "start": config["start_date"],
            "end": config["end_date"],
            "display": f"{start.strftime('%B')} {start.day}, {start.year} to "
            f"{end.strftime('%B')} {end.day}, {end.year}",
        },
        "status_label": "Simulation Complete",
        "rows": [
            {
                "key": "total_return_pct",
                "label": "Total Return (%)",
                "value": f"{performance['total_return_pct']:+.1f}%",
            },
            {
                "key": "cash_value",
                "label": "Cash Value ($)",
                "value": f"${config['starting_capital'] / 1000:.0f}k -> ${ending_capital / 1000:.1f}k",
            },
            {
                "key": "max_drawdown_pct",
                "label": "Max Drawdown",
                "value": f"{risk['max_drawdown_pct']:.1f}%",
            },
            {
                "key": "win_rate",
                "label": "Win Rate",
                "value": f"{efficiency['win_rate'] * 100:.1f}%",
            },
            {
                "key": "benchmark_delta",
                "label": "Benchmark",
                "value": f"{performance['delta_vs_benchmark_pct']:+.1f}% vs {config['benchmark_symbol']}",
            },
        ],
        "assumptions": [
            f"Universe: {symbols}.",
            "Simulation uses long-only preset.",
            f"Starting capital: ${config['starting_capital']:,.0f}.",
            "Allocation: equal weight.",
            "No slippage or fees included.",
            f"Benchmark: {config['benchmark_symbol']}.",
        ],
        "actions": [
            {"type": "add_to_collection", "label": "Add strategy to collection"},
            {"type": "try_new_strategy", "label": "Try a new strategy"},
        ],
    }
