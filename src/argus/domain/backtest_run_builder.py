from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from argus.api.schemas import BacktestRun
from argus.domain.backtesting.config import classify_symbol, default_benchmark


def resolved_run_symbols(resolved_strategy: dict[str, Any]) -> list[str]:
    asset_universe = resolved_strategy.get("asset_universe")
    raw_symbols: list[Any] = []
    if isinstance(asset_universe, list):
        raw_symbols.extend(asset_universe)
    elif isinstance(asset_universe, str):
        raw_symbols.append(asset_universe)
    symbol = resolved_strategy.get("symbol")
    if isinstance(symbol, str):
        raw_symbols.append(symbol)

    symbols: list[str] = []
    for raw_symbol in raw_symbols:
        candidate = str(raw_symbol).strip().upper()
        if candidate and candidate not in symbols:
            symbols.append(candidate)
    return symbols


def enrich_result_card_actions(
    *,
    result_card: dict[str, Any],
    run_id: str,
    strategy_id: str | None,
    conversation_id: str,
) -> dict[str, Any]:
    enriched = deepcopy(result_card)
    actions = enriched.get("actions")
    if not isinstance(actions, list):
        return enriched

    enriched_actions: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        payload = action.get("payload")
        action_payload = dict(payload) if isinstance(payload, dict) else {}
        action_payload.update(
            {
                "run_id": run_id,
                "strategy_id": strategy_id,
                "conversation_id": conversation_id,
            }
        )
        enriched_actions.append(
            {
                **action,
                "presentation": "result",
                "payload": action_payload,
            }
        )
    enriched["actions"] = enriched_actions
    return enriched


def build_backtest_run_from_result(
    *,
    conversation_id: str,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
    run_id_factory: Callable[[], str] | None = None,
    now_func: Callable[[], datetime] | None = None,
    classify_symbol_func: Any = classify_symbol,
    default_benchmark_func: Any = default_benchmark,
) -> BacktestRun | None:
    resolved_strategy = envelope.get("resolved_strategy")
    resolved_parameters = envelope.get("resolved_parameters")
    metrics = envelope.get("metrics")
    benchmark_metrics = envelope.get("benchmark_metrics")
    if not isinstance(resolved_strategy, dict) or not isinstance(metrics, dict):
        return None

    symbols = resolved_run_symbols(resolved_strategy)
    if not symbols:
        return None
    symbol = symbols[0]
    run_id = (run_id_factory or (lambda: str(uuid4())))()

    try:
        asset_class = classify_symbol_func(symbol).asset_class
    except Exception:
        asset_class = "equity"

    resolved_strategy_snapshot = deepcopy(resolved_strategy)
    resolved_parameters_dict = (
        deepcopy(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )
    benchmark_metrics_dict = (
        deepcopy(benchmark_metrics) if isinstance(benchmark_metrics, dict) else None
    )
    benchmark_symbol = _explicit_benchmark_symbol(
        resolved_parameters=resolved_parameters_dict,
        benchmark_metrics=benchmark_metrics_dict,
    ) or default_benchmark_func(asset_class, symbols)
    resolved_parameters_dict.setdefault("benchmark_symbol", benchmark_symbol)
    provider_metadata = envelope.get("provider_metadata")
    config_snapshot = {
        "template": resolved_strategy_snapshot.get("strategy_type", "strategy"),
        "symbols": symbols,
        "timeframe": resolved_parameters_dict.get("timeframe", "1D"),
        "date_range": resolved_parameters_dict.get("date_range"),
        "benchmark_symbol": benchmark_symbol,
        "resolved_strategy": resolved_strategy_snapshot,
        "resolved_parameters": resolved_parameters_dict,
    }
    engine_config = resolved_parameters_dict.get("engine_config")
    if isinstance(engine_config, dict):
        config_snapshot["engine_config"] = deepcopy(engine_config)
    if isinstance(provider_metadata, dict):
        config_snapshot["provider_metadata"] = deepcopy(provider_metadata)
    enriched_result_card = enrich_result_card_actions(
        result_card=result_card,
        run_id=run_id,
        strategy_id=None,
        conversation_id=conversation_id,
    )

    chart = (
        deepcopy(enriched_result_card.get("chart"))
        if isinstance(enriched_result_card.get("chart"), dict)
        else None
    )
    if chart is not None:
        enriched_result_card["chart"] = deepcopy(chart)
    markers = chart.get("markers", []) if isinstance(chart, dict) else []
    trades = deepcopy(markers) if isinstance(markers, list) else []

    return BacktestRun(
        id=run_id,
        conversation_id=conversation_id,
        strategy_id=None,
        status="completed",
        asset_class=asset_class,
        symbols=symbols,
        allocation_method="equal_weight",
        benchmark_symbol=benchmark_symbol,
        metrics=metrics,
        config_snapshot=config_snapshot,
        conversation_result_card=enriched_result_card,
        created_at=(now_func or (lambda: datetime.now(timezone.utc)))(),
        chart=chart,
        trades=trades,
    )


def _explicit_benchmark_symbol(
    *,
    resolved_parameters: dict[str, Any],
    benchmark_metrics: dict[str, Any] | None,
) -> str | None:
    for candidate in (
        resolved_parameters.get("benchmark_symbol"),
        benchmark_metrics.get("symbol") if benchmark_metrics else None,
        benchmark_metrics.get("benchmark_symbol") if benchmark_metrics else None,
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().upper()
    return None
