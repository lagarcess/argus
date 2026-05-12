from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from loguru import logger

from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
    strategy_can_be_approved,
)
from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import (
    BacktestRun,
    ChatStreamRequest,
    Conversation,
    Message,
    Strategy,
    User,
)
from argus.domain.engine import classify_symbol, default_benchmark
from argus.domain.store import utcnow
from argus.llm.openrouter import build_openrouter_model, log_openrouter_failure

SUPPORTED_ONBOARDING_GOALS = {
    "learn_basics",
    "test_stock_idea",
    "build_passive_strategy",
    "explore_crypto",
    "surprise_me",
}

CONFIRMATION_ACTION_TYPES = {
    "run_backtest",
    "change_dates",
    "change_asset",
    "adjust_assumptions",
    "cancel_confirmation",
}

LOST_CONFIRMATION_STATE_MESSAGE = (
    "I lost the active confirmation state, but your conversation is saved. "
    "I can restate the strategy so you can confirm it again."
)


@dataclass(frozen=True)
class RuntimeFallbackContext:
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] | None = None
    artifact_references: list[ArtifactReference] | None = None
    confirmation_payload: dict[str, Any] | None = None
    recovery_message: str | None = None


def parse_onboarding_control_message(message: str) -> str | None:
    if message == "__ONBOARDING_SKIP__":
        return "surprise_me"
    prefix = "__ONBOARDING_GOAL__:"
    if not message.startswith(prefix):
        return None
    goal = message.removeprefix(prefix)
    if goal in SUPPORTED_ONBOARDING_GOALS:
        return goal
    return None


def sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


def fetch_run_metrics(user_id: str, run_id: str) -> dict[str, Any] | None:
    run = None
    if api_state.supabase_gateway is not None:
        try:
            run = api_state.supabase_gateway.get_backtest_run(
                user_id=user_id, run_id=run_id
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch run for result explanation",
                error=str(exc),
                run_id=run_id,
            )
    if run is None:
        run = api_state.store.backtest_runs.get(run_id)
    if run is None:
        return None
    return {
        "aggregate": run.metrics.get("aggregate", {}),
        "by_symbol": run.metrics.get("by_symbol", {}),
        "config": run.config_snapshot,
    }


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    if language.startswith("es"):
        return (
            f"\u00a1Listo! Aqu\u00ed tienes los resultados del backtest para "
            f"{joined}. \u00bfQu\u00e9 te parecen estas m\u00e9tricas?"
        )
    return f"Done! Here are the backtest results for {joined}. What do you think about these metrics?"


def runtime_result_message(runtime_result: dict[str, Any]) -> str | None:
    assistant_response = runtime_result.get("assistant_response")
    if isinstance(assistant_response, str) and assistant_response:
        return assistant_response
    assistant_prompt = runtime_result.get("assistant_prompt")
    if isinstance(assistant_prompt, str) and assistant_prompt:
        return assistant_prompt
    return None


def runtime_stage_status(runtime_result: dict[str, Any]) -> str:
    stage_outcome = runtime_result.get("stage_outcome")
    if isinstance(stage_outcome, str) and stage_outcome:
        return stage_outcome
    return "agent_runtime_turn"


def runtime_result_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return None
    result_card = final_payload.get("result_card")
    if isinstance(result_card, dict):
        return result_card
    return None


def runtime_confirmation_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    if runtime_result.get("stage_outcome") != "await_approval":
        return None
    payload = runtime_result.get("confirmation_payload")
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    optional_parameters = payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        optional_parameters = {}

    symbols = [
        str(symbol)
        for symbol in strategy.get("asset_universe", [])
        if str(symbol).strip()
    ]
    assets = ", ".join(symbols) if symbols else "Selected asset"
    strategy_type = display_strategy_slug(strategy)
    strategy_label = display_strategy_type(strategy)
    date_range = _format_confirmation_period(strategy.get("date_range"))
    title = f"{assets} {strategy_type}".strip()

    rows = [
        {"label": "Strategy", "value": strategy_label},
        {"label": "Assets", "value": assets},
        {"label": "Period", "value": date_range},
    ]
    canonical_strategy_type = executable_strategy_type(strategy)
    if strategy.get("cadence") and _strategy_type_uses_cadence(canonical_strategy_type):
        rows.append({"label": "Cadence", "value": str(strategy["cadence"]).title()})
    if strategy.get("entry_logic"):
        rows.append(
            {
                "label": "Buy rule",
                "value": _format_confirmation_value(strategy["entry_logic"]),
            }
        )
    if strategy.get("exit_logic"):
        rows.append(
            {
                "label": "Exit rule",
                "value": _format_confirmation_value(strategy["exit_logic"]),
            }
        )
    if strategy.get("capital_amount"):
        capital_label = (
            "Contribution"
            if _strategy_type_uses_cadence(canonical_strategy_type)
            else "Starting capital"
        )
        rows.append(
            {
                "label": capital_label,
                "value": f"${float(strategy['capital_amount']):,.0f}",
            }
        )

    assumptions = _confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )
    summary_period = _confirmation_period_without_parentheses(date_range)
    summary = (
        f"I read this as {assets} using {_article_for(strategy_type)} "
        f"{strategy_type} approach over {summary_period}."
    )
    return {
        "title": title,
        "statusLabel": "Ready to run",
        "summary": summary,
        "rows": rows,
        "assumptions": assumptions,
        "actions": [
            {
                "id": "run-backtest",
                "type": "run_backtest",
                "label": "Run backtest",
                "presentation": "confirmation",
                "payload": {},
            },
            {
                "id": "change-dates",
                "type": "change_dates",
                "label": "Change dates",
                "presentation": "confirmation",
                "payload": {},
            },
            {
                "id": "change-asset",
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {},
            },
            {
                "id": "adjust-assumptions",
                "type": "adjust_assumptions",
                "label": "Adjust assumptions",
                "presentation": "confirmation",
                "payload": {},
            },
            {
                "id": "cancel-confirmation",
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {},
            },
        ],
    }


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
) -> list[str]:
    assumptions: list[str] = []
    strategy_type = executable_strategy_type(strategy)
    strategy_capital = strategy.get("capital_amount")
    if isinstance(strategy_capital, int | float):
        if _strategy_type_uses_cadence(strategy_type):
            assumptions.append(f"${float(strategy_capital):,.0f} recurring contribution")
        else:
            assumptions.append(f"${float(strategy_capital):,.0f} starting capital")
    initial_capital = _optional_parameter_value(optional_parameters, "initial_capital")
    if isinstance(initial_capital, int | float) and not isinstance(
        strategy_capital, int | float
    ):
        if _strategy_type_uses_cadence(strategy_type) and strategy.get("capital_amount"):
            assumptions.append(
                f"${float(strategy['capital_amount']):,.0f} recurring contribution"
            )
        else:
            assumptions.append(f"${float(initial_capital):,.0f} starting capital")
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(f"{timeframe} bars")
    fees = _optional_parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")
    slippage = _optional_parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    return assumptions


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    value = optional_parameters.get(key)
    if isinstance(value, dict):
        return value.get("value")
    return None


def _format_confirmation_value(value: Any) -> str:
    if isinstance(value, dict):
        start = value.get("start") or value.get("from")
        end = value.get("end") or value.get("to")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None or value == "":
        return "Default period"
    return str(value)


def _format_confirmation_period(value: Any) -> str:
    return resolve_date_range(value, today=_confirmation_today()).display


def _confirmation_period_without_parentheses(value: str) -> str:
    if "(" not in value or not value.endswith(")"):
        return value
    label, _, dates = value.partition("(")
    return f"{label.strip()}, {dates[:-1].strip()}"


def _strategy_type_uses_cadence(strategy_type: str) -> bool:
    normalized = strategy_type.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "dca",
        "dca_accumulation",
        "recurring_accumulation",
        "recurring_buys",
    }


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _confirmation_today() -> date:
    return date.today()


def runtime_result_envelope(runtime_result: dict[str, Any]) -> dict[str, Any]:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return {}
    result = final_payload.get("result")
    return dict(result) if isinstance(result, dict) else {}


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
        asset_class = classify_symbol(symbol).asset_class
    except ValueError:
        asset_class = "equity"

    benchmark_symbol = default_benchmark(asset_class, symbols)
    if isinstance(benchmark_metrics, dict):
        candidate_benchmark = benchmark_metrics.get("benchmark_symbol")
        if isinstance(candidate_benchmark, str) and candidate_benchmark:
            benchmark_symbol = candidate_benchmark.strip().upper()

    resolved_parameters_dict = (
        dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )
    config_snapshot = {
        "template": resolved_strategy.get("strategy_type", "strategy"),
        "symbols": symbols,
        "timeframe": resolved_parameters_dict.get("timeframe", "1D"),
        "date_range": resolved_parameters_dict.get("date_range"),
        "benchmark_symbol": benchmark_symbol,
        "resolved_strategy": resolved_strategy,
        "resolved_parameters": resolved_parameters_dict,
    }

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
) -> BacktestRun | None:
    run = build_runtime_backtest_run(
        user_id=user.id,
        conversation_id=conversation.id,
        result_card=result_card,
        envelope=envelope,
    )
    if run is None:
        return None

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


def persist_onboarding_update(user: User, patch: dict[str, Any]) -> User:
    current = (
        api_state.supabase_gateway.get_user(user_id=user.id)
        if api_state.supabase_gateway is not None
        else api_state.store.users.get(user.id, user)
    )
    if current is None:
        current = user

    onboarding = current.onboarding.model_copy(update=patch)
    updated = current.model_copy(
        update={
            "onboarding": onboarding,
            "updated_at": utcnow(),
        }
    )
    if api_state.supabase_gateway is not None:
        try:
            updated = api_state.supabase_gateway.update_user(
                user.id, updated.model_dump(mode="json")
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile update failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    api_state.store.users[user.id] = updated
    return updated


def chat_request_message(payload: ChatStreamRequest) -> str:
    if payload.action is None:
        return payload.message or ""
    action_type = payload.action.type
    action_messages = {
        "run_backtest": "run backtest",
        "change_dates": "change dates",
        "change_asset": "change asset",
        "adjust_assumptions": "adjust assumptions",
        "cancel_confirmation": "cancel backtest",
        "show_breakdown": "show a detailed breakdown of this result",
        "refine_strategy": "refine this strategy",
        "save_strategy": "save this strategy",
    }
    return action_messages[action_type]


def chat_display_message(payload: ChatStreamRequest) -> str:
    if payload.action is None:
        return payload.message or ""
    return payload.action.label or chat_request_message(payload)


def chat_action_run_id(payload: ChatStreamRequest) -> str | None:
    if payload.action is None:
        return None
    raw_run_id = payload.action.payload.get("run_id")
    if raw_run_id is None:
        raw_run_id = payload.action.payload.get("runId")
    if raw_run_id is None:
        return None
    run_id = str(raw_run_id).strip()
    return run_id or None


def chat_action_conversation_id(payload: ChatStreamRequest) -> str | None:
    if payload.action is None:
        return None
    raw_conversation_id = payload.action.payload.get("conversation_id")
    if raw_conversation_id is None:
        raw_conversation_id = payload.action.payload.get("conversationId")
    if raw_conversation_id is None:
        return None
    conversation_id = str(raw_conversation_id).strip()
    return conversation_id or None


def is_confirmation_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type in CONFIRMATION_ACTION_TYPES


def pending_confirmation_exists(*, user_id: str, conversation_id: str) -> bool:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )

    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        if _metadata_invalidates_confirmation(metadata):
            return False
        if metadata.get("confirmation_card"):
            return True
    return False


def _recent_messages_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
    limit: int,
) -> list[Message]:
    messages: list[Message] = []
    if api_state.supabase_gateway is not None:
        try:
            messages = api_state.supabase_gateway.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase confirmation state read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
    if not messages:
        messages = list(api_state.store.messages.get(conversation_id, []))[-limit:]
    return messages


async def runtime_checkpoint_values(
    *,
    workflow: Any,
    conversation_id: str,
) -> dict[str, Any]:
    try:
        state_snapshot = await workflow.aget_state(
            {"configurable": {"thread_id": conversation_id}}
        )
    except Exception as exc:
        logger.warning(
            "Agent runtime checkpoint read failed; considering metadata fallback",
            error=str(exc),
            conversation_id=conversation_id,
        )
        return {}
    values = getattr(state_snapshot, "values", None)
    return values if isinstance(values, dict) else {}


def checkpoint_has_pending_confirmation(values: dict[str, Any]) -> bool:
    stage_outcome = values.get("stage_outcome")
    stage_outcome_value = str(getattr(stage_outcome, "value", stage_outcome or ""))
    if stage_outcome_value != "await_approval":
        return False
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        return True
    run_state = values.get("run_state")
    return getattr(run_state, "confirmation_payload", None) is not None


def checkpoint_has_latest_result(values: dict[str, Any]) -> bool:
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    return (
        snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    )


def confirmation_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        if _metadata_invalidates_confirmation(metadata):
            return None
        if not metadata.get("confirmation_card"):
            continue
        payload = metadata.get("confirmation_payload")
        if not isinstance(payload, dict):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        strategy = payload.get("strategy")
        if not isinstance(strategy, dict):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        try:
            pending_strategy = StrategySummary.model_validate(strategy)
        except Exception:
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        if not strategy_can_be_approved(pending_strategy):
            return RuntimeFallbackContext(
                recovery_message=LOST_CONFIRMATION_STATE_MESSAGE
            )
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="backtest_execution",
                completed=False,
                pending_strategy_summary=pending_strategy,
                last_unresolved_follow_up=(
                    pending_strategy.raw_user_phrasing
                    or pending_strategy.strategy_thesis
                    or pending_strategy.strategy_type
                ),
                resolution_provenance=list(pending_strategy.resolution_provenance),
            ),
            selected_thread_metadata={
                "latest_task_type": "backtest_execution",
                "last_stage_outcome": "await_approval",
                "fallback_source": "message_metadata",
            },
            artifact_references=[],
            confirmation_payload=payload,
        )
    return None


def _metadata_invalidates_confirmation(metadata: dict[str, Any]) -> bool:
    if metadata.get("result_card") or metadata.get("result_run_id"):
        return True
    action = metadata.get("chat_action")
    return isinstance(action, dict) and action.get("type") == "cancel_confirmation"


def latest_result_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        raw_run_id = metadata.get("result_run_id") or metadata.get("latest_run_id")
        if raw_run_id is None:
            continue
        run = _run_by_id_for_user(user_id=user_id, run_id=str(raw_run_id))
        if run is None or run.conversation_id != conversation_id:
            continue
        if run.status != "completed":
            continue
        reference = ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id=run.id,
            metadata={
                "conversation_id": run.conversation_id,
                "strategy_id": run.strategy_id,
                "asset_class": run.asset_class,
                "symbols": list(run.symbols),
                "benchmark_symbol": run.benchmark_symbol,
                "metrics": run.metrics,
                "config_snapshot": run.config_snapshot,
                "result_card": run.conversation_result_card,
            },
        )
        return RuntimeFallbackContext(
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="results_explanation",
                completed=True,
                latest_backtest_result_reference=reference,
            ),
            selected_thread_metadata={
                "latest_task_type": "results_explanation",
                "last_stage_outcome": "ready_to_respond",
                "fallback_source": "message_metadata",
            },
            artifact_references=[reference],
        )
    return None


def _task_snapshot_from_value(value: Any) -> TaskSnapshot | None:
    if value is None:
        return None
    if isinstance(value, TaskSnapshot):
        return value
    try:
        return TaskSnapshot.model_validate(value)
    except Exception:
        return None


def _run_by_id_for_user(*, user_id: str, run_id: str) -> BacktestRun | None:
    run = None
    if api_state.supabase_gateway is not None:
        try:
            run = api_state.supabase_gateway.get_backtest_run(
                user_id=user_id,
                run_id=run_id,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase backtest run read failed; using dev memory fallback",
                error=str(exc),
                run_id=run_id,
            )
    if run is None:
        run = api_state.store.backtest_runs.get(run_id)
    if run is None:
        return None
    if api_state.store.backtest_run_owners.get(run.id, user_id) != user_id:
        return None
    return run


def latest_completed_run_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
) -> BacktestRun | None:
    candidates = [
        run
        for run_id, run in api_state.store.backtest_runs.items()
        if api_state.store.backtest_run_owners.get(run_id) == user_id
        and run.conversation_id == conversation_id
        and run.status == "completed"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda run: run.created_at)


def run_for_result_action(
    *,
    payload: ChatStreamRequest,
    user: User,
    conversation_id: str,
    require_run_id: bool = False,
) -> BacktestRun | None:
    run_id = chat_action_run_id(payload)
    action_conversation_id = chat_action_conversation_id(payload)
    if action_conversation_id and action_conversation_id != conversation_id:
        return None
    if require_run_id and not run_id:
        return None
    if run_id:
        run = _run_by_id_for_user(user_id=user.id, run_id=run_id)
        if run is None:
            return None
        if run.conversation_id != conversation_id or run.status != "completed":
            return None
        return run
    return latest_completed_run_for_conversation(
        user_id=user.id,
        conversation_id=conversation_id,
    )


def strategy_template_from_run(run: BacktestRun) -> str:
    template = str(run.config_snapshot.get("template") or "buy_and_hold")
    supported_templates = {
        "buy_and_hold",
        "buy_the_dip",
        "rsi_mean_reversion",
        "moving_average_crossover",
        "dca_accumulation",
        "momentum_breakout",
        "trend_follow",
    }
    return template if template in supported_templates else "buy_and_hold"


def save_strategy_from_run(*, user: User, run: BacktestRun) -> Strategy:
    if run.strategy_id:
        existing = (
            api_state.supabase_gateway.get_strategy(
                user_id=user.id, strategy_id=run.strategy_id
            )
            if api_state.supabase_gateway is not None
            else api_state.store.strategies.get(run.strategy_id)
        )
        if existing is not None:
            return existing

    now = utcnow()
    template = strategy_template_from_run(run)
    strategy_name = (
        run.conversation_result_card.get("title") or f"{', '.join(run.symbols)} idea"
    )
    parameters = dict(run.config_snapshot)
    payload = {
        "name": strategy_name,
        "name_source": "ai_generated",
        "template": template,
        "asset_class": run.asset_class,
        "symbols": run.symbols,
        "parameters": parameters,
        "metrics_preferences": [
            "total_return_pct",
            "max_drawdown_pct",
            "benchmark_delta",
        ],
        "benchmark_symbol": run.benchmark_symbol,
        "conversation_id": run.conversation_id,
    }
    if api_state.supabase_gateway is not None:
        strategy = api_state.supabase_gateway.create_strategy(
            user_id=user.id, payload=payload
        )
    else:
        strategy = Strategy(
            id=api_state.store.new_id(),
            name=strategy_name,
            name_source="ai_generated",
            template=template,  # type: ignore[arg-type]
            asset_class=run.asset_class,
            symbols=run.symbols,
            parameters=parameters,
            metrics_preferences=payload["metrics_preferences"],
            benchmark_symbol=run.benchmark_symbol,
            created_at=now,
            updated_at=now,
        )
        api_state.store.strategies[strategy.id] = strategy
    run.strategy_id = strategy.id
    return strategy


def result_breakdown_context(run: BacktestRun) -> dict[str, Any]:
    card = run.conversation_result_card
    return {
        "run_id": run.id,
        "title": card.get("title") if isinstance(card, dict) else None,
        "asset_class": run.asset_class,
        "symbols": run.symbols,
        "benchmark_symbol": run.benchmark_symbol,
        "date_range": card.get("date_range") if isinstance(card, dict) else None,
        "metrics": card.get("rows") if isinstance(card, dict) else None,
        "assumptions": card.get("assumptions") if isinstance(card, dict) else None,
        "benchmark_note": card.get("benchmark_note") if isinstance(card, dict) else None,
        "config_snapshot": run.config_snapshot,
        "raw_metrics": run.metrics,
    }


def llm_result_breakdown_message(context: dict[str, Any]) -> str | None:
    model = build_openrouter_model("result_breakdown")
    if model is None:
        return None
    try:
        response = model.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are Argus, an investing backtest copilot. Explain the stored "
                        "backtest result for a novice using only the supplied JSON. Do not "
                        "invent causes, trades, prices, support, or missing metrics. Explain "
                        "what the metrics mean, the benchmark comparison, assumptions, and "
                        "caveats. Keep the answer under 90 words. Do not restate every "
                        "result-card metric. Interpret what matters, name the main caveat, "
                        "and use only supplied run data."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, default=str),
                },
            ]
        )
    except Exception as exc:
        log_openrouter_failure(
            task="result_breakdown",
            model_name=None,
            exc=exc,
            message="LLM result breakdown failed; using deterministic fallback",
        )
        return None
    content = getattr(response, "content", "")
    text = content.strip() if isinstance(content, str) else ""
    words = text.split()
    if len(words) < 12 or len(words) > 95:
        return None
    if "not a prediction" not in text.lower():
        return None
    return text


def fallback_result_breakdown_message(context: dict[str, Any]) -> str:
    total_return = _result_breakdown_metric(
        context,
        "total_return_pct",
        row_keys=("total_return_pct", "total_return"),
    )
    benchmark_return = _result_breakdown_metric(
        context,
        "benchmark_return_pct",
        row_keys=("benchmark_return_pct", "benchmark_return"),
    )
    max_drawdown = _result_breakdown_metric(
        context,
        "max_drawdown_pct",
        row_keys=("max_drawdown_pct", "max_drawdown"),
    )
    assumptions = context.get("assumptions")
    assumption_text = (
        " ".join(str(item).strip() for item in assumptions[:3] if str(item).strip())
        if isinstance(assumptions, list)
        else ""
    ) or "the stored run settings"
    benchmark = str(context.get("benchmark_symbol") or "").strip()
    symbols = context.get("symbols")
    symbols_text = (
        ", ".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        if isinstance(symbols, list)
        else ""
    ) or "The available result"
    return_text = (
        f"with a {_format_result_breakdown_percent(total_return)} total return"
        if total_return is not None
        else "with the available result"
    )
    benchmark_text = (
        f"{benchmark} at {_format_result_breakdown_percent(benchmark_return)}"
        if benchmark and benchmark_return is not None
        else benchmark or "the benchmark"
    )
    drawdown_text = (
        _format_result_breakdown_percent(max_drawdown)
        if max_drawdown is not None
        else "the available risk data"
    )
    return (
        f"{symbols_text} finished {return_text} versus {benchmark_text}. "
        f"The main risk shown here was max drawdown of {drawdown_text}. "
        f"Assumptions: {assumption_text}. "
        "This is historical simulation evidence, not a prediction or trading recommendation."
    )


def _result_breakdown_metric(
    context: dict[str, Any],
    metric_key: str,
    *,
    row_keys: tuple[str, ...],
) -> float | None:
    raw_metrics = context.get("raw_metrics")
    value = _nested_result_breakdown_number(
        raw_metrics,
        ("aggregate", "performance", metric_key),
    )
    if value is not None:
        return value

    rows = context.get("metrics")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "").strip()
            if key not in row_keys:
                continue
            return _coerce_result_breakdown_number(row.get("value"))
    return None


def _nested_result_breakdown_number(
    payload: Any,
    path: tuple[str, ...],
) -> float | None:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _coerce_result_breakdown_number(current)


def _coerce_result_breakdown_number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def _format_result_breakdown_percent(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def result_breakdown_message(run: BacktestRun | None) -> str:
    if run is None:
        return (
            "I could not find the latest completed result for this conversation. "
            "Run the backtest again and I can break down the metrics from that result."
        )
    context = result_breakdown_context(run)
    return llm_result_breakdown_message(context) or fallback_result_breakdown_message(
        context
    )


_assistant_copy_for_result = assistant_copy_for_result
_runtime_result_message = runtime_result_message
_runtime_stage_status = runtime_stage_status
_runtime_result_card = runtime_result_card
_runtime_confirmation_card = runtime_confirmation_card
_runtime_result_envelope = runtime_result_envelope
_resolved_run_symbols = resolved_run_symbols
_build_runtime_backtest_run = build_runtime_backtest_run
_persist_runtime_backtest_run = persist_runtime_backtest_run
_count_completed_runs_for_user = count_completed_runs_for_user
_persist_onboarding_update = persist_onboarding_update
_chat_request_message = chat_request_message
_chat_display_message = chat_display_message
_chat_action_run_id = chat_action_run_id
_chat_action_conversation_id = chat_action_conversation_id
_is_confirmation_action = is_confirmation_action
_pending_confirmation_exists = pending_confirmation_exists
_latest_completed_run_for_conversation = latest_completed_run_for_conversation
_run_for_result_action = run_for_result_action
_strategy_template_from_run = strategy_template_from_run
_save_strategy_from_run = save_strategy_from_run
_result_breakdown_context = result_breakdown_context
_llm_result_breakdown_message = llm_result_breakdown_message
_fallback_result_breakdown_message = fallback_result_breakdown_message
_result_breakdown_message = result_breakdown_message
