from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import problem
from argus.api.schemas import BacktestRun, User
from argus.domain import engine as domain_engine
from argus.domain.backtesting.coverage import (
    PreparedMarketData,
    apply_coverage_to_config,
    prepare_market_data,
)
from argus.domain.engine import (
    build_result_card,
    build_result_chart,
    classify_symbol,
    compute_alpha_metrics,
    normalize_backtest_config,
    validate_backtest_config,
)
from argus.domain.market_data.capabilities import fetch_alpaca_market_calendar
from argus.domain.store import utcnow

_DEFAULT_FETCH_OHLC = domain_engine.fetch_ohlcv


def _market_calendar_for_preflight():
    if domain_engine.fetch_ohlcv is not _DEFAULT_FETCH_OHLC:
        return None
    return fetch_alpaca_market_calendar


@dataclass(frozen=True)
class PreparedBacktestExecution:
    config: dict[str, Any]
    market_data: PreparedMarketData


def raise_backtest_problem(
    request: Request, code: str, *, context: dict[str, Any] | None = None
) -> None:
    mapping: dict[str, tuple[int, str, str]] = {
        "invalid_symbol": (
            422,
            "Invalid Symbol",
            "One or more symbols are not supported in the active Alpaca asset universe.",
        ),
        "invalid_symbol_count": (
            422,
            "Invalid Symbol Count",
            "Alpha supports between 1 and 5 symbols per run.",
        ),
        "mixed_asset_not_supported": (
            422,
            "Mixed Asset Simulation Not Supported",
            "Alpha supports grouped symbols within the same asset class only.",
        ),
        "asset_class_conflict": (
            422,
            "Asset Class Conflict",
            "Requested asset_class does not match inferred symbol asset class.",
        ),
        "unsupported_template": (
            422,
            "Unsupported Strategy Template",
            "Template is not supported in Alpha.",
        ),
        "unsupported_timeframe": (
            422,
            "Unsupported Timeframe",
            "Supported timeframes are 1h, 2h, 4h, 6h, 12h, and 1D.",
        ),
        "provider_timeframe_unavailable": (
            422,
            "Timeframe Unavailable",
            "That asset is not available at the selected bar size in the current "
            "launch path. Use 1h, 4h, or 1D bars for this kind of test.",
        ),
        "unsupported_side": (
            422,
            "Unsupported Position Side",
            "Alpha supports long-only backtests.",
        ),
        "unsupported_allocation_method": (
            422,
            "Unsupported Allocation Method",
            "Alpha supports equal_weight allocation only.",
        ),
        "unsupported_parameters": (
            422,
            "Unsupported Parameters",
            "Indicator and risk parameter customization is not enabled for Alpha MVP templates.",
        ),
        "invalid_starting_capital": (
            422,
            "Invalid Starting Capital",
            "starting_capital must be between 1,000 and 100,000,000.",
        ),
        "invalid_date_range": (
            422,
            "Invalid Date Range",
            "start_date must be before end_date and end_date cannot be in the future.",
        ),
        "invalid_chronological_date_range": (
            422,
            "Invalid Date Range",
            "start_date must be before end_date.",
        ),
        "future_end_date": (
            422,
            "Future End Date",
            "end_date cannot be later than today.",
        ),
        "provider_history_start_unavailable": (
            422,
            "History Unavailable",
            "Equity launch history starts in 2016 for this path. Choose a start "
            "date in 2016 or later.",
        ),
        "stablecoin_not_supported": (
            422,
            "Stablecoin Not Supported",
            "Stablecoins are excluded from Alpha backtesting.",
        ),
        "invalid_benchmark_symbol": (
            422,
            "Invalid Benchmark Symbol",
            "benchmark_symbol must match the run asset class.",
        ),
        "asset_universe_unavailable": (
            503,
            "Asset Universe Unavailable",
            "Asset validation is temporarily unavailable. Please retry shortly.",
        ),
        "market_data_unavailable": (
            503,
            "Market Data Unavailable",
            "Market data is temporarily unavailable. Please retry shortly.",
        ),
        "benchmark_data_unavailable": (
            503,
            "Benchmark Data Unavailable",
            "Benchmark data does not cover enough of the selected window for a "
            "trustworthy comparison. Try a shorter date range or another "
            "same-class benchmark.",
        ),
        "no_common_data_window": (
            422,
            "No Common Data Window",
            "The selected assets and benchmark do not share a usable data window.",
        ),
        "insufficient_common_data": (
            422,
            "Insufficient Common Data",
            "The shared data window is not complete enough for a trustworthy test.",
        ),
        "approved_data_window_unavailable": (
            409,
            "Approved Data Window Changed",
            "The approved data window is no longer available. Review the dates again.",
        ),
        "kraken_ohlc_window_exceeded": (
            422,
            "Data Window Too Wide",
            "That date range is too wide for the selected bar size in the current "
            "launch path. Choose a shorter date range or a wider timeframe.",
        ),
    }
    status_code, title, detail = mapping.get(
        code,
        (
            422,
            "Invalid Backtest Request",
            f"Backtest request failed Alpha validation: {code}.",
        ),
    )
    raise problem(
        request,
        status_code=status_code,
        code=code,
        title=title,
        detail=detail,
        context=context,
    )


def ensure_same_asset_or_raise(
    symbols: list[str], request: Request
) -> tuple[str, list[Any]]:
    classified = []
    for symbol in symbols:
        try:
            classified.append(classify_symbol(symbol))
        except ValueError as exc:
            code = str(exc)
            raise_backtest_problem(
                request,
                code,
                context={"symbol": symbol.strip().upper()},
            )
    classes = {entry.asset_class for entry in classified}
    if len(classes) > 1:
        raise_backtest_problem(
            request,
            "mixed_asset_not_supported",
            context={
                "conflicting_symbols": [
                    {"symbol": entry.symbol, "asset_class": entry.asset_class}
                    for entry in classified
                ]
            },
        )
    return classified[0].asset_class, classified


def create_run_from_payload(
    payload: dict[str, Any],
    request: Request,
    *,
    user: User | None = None,
    user_id: str | None = None,
    strategy_id: str | None = None,
    conversation_id: str | None = None,
    persist_in_memory: bool = True,
    language: str | None = None,
    run_id: str | None = None,
    prepared_execution: PreparedBacktestExecution | None = None,
) -> BacktestRun:
    if prepared_execution is None:
        prepared_execution = prepare_run_from_payload(payload, request)
    config = prepared_execution.config
    prepared_market_data = prepared_execution.market_data
    try:
        metrics = compute_alpha_metrics(
            config,
            prepared_market_data=prepared_market_data,
        )
    except ValueError as exc:
        raise_backtest_problem(request, str(exc))
    try:
        chart = build_result_chart(
            config,
            prepared_market_data=prepared_market_data,
        )
    except Exception as exc:
        logger.warning("Result chart build failed", error=str(exc))
        chart = None
    now = utcnow()
    run = BacktestRun(
        id=run_id or api_state.store.new_id(),
        conversation_id=conversation_id or payload.get("conversation_id"),
        strategy_id=strategy_id or payload.get("strategy_id"),
        status="completed",
        asset_class=config["asset_class"],
        symbols=config["symbols"],
        allocation_method="equal_weight",
        benchmark_symbol=config["benchmark_symbol"],
        metrics=metrics,
        config_snapshot=config,
        conversation_result_card=build_result_card(
            config,
            metrics,
            language=language or (user.language if user else "en"),
            chart=chart,
        ),
        created_at=now,
        chart=chart,
        trades=list(chart.get("markers", [])) if isinstance(chart, dict) else [],
    )
    if persist_in_memory:
        api_state.store.backtest_runs[run.id] = run
        if user_id:
            api_state.store.backtest_run_owners[run.id] = user_id
    return run


def prepare_run_from_payload(
    payload: dict[str, Any],
    request: Request,
) -> PreparedBacktestExecution:
    symbols = payload.get("symbols") or []
    if not symbols:
        raise problem(
            request,
            status_code=400,
            code="validation_error",
            title="Validation Error",
            detail="Symbol is required.",
        )
    inferred_asset_class, classified_symbols = ensure_same_asset_or_raise(
        symbols, request
    )
    requested_asset_class = payload.get("asset_class")
    if requested_asset_class and requested_asset_class != inferred_asset_class:
        raise_backtest_problem(
            request,
            "asset_class_conflict",
            context={
                "requested_asset_class": requested_asset_class,
                "inferred_asset_class": inferred_asset_class,
                "symbols": [entry.symbol for entry in classified_symbols],
            },
        )
    try:
        config = normalize_backtest_config(payload)
        validate_backtest_config(config)
        prepared_market_data = prepare_market_data(
            config,
            fetch_ohlcv_func=domain_engine.fetch_ohlcv,
            fetch_market_calendar_func=_market_calendar_for_preflight(),
        )
        config = apply_coverage_to_config(config, prepared_market_data)
        validate_backtest_config(config)
    except ValueError as exc:
        raise_backtest_problem(request, str(exc))
    return PreparedBacktestExecution(
        config=config,
        market_data=prepared_market_data,
    )


_raise_backtest_problem = raise_backtest_problem
