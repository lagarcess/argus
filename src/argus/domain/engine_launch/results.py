from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)


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
    symbol_metrics = by_symbol.get(request.symbol, {})
    symbol_performance = symbol_metrics.get("performance", {})

    return {
        "symbol": request.benchmark_symbol,
        "aggregate": {
            "total_return_pct": aggregate_performance.get("benchmark_return_pct"),
        },
        "by_symbol": {
            request.symbol: {
                "total_return_pct": symbol_performance.get("benchmark_return_pct"),
            }
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
        "timeframe": request.timeframe,
        "date_range": request.date_range.model_dump(mode="python"),
        "metrics": envelope.metrics,
        "benchmark_metrics": envelope.benchmark_metrics,
        "assumptions": envelope.assumptions,
        "caveats": envelope.caveats,
        "result_card": result_card,
    }
