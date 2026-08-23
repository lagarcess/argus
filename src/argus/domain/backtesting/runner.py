from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import vectorbt as vbt
from loguru import logger

from argus.domain.backtesting.config import _vbt_freq
from argus.domain.backtesting.coverage import (
    MetricTimeBasis,
    PreparedMarketData,
    build_metric_time_basis,
)
from argus.domain.backtesting.execution import (
    ClosedTrade,
    LongOnlyExecutionResult,
    _build_long_only_execution_ledger,
    _dca_equity_curve,
    _execute_long_only_ledger,
    _execution_fill_count,
    _execution_realism_settings,
    symbol_allocation_capital,
)
from argus.domain.backtesting.metrics import (
    _compute_dca_metrics,
    _compute_metrics_from_equity,
    portfolio_value_summary,
)
from argus.domain.backtesting.signals import _build_signals
from argus.domain.dca_capital import dca_capital_plan_from_config
from argus.domain.market_data import fetch_ohlcv, fetch_price_series

_MIN_BENCHMARK_OBSERVATION_COVERAGE = 0.8


def build_benchmark_curve(
    config: dict[str, Any],
    target_index: pd.DatetimeIndex,
    *,
    fetch_price_series_func=fetch_price_series,
) -> dict[str, Any]:
    benchmark_symbol = config["benchmark_symbol"]
    benchmark_series = fetch_price_series_func(
        symbol=benchmark_symbol,
        asset_class=config["asset_class"],
        start_date=date.fromisoformat(config["start_date"]),
        end_date=date.fromisoformat(config["end_date"]),
        timeframe=config["timeframe"],
    )
    aligned, observed, coverage = _align_benchmark_series(
        benchmark_series,
        target_index,
    )
    if aligned.empty:
        raise ValueError("market_data_unavailable")
    normalized = aligned / float(aligned.iloc[0])
    return {
        "symbol": benchmark_symbol,
        "equity_curve": normalized.tolist(),
        "observed_mask": observed.tolist(),
        "total_return_pct": round((float(normalized.iloc[-1]) - 1.0) * 100.0, 2),
        "coverage": coverage,
    }


def _align_benchmark_series(
    benchmark_series: pd.Series,
    target_index: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    target = pd.DatetimeIndex(target_index)
    if target.empty:
        raise ValueError("market_data_unavailable")
    target = target.unique().sort_values()

    benchmark = pd.Series(benchmark_series).dropna().astype(float)
    if benchmark.empty:
        raise ValueError("market_data_unavailable")
    benchmark.index = _coerce_index_timezone(benchmark.index, target)
    benchmark = benchmark[~benchmark.index.duplicated(keep="last")].sort_index()

    observed = benchmark.reindex(target).notna()
    # The first target bar anchors the curve and is the buy-and-hold
    # benchmark's fill; the last is every template's ending value. Neither
    # may be a forward-filled price, so both must be real observations.
    if not bool(observed.iloc[0]) or not bool(observed.iloc[-1]):
        raise ValueError("benchmark_data_unavailable")
    observed_points = int(observed.sum())
    target_points = int(len(target))
    observed_ratio = observed_points / target_points
    min_ratio = 1.0 if target_points <= 2 else _MIN_BENCHMARK_OBSERVATION_COVERAGE
    if observed_ratio < min_ratio:
        raise ValueError("benchmark_data_unavailable")

    aligned = (
        benchmark.reindex(benchmark.index.union(target))
        .sort_index()
        .ffill()
        .reindex(target)
    )
    if aligned.isna().any():
        raise ValueError("benchmark_data_unavailable")
    return (
        aligned,
        observed,
        {
            "observed_points": observed_points,
            "target_points": target_points,
            "observed_ratio": round(observed_ratio, 4),
        },
    )


def _benchmark_series_from_curve(
    benchmark_curve: dict[str, Any],
    *,
    target_index: pd.Index,
) -> tuple[pd.Series, pd.Series]:
    """The normalized benchmark path and the alignment boundary's record of
    which of its bars are real observations, both positional over the target.

    A curve without the mask cannot say which prices are executable, so it
    is refused rather than treated as fully observed.
    """
    try:
        equity_values = list(benchmark_curve["equity_curve"])
        observed_values = list(benchmark_curve["observed_mask"])
    except (KeyError, TypeError) as exc:
        raise ValueError("benchmark_curve_incomplete") from exc
    if len(equity_values) != len(target_index) or len(observed_values) != len(
        target_index
    ):
        raise ValueError("benchmark_data_unavailable")
    return (
        pd.Series(equity_values, index=target_index, dtype=float),
        pd.Series(observed_values, index=target_index, dtype=bool),
    )


def _coerce_index_timezone(
    index: pd.Index,
    target: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    coerced = pd.DatetimeIndex(index)
    if target.tz is None:
        if coerced.tz is not None:
            return coerced.tz_convert("UTC").tz_localize(None)
        return coerced
    if coerced.tz is None:
        return coerced.tz_localize(target.tz)
    return coerced.tz_convert(target.tz)


def compute_alpha_metrics(
    config: dict[str, Any],
    *,
    fetch_ohlcv_func=fetch_ohlcv,
    build_signals_func=_build_signals,
    build_benchmark_curve_func=build_benchmark_curve,
    prepared_market_data: PreparedMarketData | None = None,
) -> dict[str, Any]:
    by_symbol: dict[str, Any] = {}
    symbol_equity_curves: list[pd.Series] = []
    benchmark_equity_curves: list[pd.Series] = []
    gross_symbol_equity_curves: list[pd.Series] = []
    symbol_external_flows: list[pd.Series] = []
    symbol_coverages: list[dict[str, Any]] = []
    closed_trades: list[ClosedTrade] = []
    gross_closed_trades: list[ClosedTrade] = []
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    realism = _execution_realism_settings(config)
    has_modeled_costs = _execution_realism_has_costs(realism)
    is_dca = config["template"] == "dca_accumulation"
    # A DCA config declares its two money roles; every other template funds
    # one bankroll. Neither shape can read the other's field.
    dca_plan = dca_capital_plan_from_config(config) if is_dca else None
    symbol_dca_plan = (
        dca_plan.per_symbol(len(config["symbols"])) if dca_plan is not None else None
    )
    allocation_capital = symbol_allocation_capital(
        config,
        symbol_count=len(config["symbols"]),
    )

    for symbol in config["symbols"]:
        if prepared_market_data is None:
            bars = fetch_ohlcv_func(
                symbol=symbol,
                asset_class=config["asset_class"],
                start_date=start,
                end_date=end,
                timeframe=config["timeframe"],
            )
        else:
            bars = prepared_market_data.bars_for(symbol)
        close = bars["close"].astype(float)
        entries, exits = build_signals_func(config, bars)
        execution_events = _build_long_only_execution_ledger(
            symbol=symbol,
            entries=entries,
            exits=exits,
            allow_accumulation=is_dca,
        )
        symbol_execution: LongOnlyExecutionResult | None = None
        if not is_dca:
            symbol_execution = _execute_long_only_ledger(
                execution_events=execution_events,
                close=close,
                initial_capital=allocation_capital,
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
            )
        symbol_closed_trades = (
            symbol_execution.closed_trades if symbol_execution is not None else ()
        )
        closed_trades.extend(symbol_closed_trades)
        gross_symbol_execution: LongOnlyExecutionResult | None = None
        if has_modeled_costs and not is_dca:
            gross_symbol_execution = _execute_long_only_ledger(
                execution_events=execution_events,
                close=close,
                initial_capital=allocation_capital,
                fees=0.0,
                slippage=0.0,
            )
            gross_closed_trades.extend(gross_symbol_execution.closed_trades)
        symbol_time_basis = _metric_time_basis_for(
            config=config,
            effective_index=close.index,
            prepared_market_data=prepared_market_data,
        )

        if prepared_market_data is None:
            benchmark_curve = build_benchmark_curve_func(config, close.index)
        else:
            benchmark_curve = build_benchmark_curve(
                config,
                close.index,
                fetch_price_series_func=lambda *, symbol, **_: (
                    prepared_market_data.price_series_for(symbol)
                ),
            )
        benchmark_normalized, benchmark_observed = _benchmark_series_from_curve(
            benchmark_curve,
            target_index=close.index,
        )
        deferred_fill_count = 0
        if is_dca:
            assert symbol_dca_plan is not None
            dca_result = _dca_equity_curve(
                close=close,
                entries=entries,
                contribution=symbol_dca_plan.contribution,
                starting_capital=symbol_dca_plan.starting_capital,
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
            )
            symbol_equity = dca_result.equity_curve
            benchmark_result = _dca_equity_curve(
                close=benchmark_normalized,
                entries=entries,
                contribution=symbol_dca_plan.contribution,
                starting_capital=symbol_dca_plan.starting_capital,
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
                observed=benchmark_observed,
            )
            deferred_fill_count = benchmark_result.deferred_fill_count
            if deferred_fill_count:
                logger.info(
                    "DCA benchmark deferred {count} contribution fill(s) to the "
                    "next observed price symbol={symbol} benchmark={benchmark}",
                    count=benchmark_result.deferred_fill_count,
                    symbol=symbol,
                    benchmark=config["benchmark_symbol"],
                )
            benchmark_equity = benchmark_result.equity_curve
            if has_modeled_costs:
                gross_result = _dca_equity_curve(
                    close=close,
                    entries=entries,
                    contribution=symbol_dca_plan.contribution,
                    starting_capital=symbol_dca_plan.starting_capital,
                )
                gross_symbol_equity_curves.append(gross_result.equity_curve)
            symbol_external_flows.append(dca_result.external_flows)
            invested_capital = max(
                dca_result.invested_capital,
                benchmark_result.invested_capital,
            )
            by_symbol[symbol] = _compute_dca_metrics(
                strategy_equity=symbol_equity,
                benchmark_equity=benchmark_equity,
                external_flows=dca_result.external_flows,
                invested_capital=invested_capital,
                time_basis=symbol_time_basis,
                trade_count=_execution_fill_count(execution_events, side="buy"),
            )
        else:
            if symbol_execution is None:
                raise ValueError("execution_result_unavailable")
            symbol_equity = symbol_execution.equity_curve
            if has_modeled_costs:
                if gross_symbol_execution is None:
                    raise ValueError("execution_result_unavailable")
                gross_symbol_equity_curves.append(gross_symbol_execution.equity_curve)
            benchmark_equity = _benchmark_buy_and_hold_equity(
                close=benchmark_normalized,
                allocation_capital=allocation_capital,
                fees=float(realism["fees"]),
                slippage=float(realism["slippage"]),
                timeframe=config["timeframe"],
            )
            # One equity-based metric path with or without modeled costs: the
            # baseline-anchored series owns the entry-cost hit at t0 (#468).
            by_symbol[symbol] = _compute_metrics_from_equity(
                strategy_equity=symbol_equity,
                benchmark_equity=benchmark_equity,
                invested_capital=allocation_capital,
                time_basis=symbol_time_basis,
                trade_count=_execution_fill_count(execution_events),
                closed_trade_pnls=[trade.net_pnl for trade in symbol_closed_trades],
            )

        symbol_coverage = _benchmark_coverage_block(
            benchmark_curve,
            deferred_fill_count=deferred_fill_count,
        )
        by_symbol[symbol]["performance"]["benchmark_coverage"] = symbol_coverage
        symbol_coverages.append(symbol_coverage)
        symbol_equity_curves.append(symbol_equity)
        benchmark_equity_curves.append(benchmark_equity)

    aggregate_strategy_equity = _sum_without_edge_backfill(symbol_equity_curves)
    aggregate_benchmark_equity = _sum_without_edge_backfill(benchmark_equity_curves)
    trade_count = sum(row["efficiency"]["total_trades"] for row in by_symbol.values())
    aggregate_time_basis = _metric_time_basis_for(
        config=config,
        effective_index=aggregate_strategy_equity.index,
        prepared_market_data=prepared_market_data,
    )
    aggregate_closed_trade_pnls = [trade.net_pnl for trade in closed_trades]
    aggregate_external_flows: pd.Series | None = None
    if is_dca:
        assert dca_plan is not None
        # Contributions are already per symbol, so they scale with the summed
        # fill count; the seed is one whole-plan amount and is added once.
        aggregate_invested = dca_plan.starting_capital + allocation_capital * max(
            trade_count, 1
        )
        aggregate_external_flows = _aggregate_external_flows(
            symbol_external_flows,
            aggregate_strategy_equity.index,
        )
        aggregate_metrics = _compute_dca_metrics(
            strategy_equity=aggregate_strategy_equity,
            benchmark_equity=aggregate_benchmark_equity,
            external_flows=aggregate_external_flows,
            invested_capital=aggregate_invested,
            time_basis=aggregate_time_basis,
            trade_count=trade_count,
        )
    else:
        aggregate_invested = float(config["starting_capital"])
        aggregate_metrics = _compute_metrics_from_equity(
            strategy_equity=aggregate_strategy_equity,
            benchmark_equity=aggregate_benchmark_equity,
            invested_capital=aggregate_invested,
            time_basis=aggregate_time_basis,
            trade_count=trade_count,
            closed_trade_pnls=aggregate_closed_trade_pnls,
        )
    if has_modeled_costs and gross_symbol_equity_curves:
        gross_aggregate_equity = _sum_without_edge_backfill(gross_symbol_equity_curves)
        if is_dca:
            # Contribution amounts do not depend on modeled costs, so the
            # gross side reuses the same deposit schedule.
            gross_metrics = _compute_dca_metrics(
                strategy_equity=gross_aggregate_equity,
                benchmark_equity=aggregate_benchmark_equity,
                external_flows=_aggregate_external_flows(
                    symbol_external_flows,
                    gross_aggregate_equity.index,
                ),
                invested_capital=aggregate_invested,
                time_basis=aggregate_time_basis,
                trade_count=trade_count,
            )
        else:
            gross_metrics = _compute_metrics_from_equity(
                strategy_equity=gross_aggregate_equity,
                benchmark_equity=aggregate_benchmark_equity,
                invested_capital=aggregate_invested,
                time_basis=aggregate_time_basis,
                trade_count=trade_count,
                closed_trade_pnls=[trade.net_pnl for trade in gross_closed_trades],
            )
        aggregate_metrics.setdefault("performance", {})["execution_realism"] = (
            _execution_realism_performance_summary(
                realism=realism,
                gross_performance=gross_metrics["performance"],
                net_performance=aggregate_metrics["performance"],
            )
        )
    aggregate_metrics.setdefault("performance", {})["benchmark_coverage"] = (
        _aggregate_benchmark_coverage(symbol_coverages)
    )
    value_summary = portfolio_value_summary(aggregate_strategy_equity)
    if value_summary is not None:
        aggregate_metrics.setdefault("performance", {})["portfolio_value_range"] = (
            value_summary
        )

    return {
        "aggregate": aggregate_metrics,
        "by_symbol": by_symbol,
    }


def _metric_time_basis_for(
    *,
    config: dict[str, Any],
    effective_index: pd.Index,
    prepared_market_data: PreparedMarketData | None,
) -> MetricTimeBasis:
    if prepared_market_data is not None:
        return prepared_market_data.metric_time_basis_for(
            asset_class=str(config["asset_class"]),
            timeframe=str(config["timeframe"]),
            effective_index=effective_index,
        )
    return build_metric_time_basis(
        asset_class=str(config["asset_class"]),
        timeframe=str(config["timeframe"]),
        effective_index=effective_index,
    )


def _sum_without_edge_backfill(curves: list[pd.Series]) -> pd.Series:
    aligned = pd.concat(curves, axis=1).sort_index().ffill().dropna(how="any")
    if aligned.empty:
        raise ValueError("market_data_unavailable")
    return aligned.sum(axis=1)


def _aggregate_external_flows(
    flow_curves: list[pd.Series],
    target_index: pd.Index,
) -> pd.Series:
    """Sum per-symbol deposit schedules onto the aggregate equity index.

    A deposit on a bar the aggregate index dropped still bought shares, so
    it rolls forward to the next bar the aggregate keeps.
    """
    combined = pd.concat(flow_curves, axis=1).sort_index().fillna(0.0).sum(axis=1)
    cumulative = combined.cumsum()
    aligned_cumulative = (
        cumulative.reindex(cumulative.index.union(target_index))
        .ffill()
        .reindex(target_index)
        .fillna(0.0)
    )
    flows = aligned_cumulative.diff()
    if len(flows) > 0:
        flows.iloc[0] = float(aligned_cumulative.iloc[0])
    return flows.astype(float)


def _benchmark_coverage_block(
    benchmark_curve: dict[str, Any],
    *,
    deferred_fill_count: int,
) -> dict[str, Any]:
    """What the stored run says about the benchmark data it compared against.

    The alignment boundary's coverage counts and the number of deposits whose
    fill waited for an observed price travel with the metrics, so a
    comparison that rests on forward-filled bars records that it did.
    """
    try:
        coverage = benchmark_curve["coverage"]
        observed_points = int(coverage["observed_points"])
        target_points = int(coverage["target_points"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("benchmark_curve_incomplete") from exc
    return _coverage_block(
        observed_points=observed_points,
        target_points=target_points,
        deferred_fill_count=deferred_fill_count,
    )


def _aggregate_benchmark_coverage(
    symbol_coverages: list[dict[str, Any]],
) -> dict[str, Any]:
    return _coverage_block(
        observed_points=sum(int(block["observed_points"]) for block in symbol_coverages),
        target_points=sum(int(block["target_points"]) for block in symbol_coverages),
        deferred_fill_count=sum(
            int(block["deferred_fill_count"]) for block in symbol_coverages
        ),
    )


def _coverage_block(
    *,
    observed_points: int,
    target_points: int,
    deferred_fill_count: int,
) -> dict[str, Any]:
    return {
        "observed_points": int(observed_points),
        "target_points": int(target_points),
        "observed_ratio": (
            round(observed_points / target_points, 4) if target_points else 0.0
        ),
        "deferred_fill_count": int(deferred_fill_count),
    }


def _execution_realism_has_costs(realism: dict[str, float | bool]) -> bool:
    return bool(realism["enabled"]) and (
        float(realism["fees"]) > 0.0 or float(realism["slippage"]) > 0.0
    )


def _benchmark_buy_and_hold_equity(
    *,
    close: pd.Series,
    allocation_capital: float,
    fees: float,
    slippage: float,
    timeframe: str,
) -> pd.Series:
    if fees <= 0.0 and slippage <= 0.0:
        return close * allocation_capital
    entries = pd.Series(False, index=close.index, dtype=bool)
    if not entries.empty:
        entries.iloc[0] = True
    exits = pd.Series(False, index=close.index, dtype=bool)
    portfolio = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        fees=fees,
        slippage=slippage,
        init_cash=allocation_capital,
        freq=_vbt_freq(timeframe),
        accumulate=False,
    )
    return pd.Series(portfolio.value().values, index=close.index, dtype=float)


def _execution_realism_performance_summary(
    *,
    realism: dict[str, float | bool],
    gross_performance: dict[str, Any],
    net_performance: dict[str, Any],
) -> dict[str, Any]:
    gross_return = float(gross_performance["total_return_pct"])
    net_return = float(net_performance["total_return_pct"])
    return {
        "enabled": True,
        "fee_bps": round(float(realism["fees"]) * 10000.0, 4),
        "slippage_bps": round(float(realism["slippage"]) * 10000.0, 4),
        "gross_total_return_pct": gross_return,
        "net_total_return_pct": net_return,
        "return_drag_pct": round(gross_return - net_return, 2),
    }
