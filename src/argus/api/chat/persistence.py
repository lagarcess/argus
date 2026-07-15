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
from argus.domain.backtest_finalization import stable_backtest_run_id
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
    quick_take: str | None = None,
    breakdown: Any = None,
    classify_symbol_func: Any = classify_symbol,
    default_benchmark_func: Any = default_benchmark,
    run_id: str | None = None,
) -> BacktestRun | None:
    del user_id
    result_card = _result_card_with_evidence_context(
        result_card=result_card,
        quick_take=quick_take,
        breakdown=breakdown,
    )
    return backtest_run_builder.build_backtest_run_from_result(
        conversation_id=conversation_id,
        result_card=result_card,
        envelope=envelope,
        run_id_factory=(lambda: run_id) if run_id is not None else api_state.store.new_id,
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
    quick_take: str | None = None,
    breakdown: Any = None,
    classify_symbol_func: Any = classify_symbol,
    default_benchmark_func: Any = default_benchmark,
    execution_identity: str,
) -> BacktestRun | None:
    run_id = stable_backtest_run_id(user.id, execution_identity)
    run = build_runtime_backtest_run(
        user_id=user.id,
        conversation_id=conversation.id,
        result_card=result_card,
        envelope=envelope,
        quick_take=quick_take,
        breakdown=breakdown,
        classify_symbol_func=classify_symbol_func,
        default_benchmark_func=default_benchmark_func,
        run_id=run_id,
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

    from argus.api.chat.evidence import finalize_completed_backtest

    finalized = finalize_completed_backtest(
        user_id=user.id,
        conversation_id=conversation.id,
        run=run,
        execution_identity=execution_identity,
    )
    run = finalized.run

    if api_state.supabase_gateway is not None:
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
                "last_message_preview": run.conversation_result_card.get("title")
                or conversation.last_message_preview,
                "updated_at": utcnow(),
            }
        )

    return run


def _result_card_with_evidence_context(
    *,
    result_card: dict[str, Any],
    quick_take: str | None,
    breakdown: Any,
) -> dict[str, Any]:
    enriched = dict(result_card)
    if (
        "quick_take" not in enriched
        and isinstance(quick_take, str)
        and quick_take.strip()
    ):
        enriched["quick_take"] = quick_take.strip()
    if "breakdown" not in enriched and breakdown is not None:
        enriched["breakdown"] = breakdown
    return enriched


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
