from __future__ import annotations

from typing import Any

from argus.agent_runtime.state.models import ArtifactReference
from argus.api.schemas import BacktestRun


def result_fact_bank(run: BacktestRun) -> dict[str, Any]:
    context_packets = (
        run.conversation_result_card.get("context_packets")
        if isinstance(run.conversation_result_card, dict)
        else None
    )
    return {
        "run_id": run.id,
        "conversation_id": run.conversation_id,
        "strategy_id": run.strategy_id,
        "asset_class": run.asset_class,
        "symbols": list(run.symbols),
        "benchmark_symbol": run.benchmark_symbol,
        "metrics": run.metrics,
        "config_snapshot": run.config_snapshot,
        "result_card": run.conversation_result_card,
        "context_packets": context_packets if isinstance(context_packets, list) else [],
        "chart": run.chart,
        "trades": run.trades,
    }


def result_reference_from_run(run: BacktestRun) -> ArtifactReference:
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id=run.id,
        artifact_status=run.status,
        metadata=result_fact_bank(run),
    )


def saved_strategy_metadata(run: BacktestRun, strategy_id: str) -> dict[str, Any]:
    return {
        "saved_strategy_id": strategy_id,
        "result_strategy_id": strategy_id,
        "result_run_id": run.id,
        "latest_run_id": run.id,
    }


def saved_strategy_metadata_from_sources(
    *,
    run: BacktestRun,
    message_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy_id = _saved_strategy_id_from_message(message_metadata)
    if strategy_id is None:
        strategy_id = _saved_strategy_id_from_result_card(run.conversation_result_card)
    if strategy_id is None:
        return {}
    return saved_strategy_metadata(run, strategy_id)


def _saved_strategy_id_from_message(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("saved_strategy_id", "result_strategy_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _saved_strategy_id_from_result_card(card: dict[str, Any]) -> str | None:
    if not isinstance(card, dict):
        return None
    for key in ("saved_strategy_id", "savedStrategyId", "result_strategy_id"):
        value = card.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("saved_state", "savedState"):
        saved_state = card.get(key)
        if not isinstance(saved_state, dict):
            continue
        value = saved_state.get("strategy_id") or saved_state.get("strategyId")
        if isinstance(value, str) and value:
            return value
    return None
