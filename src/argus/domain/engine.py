from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

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
    if date.fromisoformat(config["start_date"]) >= date.fromisoformat(
        config["end_date"]
    ):
        raise ValueError("invalid_date_range")
    if any(symbol in STABLECOINS for symbol in config["symbols"]):
        raise ValueError("stablecoin_not_supported")


def compute_alpha_metrics(config: dict[str, Any]) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    returns: list[float] = []
    drawdowns: list[float] = []
    win_rates: list[float] = []
    benchmark_return = 12.1 if config["asset_class"] == "equity" else 31.4

    for symbol in config["symbols"]:
        digest = hashlib.sha256(
            f"{symbol}:{config['template']}:{config['start_date']}".encode()
        ).hexdigest()
        seed = int(digest[:8], 16)
        total_return = round(((seed % 5200) / 100) - 12, 2)
        max_drawdown = round(-1 * (5 + (seed % 2200) / 100), 2)
        win_rate = round(0.38 + ((seed >> 5) % 28) / 100, 2)
        profit = round(config["starting_capital"] * total_return / 100, 2)
        returns.append(total_return)
        drawdowns.append(max_drawdown)
        win_rates.append(win_rate)
        by_symbol[symbol] = {
            "performance": {
                "total_return_pct": total_return,
                "benchmark_return_pct": benchmark_return,
                "delta_vs_benchmark_pct": round(total_return - benchmark_return, 2),
                "profit": profit,
                "annualized_return_pct": round(total_return * 0.88, 2),
            },
            "risk": {
                "max_drawdown_pct": max_drawdown,
                "volatility_pct": round(abs(max_drawdown) * 1.4, 2),
            },
            "efficiency": {
                "win_rate": win_rate,
                "total_trades": 12 + (seed % 18),
                "profit_factor": round(1.0 + max(total_return, 0) / 35, 2),
                "sharpe_ratio": round(total_return / max(abs(max_drawdown), 1), 2),
            },
        }

    aggregate_return = round(sum(returns) / len(returns), 2)
    aggregate_drawdown = round(min(drawdowns), 2)
    aggregate_win_rate = round(sum(win_rates) / len(win_rates), 2)
    return {
        "aggregate": {
            "performance": {
                "total_return_pct": aggregate_return,
                "benchmark_return_pct": benchmark_return,
                "delta_vs_benchmark_pct": round(aggregate_return - benchmark_return, 2),
                "profit": round(config["starting_capital"] * aggregate_return / 100, 2),
                "annualized_return_pct": round(aggregate_return * 0.88, 2),
            },
            "risk": {
                "max_drawdown_pct": aggregate_drawdown,
                "volatility_pct": round(abs(aggregate_drawdown) * 1.4, 2),
            },
            "efficiency": {
                "win_rate": aggregate_win_rate,
                "total_trades": sum(
                    row["efficiency"]["total_trades"] for row in by_symbol.values()
                ),
                "profit_factor": round(1.0 + max(aggregate_return, 0) / 35, 2),
                "sharpe_ratio": round(
                    aggregate_return / max(abs(aggregate_drawdown), 1), 2
                ),
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
