from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from typing import Any, Literal

import numpy as np
import pandas as pd
import vectorbt as vbt

from argus.domain.market_data import fetch_ohlcv, fetch_price_series, resolve_asset

try:  # noqa: SIM105
    import pandas_ta_classic  # noqa: F401
except Exception:  # pragma: no cover - accessor may already be available
    pass

AssetClass = Literal["equity", "crypto"]

ALLOWED_TEMPLATES = {
    "buy_the_dip",
    "rsi_mean_reversion",
    "moving_average_crossover",
    "dca_accumulation",
    "momentum_breakout",
    "trend_follow",
}

ALLOWED_TIMEFRAMES = {"1h", "2h", "4h", "6h", "12h", "1D"}

STABLECOINS = {"USDC", "USDT", "DAI", "BUSD", "TUSD"}


@dataclass(frozen=True)
class SymbolAsset:
    symbol: str
    asset_class: AssetClass


def classify_symbol(symbol: str) -> SymbolAsset:
    resolved = resolve_asset(symbol)
    return SymbolAsset(symbol=resolved.canonical_symbol, asset_class=resolved.asset_class)


def default_benchmark(asset_class: AssetClass) -> str:
    return "SPY" if asset_class == "equity" else "BTC"


def _normalize_timeframe(timeframe: str | None) -> str:
    if timeframe is None:
        return "1D"
    normalized = timeframe.strip().lower()
    mapping = {
        "1d": "1D",
        "1day": "1D",
        "1h": "1h",
        "1hour": "1h",
        "2h": "2h",
        "2hour": "2h",
        "4h": "4h",
        "4hour": "4h",
        "6h": "6h",
        "6hour": "6h",
        "12h": "12h",
        "12hour": "12h",
    }
    if normalized not in mapping:
        raise ValueError("unsupported_timeframe")
    return mapping[normalized]


def _to_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _periods_per_year(timeframe: str) -> float:
    mapping = {
        "1D": 252.0,
        "1h": 24.0 * 365.0,
        "2h": 12.0 * 365.0,
        "4h": 6.0 * 365.0,
        "6h": 4.0 * 365.0,
        "12h": 2.0 * 365.0,
    }
    return mapping[timeframe]


def _vbt_freq(timeframe: str) -> str:
    mapping = {
        "1D": "1D",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
    }
    return mapping[timeframe]


def normalize_backtest_config(payload: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    end_default = today - timedelta(days=1)
    end = _to_date(payload.get("end_date") or end_default)
    start = _to_date(payload.get("start_date") or (end - timedelta(days=365)))
    asset_class = payload["asset_class"]
    symbols = [classify_symbol(symbol).symbol for symbol in payload["symbols"]]
    timeframe = _normalize_timeframe(payload.get("timeframe"))

    benchmark_input = payload.get("benchmark_symbol")
    if benchmark_input:
        benchmark_asset = classify_symbol(benchmark_input)
        if benchmark_asset.asset_class != asset_class:
            raise ValueError("invalid_benchmark_symbol")
        benchmark_symbol = benchmark_asset.symbol
    else:
        benchmark_symbol = default_benchmark(asset_class)

    return {
        "template": payload["template"],
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": timeframe,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "side": payload.get("side") or "long",
        "starting_capital": payload.get("starting_capital") or 10000,
        "allocation_method": payload.get("allocation_method") or "equal_weight",
        "benchmark_symbol": benchmark_symbol,
        "parameters": payload.get("parameters") or {},
        "_execution_realism": payload.get("_execution_realism") or {"enabled": False},
    }


def validate_backtest_config(config: dict[str, Any]) -> None:
    if config["template"] not in ALLOWED_TEMPLATES:
        raise ValueError("unsupported_template")
    if config["side"] != "long":
        raise ValueError("unsupported_side")
    if config["allocation_method"] != "equal_weight":
        raise ValueError("unsupported_allocation_method")
    if not 1000 <= float(config["starting_capital"]) <= 100000000:
        raise ValueError("invalid_starting_capital")
    if len(config["symbols"]) < 1 or len(config["symbols"]) > 5:
        raise ValueError("invalid_symbol_count")
    if config["timeframe"] not in ALLOWED_TIMEFRAMES:
        raise ValueError("unsupported_timeframe")

    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    if start >= end:
        raise ValueError("invalid_date_range")
    if end > date.today():
        raise ValueError("invalid_date_range")
    if (end - start).days > 365 * 3:
        raise ValueError("invalid_lookback_window")

    if any(symbol in STABLECOINS for symbol in config["symbols"]):
        raise ValueError("stablecoin_not_supported")

    if config.get("parameters"):
        raise ValueError("unsupported_parameters")


def _resolve_indicator_series(
    data: pd.DataFrame,
    *,
    indicator: str,
    period: int,
    fallback_col: str = "close",
) -> pd.Series:
    if fallback_col not in data.columns:
        raise ValueError("market_data_unavailable")

    name = indicator.strip().lower()
    ta_accessor = getattr(data, "ta", None)
    if ta_accessor is None:
        raise ValueError("unsupported_indicator")
    accessor = getattr(ta_accessor, name, None)
    if accessor is None:
        raise ValueError("unsupported_indicator")

    kwargs: dict[str, Any] = {"append": True}
    try:
        params = inspect.signature(accessor).parameters
    except (TypeError, ValueError):
        params = {}

    if "length" in params:
        kwargs["length"] = period
    elif "window" in params:
        kwargs["window"] = period
    elif "period" in params:
        kwargs["period"] = period

    if "close" in params:
        kwargs["close"] = data[fallback_col]

    accessor(**kwargs)

    upper = indicator.upper()
    candidates = [
        col for col in data.columns if upper in col.upper() and str(period) in col
    ]
    if not candidates:
        candidates = [col for col in data.columns if upper in col.upper()]
    if not candidates:
        raise ValueError("unsupported_indicator")
    return data[candidates[-1]].astype(float)


def _build_signals(
    config: dict[str, Any], data: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    close = data["close"].astype(float)
    template = config["template"]
    index = close.index

    if template == "dca_accumulation":
        entries = pd.Series(False, index=index, dtype=bool)
        entries.iloc[0] = True
        exits = pd.Series(False, index=index, dtype=bool)
        return entries, exits

    if template == "rsi_mean_reversion":
        rsi = _resolve_indicator_series(data, indicator="rsi", period=14)
        entries = (rsi <= 30).fillna(False)
        exits = (rsi >= 55).fillna(False)
        return entries.astype(bool), exits.astype(bool)

    if template == "moving_average_crossover":
        fast = _resolve_indicator_series(data, indicator="sma", period=20)
        slow = _resolve_indicator_series(data, indicator="sma", period=50)
        entries = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        exits = (fast < slow) & (fast.shift(1) >= slow.shift(1))
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "momentum_breakout":
        rolling_high = close.rolling(20).max().shift(1)
        rolling_mid = close.rolling(20).mean()
        entries = close >= rolling_high
        exits = close < rolling_mid
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "trend_follow":
        trend = close > close.rolling(50).mean()
        entries = trend & ~trend.shift(1).fillna(False)
        exits = (~trend) & trend.shift(1).fillna(False)
        return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)

    if template == "buy_the_dip":
        dip = close.pct_change().fillna(0.0) <= -0.03
        entries = dip.fillna(False)
        exits = entries.shift(5).fillna(False)
        return entries.astype(bool), exits.astype(bool)

    raise ValueError("unsupported_template")


def _execution_realism_settings(config: dict[str, Any]) -> dict[str, float | bool]:
    raw = config.get("_execution_realism") or {}
    enabled = bool(raw.get("enabled", False))
    fee_bps = float(raw.get("fee_bps", 0.0))
    slippage_bps = float(raw.get("slippage_bps", 0.0))
    if not enabled:
        fee_bps = 0.0
        slippage_bps = 0.0
    return {
        "enabled": enabled,
        "fees": fee_bps / 10000.0,
        "slippage": slippage_bps / 10000.0,
    }


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


def _trade_count(entries: pd.Series) -> int:
    return int(entries.fillna(False).sum())


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
        raise ValueError("market_data_unavailable")
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
    symbol_equity_curves: list[pd.Series] = []
    benchmark_equity_curves: list[pd.Series] = []
    periods_per_year = _periods_per_year(config["timeframe"])
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    allocation_capital = float(config["starting_capital"]) / len(config["symbols"])
    realism = _execution_realism_settings(config)

    for symbol in config["symbols"]:
        bars = fetch_ohlcv(
            symbol=symbol,
            asset_class=config["asset_class"],
            start_date=start,
            end_date=end,
            timeframe=config["timeframe"],
        )
        close = bars["close"].astype(float)
        entries, exits = _build_signals(config, bars)

        portfolio = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            fees=float(realism["fees"]),
            slippage=float(realism["slippage"]),
            init_cash=allocation_capital,
            freq=_vbt_freq(config["timeframe"]),
        )

        symbol_equity = pd.Series(
            portfolio.value().values, index=close.index, dtype=float
        )
        strategy_returns = symbol_equity.pct_change().fillna(0.0)

        benchmark_curve = build_benchmark_curve(config, close.index)
        benchmark_normalized = pd.Series(
            benchmark_curve["equity_curve"], index=close.index, dtype=float
        )
        benchmark_equity = benchmark_normalized * allocation_capital
        benchmark_returns = benchmark_equity.pct_change().fillna(0.0)

        symbol_returns.append(strategy_returns)
        benchmark_returns_aligned.append(benchmark_returns)
        symbol_equity_curves.append(symbol_equity)
        benchmark_equity_curves.append(benchmark_equity)

        by_symbol[symbol] = _compute_metrics(
            strategy_returns=strategy_returns,
            benchmark_returns=benchmark_returns,
            allocation_capital=allocation_capital,
            periods_per_year=periods_per_year,
            trade_count=_trade_count(entries),
        )

    aggregate_strategy_equity = (
        pd.concat(symbol_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
    aggregate_benchmark_equity = (
        pd.concat(benchmark_equity_curves, axis=1).ffill().bfill().sum(axis=1)
    )
    aggregate_strategy_returns = aggregate_strategy_equity.pct_change().fillna(0.0)
    aggregate_benchmark_returns = aggregate_benchmark_equity.pct_change().fillna(0.0)

    aggregate_metrics = _compute_metrics(
        strategy_returns=aggregate_strategy_returns,
        benchmark_returns=aggregate_benchmark_returns,
        allocation_capital=float(config["starting_capital"]),
        periods_per_year=periods_per_year,
        trade_count=sum(row["efficiency"]["total_trades"] for row in by_symbol.values()),
    )

    return {
        "aggregate": aggregate_metrics,
        "by_symbol": by_symbol,
    }


def build_result_card(
    config: dict[str, Any], metrics: dict[str, Any], language: str = "en"
) -> dict[str, Any]:
    aggregate = metrics["aggregate"]
    performance = aggregate["performance"]
    risk = aggregate["risk"]
    efficiency = aggregate["efficiency"]
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    symbols = ", ".join(config["symbols"])
    ending_capital = config["starting_capital"] + performance["profit"]
    realism = _execution_realism_settings(config)

    is_es = language.startswith("es")
    template_names = {
        "buy_the_dip": "Comprar la Caída" if is_es else "Buy the Dip",
        "rsi_mean_reversion": "Reversión a la Media RSI" if is_es else "RSI Mean Reversion",
        "moving_average_crossover": "Cruce de Medias Móviles" if is_es else "Moving Average Crossover",
        "dca_accumulation": "Acumulación DCA" if is_es else "DCA Accumulation",
        "momentum_breakout": "Ruptura de Impulso" if is_es else "Momentum Breakout",
        "trend_follow": "Seguimiento de Tendencia" if is_es else "Trend Follow",
    }
    template_display = template_names.get(config["template"], config["template"].replace("_", " ").title())

    status_label = "Simulación Completa" if is_es else "Simulation Complete"

    benchmark_note = f"Universe: {symbols}. Benchmark: {config['benchmark_symbol']}."
    if is_es:
        benchmark_note = f"Universo: {symbols}. Referencia: {config['benchmark_symbol']}."
        assumptions = [
            "La simulación utiliza el preajuste solo-largo.",
            f"Capital inicial: ${config['starting_capital']:,.0f}.",
            "Asignación: igual peso.",
            "No se incluyen deslizamientos ni comisiones.",
        ]
        if bool(realism["enabled"]):
            assumptions[3] = "Realismo de ejecución habilitado (comisiones/deslizamiento aplicados)."
    else:
        assumptions = [
            "Simulation uses long-only preset.",
            f"Starting capital: ${config['starting_capital']:,.0f}.",
            "Allocation: equal weight.",
            "No slippage or fees included.",
        ]
        if bool(realism["enabled"]):
            assumptions[3] = "Execution realism enabled (fees/slippage applied)."

    rows = [
        {
            "key": "total_return_pct",
            "label": "Retorno Total (%)" if is_es else "Total Return (%)",
            "value": f"{performance['total_return_pct']:+.1f}%",
        },
        {
            "key": "cash_value",
            "label": "Valor en Efectivo ($)" if is_es else "Cash Value ($)",
            "value": f"${config['starting_capital'] / 1000:.0f}k -> ${ending_capital / 1000:.1f}k",
        },
        {
            "key": "max_drawdown_pct",
            "label": "Máxima Caída" if is_es else "Max Drawdown",
            "value": f"{risk['max_drawdown_pct']:.1f}%",
        },
        {
            "key": "win_rate",
            "label": "Tasa de Acierto" if is_es else "Win Rate",
            "value": f"{efficiency['win_rate'] * 100:.1f}%",
        },
        {
            "key": "benchmark_delta",
            "label": "Referencia" if is_es else "Benchmark",
            "value": f"{performance['delta_vs_benchmark_pct']:+.1f}% vs {config['benchmark_symbol']}",
        },
    ]

    return {
        "title": f"{symbols} {template_display}",
        "date_range": {
            "start": config["start_date"],
            "end": config["end_date"],
            "display": f"{start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}" if is_es
            else f"{start.strftime('%B')} {start.day}, {start.year} to {end.strftime('%B')} {end.day}, {end.year}",
        },
        "status_label": status_label,
        "rows": rows,
        "assumptions": assumptions,
        "benchmark_note": benchmark_note,
        "actions": [
            {"type": "add_to_collection", "label": "Añadir estrategia a colección" if is_es else "Add strategy to collection"},
            {"type": "try_new_strategy", "label": "Probar nueva estrategia" if is_es else "Try a new strategy"},
        ],
    }
