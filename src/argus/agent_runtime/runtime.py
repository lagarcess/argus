from __future__ import annotations

import re
from typing import Any

from argus.agent_runtime.graph.workflow import WorkflowState
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategyFrame,
    TaskSnapshot,
    UserState,
)

SEEDED_THREAD_METADATA_KEYS = (
    "latest_task_type",
    "last_stage_outcome",
)
MAX_SEEDED_ARTIFACT_REFERENCES = 3
MAX_RECENT_THREAD_HISTORY = 6


def run_agent_turn(
    *,
    workflow: Any,
    session_manager: InMemorySessionManager,
    user: UserState,
    thread_id: str,
    message: str,
) -> dict[str, Any]:
    initial_state = build_workflow_input(
        session_manager=session_manager,
        user=user,
        thread_id=thread_id,
        message=message,
    )
    result = _apply_response_quality_gate(
        result=workflow.invoke(initial_state),
        message=message,
    )
    run_state = result["run_state"]
    persisted_artifact_references = _resolve_persisted_artifact_references(
        result=result,
        initial_state=initial_state,
    )
    assistant_message = _assistant_message(result)

    session_manager.append_message(
        user_id=user.user_id,
        thread_id=thread_id,
        role="user",
        content=message,
    )
    if assistant_message is not None:
        session_manager.append_message(
            user_id=user.user_id,
            thread_id=thread_id,
            role="assistant",
            content=assistant_message,
        )
    session_manager.save_thread_context(
        user_id=user.user_id,
        thread_id=thread_id,
        latest_task_snapshot=_build_task_snapshot(
            run_state=run_state,
            stage_outcome=result["stage_outcome"],
            prior_task_snapshot=initial_state.get("latest_task_snapshot"),
            artifact_references=persisted_artifact_references,
        ),
        artifact_references=persisted_artifact_references,
        thread_metadata=_build_thread_metadata(
            run_state=run_state,
            stage_outcome=result["stage_outcome"],
        ),
    )

    return _public_result(result)


def build_workflow_input(
    *,
    session_manager: InMemorySessionManager,
    user: UserState,
    thread_id: str,
    message: str,
) -> WorkflowState:
    thread = session_manager.load_thread(user_id=user.user_id, thread_id=thread_id)
    normalized_message = _normalize_message_for_runtime_slice(message)
    return {
        "run_state": RunState.new(
            current_user_message=normalized_message,
            recent_thread_history=_bounded_recent_thread_history(thread.message_history),
        ),
        "user": user,
        "latest_task_snapshot": thread.latest_task_snapshot,
        "selected_thread_metadata": _select_thread_metadata(thread.thread_metadata),
        "artifact_references": _select_artifact_references(thread.artifact_references),
    }


def _assistant_message(result: dict[str, Any]) -> str | None:
    assistant_response = result.get("assistant_response")
    assistant_prompt = result.get("assistant_prompt")
    if isinstance(assistant_response, str) and assistant_response:
        if isinstance(assistant_prompt, str) and assistant_prompt:
            return f"{assistant_response}\n\n{assistant_prompt}"
        return assistant_response
    if isinstance(assistant_prompt, str) and assistant_prompt:
        return assistant_prompt
    return None


def _apply_response_quality_gate(
    *,
    result: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    checked = dict(result)
    for key in ("assistant_response", "assistant_prompt"):
        value = checked.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        replacement = _replacement_for_low_quality_text(
            text=value,
            message=message,
        )
        if replacement is not None:
            checked[key] = replacement
    return checked


def _replacement_for_low_quality_text(*, text: str, message: str) -> str | None:
    if _contains_backend_scaffolding(text):
        return _scaffolding_recovery_prompt(text=text, message=message)
    if _assistant_text_is_too_thin(text):
        return _educational_recovery_response(message)
    return None


def _contains_backend_scaffolding(text: str) -> bool:
    lowered = text.lower()
    scaffolding_markers = (
        "not specified",
        "asset universe",
        "capital amount",
        "requested_field",
        "missing_required_fields",
    )
    return any(marker in lowered for marker in scaffolding_markers)


def _assistant_text_is_too_thin(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    words = stripped.split()
    if len(words) <= 3:
        return True
    return bool(
        len(words) <= 5
        and re.fullmatch(r"[A-Z0-9.,\s-]+", stripped)
        and any(char.isalpha() for char in stripped)
    )


def _scaffolding_recovery_prompt(*, text: str, message: str) -> str:
    combined = f"{text} {message}".lower()
    questions: list[str] = []
    if "asset universe" in combined or "asset" in combined:
        questions.append("Which asset should I use?")
    if "capital amount" in combined or "fixed amount" in combined:
        questions.append("How much should each purchase be?")
    if "date_range" in combined or "time period" in combined:
        questions.append("What time period should I test?")
    if questions:
        return "I understand the direction. " + " ".join(questions)
    return (
        "I understand the direction, but I need one more detail before I can "
        "turn it into a backtest."
    )


def _educational_recovery_response(message: str) -> str | None:
    lowered = message.lower().strip()
    if re.search(
        r"\bwhat(?:'s| is)\s+(?:a\s+)?backtest\b|\bexplain backtests?\b", lowered
    ):
        return (
            "A backtest is a historical replay of an investing idea. Argus takes "
            "the rule you describe, applies it to past market data, and shows how "
            "that simulated strategy performed against a benchmark. It is useful "
            "for learning from history, but it is not a prediction."
        )
    if re.search(r"\bwhat(?:'s| is)\s+dca\b|\bexplain dca\b", lowered):
        return (
            "DCA means buying a fixed amount on a regular schedule, like $500 every month. "
            "The point is to avoid trying to pick the perfect day. In Argus, I can test how that "
            "recurring-buy plan would have performed historically for a supported asset."
        )
    if re.search(
        r"\bi do(?:n't| not) understand\b|\bexplain.*different(?:ly)?\b",
        lowered,
    ):
        return (
            "No problem. The simple version: Argus turns an investing idea into a historical test. "
            "If we were talking about RSI, think of it like a temperature gauge for recent price movement: "
            "low can mean the asset has been weak recently, high can mean it has been strong recently. "
            "It is useful only as a rule to test, not as a prediction."
        )
    return None


def _build_task_snapshot(
    *,
    run_state: RunState,
    stage_outcome: Any,
    prior_task_snapshot: TaskSnapshot | None,
    artifact_references: list[ArtifactReference],
) -> TaskSnapshot:
    stage_outcome_value = getattr(stage_outcome, "value", stage_outcome)
    completed_outcomes = {"execution_succeeded", "ready_to_respond", "end_run"}
    latest_backtest_reference = _latest_artifact_reference(
        artifact_references=artifact_references,
        artifact_kind="backtest_result",
    )
    latest_collection_reference = _latest_artifact_reference(
        artifact_references=artifact_references,
        artifact_kind="collection_action",
    )
    pending_strategy_summary = (
        run_state.candidate_strategy_draft
        if stage_outcome_value in {"await_user_reply", "await_approval"}
        else (
            prior_task_snapshot.pending_strategy_summary
            if prior_task_snapshot is not None
            and stage_outcome_value not in completed_outcomes
            else None
        )
    )
    pending_needs = _pending_needs_from_run_state(
        run_state=run_state,
        stage_outcome_value=stage_outcome_value,
        pending_strategy_summary=pending_strategy_summary,
    )
    field_provenance = _field_provenance_from_strategy(pending_strategy_summary)
    strategy_frame = (
        StrategyFrame(
            strategy=pending_strategy_summary,
            pending_needs=pending_needs,
            field_provenance=field_provenance,
            last_assistant_question=run_state.user_goal_summary,
        )
        if pending_strategy_summary is not None
        else None
    )
    return TaskSnapshot(
        latest_task_type=run_state.intent,
        completed=stage_outcome_value in completed_outcomes,
        pending_strategy_summary=pending_strategy_summary,
        confirmed_strategy_summary=(
            run_state.candidate_strategy_draft
            if stage_outcome_value in completed_outcomes
            else (
                prior_task_snapshot.confirmed_strategy_summary
                if prior_task_snapshot is not None
                else None
            )
        ),
        strategy_frame=strategy_frame,
        pending_needs=pending_needs,
        field_provenance=field_provenance,
        latest_backtest_result_reference=(
            latest_backtest_reference
            or (
                prior_task_snapshot.latest_backtest_result_reference
                if prior_task_snapshot is not None
                else None
            )
        ),
        latest_collection_action_reference=(
            latest_collection_reference
            or (
                prior_task_snapshot.latest_collection_action_reference
                if prior_task_snapshot is not None
                else None
            )
        ),
        last_unresolved_follow_up=(
            run_state.user_goal_summary
            if stage_outcome_value in {"await_user_reply", "await_approval"}
            else None
        ),
    )


def _pending_needs_from_run_state(
    *,
    run_state: RunState,
    stage_outcome_value: str,
    pending_strategy_summary: Any,
) -> list[str]:
    if stage_outcome_value not in {"await_user_reply", "await_approval"}:
        return []
    semantic_needs: list[str] = []
    field_map = {
        "asset_universe": "asset_target",
        "capital_amount": "sizing_amount",
        "date_range": "period",
        "entry_logic": "rule_definition",
        "exit_logic": "rule_definition",
    }
    for field_name in run_state.missing_required_fields:
        need = field_map.get(field_name)
        if need is not None and need not in semantic_needs:
            semantic_needs.append(need)
    if pending_strategy_summary is not None:
        if (
            not pending_strategy_summary.asset_universe
            and "asset_target" not in semantic_needs
        ):
            semantic_needs.append("asset_target")
        if (
            pending_strategy_summary.strategy_type == "dca_accumulation"
            and pending_strategy_summary.capital_amount is None
            and "sizing_amount" not in semantic_needs
        ):
            semantic_needs.append("sizing_amount")
        if pending_strategy_summary.date_range is None and "period" not in semantic_needs:
            semantic_needs.append("period")
    return semantic_needs


def _field_provenance_from_strategy(strategy: Any) -> dict[str, str]:
    if strategy is None:
        return {}
    provenance: dict[str, str] = {}
    for field_name in (
        "asset_universe",
        "capital_amount",
        "date_range",
        "cadence",
        "entry_logic",
        "exit_logic",
    ):
        value = getattr(strategy, field_name, None)
        if value not in (None, "", [], {}):
            provenance[field_name] = "user_or_confirmed_state"
    return provenance


def _build_thread_metadata(
    *,
    run_state: RunState,
    stage_outcome: Any,
) -> dict[str, Any]:
    stage_outcome_value = getattr(stage_outcome, "value", stage_outcome)
    return {
        "latest_task_type": run_state.intent,
        "last_stage_outcome": stage_outcome_value,
    }


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "stage_outcome",
        "assistant_prompt",
        "assistant_response",
        "requested_field",
        "optional_parameter_choices",
        "confirmation_payload",
        "next_actions",
        "failure_classification",
        "final_response_payload",
    }
    serialized = {
        key: _serialize_public_value(key, value)
        for key, value in result.items()
        if key in allowed_keys and value is not None
    }
    run_state = result.get("run_state")
    if run_state is not None:
        if (
            "confirmation_payload" not in serialized
            and getattr(run_state, "confirmation_payload", None) is not None
        ):
            serialized["confirmation_payload"] = _serialize_public_value(
                "confirmation_payload",
                run_state.confirmation_payload,
            )
        if (
            "final_response_payload" not in serialized
            and getattr(run_state, "final_response_payload", None) is not None
        ):
            serialized["final_response_payload"] = _serialize_public_value(
                "final_response_payload",
                run_state.final_response_payload,
            )
        if (
            "failure_classification" not in serialized
            and getattr(run_state, "failure_classification", None) is not None
        ):
            serialized["failure_classification"] = run_state.failure_classification
    stage_outcome = result.get("stage_outcome")
    if stage_outcome is not None:
        serialized["stage_outcome"] = getattr(stage_outcome, "value", stage_outcome)
    return serialized


def _serialize_public_value(key: str, value: Any) -> Any:
    if key in {"confirmation_payload", "final_response_payload"} and hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump(mode="python")
    return value


def _normalize_message_for_runtime_slice(message: str) -> str:
    normalized = " ".join(message.strip().split())
    normalized = _move_trailing_date_clause_ahead_of_strategy_logic(normalized)
    normalized = _normalize_entry_clause(normalized)
    normalized = _normalize_exit_clause(normalized)
    return normalized


def _normalize_single_unit_date_ranges(message: str) -> str:
    patterns = {
        r"\bover the last year\b": "over the last 1 year",
        r"\bover the last month\b": "over the last 1 month",
        r"\bover the last week\b": "over the last 1 week",
        r"\bover the last day\b": "over the last 1 day",
        r"\blast year\b": "last 1 year",
        r"\blast month\b": "last 1 month",
        r"\blast week\b": "last 1 week",
        r"\blast day\b": "last 1 day",
    }
    normalized = message
    for pattern, replacement in patterns.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _move_trailing_date_clause_ahead_of_strategy_logic(message: str) -> str:
    match = re.search(
        r"^(?P<head>.+?)\s+(?P<date>(?:over the last|last)\s+\d+\s+"
        r"(?:day|days|week|weeks|month|months|year|years))\.?$",
        message,
        flags=re.IGNORECASE,
    )
    if match is None:
        return message

    head = match.group("head").rstrip(" ,")
    date_clause = match.group("date")
    if " when " not in head.lower() and " exit " not in head.lower():
        return message

    logic_start = re.search(r"\bwhen\b", head, flags=re.IGNORECASE)
    if logic_start is None:
        return message

    prefix = head[: logic_start.start()].rstrip(" ,")
    suffix = head[logic_start.start() :].lstrip(" ,")
    return f"{prefix} {date_clause}, {suffix}"


def _normalize_entry_clause(message: str) -> str:
    if "backtest" not in message.lower():
        return message
    if "enter when" in message.lower():
        return message
    return re.sub(r"\bwhen\b", "enter when", message, count=1, flags=re.IGNORECASE)


def _normalize_exit_clause(message: str) -> str:
    if "exit when" in message.lower():
        return message
    return re.sub(
        r"\band\s+exit\b",
        ", exit when",
        message,
        count=1,
        flags=re.IGNORECASE,
    )


def _select_thread_metadata(thread_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in thread_metadata.items()
        if key in SEEDED_THREAD_METADATA_KEYS
    }


def _select_artifact_references(
    artifact_references: list[ArtifactReference],
) -> list[ArtifactReference]:
    return [
        reference.model_copy(deep=True)
        for reference in artifact_references[-MAX_SEEDED_ARTIFACT_REFERENCES:]
    ]


def _bounded_recent_thread_history(
    message_history: list[Any],
) -> list[Any]:
    return [
        message.model_copy(deep=True) if hasattr(message, "model_copy") else message
        for message in message_history[-MAX_RECENT_THREAD_HISTORY:]
    ]


def _resolve_persisted_artifact_references(
    *,
    result: dict[str, Any],
    initial_state: WorkflowState,
) -> list[ArtifactReference]:
    raw_references = result.get(
        "artifact_references", initial_state.get("artifact_references", [])
    )
    references: list[ArtifactReference] = []
    for reference in raw_references:
        references.append(ArtifactReference.model_validate(reference))
    return references


def _latest_artifact_reference(
    *,
    artifact_references: list[ArtifactReference],
    artifact_kind: str,
) -> ArtifactReference | None:
    for reference in reversed(artifact_references):
        if reference.artifact_kind == artifact_kind:
            return reference.model_copy(deep=True)
    return None
