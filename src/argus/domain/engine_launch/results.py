from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)

USER_SAFE_FAILURE_MESSAGES = {
    "missing_rule_group": (
        "The visible strategy is missing a complete executable entry and exit rule. "
        "Keep the draft and choose the rule details before running it."
    ),
    "indicator_data_insufficient": (
        "That indicator needs more historical bars than this date window provides. "
        "Use a longer date range or a shorter indicator period before running it."
    ),
    "unsupported_indicator": (
        "That indicator is not executable in the current backtest engine yet. "
        "I can keep it as a draft or help convert the idea to a supported RSI or "
        "SMA/EMA rule."
    ),
    "unsupported_indicator_threshold": (
        "That threshold rule is not executable with the current indicator registry. "
        "Use a supported indicator threshold or keep the idea as a draft."
    ),
    "unsupported_rule_operator": (
        "That rule operator is not executable yet. Choose one of the supported "
        "comparison or crossover rules and I can keep the rest of the draft intact."
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
        "Market data was unavailable for that run. I still have the draft; try "
        "again, change the dates, or choose a different supported asset."
    ),
    "invalid_date_range": (
        "That date range is not valid for a backtest. Choose a start and end date "
        "in chronological order and I will keep the strategy intact."
    ),
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
            "missing rule, asset, or date range and I will keep the draft intact."
        )
    if failure_category == "unsupported_capability":
        return (
            "That request is outside the current executable backtest capability. "
            "I can preserve the idea and offer supported alternatives."
        )
    if failure_category == "parameter_validation_error":
        return (
            "One detail in the launch payload is not valid for the current engine. "
            "Adjust the strategy, dates, or sizing and I can run the same draft."
        )
    if failure_category == "upstream_dependency_error":
        return (
            "The run hit a temporary data or service issue. I still have the draft; "
            "ask me to try again or adjust the setup."
        )
    return (
        "The backtest could not complete. I still have the draft; ask me to try "
        "again or adjust the setup."
    )


def build_failure_envelope(
    *,
    request: LaunchBacktestRequest,
    execution_status: str,
    failure_category: str,
    failure_reason: str,
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
        provider_metadata={},
        failure_category=failure_category,
        failure_reason=failure_reason,
    )


def build_benchmark_metrics(
    *,
    request: LaunchBacktestRequest,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    aggregate_performance = metrics.get("aggregate", {}).get("performance", {})
    by_symbol = metrics.get("by_symbol", {})

    return {
        "symbol": request.benchmark_symbol,
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
    return {
        "strategy_type": request.strategy_type,
        "symbol": request.symbol,
        "symbols": request.symbols,
        "timeframe": request.timeframe,
        "date_range": request.date_range.model_dump(mode="python"),
        "metrics": envelope.metrics,
        "benchmark_metrics": envelope.benchmark_metrics,
        "assumptions": envelope.assumptions,
        "caveats": envelope.caveats,
        "result_card": result_card,
    }
