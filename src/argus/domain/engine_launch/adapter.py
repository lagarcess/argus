from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from argus.domain.engine import (
    build_result_card,
    classify_symbol,
    compute_alpha_metrics,
    validate_backtest_config,
)
from argus.domain.engine_launch.cadence import resolve_dca_cadence
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)
from argus.domain.engine_launch.results import (
    build_benchmark_metrics,
    build_explanation_context,
    build_failure_envelope,
    build_success_envelope,
)
from argus.domain.engine_launch.sizing import resolve_starting_capital
from argus.domain.engine_launch.strategies import (
    normalize_template_name,
    validate_launch_supported,
)
from argus.domain.market_data import fetch_price_series


@dataclass(frozen=True)
class LaunchExecutionAdapterResult:
    envelope: LaunchExecutionEnvelope
    result_card: dict[str, Any] | None = None
    explanation_context: dict[str, Any] | None = None


def run_launch_backtest(
    request: LaunchBacktestRequest,
    *,
    language: str = "en",
) -> LaunchExecutionAdapterResult:
    try:
        validate_launch_supported(request)
    except ValueError as exc:
        return _blocked_result(
            request,
            failure_reason=str(exc),
        )

    try:
        if request.strategy_type == "dca_accumulation":
            result = _run_dca_accumulation(request, language=language)
        elif request.strategy_type == "indicator_threshold":
            result = _run_indicator_threshold(request, language=language)
        else:
            result = _run_buy_and_hold(request, language=language)
    except ValueError as exc:
        category, status = _normalize_value_error(str(exc))
        return LaunchExecutionAdapterResult(
            envelope=build_failure_envelope(
                request=request,
                execution_status=status,
                failure_category=category,
                failure_reason=str(exc),
            )
        )
    except Exception:
        return LaunchExecutionAdapterResult(
            envelope=build_failure_envelope(
                request=request,
                execution_status="failed_internal",
                failure_category="internal_system_error",
                failure_reason="launch_execution_failed",
            )
        )
    return result


def _run_indicator_threshold(
    request: LaunchBacktestRequest,
    *,
    language: str,
) -> LaunchExecutionAdapterResult:
    asset = classify_symbol(request.symbol)
    initial_price = _initial_price(request, asset_class=asset.asset_class)
    starting_capital = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    config = _build_indicator_threshold_config(
        request=request,
        asset_class=asset.asset_class,
        symbol=asset.symbol,
        starting_capital=starting_capital,
    )
    validate_backtest_config(config)

    metrics = compute_alpha_metrics(config)
    result_card = build_result_card(config, metrics, language=language)
    benchmark_metrics = build_benchmark_metrics(request=request, metrics=metrics)
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "entry_rule": request.entry_rule,
            "exit_rule": request.exit_rule,
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": starting_capital,
            "position_size": request.position_size,
            "cadence": request.cadence,
            "template": config["template"],
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[
            f"{config['timeframe']} bars only.",
            "Launch support is currently limited to RSI below 30 and RSI above 55.",
        ],
        provider_metadata={
            "provider": "alpaca",
            "asset_class": asset.asset_class,
            "timeframe": config["timeframe"],
        },
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _run_dca_accumulation(
    request: LaunchBacktestRequest,
    *,
    language: str,
) -> LaunchExecutionAdapterResult:
    asset = classify_symbol(request.symbol)
    initial_price = _initial_price(request, asset_class=asset.asset_class)
    recurring_allocation = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    cadence = resolve_dca_cadence(request.cadence)
    config = _build_periodic_config(
        request=request,
        asset_class=asset.asset_class,
        symbol=asset.symbol,
        starting_capital=recurring_allocation,
        cadence=cadence,
    )
    _validate_launch_config(config)

    metrics = compute_alpha_metrics(config)
    result_card = build_result_card(config, metrics, language=language)
    benchmark_metrics = build_benchmark_metrics(request=request, metrics=metrics)
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "entry_rule": {"type": "periodic_accumulation", "cadence": cadence},
            "exit_rule": {"type": "end_of_period"},
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": recurring_allocation,
            "position_size": request.position_size,
            "cadence": cadence,
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=[
            f"Recurring allocation: ${recurring_allocation:,.0f}.",
            f"Cadence: {cadence}.",
        ],
        caveats=[
            f"{config['timeframe']} bars only.",
            "Recurring entries use the first available bar in each cadence window.",
        ],
        provider_metadata={
            "provider": "alpaca",
            "asset_class": asset.asset_class,
            "timeframe": config["timeframe"],
        },
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _run_buy_and_hold(
    request: LaunchBacktestRequest,
    *,
    language: str,
) -> LaunchExecutionAdapterResult:
    asset = classify_symbol(request.symbol)
    initial_price = _initial_price(request, asset_class=asset.asset_class)
    starting_capital = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    config = _build_buy_and_hold_config(
        request=request,
        asset_class=asset.asset_class,
        symbol=asset.symbol,
        starting_capital=starting_capital,
    )
    validate_backtest_config(config)

    metrics = compute_alpha_metrics(config)
    result_card = build_result_card(config, metrics, language=language)
    benchmark_metrics = build_benchmark_metrics(request=request, metrics=metrics)
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "entry_rule": {"type": "start_of_period"},
            "exit_rule": {"type": "end_of_period"},
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": starting_capital,
            "position_size": request.position_size,
            "cadence": request.cadence,
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[f"{config['timeframe']} bars only."],
        provider_metadata={
            "provider": "alpaca",
            "asset_class": asset.asset_class,
            "timeframe": config["timeframe"],
        },
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _build_periodic_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbol: str,
    starting_capital: float,
    cadence: str,
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    return {
        "template": "dca_accumulation",
        "asset_class": asset_class,
        "symbols": [symbol],
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {"dca_cadence": cadence},
    }


def _validate_launch_config(config: dict[str, Any]) -> None:
    if config["template"] == "dca_accumulation":
        validation_config = dict(config)
        # Shared engine validation treats starting_capital as a one-time bankroll.
        # Launch DCA uses it as the recurring contribution amount instead.
        validation_config["starting_capital"] = max(
            1000.0,
            float(config["starting_capital"]),
        )
        validation_parameters = dict(config.get("parameters") or {})
        cadence = validation_parameters.get("dca_cadence")
        if cadence == "quarterly":
            validation_parameters["dca_cadence"] = "monthly"
        validation_config["parameters"] = validation_parameters
        validate_backtest_config(validation_config)
        return
    validate_backtest_config(config)


def _build_buy_and_hold_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbol: str,
    starting_capital: float,
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    return {
        "template": "buy_and_hold",
        "asset_class": asset_class,
        "symbols": [symbol],
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {},
    }


def _build_indicator_threshold_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbol: str,
    starting_capital: float,
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    return {
        "template": normalize_template_name(request),
        "asset_class": asset_class,
        "symbols": [symbol],
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {},
    }


def _initial_price(
    request: LaunchBacktestRequest,
    *,
    asset_class: str,
) -> float | None:
    if request.sizing_mode != "position_size":
        return None

    series = fetch_price_series(
        symbol=request.symbol,
        asset_class=asset_class,
        start_date=date.fromisoformat(request.date_range.start),
        end_date=date.fromisoformat(request.date_range.end),
        timeframe=request.timeframe,
    )
    if series.empty:
        raise ValueError("market_data_unavailable")
    return float(series.iloc[0])


def _blocked_result(
    request: LaunchBacktestRequest,
    *,
    failure_reason: str,
) -> LaunchExecutionAdapterResult:
    return LaunchExecutionAdapterResult(
        envelope=build_failure_envelope(
            request=request,
            execution_status="blocked_unsupported",
            failure_category="unsupported_capability",
            failure_reason=failure_reason,
        )
    )


def _normalize_value_error(error_code: str) -> tuple[str, str]:
    invalid_inputs = {
        "capital_amount_required",
        "position_size_required",
        "capital_amount_not_applicable",
        "position_size_not_applicable",
        "invalid_date_range",
        "invalid_starting_capital",
        "invalid_symbol_count",
        "position_price_required",
    }
    unsupported = {
        "cadence_required",
        "cadence_not_applicable",
        "unsupported_timeframe",
        "unsupported_template",
        "stablecoin_not_supported",
        "unsupported_parameters",
        "unsupported_allocation_method",
        "unsupported_side",
    }
    if error_code == "market_data_unavailable":
        return "upstream_dependency_error", "failed_upstream"
    if error_code in invalid_inputs:
        return "parameter_validation_error", "blocked_invalid_input"
    if error_code in unsupported:
        return "unsupported_capability", "blocked_unsupported"
    return "internal_system_error", "failed_internal"
