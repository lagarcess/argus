from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)

USER_SAFE_FAILURE_MESSAGES = {
    "missing_rule_group": (
        "The visible strategy is missing a complete executable entry and exit rule. "
        "Choose the rule details before running it."
    ),
    "indicator_data_insufficient": (
        "That indicator needs more historical bars than this date window provides. "
        "Use a longer date range or a shorter indicator period before running it."
    ),
    "unsupported_indicator": (
        "That indicator is not executable in the current backtest engine yet. "
        "I can help convert the idea to a supported RSI or "
        "SMA/EMA rule."
    ),
    "unsupported_indicator_threshold": (
        "That threshold rule is not executable with the current indicator registry. "
        "Use a supported indicator threshold or simplify the rule."
    ),
    "unsupported_rule_operator": (
        "That rule operator is not executable yet. Choose one of the supported "
        "comparison or crossover rules and I can keep the rest of the setup intact."
    ),
    "invalid_indicator_parameter": (
        "One indicator parameter is outside the supported schema. Adjust the "
        "period or threshold values and I can run the same idea."
    ),
    "indicator_period_out_of_bounds": (
        "That indicator period is outside the supported range. Choose a valid "
        "period and I can run the same idea."
    ),
    "indicator_threshold_out_of_bounds": (
        "That indicator threshold is outside the supported range. Choose a value "
        "inside the indicator scale and I can run the same idea."
    ),
    "market_data_unavailable": (
        "I could not find enough price history for the selected asset over that "
        "date range. Keep the strategy intact and choose a shorter or more recent "
        "window, or try another supported asset."
    ),
    "benchmark_data_unavailable": (
        "I could not find enough benchmark history over that date range. Keep the "
        "strategy intact and choose a shorter or more recent window, or use a "
        "supported benchmark."
    ),
    "invalid_date_range": (
        "That date range is not valid for a backtest. Choose a start and end date "
        "in chronological order and I will keep the strategy intact."
    ),
    "invalid_chronological_date_range": (
        "The end date needs to come after the start date. Choose a valid date "
        "window and I will keep the strategy intact."
    ),
    "future_end_date": (
        "That end date is later than the latest date Argus can backtest. Choose "
        "an end date up to today and I will keep the strategy intact."
    ),
    "approved_data_window_unavailable": (
        "That confirmation needs its data window checked again before it can run. "
        "Review the refreshed dates and approve the new card."
    ),
}


USER_SAFE_FAILURE_DETAILS = {
    "missing_rule_group": "incomplete_rule",
    "indicator_data_insufficient": "insufficient_indicator_data",
    "unsupported_indicator": "unsupported_signal_family",
    "unsupported_indicator_threshold": "unsupported_rule",
    "unsupported_rule_operator": "unsupported_rule",
    "invalid_indicator_parameter": "invalid_parameter",
    "indicator_period_out_of_bounds": "invalid_parameter",
    "indicator_threshold_out_of_bounds": "invalid_parameter",
    "market_data_unavailable": "market_data_issue",
    "benchmark_data_unavailable": "benchmark_data_issue",
    "invalid_date_range": "invalid_date_window",
    "invalid_chronological_date_range": "invalid_date_window",
    "future_end_date": "future_date_window",
    "approved_data_window_unavailable": "approved_data_window_unavailable",
    "capital_amount_required": "invalid_parameter",
    "position_size_required": "invalid_parameter",
    "capital_amount_not_applicable": "invalid_parameter",
    "position_size_not_applicable": "invalid_parameter",
}


def user_safe_failure_detail(
    *,
    failure_reason: str | None,
    failure_category: str | None = None,
) -> str:
    code = str(failure_reason or "").strip()
    if code in USER_SAFE_FAILURE_DETAILS:
        return USER_SAFE_FAILURE_DETAILS[code]
    if failure_category == "missing_required_input":
        return "missing_required_input"
    if failure_category == "unsupported_capability":
        return "unsupported_capability"
    if failure_category == "parameter_validation_error":
        return "invalid_parameter"
    if failure_category == "upstream_dependency_error":
        return "temporary_dependency_issue"
    return "execution_failed"


def is_user_safe_failure_code(value: str | None) -> bool:
    code = str(value or "").strip()
    return code in USER_SAFE_FAILURE_MESSAGES or code in USER_SAFE_FAILURE_DETAILS


def is_user_safe_failure_detail(value: str | None) -> bool:
    detail = str(value or "").strip()
    return detail in {
        *USER_SAFE_FAILURE_DETAILS.values(),
        "missing_required_input",
        "unsupported_capability",
        "invalid_parameter",
        "temporary_dependency_issue",
        "execution_failed",
    }


def build_success_envelope(
    *,
    resolved_strategy: dict[str, Any],
    resolved_parameters: dict[str, Any],
    metrics: dict[str, Any],
    benchmark_metrics: dict[str, Any],
    assumptions: list[str],
    caveats: list[str],
    provider_metadata: dict[str, Any],
    artifact_references: list[dict[str, Any]] | None = None,
) -> LaunchExecutionEnvelope:
    return LaunchExecutionEnvelope(
        execution_status="succeeded",
        resolved_strategy=resolved_strategy,
        resolved_parameters=resolved_parameters,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=assumptions,
        caveats=caveats,
        artifact_references=artifact_references or [],
        provider_metadata=provider_metadata,
    )


def user_safe_failure_message(
    *,
    failure_reason: str | None,
    failure_category: str | None = None,
) -> str:
    code = str(failure_reason or "").strip()
    if code in USER_SAFE_FAILURE_MESSAGES:
        return USER_SAFE_FAILURE_MESSAGES[code]
    if failure_category == "missing_required_input":
        return (
            "I need one more executable detail before I can run this. Tell me the "
            "missing rule, asset, or date range and I will keep the current setup intact."
        )
    if failure_category == "unsupported_capability":
        return (
            "That request is outside the current executable backtest capability. "
            "I can preserve the idea and offer supported alternatives."
        )
    if failure_category == "parameter_validation_error":
        return (
            "One detail in the launch payload is not valid for the current engine. "
            "Adjust the strategy, dates, or sizing and I can run the same setup."
        )
    if failure_category == "upstream_dependency_error":
        return (
            "The run hit a temporary data or service issue. Try again from the "
            "current setup or adjust it first."
        )
    return (
        "The backtest could not complete. Try again from the current setup or "
        "adjust it first."
    )


def build_failure_envelope(
    *,
    request: LaunchBacktestRequest,
    execution_status: str,
    failure_category: str,
    failure_reason: str,
    provider_metadata: dict[str, Any] | None = None,
) -> LaunchExecutionEnvelope:
    return LaunchExecutionEnvelope(
        execution_status=execution_status,
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": request.symbol,
            "asset_universe": request.symbols,
        },
        resolved_parameters={
            "timeframe": request.timeframe,
            "date_range": request.date_range.model_dump(mode="python"),
            "benchmark_symbol": request.benchmark_symbol,
            "sizing_mode": request.sizing_mode,
        },
        metrics={},
        benchmark_metrics={},
        assumptions=[],
        caveats=[],
        artifact_references=[],
        provider_metadata=provider_metadata or {},
        failure_category=failure_category,
        failure_reason=failure_reason,
    )


def build_benchmark_metrics(
    *,
    request: LaunchBacktestRequest,
    metrics: dict[str, Any],
    benchmark_symbol: str | None = None,
) -> dict[str, Any]:
    aggregate_performance = metrics.get("aggregate", {}).get("performance", {})
    by_symbol = metrics.get("by_symbol", {})
    resolved_benchmark = str(benchmark_symbol or request.benchmark_symbol).strip().upper()

    return {
        "symbol": resolved_benchmark,
        "aggregate": {
            "total_return_pct": aggregate_performance.get("benchmark_return_pct"),
        },
        "by_symbol": {
            symbol: {
                "total_return_pct": by_symbol.get(symbol, {})
                .get("performance", {})
                .get("benchmark_return_pct"),
            }
            for symbol in request.symbols
        },
    }


def build_explanation_context(
    *,
    request: LaunchBacktestRequest,
    envelope: LaunchExecutionEnvelope,
    result_card: dict[str, Any],
) -> dict[str, Any]:
    resolved_parameters = dict(envelope.resolved_parameters or {})
    benchmark_symbol = str(
        resolved_parameters.get("benchmark_symbol") or request.benchmark_symbol
    ).strip().upper()
    return {
        "strategy_type": request.strategy_type,
        "symbol": request.symbol,
        "symbols": request.symbols,
        "benchmark_symbol": benchmark_symbol,
        "timeframe": request.timeframe,
        "date_range": request.date_range.model_dump(mode="python"),
        "metrics": envelope.metrics,
        "benchmark_metrics": envelope.benchmark_metrics,
        "assumptions": envelope.assumptions,
        "caveats": envelope.caveats,
        "result_card": result_card,
    }
