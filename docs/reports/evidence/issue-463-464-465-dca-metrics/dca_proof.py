"""Before/after proof for the DCA metrics arithmetic lane (#463/#464/#465).

Runs two deterministic offline DCA scenarios through compute_alpha_metrics:
1. The audit's independent example (equity [100, 80, 180, 144],
   contributions [100, 0, 100, 0], zero costs).
2. A six-month synthetic monthly DCA with modeled costs (10 bps fee,
   5 bps slippage) shaped like the audit's live AAPL run: a losing asset
   with periodic deposits.

No provider, no network, no paid calls.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

os.environ["ARGUS_ENABLE_EXECUTION_REALISM"] = "true"
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "synthetic_unit_fixture"

from argus.domain.backtesting.runner import compute_alpha_metrics  # noqa: E402


def bars(prices: list[float], index: pd.DatetimeIndex) -> pd.DataFrame:
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


def run_dca(
    *,
    prices: list[float],
    benchmark_prices: list[float],
    entries: list[bool],
    contribution: float,
    fee_bps: float,
    slippage_bps: float,
    index: pd.DatetimeIndex,
) -> dict:
    config = {
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
            "starting_capital": 0.0,
            "contribution": contribution,
        },
        "_execution_realism": {
            "enabled": True,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
        },
    }
    strategy_bars = bars(prices, index)
    benchmark = pd.Series(benchmark_prices, index=index, dtype=float)
    return compute_alpha_metrics(
        config,
        fetch_ohlcv_func=lambda **_: strategy_bars,
        build_signals_func=lambda *_: (
            pd.Series(entries, index=index, dtype=bool),
            pd.Series(False, index=index, dtype=bool),
        ),
        build_benchmark_curve_func=lambda *_a, **_k: {
            "equity_curve": (benchmark / benchmark.iloc[0]).tolist(),
        },
    )


def summarize(metrics: dict) -> dict:
    aggregate = metrics["aggregate"]
    performance = aggregate["performance"]
    return {
        "total_return_pct": performance.get("total_return_pct"),
        "contribution_return_pct": performance.get("contribution_return_pct"),
        "return_basis": performance.get("return_basis"),
        "annualized_return_pct": performance.get("annualized_return_pct"),
        "profit": performance.get("profit"),
        "benchmark_return_pct": performance.get("benchmark_return_pct"),
        "delta_vs_benchmark_pct": performance.get("delta_vs_benchmark_pct"),
        "max_drawdown_pct": aggregate["risk"]["max_drawdown_pct"],
        "volatility_pct": aggregate["risk"]["volatility_pct"],
        "sharpe_ratio": aggregate["efficiency"]["sharpe_ratio"],
        "win_rate": aggregate["efficiency"]["win_rate"],
        "profit_factor": aggregate["efficiency"]["profit_factor"],
        "total_trades": aggregate["efficiency"]["total_trades"],
        "peak_value": performance.get("portfolio_value_range", {}).get("peak_value"),
        "lowest_value": performance.get("portfolio_value_range", {}).get(
            "lowest_value"
        ),
    }


def audit_example() -> dict:
    # Prices chosen so nominal equity is exactly [100, 80, 180, 144] with
    # contributions [100, 0, 100, 0] and zero costs (audit report's D1 example).
    index = pd.bdate_range("2025-01-02", periods=4, tz="UTC")
    return run_dca(
        prices=[100.0, 80.0, 80.0, 64.0],
        benchmark_prices=[100.0, 100.0, 100.0, 100.0],
        entries=[True, False, True, False],
        contribution=100.0,
        fee_bps=0.0,
        slippage_bps=0.0,
        index=index,
    )


def six_month_example() -> dict:
    index = pd.bdate_range("2025-01-02", "2025-06-30", tz="UTC")
    rng = np.random.RandomState(456)
    steps = rng.normal(loc=-0.0008, scale=0.012, size=len(index))
    prices = 240.0 * np.exp(np.cumsum(steps))
    bench_steps = rng.normal(loc=0.0004, scale=0.008, size=len(index))
    bench = 580.0 * np.exp(np.cumsum(bench_steps))
    months = index.to_period("M")
    entries = [
        bool(i == 0 or months[i] != months[i - 1]) for i in range(len(index))
    ]
    return run_dca(
        prices=[float(p) for p in prices],
        benchmark_prices=[float(p) for p in bench],
        entries=entries,
        contribution=10_000.0,
        fee_bps=10.0,
        slippage_bps=5.0,
        index=index,
    )


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "before"
    out = {
        "label": label,
        "audit_example": summarize(audit_example()),
        "six_month_monthly_dca": summarize(six_month_example()),
    }
    path = os.path.join(os.path.dirname(__file__), f"dca_metrics_{label}.json")
    with open(path, "w") as handle:
        json.dump(out, handle, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
