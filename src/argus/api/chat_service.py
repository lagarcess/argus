from __future__ import annotations

from datetime import date
from typing import Any

from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.api.chat import actions as _actions
from argus.api.chat import breakdown as _breakdown
from argus.api.chat import confirmation as _confirmation
from argus.api.chat import onboarding as _onboarding
from argus.api.chat import persistence as _persistence
from argus.api.chat import recovery as _recovery
from argus.api.chat import strategies as _strategies
from argus.api.chat import streaming as _streaming
from argus.api.chat.actions import (
    CONFIRMATION_ACTION_TYPES,
    STALE_CONFIRMATION_ACTION_MESSAGE,
)
from argus.api.chat.breakdown import (
    ResultBreakdownDraft,
    ResultBreakdownPart,
    ResultBreakdownSection,
)
from argus.api.chat.onboarding import SUPPORTED_ONBOARDING_GOALS
from argus.api.chat.recovery import (
    LOST_CONFIRMATION_STATE_MESSAGE,
    RuntimeFallbackContext,
)
from argus.api.schemas import BacktestRun, ChatStreamRequest, Conversation, Strategy, User
from argus.domain.engine import classify_symbol, default_benchmark
from argus.llm.openrouter import build_openrouter_model, log_openrouter_failure

__all__ = [
    "Any",
    "BacktestRun",
    "CONFIRMATION_ACTION_TYPES",
    "ChatStreamRequest",
    "Conversation",
    "LOST_CONFIRMATION_STATE_MESSAGE",
    "ResultBreakdownDraft",
    "ResultBreakdownPart",
    "ResultBreakdownSection",
    "RuntimeFallbackContext",
    "STALE_CONFIRMATION_ACTION_MESSAGE",
    "SUPPORTED_ONBOARDING_GOALS",
    "Strategy",
    "User",
    "assistant_copy_for_result",
    "build_openrouter_model",
    "build_runtime_backtest_run",
    "chat_action_conversation_id",
    "chat_action_run_id",
    "chat_display_message",
    "chat_request_message",
    "classify_symbol",
    "checkpoint_has_latest_result",
    "checkpoint_has_pending_confirmation",
    "checkpoint_has_pending_strategy",
    "confirmation_metadata_fallback_context",
    "count_completed_runs_for_user",
    "date",
    "default_benchmark",
    "enrich_result_card_actions",
    "fallback_result_breakdown_message",
    "fetch_run_metrics",
    "is_confirmation_action",
    "latest_active_confirmation_id",
    "latest_completed_run_for_conversation",
    "latest_result_fallback_context",
    "llm_result_breakdown_message",
    "log_openrouter_failure",
    "parse_onboarding_control_message",
    "pending_confirmation_exists",
    "pending_strategy_metadata_fallback_context",
    "persist_onboarding_update",
    "persist_runtime_backtest_run",
    "resolve_date_range",
    "resolved_run_symbols",
    "result_breakdown_context",
    "result_breakdown_fact_bank",
    "result_breakdown_message",
    "run_for_result_action",
    "runtime_checkpoint_values",
    "runtime_confirmation_card",
    "runtime_result_card",
    "runtime_result_envelope",
    "runtime_result_message",
    "runtime_stage_status",
    "save_strategy_from_run",
    "sse_data",
    "sse_done",
    "stale_confirmation_action_message",
    "strategy_template_from_run",
]


def parse_onboarding_control_message(message: str) -> str | None:
    return _onboarding.parse_onboarding_control_message(message)


def sse_data(payload: dict[str, Any]) -> str:
    return _streaming.sse_data(payload)


def sse_done() -> str:
    return _streaming.sse_done()


def fetch_run_metrics(user_id: str, run_id: str) -> dict[str, Any] | None:
    return _streaming.fetch_run_metrics(user_id, run_id)


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    return _streaming.assistant_copy_for_result(symbols, language)


def runtime_result_message(runtime_result: dict[str, Any]) -> str | None:
    return _streaming.runtime_result_message(runtime_result)


def runtime_stage_status(runtime_result: dict[str, Any]) -> str:
    return _streaming.runtime_stage_status(runtime_result)


def runtime_result_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    return _streaming.runtime_result_card(runtime_result)


def runtime_confirmation_card(
    runtime_result: dict[str, Any],
    *,
    confirmation_id: str | None = None,
) -> dict[str, Any] | None:
    return _confirmation.runtime_confirmation_card(
        runtime_result,
        confirmation_id=confirmation_id,
        format_confirmation_period_func=_format_confirmation_period,
    )


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
) -> list[str]:
    return _confirmation._confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    return _confirmation._optional_parameter_value(optional_parameters, key)


def _format_confirmation_value(value: Any) -> str:
    return _confirmation._format_confirmation_value(value)


def _format_confirmation_period(value: Any) -> str:
    return resolve_date_range(value, today=_confirmation_today()).display


def _confirmation_period_without_parentheses(value: str) -> str:
    return _confirmation._confirmation_period_without_parentheses(value)


def _strategy_type_uses_cadence(strategy_type: str) -> bool:
    return _confirmation._strategy_type_uses_cadence(strategy_type)


def _article_for(value: str) -> str:
    return _confirmation._article_for(value)


def _confirmation_today() -> date:
    return _confirmation._confirmation_today()


def runtime_result_envelope(runtime_result: dict[str, Any]) -> dict[str, Any]:
    return _streaming.runtime_result_envelope(runtime_result)


def resolved_run_symbols(resolved_strategy: dict[str, Any]) -> list[str]:
    return _persistence.resolved_run_symbols(resolved_strategy)


def enrich_result_card_actions(
    *,
    result_card: dict[str, Any],
    run_id: str,
    strategy_id: str | None,
    conversation_id: str,
) -> dict[str, Any]:
    return _persistence.enrich_result_card_actions(
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
) -> BacktestRun | None:
    return _persistence.build_runtime_backtest_run(
        user_id=user_id,
        conversation_id=conversation_id,
        result_card=result_card,
        envelope=envelope,
        classify_symbol_func=classify_symbol,
        default_benchmark_func=default_benchmark,
    )


def persist_runtime_backtest_run(
    *,
    user: User,
    conversation: Conversation,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
) -> BacktestRun | None:
    return _persistence.persist_runtime_backtest_run(
        user=user,
        conversation=conversation,
        result_card=result_card,
        envelope=envelope,
        classify_symbol_func=classify_symbol,
        default_benchmark_func=default_benchmark,
    )


def count_completed_runs_for_user(user_id: str) -> int:
    return _persistence.count_completed_runs_for_user(user_id)


def persist_onboarding_update(user: User, patch: dict[str, Any]) -> User:
    return _onboarding.persist_onboarding_update(user, patch)


def chat_request_message(payload: ChatStreamRequest) -> str:
    return _actions.chat_request_message(payload)


def chat_display_message(payload: ChatStreamRequest) -> str:
    return _actions.chat_display_message(payload)


def chat_action_run_id(payload: ChatStreamRequest) -> str | None:
    return _actions.chat_action_run_id(payload)


def chat_action_conversation_id(payload: ChatStreamRequest) -> str | None:
    return _actions.chat_action_conversation_id(payload)


def is_confirmation_action(payload: ChatStreamRequest) -> bool:
    return _actions.is_confirmation_action(payload)


def pending_confirmation_exists(*, user_id: str, conversation_id: str) -> bool:
    return _actions.pending_confirmation_exists(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def stale_confirmation_action_message(
    *,
    payload: ChatStreamRequest,
    user_id: str,
    conversation_id: str,
) -> str | None:
    return _actions.stale_confirmation_action_message(
        payload=payload,
        user_id=user_id,
        conversation_id=conversation_id,
    )


def latest_active_confirmation_id(
    *,
    user_id: str,
    conversation_id: str,
) -> str | None:
    return _actions.latest_active_confirmation_id(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _confirmation_id_from_action_payload(payload: dict[str, Any]) -> str | None:
    return _actions._confirmation_id_from_action_payload(payload)


def _confirmation_id_from_card(card: dict[str, Any]) -> str | None:
    return _actions._confirmation_id_from_card(card)


def _recent_messages_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
    limit: int,
):
    return _recovery._recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
    )


async def runtime_checkpoint_values(
    *,
    workflow: Any,
    conversation_id: str,
) -> dict[str, Any]:
    return await _recovery.runtime_checkpoint_values(
        workflow=workflow,
        conversation_id=conversation_id,
    )


def checkpoint_has_pending_confirmation(values: dict[str, Any]) -> bool:
    return _recovery.checkpoint_has_pending_confirmation(values)


def checkpoint_has_latest_result(values: dict[str, Any]) -> bool:
    return _recovery.checkpoint_has_latest_result(values)


def checkpoint_has_pending_strategy(values: dict[str, Any]) -> bool:
    return _recovery.checkpoint_has_pending_strategy(values)


def confirmation_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    return _recovery.confirmation_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _metadata_invalidates_confirmation(metadata: dict[str, Any]) -> bool:
    return _recovery._metadata_invalidates_confirmation(metadata)


def pending_strategy_metadata_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    return _recovery.pending_strategy_metadata_fallback_context(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _metadata_invalidates_pending_strategy(metadata: dict[str, Any]) -> bool:
    return _recovery._metadata_invalidates_pending_strategy(metadata)


def latest_result_fallback_context(
    *,
    user_id: str,
    conversation_id: str,
) -> RuntimeFallbackContext | None:
    return _recovery.latest_result_fallback_context(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _task_snapshot_from_value(value: Any):
    return _recovery._task_snapshot_from_value(value)


def _run_by_id_for_user(*, user_id: str, run_id: str) -> BacktestRun | None:
    return _recovery._run_by_id_for_user(user_id=user_id, run_id=run_id)


def latest_completed_run_for_conversation(
    *,
    user_id: str,
    conversation_id: str,
) -> BacktestRun | None:
    return _recovery.latest_completed_run_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
    )


def run_for_result_action(
    *,
    payload: ChatStreamRequest,
    user: User,
    conversation_id: str,
    require_run_id: bool = False,
) -> BacktestRun | None:
    return _actions.run_for_result_action(
        payload=payload,
        user=user,
        conversation_id=conversation_id,
        require_run_id=require_run_id,
    )


def strategy_template_from_run(run: BacktestRun) -> str:
    return _strategies.strategy_template_from_run(run)


def save_strategy_from_run(*, user: User, run: BacktestRun) -> Strategy:
    return _strategies.save_strategy_from_run(user=user, run=run)


def result_breakdown_context(run: BacktestRun) -> dict[str, Any]:
    return _breakdown.result_breakdown_context(run)


def llm_result_breakdown_message(context: dict[str, Any]) -> str | None:
    return _breakdown.llm_result_breakdown_message(
        context,
        build_openrouter_model_func=build_openrouter_model,
        log_openrouter_failure_func=log_openrouter_failure,
    )


def result_breakdown_fact_bank(context: dict[str, Any]) -> dict[str, str]:
    return _breakdown.result_breakdown_fact_bank(context)


def _coerce_result_breakdown_draft(value: Any) -> ResultBreakdownDraft | None:
    return _breakdown._coerce_result_breakdown_draft(value)


def _render_result_breakdown_draft(
    *,
    draft: ResultBreakdownDraft,
    fact_bank: dict[str, str],
    required_fact_ids: set[str],
) -> str | None:
    return _breakdown._render_result_breakdown_draft(
        draft=draft,
        fact_bank=fact_bank,
        required_fact_ids=required_fact_ids,
    )


def _render_result_breakdown_parts(
    parts: list[ResultBreakdownPart],
    *,
    fact_bank: dict[str, str],
):
    return _breakdown._render_result_breakdown_parts(parts, fact_bank=fact_bank)


def _render_result_breakdown_fact_block(
    fact_ids: list[str],
    *,
    fact_bank: dict[str, str],
) -> str:
    return _breakdown._render_result_breakdown_fact_block(
        fact_ids,
        fact_bank=fact_bank,
    )


def _append_result_breakdown_piece(current: str, piece: str) -> str:
    return _breakdown._append_result_breakdown_piece(current, piece)


def _normalize_result_breakdown_body(value: str) -> str:
    return _breakdown._normalize_result_breakdown_body(value)


def _result_breakdown_body_is_fragmentary(body: str, fact_ids: list[str]) -> bool:
    return _breakdown._result_breakdown_body_is_fragmentary(body, fact_ids)


def _sentence_fragment(value: str) -> str:
    return _breakdown._sentence_fragment(value)


def _ensure_sentence(value: str) -> str:
    return _breakdown._ensure_sentence(value)


def _required_result_breakdown_fact_ids(fact_bank: dict[str, str]) -> set[str]:
    return _breakdown._required_result_breakdown_fact_ids(fact_bank)


def _clean_result_breakdown_heading(value: str) -> str:
    return _breakdown._clean_result_breakdown_heading(value)


def _result_breakdown_starting_capital(context: dict[str, Any]) -> str:
    return _breakdown._result_breakdown_starting_capital(context)


def fallback_result_breakdown_message(context: dict[str, Any]) -> str:
    return _breakdown.fallback_result_breakdown_message(context)


def _result_breakdown_metric(
    context: dict[str, Any],
    metric_key: str,
    *,
    row_keys: tuple[str, ...],
) -> float | None:
    return _breakdown._result_breakdown_metric(
        context,
        metric_key,
        row_keys=row_keys,
    )


def _nested_result_breakdown_number(payload: Any, path: tuple[str, ...]) -> float | None:
    return _breakdown._nested_result_breakdown_number(payload, path)


def _coerce_result_breakdown_number(value: Any) -> float | None:
    return _breakdown._coerce_result_breakdown_number(value)


def _format_result_breakdown_percent(value: float) -> str:
    return _breakdown._format_result_breakdown_percent(value)


def _format_result_breakdown_date_range(value: Any) -> str:
    return _breakdown._format_result_breakdown_date_range(value)


def result_breakdown_message(run: BacktestRun | None) -> str:
    if run is None:
        return _breakdown.result_breakdown_message(run)
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
