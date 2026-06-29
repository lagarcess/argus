"""Interpreter-unavailable / offline recovery result helpers.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

import os
from typing import Any

from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
    retry_last_turn_stage_patch,
)
from argus.agent_runtime.stages.artifact_context import (
    draft_assumptions_response as _draft_assumptions_response,
)
from argus.agent_runtime.stages.interpret_internal.shared import _field_base
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
)
from argus.agent_runtime.state.models import (
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_contract import display_strategy_type

_LATEST_RESULT_SAVE_REQUESTED_REASON = "latest_result_save_requested"


def _offline_interpreter_unavailable_result(
    *,
    user: UserState,
    snapshot: TaskSnapshot | None = None,
    current_user_message: str = "",
    selected_thread_metadata: dict[str, Any] | None = None,
) -> StageResult:
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    decision = InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Structured interpretation was unavailable for this turn.",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        optional_parameter_opportunity=[],
        confidence=0.0,
        arbitration_mode="deterministic",
        reason_codes=["llm_interpreter_unavailable"],
        effective_response_profile=effective_profile,
        semantic_turn_act=None,
    )
    stage_patch: dict[str, Any] = {
        "assistant_response": _offline_recovery_message(
            snapshot,
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
            language=user.language_preference,
        ),
    }
    stage_patch.update(
        recovery_state_stage_patch(
            "interpreter_unavailable",
            language=user.language_preference,
            retryable=True,
        )
    )
    retry_last_turn = retry_last_turn_stage_patch(current_user_message)
    if retry_last_turn is not None:
        stage_patch.update(retry_last_turn)
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )


def _strategies_enabled() -> bool:
    raw = os.getenv("ARGUS_STRATEGIES_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _latest_result_save_requested(decision: InterpretDecision) -> bool:
    return _LATEST_RESULT_SAVE_REQUESTED_REASON in decision.reason_codes


def _offline_recovery_message(
    snapshot: TaskSnapshot | None,
    *,
    current_user_message: str = "",
    selected_thread_metadata: dict[str, Any] | None = None,
    language: str = "en",
) -> str:
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        strategy = snapshot.pending_strategy_summary
        setup_phrase = _current_setup_phrase(strategy)
        if _pending_assumption_edit_was_not_applied(
            current_user_message=current_user_message,
            selected_thread_metadata=selected_thread_metadata or {},
        ):
            return recovery_message("assumption_edit_unapplied", language=language)
        if snapshot.active_confirmation_reference is None:
            return recovery_message(
                "setup_change_unapplied",
                language=language,
                setup_phrase=setup_phrase,
            )
        assumptions_response = _draft_assumptions_response(snapshot)
        action_guidance = recovery_message(
            "confirmation_action_guidance",
            language=language,
        )
        if assumptions_response is not None:
            return f"{assumptions_response} {action_guidance}"
        return recovery_message(
            "confirmation_change_unapplied",
            language=language,
            setup_phrase=setup_phrase,
            action_guidance=action_guidance,
        )
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return recovery_message(
            "latest_result_followup_unavailable",
            language=language,
        )
    return recovery_message("interpreter_unavailable", language=language)


def _current_setup_phrase(strategy: StrategySummary) -> str:
    assets = [symbol for symbol in strategy.asset_universe if symbol]
    asset_label = ", ".join(assets)
    strategy_label = display_strategy_type(strategy).strip().lower()
    if asset_label and strategy_label:
        return f"{asset_label} {strategy_label} setup"
    if asset_label:
        return f"{asset_label} setup"
    if strategy_label:
        return f"current {strategy_label} setup"
    return "current setup"


def _pending_assumption_edit_was_not_applied(
    *,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(str(selected_thread_metadata.get("requested_field") or ""))
    return requested_field == "assumption" and bool(current_user_message.strip())
