from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

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

STALE_CONFIRMATION_ACTION_MESSAGE = (
    "That confirmation was updated. Use the latest Ready to run card before "
    "running the backtest."
)


@dataclass(frozen=True)
class RuntimeFallbackContext:
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] | None = None
    artifact_references: list[ArtifactReference] | None = None
    confirmation_payload: dict[str, Any] | None = None
    recovery_message: str | None = None


class ResultBreakdownPart(BaseModel):
    kind: Literal["text", "fact"]
    text: str = ""
    fact_id: str | None = None


class ResultBreakdownSection(BaseModel):
    heading: str
    parts: list[ResultBreakdownPart] = Field(default_factory=list)


class ResultBreakdownDraft(BaseModel):
    sections: list[ResultBreakdownSection] = Field(default_factory=list)


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


def runtime_confirmation_card(
    runtime_result: dict[str, Any],
    *,
    confirmation_id: str | None = None,
) -> dict[str, Any] | None:
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
    active_confirmation_id = confirmation_id or f"confirmation-{uuid4()}"
    return {
        "confirmation_id": active_confirmation_id,
        "confirmation_state": "active",
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
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "change-dates",
                "type": "change_dates",
                "label": "Change dates",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "change-asset",
                "type": "change_asset",
                "label": "Change asset",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "adjust-assumptions",
                "type": "adjust_assumptions",
                "label": "Adjust assumptions",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
            },
            {
                "id": "cancel-confirmation",
                "type": "cancel_confirmation",
                "label": "Cancel",
                "presentation": "confirmation",
                "payload": {"confirmation_id": active_confirmation_id},
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


def stale_confirmation_action_message(
    *,
    payload: ChatStreamRequest,
    user_id: str,
    conversation_id: str,
) -> str | None:
    if (
        payload.action is None
        or payload.action.type != "run_backtest"
        or payload.action.presentation != "confirmation"
    ):
        return None
    action_confirmation_id = _confirmation_id_from_action_payload(payload.action.payload)
    if action_confirmation_id is None:
        return None
    latest_confirmation_id = latest_active_confirmation_id(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if latest_confirmation_id is None or latest_confirmation_id == action_confirmation_id:
        return None
    return STALE_CONFIRMATION_ACTION_MESSAGE


def latest_active_confirmation_id(
    *,
    user_id: str,
    conversation_id: str,
) -> str | None:
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
        card = metadata.get("confirmation_card")
        if not isinstance(card, dict):
            continue
        return _confirmation_id_from_card(card)
    return None


def _confirmation_id_from_action_payload(payload: dict[str, Any]) -> str | None:
    raw_value = payload.get("confirmation_id") or payload.get("confirmationId")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _confirmation_id_from_card(card: dict[str, Any]) -> str | None:
    raw_value = card.get("confirmation_id") or card.get("confirmationId")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


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
    return snapshot is not None and snapshot.latest_backtest_result_reference is not None


def checkpoint_has_pending_strategy(values: dict[str, Any]) -> bool:
    snapshot = _task_snapshot_from_value(values.get("latest_task_snapshot"))
    return snapshot is not None and snapshot.pending_strategy_summary is not None


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


def pending_strategy_metadata_fallback_context(
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
        if message.role != "assistant":
            continue
        if not isinstance(message.metadata, dict):
            return None
        metadata = message.metadata
        if _metadata_invalidates_pending_strategy(metadata):
            return None
        pending_payload = metadata.get("pending_strategy")
        if not isinstance(pending_payload, dict):
            return None
        strategy_payload = pending_payload.get("strategy")
        if not isinstance(strategy_payload, dict):
            continue
        try:
            pending_strategy = StrategySummary.model_validate(strategy_payload)
        except Exception:
            continue
        requested_field = pending_payload.get("requested_field")
        stage_outcome = str(
            metadata.get("agent_runtime_stage_outcome") or "await_user_reply"
        )
        selected_thread_metadata: dict[str, Any] = {
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": stage_outcome,
            "fallback_source": "pending_strategy_metadata",
        }
        if isinstance(requested_field, str) and requested_field:
            selected_thread_metadata["requested_field"] = requested_field
        pending_resolution = pending_payload.get("pending_resolution")
        if isinstance(pending_resolution, dict):
            selected_thread_metadata["pending_resolution"] = dict(pending_resolution)
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
            selected_thread_metadata=selected_thread_metadata,
            artifact_references=[],
            confirmation_payload=(
                metadata.get("confirmation_payload")
                if isinstance(metadata.get("confirmation_payload"), dict)
                else None
            ),
        )
    return None


def _metadata_invalidates_pending_strategy(metadata: dict[str, Any]) -> bool:
    if metadata.get("result_card") or metadata.get("result_run_id"):
        return True
    action = metadata.get("chat_action")
    if isinstance(action, dict) and action.get("type") == "cancel_confirmation":
        return True
    stage_outcome = str(metadata.get("agent_runtime_stage_outcome") or "")
    return stage_outcome in {
        "execution_succeeded",
        "ready_to_respond",
        "end_run",
    }


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
    fact_bank = result_breakdown_fact_bank(context)
    required_fact_ids = _required_result_breakdown_fact_ids(fact_bank)
    try:
        structured_model = model.with_structured_output(ResultBreakdownDraft)
        response = structured_model.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are Argus, an investing backtest copilot. Explain the stored "
                        "backtest result using only the supplied fact_bank. Return flexible, "
                        "non-template professional markdown sections and vary the section "
                        "headings. Build each section from text parts and fact reference "
                        "parts. Use text parts for educational framing and fact reference "
                        "parts for every run-specific symbol, date, percentage, benchmark, "
                        "assumption, and caveat. Fact references render as polished canonical "
                        "callouts, so do not try to manually copy or decorate the fact values "
                        "inside text parts. Keep the writing polished, conversational, and "
                        "cohesive rather than fragmented. Respect capability truth in next "
                        "steps: runnable ideas must come from runnable_next_tests, while "
                        "draft-only or future ideas must be clearly labeled that way. Do not "
                        "invent causes, trades, prices, support, missing metrics, unsupported "
                        "strategy mechanics, predictions, or investment advice. Cover what "
                        "was tested, what happened, benchmark comparison, risk or drawdown, "
                        "assumptions, caveats, and one useful next test."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "fact_bank": fact_bank,
                            "required_fact_ids": sorted(required_fact_ids),
                        },
                        default=str,
                    ),
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
    draft = _coerce_result_breakdown_draft(response)
    if draft is None:
        return None
    return _render_result_breakdown_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
    )


def result_breakdown_fact_bank(context: dict[str, Any]) -> dict[str, str]:
    fact_bank: dict[str, str] = {}
    title = str(context.get("title") or "").strip()
    if title:
        fact_bank["title"] = title

    symbols = context.get("symbols")
    symbols_text = (
        ", ".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        if isinstance(symbols, list)
        else ""
    )
    if symbols_text:
        fact_bank["symbols"] = symbols_text

    date_range = _format_result_breakdown_date_range(context.get("date_range"))
    if date_range:
        fact_bank["date_range"] = date_range

    benchmark = str(context.get("benchmark_symbol") or "").strip()
    if benchmark:
        fact_bank["benchmark_symbol"] = benchmark

    total_return = _result_breakdown_metric(
        context,
        "total_return_pct",
        row_keys=("total_return_pct", "total_return"),
    )
    if total_return is not None:
        fact_bank["total_return"] = _format_result_breakdown_percent(total_return)

    benchmark_return = _result_breakdown_metric(
        context,
        "benchmark_return_pct",
        row_keys=("benchmark_return_pct", "benchmark_return"),
    )
    if benchmark_return is not None:
        fact_bank["benchmark_return"] = _format_result_breakdown_percent(benchmark_return)

    delta_vs_benchmark = _result_breakdown_metric(
        context,
        "delta_vs_benchmark_pct",
        row_keys=("delta_vs_benchmark_pct", "benchmark_delta"),
    )
    if delta_vs_benchmark is not None:
        fact_bank["benchmark_delta"] = _format_result_breakdown_percent(
            delta_vs_benchmark
        )

    max_drawdown = _result_breakdown_metric(
        context,
        "max_drawdown_pct",
        row_keys=("max_drawdown_pct", "max_drawdown"),
    )
    if max_drawdown is not None:
        fact_bank["max_drawdown"] = _format_result_breakdown_percent(max_drawdown)

    starting_capital = _result_breakdown_starting_capital(context)
    if starting_capital:
        fact_bank["starting_capital"] = starting_capital

    assumptions = context.get("assumptions")
    assumption_text = (
        " ".join(str(item).strip() for item in assumptions if str(item).strip())
        if isinstance(assumptions, list)
        else ""
    )
    if assumption_text:
        fact_bank["assumptions"] = assumption_text

    fact_bank["caveat"] = (
        "This is historical simulation evidence, not a prediction or trading "
        "recommendation."
    )
    fact_bank["runnable_next_tests"] = (
        "Runnable now: change the date range, change the benchmark, or test the "
        "same supported strategy on a different single asset."
    )
    fact_bank["draft_only_or_future_tests"] = (
        "Draft-only or future support: DCA with separate starting principal, "
        "investment ceilings, and unsupported custom rules."
    )
    return fact_bank


def _coerce_result_breakdown_draft(value: Any) -> ResultBreakdownDraft | None:
    if isinstance(value, ResultBreakdownDraft):
        return value
    try:
        return ResultBreakdownDraft.model_validate(value)
    except (TypeError, ValidationError):
        return None


def _render_result_breakdown_draft(
    *,
    draft: ResultBreakdownDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> str | None:
    if not draft.sections or len(draft.sections) > 6:
        return None

    used_fact_ids: set[str] = set()
    rendered_sections: list[str] = []
    for section in draft.sections:
        heading = _clean_result_breakdown_heading(section.heading)
        if not heading or not section.parts:
            return None
        body, section_fact_ids = _render_result_breakdown_parts(
            section.parts,
            fact_bank=fact_bank,
        )
        if not body:
            return None
        used_fact_ids.update(section_fact_ids)
        rendered_sections.append(f"### {heading}\n{body}")

    if not required_fact_ids.issubset(used_fact_ids):
        return None

    rendered_text = "\n\n".join(rendered_sections).strip()
    if len(rendered_text.split()) > 520:
        return None
    return rendered_text


def _render_result_breakdown_parts(
    parts: list[ResultBreakdownPart],
    *,
    fact_bank: dict[str, str],
) -> tuple[str | None, set[str]]:
    body = ""
    fact_ids: list[str] = []
    used_fact_ids: set[str] = set()
    for part in parts:
        if part.kind == "text":
            body = _append_result_breakdown_piece(body, part.text)
            continue
        fact_id = str(part.fact_id or "").strip()
        if fact_id not in fact_bank:
            return None, used_fact_ids
        if fact_id not in used_fact_ids:
            fact_ids.append(fact_id)
            used_fact_ids.add(fact_id)
    body = _normalize_result_breakdown_body(body)
    fact_block = _render_result_breakdown_fact_block(fact_ids, fact_bank=fact_bank)
    if _result_breakdown_body_is_fragmentary(body, fact_ids):
        body = ""
    if body and fact_block:
        return f"{body}\n\n{fact_block}", used_fact_ids
    return (body or fact_block or None), used_fact_ids


def _render_result_breakdown_fact_block(
    fact_ids: list[str],
    *,
    fact_bank: dict[str, str],
) -> str:
    if not fact_ids:
        return ""
    remaining = list(fact_ids)
    lines: list[str] = []

    def _has(*ids: str) -> bool:
        return any(fact_id in remaining for fact_id in ids)

    def _consume(*ids: str) -> None:
        for fact_id in ids:
            if fact_id in remaining:
                remaining.remove(fact_id)

    if _has("title", "symbols", "date_range"):
        title = _sentence_fragment(fact_bank.get("title") or "Stored backtest")
        symbols = _sentence_fragment(fact_bank.get("symbols") or "")
        date_range = _sentence_fragment(fact_bank.get("date_range") or "")
        test_text = title
        if symbols and symbols.lower() not in title.lower():
            test_text = f"{test_text} on {symbols}"
        if date_range:
            test_text = f"{test_text}, {date_range}"
        lines.append(f"**Test:** {test_text}.")
        _consume("title", "symbols", "date_range")

    if _has(
        "total_return",
        "benchmark_symbol",
        "benchmark_return",
        "benchmark_delta",
    ):
        performance_parts: list[str] = []
        if "total_return" in remaining:
            performance_parts.append(f"total return {fact_bank['total_return']}")
        benchmark = _sentence_fragment(fact_bank.get("benchmark_symbol") or "")
        if "benchmark_return" in remaining and benchmark:
            performance_parts.append(
                f"{benchmark} benchmark return {fact_bank['benchmark_return']}"
            )
        elif "benchmark_symbol" in remaining and benchmark:
            performance_parts.append(f"benchmark {benchmark}")
        if "benchmark_delta" in remaining:
            performance_parts.append(
                f"relative performance {fact_bank['benchmark_delta']}"
            )
        if performance_parts:
            lines.append(f"**Performance:** {'; '.join(performance_parts)}.")
        _consume(
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
        )

    if _has("max_drawdown"):
        lines.append(f"**Risk marker:** max drawdown {fact_bank['max_drawdown']}.")
        _consume("max_drawdown")

    if _has("starting_capital"):
        lines.append(f"**Starting capital:** {fact_bank['starting_capital']}.")
        _consume("starting_capital")

    if _has("assumptions"):
        lines.append(f"**Assumptions:** {fact_bank['assumptions']}")
        _consume("assumptions")

    if _has("caveat"):
        lines.append(f"**Caveat:** {fact_bank['caveat']}")
        _consume("caveat")

    if _has("runnable_next_tests"):
        lines.append(fact_bank["runnable_next_tests"])
        _consume("runnable_next_tests")

    if _has("draft_only_or_future_tests"):
        lines.append(fact_bank["draft_only_or_future_tests"])
        _consume("draft_only_or_future_tests")

    for fact_id in remaining:
        value = fact_bank.get(fact_id)
        if value:
            lines.append(_ensure_sentence(value))

    return "\n\n".join(_ensure_sentence(line) for line in lines if line.strip())


def _append_result_breakdown_piece(current: str, piece: str) -> str:
    cleaned = " ".join(str(piece or "").split())
    if not cleaned:
        return current
    if not current:
        return cleaned
    if cleaned[:1] in {".", ",", ";", ":", "!", "?", ")", "%"}:
        return current.rstrip() + cleaned
    if current[-1:] in {"(", "$", "/", "-"}:
        return current.rstrip() + cleaned
    return current.rstrip() + " " + cleaned


def _normalize_result_breakdown_body(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _result_breakdown_body_is_fragmentary(body: str, fact_ids: list[str]) -> bool:
    if not body or not fact_ids:
        return False
    word_count = len([word for word in body.split(" ") if word.strip()])
    return word_count < 12


def _sentence_fragment(value: str) -> str:
    return str(value or "").strip().rstrip(".")


def _ensure_sentence(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1:] in {".", "!", "?"}:
        return cleaned
    return f"{cleaned}."


def _required_result_breakdown_fact_ids(fact_bank: dict[str, str]) -> set[str]:
    required: set[str] = {"caveat"}
    for fact_id in (
        "title",
        "symbols",
        "date_range",
        "total_return",
        "benchmark_symbol",
        "max_drawdown",
        "assumptions",
    ):
        if fact_id in fact_bank:
            required.add(fact_id)
    if "benchmark_return" in fact_bank:
        required.add("benchmark_return")
    if "benchmark_delta" in fact_bank:
        required.add("benchmark_delta")
    return required


def _clean_result_breakdown_heading(value: str) -> str:
    return str(value or "").strip().lstrip("#").strip()


def _result_breakdown_starting_capital(context: dict[str, Any]) -> str:
    config_snapshot = context.get("config_snapshot")
    if isinstance(config_snapshot, dict):
        raw_value = config_snapshot.get("initial_capital") or config_snapshot.get(
            "starting_capital"
        )
        if isinstance(raw_value, (int, float)) and raw_value > 0:
            return f"${raw_value:,.0f}"
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()

    assumptions = context.get("assumptions")
    if isinstance(assumptions, list):
        for assumption in assumptions:
            text = str(assumption).strip()
            if text.lower().startswith("starting capital"):
                return text.split(":", 1)[-1].strip().rstrip(".")
    return ""


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
    delta_vs_benchmark = _result_breakdown_metric(
        context,
        "delta_vs_benchmark_pct",
        row_keys=("delta_vs_benchmark_pct", "benchmark_delta"),
    )
    assumptions = context.get("assumptions")
    assumption_lines = (
        [str(item).strip() for item in assumptions[:5] if str(item).strip()]
        if isinstance(assumptions, list)
        else []
    ) or ["The stored run settings were used."]
    benchmark = str(context.get("benchmark_symbol") or "").strip()
    symbols = context.get("symbols")
    symbols_text = (
        ", ".join(str(symbol).strip() for symbol in symbols if str(symbol).strip())
        if isinstance(symbols, list)
        else ""
    ) or "The available result"
    title = str(context.get("title") or "").strip() or f"{symbols_text} backtest"
    date_range = _format_result_breakdown_date_range(context.get("date_range"))
    total_return_text = (
        _format_result_breakdown_percent(total_return)
        if total_return is not None
        else "the available return"
    )
    benchmark_text = (
        _format_result_breakdown_percent(benchmark_return)
        if benchmark and benchmark_return is not None
        else "the available benchmark return"
    )
    delta_text = (
        _format_result_breakdown_percent(delta_vs_benchmark)
        if delta_vs_benchmark is not None
        else "the stored benchmark spread"
    )
    drawdown_text = (
        _format_result_breakdown_percent(max_drawdown)
        if max_drawdown is not None
        else "the available risk data"
    )
    assumption_bullets = "\n".join(f"- {line}" for line in assumption_lines)
    period_sentence = f" over {date_range}" if date_range else ""
    return (
        f"### What Was Tested\n"
        f"{title} tested {symbols_text}{period_sentence} using the stored "
        f"backtest configuration.\n\n"
        f"### What Happened\n"
        f"**Total return:** {total_return_text}. This is the headline portfolio "
        f"change for the selected period, before treating it as a future expectation.\n\n"
        f"### Benchmark Context\n"
        f"The benchmark was {benchmark or 'the stored benchmark'} at {benchmark_text}. "
        f"The strategy finished {delta_text} versus that benchmark, so the card is "
        f"showing relative performance as well as absolute return.\n\n"
        f"### Risk Read\n"
        f"**Max drawdown:** {drawdown_text}. This marks the largest peak-to-trough "
        f"decline during the simulation and is the first risk number to compare "
        f"against the return profile.\n\n"
        f"### Assumptions\n"
        f"{assumption_bullets}\n\n"
        f"### What To Try Next\n"
        f"Use this as historical simulation evidence, not a prediction or trading "
        f"recommendation. A runnable next check is changing the date range or "
        f"benchmark to see whether the conclusion depends on this exact window."
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


def _format_result_breakdown_date_range(value: Any) -> str:
    if isinstance(value, dict):
        display = value.get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
        start = value.get("start")
        end = value.get("end")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, str):
        return value.strip()
    return ""


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
