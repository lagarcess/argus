from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.artifacts.continuity import resolve_artifact_anchor
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.response_style import (
    result_followup_heading,
    with_response_heading,
)
from argus.agent_runtime.result_followups import (
    compose_result_followup_response,
    context_packet_ids_from_fact_bank,
    fallback_result_followup_response,
    record_result_followup_fallback_receipt,
    result_followup_fact_bank,
    result_followup_llm_task,
)
from argus.agent_runtime.stages.approval_guard import (
    decision_is_pure_approval,
    decision_replays_visible_confirmation_without_material_change,
    decision_requests_confirmation_card_action,
)
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
    confirmation_payload_dict,
    confirmation_payload_is_validated_executable,
    decision_targets_result_artifact,
    draft_assumptions_response,
    failed_action_is_retryable,
    has_pending_confirmation_context,
    latest_run_id_for_action,
    launch_payload_from_failed_action,
    non_retryable_failed_action_response,
    prior_stage_was_await_approval,
    semantic_need_for_action,
    stale_confirmation_action_response,
    strategy_from_failed_launch_payload,
    strategy_from_result_action_snapshot,
    validated_approval_confirmation_payload_from_snapshot,
    validated_approval_confirmation_payload_from_state,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ResponseProfile,
    RunState,
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.strategy_contract import strategy_can_be_approved
from argus.agent_runtime.strategy_requirements import missing_required_fields_for_strategy

CONFIRMATION_EDIT_ACTION_FIELDS = {
    "change_asset": "asset_universe",
    "change_dates": "date_range",
    "adjust_assumptions": "assumption",
}

TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE = (
    "That strategy is ready on the visible card. Use the card action when you "
    "want to start the simulation."
)
RESULT_FOLLOWUP_COMPOSER_TIMEOUT_SECONDS = 10.0


def _result_followup_decision(
    decision: InterpretDecision,
    *,
    focus: str | None = None,
    reason_code: str | None = None,
) -> InterpretDecision:
    reason_codes = list(decision.reason_codes)
    if reason_code is not None:
        reason_codes.append(reason_code)
    return decision.model_copy(
        update={
            "intent": "conversation_followup",
            "requires_clarification": False,
            "candidate_strategy_draft": StrategySummary(),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "resolution_provenance": [],
            "semantic_turn_act": "result_followup",
            "result_followup_focus": focus or decision.result_followup_focus or "general",
            "reason_codes": reason_codes,
        }
    )


def structured_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    action = state.structured_action
    if action is None:
        return None
    if action.type == "retry_failed_action":
        return _retry_failed_action_stage_result(
            decision=_retry_failed_action_decision(state=state),
            snapshot=snapshot,
        )
    if action.presentation == "result":
        return result_action_stage_result_if_applicable(
            state=state,
            snapshot=snapshot,
        )
    if action.presentation != "confirmation":
        return None
    stale_action_response = stale_confirmation_action_response(
        action=action,
        snapshot=snapshot,
    )
    if stale_action_response is not None:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": stale_action_response,
                "requested_field": None,
                "missing_required_fields": [],
            },
        )
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload=action.payload,
    )
    if (
        snapshot is None
        or (
            snapshot.pending_strategy_summary is None
            and anchor.draft is None
        )
    ):
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": (
                    "I do not have an active confirmation to change. "
                    "Describe the investing idea again and I will prepare a fresh draft."
                ),
                "requested_field": None,
                "missing_required_fields": [],
            },
        )

    pending_source = anchor.draft or snapshot.pending_strategy_summary
    pending = pending_source.model_copy(deep=True)
    action_type = action.type
    if action_type == "run_backtest":
        return _run_backtest_action_result(
            state=state,
            pending=pending,
            selected_thread_metadata=selected_thread_metadata,
        )

    if action_type in CONFIRMATION_EDIT_ACTION_FIELDS:
        requested_field = CONFIRMATION_EDIT_ACTION_FIELDS[action_type]
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "candidate_strategy_draft": pending.model_dump(mode="python"),
                "assistant_prompt": None,
                "requested_field": requested_field,
                "missing_required_fields": [requested_field],
                "response_intent": {
                    "kind": "clarification",
                    "semantic_needs": [semantic_need_for_action(action_type)],
                    "requested_fields": [requested_field],
                    "facts": {
                        "strategy": pending.model_dump(mode="python"),
                        "current_user_message": state.current_user_message,
                        "structured_action": action.model_dump(mode="python"),
                    },
                    "options": [],
                },
            },
        )

    if action_type == "cancel_confirmation":
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "candidate_strategy_draft": StrategySummary().model_dump(mode="python"),
                "assistant_response": "No problem. I will leave that draft unrun.",
            },
        )
    return None


def _run_backtest_action_result(
    *,
    state: RunState,
    pending: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> StageResult:
    approved = pending
    confirmation_payload = validated_approval_confirmation_payload_from_state(
        state=state,
        approved_strategy=approved,
    )
    if confirmation_payload is None:
        return StageResult(
            outcome="ready_for_confirmation",
            stage_patch={
                "candidate_strategy_draft": approved.model_dump(mode="python"),
                "assistant_prompt": None,
            },
        )
    if not strategy_can_be_approved(approved):
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                "candidate_strategy_draft": approved.model_dump(mode="python"),
                "missing_required_fields": missing_required_fields_for_strategy(
                    approved,
                    contract=build_default_capability_contract(),
                ),
            },
        )
    return StageResult(
        outcome="approved_for_execution",
        stage_patch={
            "candidate_strategy_draft": approved.model_dump(mode="python"),
            "confirmation_payload": confirmation_payload,
        },
    )


def result_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    action = state.structured_action
    if action is None or action.type != "refine_strategy":
        return None
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": (
                    "I do not have a completed result to refine. Run a strategy "
                    "first, then use Refine strategy from the result card."
                ),
            },
        )
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload=action.payload,
    )
    strategy = anchor.draft or strategy_from_result_action_snapshot(snapshot=snapshot)
    latest_run_id = latest_run_id_for_action(
        action_payload=action.payload,
        reference=reference,
    )
    return StageResult(
        outcome="await_user_reply",
        stage_patch={
            "candidate_strategy_draft": strategy.model_dump(mode="python"),
            "assistant_prompt": None,
            "requested_field": "refinement",
            "missing_required_fields": ["refinement"],
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": ["refinement"],
                "requested_fields": ["refinement"],
                "facts": {
                    "strategy": strategy.model_dump(mode="python"),
                    "current_user_message": state.current_user_message,
                    "structured_action": action.model_dump(mode="python"),
                    "latest_run_id": latest_run_id,
                    "latest_result_reference": reference.model_dump(mode="python"),
                },
                "options": [],
            },
        },
    )


def approval_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
    interpretation: StructuredInterpretation | None = None,
) -> StageResult | None:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    approved_strategy = snapshot.pending_strategy_summary.model_copy(deep=True)
    visible_confirmation_strategy = active_confirmation_effective_strategy(
        snapshot=snapshot,
        fallback=approved_strategy,
    )
    if (
        snapshot.active_confirmation_reference is not None
        and _active_confirmation_is_valid(snapshot)
        and decision_replays_visible_confirmation_without_material_change(
            decision=decision,
            visible_strategy=visible_confirmation_strategy,
            interpretation=interpretation,
            interpreted_candidate_strategy=(
                interpretation.candidate_strategy_draft
                if interpretation is not None
                else None
            ),
        )
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                    "reason_codes": [
                        *decision.reason_codes,
                        "text_action_deferred_to_confirmation_card",
                    ],
                }
            ),
            stage_patch={
                "assistant_response": TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE,
            },
        )
    if decision.semantic_turn_act != "approval":
        return None
    if snapshot.active_confirmation_reference is not None and _active_confirmation_is_valid(
        snapshot
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                }
            ),
            stage_patch={
                "assistant_response": TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE,
            },
        )
    if snapshot.active_confirmation_reference is not None and (
        decision_requests_confirmation_card_action(
            decision=decision,
            visible_strategy=approved_strategy,
            interpretation=interpretation,
            interpreted_candidate_strategy=(
                interpretation.candidate_strategy_draft
                if interpretation is not None
                else None
            ),
        )
    ):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                }
            ),
            stage_patch={
                "assistant_response": TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE,
            },
        )
    if not decision_is_pure_approval(
        decision=decision,
        visible_strategy=approved_strategy,
        interpretation=interpretation,
        interpreted_candidate_strategy=(
            interpretation.candidate_strategy_draft
            if interpretation is not None
            else None
        ),
    ):
        return None
    if snapshot.active_confirmation_reference is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                }
            ),
            stage_patch={
                "assistant_response": TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE,
            },
        )
    confirmation_payload = validated_approval_confirmation_payload_from_state(
        state=state,
        approved_strategy=approved_strategy,
    )
    if confirmation_payload is None:
        confirmation_payload = validated_approval_confirmation_payload_from_snapshot(
            snapshot=snapshot,
            approved_strategy=approved_strategy,
        )
    if (
        confirmation_payload is None
        and not prior_stage_was_await_approval(selected_thread_metadata)
    ):
        return None
    if confirmation_payload is None:
        return StageResult(
            outcome="ready_for_confirmation",
            decision=decision.model_copy(
                update={
                    "intent": "backtest_execution",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "candidate_strategy_draft": approved_strategy,
                    "missing_required_fields": [],
                    "semantic_turn_act": "approval",
                }
            ),
            stage_patch={
                "assistant_prompt": None,
            },
        )
    if not strategy_can_be_approved(approved_strategy):
        return None
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": approved_strategy,
                "missing_required_fields": [],
                "semantic_turn_act": "approval",
            }
        ),
        stage_patch={
            "assistant_response": TEXT_APPROVAL_REQUIRES_CARD_ACTION_RESPONSE,
        },
    )


def _active_confirmation_is_valid(snapshot: TaskSnapshot) -> bool:
    reference = snapshot.active_confirmation_reference
    if reference is None:
        return False
    payload = confirmation_payload_dict(reference.metadata.get("confirmation_payload"))
    return confirmation_payload_is_validated_executable(payload)


def retry_failed_action_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if decision.semantic_turn_act != "retry_failed_action":
        return None
    return _retry_failed_action_stage_result(decision=decision, snapshot=snapshot)


def _retry_failed_action_decision(*, state: RunState) -> InterpretDecision:
    return InterpretDecision(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Retry failed action",
        candidate_strategy_draft=StrategySummary(),
        missing_required_fields=[],
        confidence=1.0,
        arbitration_mode="deterministic",
        reason_codes=["structured_retry_failed_action"],
        effective_response_profile=state.effective_response_profile
        or ResponseProfile(
            effective_tone="friendly",
            effective_verbosity="medium",
            effective_expertise_mode="beginner",
        ),
        semantic_turn_act="retry_failed_action",
    )


def _retry_failed_action_stage_result(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult:
    reference = (
        snapshot.latest_failed_action_reference if snapshot is not None else None
    )
    launch_payload = launch_payload_from_failed_action(reference)
    if launch_payload is None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "missing_required_fields": [],
                }
            ),
            stage_patch={
                "assistant_response": (
                    "I do not have a failed run payload to retry. Use the visible "
                    "Run backtest action again, or confirm the strategy you want me "
                    "to run."
                )
            },
        )
    if not failed_action_is_retryable(reference):
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "missing_required_fields": [],
                }
            ),
            stage_patch={
                "assistant_response": non_retryable_failed_action_response(reference)
            },
        )
    strategy = strategy_from_failed_launch_payload(launch_payload)
    return StageResult(
        outcome="ready_for_confirmation",
        decision=decision.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": False,
                "candidate_strategy_draft": strategy,
                "missing_required_fields": [],
            }
        ),
        stage_patch={
            "candidate_strategy_draft": strategy,
            "assistant_response": (
                "I still have that failed setup. I rebuilt the draft so you can "
                "review the card and retry when you are ready."
            ),
        },
    )


def pending_artifact_followup_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if not has_pending_confirmation_context(snapshot):
        return None
    requested_assumptions = decision.result_followup_focus == "assumptions"
    pending_without_result = (
        decision.semantic_turn_act == "result_followup"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is None
    )
    if not requested_assumptions and not pending_without_result:
        return None
    draft_response = draft_assumptions_response(snapshot)
    if draft_response is None:
        return None
    return StageResult(
        outcome="ready_to_respond",
        decision=decision.model_copy(
            update={
                "intent": "conversation_followup",
                "requires_clarification": False,
                "missing_required_fields": [],
            }
        ),
        stage_patch={"assistant_response": draft_response},
    )


async def artifact_followup_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    if not decision_targets_result_artifact(decision=decision, snapshot=snapshot):
        return None
    focus = decision.result_followup_focus or "general"
    if focus == "assumptions":
        draft_response = draft_assumptions_response(snapshot)
        if draft_response is not None:
            return StageResult(
                outcome="ready_to_respond",
                decision=_result_followup_decision(decision, focus=focus),
                stage_patch={"assistant_response": draft_response},
            )
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    metadata = dict(reference.metadata)
    response = await _compose_result_followup_with_timeout(
        metadata=metadata,
        focus=focus,
        user_message=current_user_message,
    )
    if response is None:
        response = fallback_result_followup_response(
            metadata=metadata,
            focus=focus,
        )
    if response is None:
        return None
    return StageResult(
        outcome="ready_to_respond",
        decision=_result_followup_decision(decision, focus=focus),
        stage_patch={
            "assistant_response": with_response_heading(
                heading=result_followup_heading(focus),
                body=response,
            )
        },
    )


async def _compose_result_followup_with_timeout(
    *,
    metadata: dict[str, Any],
    focus: str,
    user_message: str,
) -> str | None:
    try:
        return await asyncio.wait_for(
            compose_result_followup_response(
                metadata=metadata,
                focus=focus,
                user_message=user_message,
            ),
            timeout=RESULT_FOLLOWUP_COMPOSER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        fact_bank = result_followup_fact_bank(metadata)
        record_result_followup_fallback_receipt(
            task=result_followup_llm_task(fact_bank=fact_bank, focus=focus),
            failure_mode="result_followup_timeout",
            context_packet_ids=context_packet_ids_from_fact_bank(fact_bank),
        )
        return None
