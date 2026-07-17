from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.artifacts.continuity import (
    resolve_artifact_anchor,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.clarification_contract import offline_clarification_fallback
from argus.agent_runtime.coverage_recovery import (
    PRESERVED_OPTIONAL_PARAMETER_STATUS_FACT,
    optional_parameter_status_without_coverage_recovery,
    preserved_optional_parameter_status_from_response_intent,
)
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
)
from argus.agent_runtime.response_style import result_followup_response_intent
from argus.agent_runtime.result_followups import (
    compose_result_followup_response,
    context_packet_ids_from_fact_bank,
    record_result_followup_recovery_receipt,
    result_followup_fact_bank,
    result_followup_llm_task,
)
from argus.agent_runtime.stages.approval_guard import (
    decision_contains_material_strategy_patch,
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
    prior_stage_was_await_approval,
    semantic_need_for_action,
    stale_confirmation_action_response,
    strategy_from_failed_launch_payload,
    strategy_from_result_action_snapshot,
    validated_approval_confirmation_payload_from_snapshot,
    validated_approval_confirmation_payload_from_state,
)
from argus.agent_runtime.stages.interpret_internal.result_artifact_patch import (
    _deterministic_result_artifact_patch_stage_result_if_applicable,
    _result_artifact_patch_stage_result_if_applicable,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ArtifactActionRecoveryFacts,
    ArtifactActionRecoveryStatus,
    ArtifactReference,
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
TRANSPORT_RESULT_ACTION_TYPES = {"show_breakdown", "save_strategy"}
COVERAGE_RECOVERY_ACTION_FIELDS = {
    "change_dates": "date_range",
    "change_asset": "asset_universe",
    "change_benchmark": "comparison_baseline",
}

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
    language: str = "en",
) -> StageResult | None:
    action = state.structured_action
    if action is None:
        return None
    if action.type == "retry_failed_action":
        return _retry_failed_action_stage_result(
            decision=_retry_failed_action_decision(state=state),
            snapshot=snapshot,
            requested_failed_action_id=action.failed_action_artifact_id,
            require_requested_failed_action_id=True,
            language=language,
        )
    coverage_recovery_result = _coverage_recovery_action_result(
        state=state,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        language=language,
    )
    if coverage_recovery_result is not None:
        return coverage_recovery_result
    if action.presentation == "result":
        return result_action_stage_result_if_applicable(
            state=state,
            snapshot=snapshot,
            language=language,
        )
    if action.presentation != "confirmation":
        return None
    stale_action_response = stale_confirmation_action_response(
        action=action,
        snapshot=snapshot,
        language=language,
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
    if snapshot is None or (
        snapshot.pending_strategy_summary is None and anchor.draft is None
    ):
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": recovery_message(
                    "confirmation_action_missing_context",
                    language=language,
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
            snapshot=snapshot,
            pending=pending,
            selected_thread_metadata=selected_thread_metadata,
        )

    if action_type in CONFIRMATION_EDIT_ACTION_FIELDS:
        requested_field = CONFIRMATION_EDIT_ACTION_FIELDS[action_type]
        facts: dict[str, Any] = {
            "strategy": pending.model_dump(mode="python"),
            "current_user_message": state.current_user_message,
            "structured_action": action.model_dump(mode="python"),
            "language": language,
        }
        if action_type == "change_asset":
            facts["asset_edit_frame"] = "operation_agnostic"
        return StageResult(
            outcome="needs_clarification",
            stage_patch={
                "candidate_strategy_draft": pending.model_dump(mode="python"),
                "assistant_prompt": None,
                "requested_field": requested_field,
                "missing_required_fields": [requested_field],
                "response_intent": {
                    "kind": "clarification",
                    "semantic_needs": [semantic_need_for_action(action_type)],
                    "requested_fields": [requested_field],
                    "facts": facts,
                    "options": [],
                },
            },
        )

    if action_type == "cancel_confirmation":
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "candidate_strategy_draft": StrategySummary().model_dump(mode="python"),
                "assistant_response": recovery_message(
                    "confirmation_cancelled",
                    language=language,
                ),
            },
        )
    return None


def _coverage_recovery_action_result(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    language: str,
) -> StageResult | None:
    action = state.structured_action
    if action is None or action.type != "select_response_option":
        return None
    response_intent = selected_thread_metadata.get("response_intent")
    if not isinstance(response_intent, dict) or response_intent.get("kind") != (
        "coverage_recovery"
    ):
        return None
    option_id = action.payload.get("option_id")
    replacement_values = action.payload.get("replacement_values")
    if not isinstance(option_id, str) or not isinstance(replacement_values, dict):
        return None
    requested_field = replacement_values.get("requested_field")
    expected_field = COVERAGE_RECOVERY_ACTION_FIELDS.get(option_id)
    if requested_field != expected_field:
        return None
    options = response_intent.get("options")
    if not isinstance(options, list) or not any(
        isinstance(option, dict)
        and option.get("id") == option_id
        and option.get("replacement_values") == replacement_values
        for option in options
    ):
        return None
    pending = snapshot.pending_strategy_summary if snapshot is not None else None
    if pending is None:
        return None
    preserved_optional_parameter_status = (
        preserved_optional_parameter_status_from_response_intent(response_intent) or {}
    )
    preserved_optional_parameter_status.update(
        optional_parameter_status_without_coverage_recovery(
            state.optional_parameter_status
        )
    )
    semantic_need = {
        "date_range": "period",
        "asset_universe": "asset_target",
        "comparison_baseline": "assumption",
    }[requested_field]
    return StageResult(
        outcome="needs_clarification",
        stage_patch={
            "candidate_strategy_draft": pending.model_dump(mode="python"),
            "assistant_prompt": None,
            "requested_field": requested_field,
            "missing_required_fields": [requested_field],
            "optional_parameter_status": preserved_optional_parameter_status,
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": [semantic_need],
                "requested_fields": [requested_field],
                "facts": {
                    "strategy": pending.model_dump(mode="python"),
                    "current_user_message": state.current_user_message,
                    "structured_action": action.model_dump(mode="python"),
                    "language": language,
                    PRESERVED_OPTIONAL_PARAMETER_STATUS_FACT: (
                        preserved_optional_parameter_status
                    ),
                },
                "options": [],
            },
        },
    )


def _run_backtest_action_result(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    pending: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> StageResult:
    approved = pending
    confirmation_payload = validated_approval_confirmation_payload_from_state(
        state=state,
        approved_strategy=approved,
    )
    if confirmation_payload is None:
        confirmation_payload = validated_approval_confirmation_payload_from_snapshot(
            snapshot=snapshot,
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
    language: str = "en",
) -> StageResult | None:
    action = state.structured_action
    if action is None:
        return None
    if action.type in TRANSPORT_RESULT_ACTION_TYPES:
        reference = (
            snapshot.latest_backtest_result_reference if snapshot is not None else None
        )
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": None,
                "result_action_request": {
                    "type": action.type,
                    "action": action.model_dump(mode="python"),
                    "latest_result_reference": (
                        reference.model_dump(mode="python")
                        if reference is not None
                        else None
                    ),
                },
            },
        )
    if action.type != "refine_strategy":
        return None
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "assistant_response": recovery_message(
                    "result_refine_missing",
                    language=language,
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
    response_intent = {
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
    }
    return StageResult(
        outcome="await_user_reply",
        stage_patch={
            "candidate_strategy_draft": strategy.model_dump(mode="python"),
            "assistant_prompt": offline_clarification_fallback(
                language=language,
                response_intent=response_intent,
                strategy=strategy,
            ),
            "requested_field": "refinement",
            "missing_required_fields": ["refinement"],
            "response_intent": response_intent,
        },
    )


def approval_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    state: RunState,
    selected_thread_metadata: dict[str, Any],
    interpretation: StructuredInterpretation | None = None,
    language: str = "en",
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
            stage_patch=_confirmation_action_guidance_patch(language),
        )
    if decision.semantic_turn_act != "approval":
        return None
    if (
        snapshot.active_confirmation_reference is not None
        and _active_confirmation_is_valid(snapshot)
        and not decision_contains_material_strategy_patch(
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
            stage_patch=_confirmation_action_guidance_patch(language),
        )
    if snapshot.active_confirmation_reference is not None and (
        decision_requests_confirmation_card_action(
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
                }
            ),
            stage_patch=_confirmation_action_guidance_patch(language),
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
            stage_patch=_confirmation_action_guidance_patch(language),
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
    if confirmation_payload is None and not prior_stage_was_await_approval(
        selected_thread_metadata
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
        stage_patch=_confirmation_action_guidance_patch(language),
    )


def _confirmation_action_guidance(language: str | None) -> str:
    return recovery_message("confirmation_action_guidance", language=language)


def _confirmation_action_guidance_patch(language: str | None) -> dict[str, Any]:
    return {
        "assistant_response": _confirmation_action_guidance(language),
        **recovery_state_stage_patch(
            "confirmation_action_guidance",
            language=language,
            retryable=False,
        ),
    }


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
    requested_failed_action_id: str | None = None,
    require_requested_failed_action_id: bool = False,
    language: str = "en",
) -> StageResult:
    reference = snapshot.latest_failed_action_reference if snapshot is not None else None
    if (
        require_requested_failed_action_id and requested_failed_action_id is None
    ) or not _failed_action_matches_requested_id(
        reference=reference,
        requested_failed_action_id=requested_failed_action_id,
    ):
        reason_codes = [*decision.reason_codes, "stale_failed_action_retry"]
        retry_status = (
            "missing_artifact_id"
            if require_requested_failed_action_id and requested_failed_action_id is None
            else "stale"
        )
        return StageResult(
            outcome="ready_to_respond",
            decision=decision.model_copy(
                update={
                    "intent": "conversation_followup",
                    "task_relation": "continue",
                    "requires_clarification": False,
                    "missing_required_fields": [],
                    "reason_codes": reason_codes,
                }
            ),
            stage_patch={
                "response_intent": _retry_failed_action_response_intent(
                    status=retry_status,
                    reference=reference,
                    requested_failed_action_id=requested_failed_action_id,
                    language=language,
                )
            },
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
                "response_intent": _retry_failed_action_response_intent(
                    status="missing_payload",
                    reference=reference,
                    requested_failed_action_id=requested_failed_action_id,
                    language=language,
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
                "response_intent": _retry_failed_action_response_intent(
                    status="non_retryable",
                    reference=reference,
                    requested_failed_action_id=requested_failed_action_id,
                    language=language,
                )
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
            "response_intent": _retry_failed_action_response_intent(
                status="rebuilt_confirmation",
                reference=reference,
                requested_failed_action_id=requested_failed_action_id,
                language=language,
            ),
        },
    )


def _retry_failed_action_response_intent(
    *,
    status: ArtifactActionRecoveryStatus,
    reference: ArtifactReference | None,
    requested_failed_action_id: str | None,
    language: str = "en",
) -> dict[str, Any]:
    metadata = dict(reference.metadata) if reference is not None else {}
    raw_user_safe_message = metadata.get("user_safe_message") or metadata.get("error")
    user_safe_message = (
        raw_user_safe_message.strip()
        if isinstance(raw_user_safe_message, str) and raw_user_safe_message.strip()
        else None
    )
    facts = ArtifactActionRecoveryFacts(
        action_type="retry_failed_action",
        status=status,
        requested_failed_action_id=requested_failed_action_id,
        latest_failed_action_id=reference.artifact_id if reference is not None else None,
        user_safe_message=user_safe_message,
    )
    payload = facts.model_dump()
    payload["language"] = language
    if facts.user_safe_message is None:
        payload.pop("user_safe_message", None)
    return {
        "kind": "artifact_action_recovery",
        "facts": payload,
    }


def _failed_action_matches_requested_id(
    *,
    reference: ArtifactReference | None,
    requested_failed_action_id: str | None,
) -> bool:
    if not requested_failed_action_id:
        return True
    if reference is None:
        return False
    return reference.artifact_id == requested_failed_action_id


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
    language: str = "en",
) -> StageResult | None:
    deterministic_patch_result = (
        _deterministic_result_artifact_patch_stage_result_if_applicable(
            decision=decision,
            snapshot=snapshot,
            current_user_message=current_user_message,
        )
    )
    if deterministic_patch_result is not None:
        return deterministic_patch_result
    if not decision_targets_result_artifact(decision=decision, snapshot=snapshot):
        return None
    artifact_patch_result = _result_artifact_patch_stage_result_if_applicable(
        decision=decision,
        snapshot=snapshot,
    )
    if artifact_patch_result is not None:
        return artifact_patch_result
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
        language=language,
    )
    used_recovery = response is None
    if response is None:
        response = recovery_message(
            "latest_result_followup_unavailable",
            language=language,
        )
    return StageResult(
        outcome="ready_to_respond",
        decision=_result_followup_decision(decision, focus=focus),
        stage_patch={
            "assistant_response": response,
            "response_intent": result_followup_response_intent(focus),
            **(
                recovery_state_stage_patch(
                    "latest_result_followup_unavailable",
                    language=language,
                    retryable=True,
                )
                if used_recovery
                else {}
            ),
        },
    )


async def _compose_result_followup_with_timeout(
    *,
    metadata: dict[str, Any],
    focus: str,
    user_message: str,
    language: str = "en",
) -> str | None:
    try:
        return await asyncio.wait_for(
            compose_result_followup_response(
                metadata=metadata,
                focus=focus,
                user_message=user_message,
                language=language,
            ),
            timeout=RESULT_FOLLOWUP_COMPOSER_TIMEOUT_SECONDS,
        )
    except (TimeoutError, asyncio.TimeoutError):
        fact_bank = result_followup_fact_bank(metadata)
        record_result_followup_recovery_receipt(
            task=result_followup_llm_task(fact_bank=fact_bank, focus=focus),
            failure_mode="result_followup_timeout",
            context_packet_ids=context_packet_ids_from_fact_bank(fact_bank),
        )
        return None
