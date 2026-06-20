from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.chat.context_packets import (
    collect_context_packet_result_for_completed_run,
    enrich_run_with_context_packets,
    persist_context_packet_records,
)
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain import backtest_run_builder
from argus.domain.backtesting.config import classify_symbol, default_benchmark
from argus.domain.store import utcnow


def resolved_run_symbols(resolved_strategy: dict[str, Any]) -> list[str]:
    return backtest_run_builder.resolved_run_symbols(resolved_strategy)


def enrich_result_card_actions(
    *,
    result_card: dict[str, Any],
    run_id: str,
    strategy_id: str | None,
    conversation_id: str,
) -> dict[str, Any]:
    return backtest_run_builder.enrich_result_card_actions(
        result_card=result_card,
        run_id=run_id,
        strategy_id=strategy_id,
        conversation_id=conversation_id,
    )


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
    return backtest_run_builder.build_backtest_run_from_result(
        conversation_id=conversation_id,
        result_card=result_card,
        envelope=envelope,
        run_id_factory=api_state.store.new_id,
        now_func=utcnow,
        classify_symbol_func=classify_symbol_func,
        default_benchmark_func=default_benchmark_func,
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

    context_collection = (
        collect_context_packet_result_for_completed_run(run)
        if api_state.supabase_gateway is not None
        else None
    )
    context_packets = context_collection.packets if context_collection else []
    context_collection_status = (
        context_collection.statuses if context_collection is not None else None
    )
    run = enrich_run_with_context_packets(
        run,
        context_packets,
        collection_status=context_collection_status,
    )

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

    from argus.api.chat.evidence import auto_capture_completed_backtest

    try:
        auto_capture_completed_backtest(
            user=user,
            conversation=conversation,
            run=run,
        )
    except Exception as exc:
        if not dev_memory_fallback_enabled():
            raise
        logger.warning(
            "Evidence auto-capture failed; result run remains persisted",
            error=str(exc),
            run_id=run.id,
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
