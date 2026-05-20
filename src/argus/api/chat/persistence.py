from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.chat.context_packets import (
    collect_context_packets_for_completed_run,
    enrich_run_with_context_packets,
    persist_context_packet_records,
)
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain.backtesting.config import classify_symbol, default_benchmark
from argus.domain.store import utcnow


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
    enriched = dict(result_card)
    actions = result_card.get("actions")
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


def build_runtime_backtest_run(
    *,
    user_id: str,
    conversation_id: str,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
    classify_symbol_func: Any = classify_symbol,
    default_benchmark_func: Any = default_benchmark,
) -> BacktestRun | None:
    del user_id
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
    run_id = api_state.store.new_id()
    result_card = enrich_result_card_actions(
        result_card=result_card,
        run_id=run_id,
        strategy_id=None,
        conversation_id=conversation_id,
    )

    try:
        asset_class = classify_symbol_func(symbol).asset_class
    except ValueError:
        asset_class = "equity"

    benchmark_symbol = default_benchmark_func(asset_class, symbols)
    if isinstance(benchmark_metrics, dict):
        candidate_benchmark = benchmark_metrics.get("benchmark_symbol")
        if isinstance(candidate_benchmark, str) and candidate_benchmark:
            benchmark_symbol = candidate_benchmark.strip().upper()

    resolved_parameters_dict = (
        dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )
    provider_metadata = envelope.get("provider_metadata")
    config_snapshot = {
        "template": resolved_strategy.get("strategy_type", "strategy"),
        "symbols": symbols,
        "timeframe": resolved_parameters_dict.get("timeframe", "1D"),
        "date_range": resolved_parameters_dict.get("date_range"),
        "benchmark_symbol": benchmark_symbol,
        "resolved_strategy": resolved_strategy,
        "resolved_parameters": resolved_parameters_dict,
    }
    if isinstance(provider_metadata, dict):
        config_snapshot["provider_metadata"] = dict(provider_metadata)

    chart = (
        result_card.get("chart") if isinstance(result_card.get("chart"), dict) else None
    )

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
        conversation_result_card=result_card,
        created_at=utcnow(),
        chart=chart,
        trades=list(chart.get("markers", [])) if isinstance(chart, dict) else [],
    )


def persist_runtime_backtest_run(
    *,
    user: User,
    conversation: Conversation,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
    classify_symbol_func: Any = classify_symbol,
    default_benchmark_func: Any = default_benchmark,
) -> BacktestRun | None:
    run = build_runtime_backtest_run(
        user_id=user.id,
        conversation_id=conversation.id,
        result_card=result_card,
        envelope=envelope,
        classify_symbol_func=classify_symbol_func,
        default_benchmark_func=default_benchmark_func,
    )
    if run is None:
        return None

    context_packets = (
        collect_context_packets_for_completed_run(run)
        if api_state.supabase_gateway is not None
        else []
    )
    run = enrich_run_with_context_packets(run, context_packets)

    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user.id

    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.create_backtest_run(user_id=user.id, run=run)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase backtest run write failed; using dev memory fallback",
                error=str(exc),
                run_id=run.id,
            )
        else:
            try:
                persist_context_packet_records(
                    gateway=api_state.supabase_gateway,
                    user_id=user.id,
                    run=run,
                    packets=context_packets,
                )
            except Exception as exc:
                logger.warning(
                    "Context packet persistence failed; result card snapshot remains",
                    error=str(exc),
                    run_id=run.id,
                )

    if conversation.id in api_state.store.conversations:
        api_state.store.conversations[conversation.id] = conversation.model_copy(
            update={
                "last_message_preview": result_card.get("title")
                or conversation.last_message_preview,
                "updated_at": utcnow(),
            }
        )

    return run


def count_completed_runs_for_user(user_id: str) -> int:
    if api_state.supabase_gateway is not None:
        try:
            return api_state.supabase_gateway.count_completed_runs(user_id=user_id)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase completed run count failed; using dev memory fallback",
                error=str(exc),
                user_id=user_id,
            )
    return sum(
        1
        for run_id, run in api_state.store.backtest_runs.items()
        if api_state.store.backtest_run_owners.get(run_id) == user_id
        and run.status == "completed"
    )
