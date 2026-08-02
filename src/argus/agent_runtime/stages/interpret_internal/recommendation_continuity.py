"""Typed result-recommendation continuity handlers for issue 345."""

from __future__ import annotations

from argus.agent_runtime.artifacts.continuity import resolve_artifact_anchor
from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.stages.interpret_internal.result_artifact_patch import (
    _stage_result_from_result_artifact_patch,
)
from argus.agent_runtime.stages.interpret_types import InterpretDecision, StageResult
from argus.agent_runtime.state.models import ResponseProfile, RunState, TaskSnapshot


def change_date_range_recommendation_result(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    language: str,
) -> StageResult:
    """Open a date-only clarification on the canonical result draft.

    The recommendation row has no new date value of its own. Anchoring the
    pending draft here keeps every owned result fact while the user's next
    natural-language turn supplies only the intended date patch.
    """

    action = state.structured_action
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if action is None or reference is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": recovery_message(
                    "result_refine_missing",
                    language=language,
                )
            },
        )
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload=action.payload,
    )
    if anchor.kind != "result" or anchor.draft is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": recovery_message(
                    "artifact_action_invalid_state",
                    language=language,
                )
            },
        )
    strategy = anchor.draft.model_copy(deep=True)
    response_intent = {
        "kind": "clarification",
        "semantic_needs": ["period"],
        "requested_fields": ["date_range"],
        "facts": {
            "strategy": strategy.model_dump(mode="python"),
            "current_user_message": state.current_user_message,
            "structured_action": action.model_dump(mode="python"),
            "latest_run_id": reference.artifact_id,
        },
        "options": [],
    }
    return StageResult(
        outcome="needs_clarification",
        stage_patch={
            "candidate_strategy_draft": strategy.model_dump(mode="python"),
            "requested_field": "date_range",
            "missing_required_fields": ["date_range"],
            "response_intent": response_intent,
        },
    )


def compare_buy_and_hold_recommendation_result(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    language: str,
) -> StageResult:
    action = state.structured_action
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if action is None or reference is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": recovery_message(
                    "result_refine_missing",
                    language=language,
                )
            },
        )
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload=action.payload,
    )
    if anchor.kind != "result" or anchor.draft is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": recovery_message(
                    "artifact_action_invalid_state",
                    language=language,
                )
            },
        )
    extra_parameters = dict(anchor.draft.extra_parameters)
    extra_parameters["artifact_patch"] = {
        "source": "structured_action",
        "changed_fields": ["strategy_type", "cadence", "sizing_mode"],
    }
    patched = anchor.draft.model_copy(
        deep=True,
        update={
            "raw_user_phrasing": None,
            "requested_strategy_template": "buy_and_hold",
            "strategy_type": "buy_and_hold",
            "strategy_thesis": None,
            "cadence": None,
            "sizing_mode": "capital_amount",
            "position_size": None,
            "entry_logic": None,
            "exit_logic": None,
            "entry_rule": None,
            "exit_rule": None,
            "rule_spec": None,
            "extra_parameters": extra_parameters,
        },
    )
    decision = InterpretDecision(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary=state.current_user_message,
        candidate_strategy_draft=patched,
        confidence=1.0,
        arbitration_mode="deterministic",
        effective_response_profile=state.effective_response_profile
        or ResponseProfile(
            effective_tone="friendly",
            effective_verbosity="medium",
            effective_expertise_mode="beginner",
        ),
        semantic_turn_act="refine_current_idea",
        artifact_target="latest_result",
        reason_codes=["typed_next_experiment_selected"],
    )
    return _stage_result_from_result_artifact_patch(
        decision=decision,
        patched=patched,
        reason_code="artifact_patch_from_latest_result",
        additional_reason_codes=("compare_buy_and_hold_recommendation",),
    )
