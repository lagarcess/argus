from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.artifacts.asset_edits import same_asset_universe
from argus.agent_runtime.artifacts.continuity import (
    apply_patch_to_anchor,
    patched_draft_from_candidate,
    resolve_artifact_anchor,
)
from argus.agent_runtime.artifacts.patch_policy import (
    RESULT_FOLLOWUP_EXECUTABLE_PATCH_FIELDS,
    artifact_patch_changed_fields,
    executable_artifact_patch_missing_fields,
    relevant_unsupported_constraints_for_artifact_patch,
    strategy_has_structured_non_patch_evidence,
)
from argus.agent_runtime.artifacts.strategy_edits import ArtifactPatch
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.clarification_contract import offline_clarification_fallback
from argus.agent_runtime.recovery_messages import (
    recovery_message,
    recovery_state_stage_patch,
)
from argus.agent_runtime.response_style import (
    result_followup_heading,
    with_response_heading,
)
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
    RESULT_FOLLOWUP_TARGET_INFERRED,
    active_confirmation_effective_strategy,
    confirmation_payload_dict,
    confirmation_payload_is_validated_executable,
    decision_allows_result_artifact_patch,
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
                    "facts": {
                        "strategy": pending.model_dump(mode="python"),
                        "current_user_message": state.current_user_message,
                        "structured_action": action.model_dump(mode="python"),
                        "language": language,
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
                "assistant_response": recovery_message(
                    "confirmation_cancelled",
                    language=language,
                ),
            },
        )
    return None


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
            stage_patch={
                "assistant_response": _confirmation_action_guidance(language),
            },
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
            stage_patch={
                "assistant_response": _confirmation_action_guidance(language),
            },
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
            stage_patch={
                "assistant_response": _confirmation_action_guidance(language),
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
                "assistant_response": _confirmation_action_guidance(language),
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
            "assistant_response": _confirmation_action_guidance(language),
        },
    )


def _confirmation_action_guidance(language: str | None) -> str:
    return recovery_message("confirmation_action_guidance", language=language)


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
    reference = (
        snapshot.latest_failed_action_reference if snapshot is not None else None
    )
    if (
        require_requested_failed_action_id and requested_failed_action_id is None
    ) or not _failed_action_matches_requested_id(
        reference=reference,
        requested_failed_action_id=requested_failed_action_id,
    ):
        reason_codes = [*decision.reason_codes, "stale_failed_action_retry"]
        retry_status = (
            "missing_artifact_id"
            if require_requested_failed_action_id
            and requested_failed_action_id is None
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
            "assistant_response": with_response_heading(
                heading=result_followup_heading(focus, language=language),
                body=response,
            ),
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


def _result_artifact_patch_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if _result_followup_target_was_inferred_non_patch(decision):
        return None
    if not decision_allows_result_artifact_patch(
        decision=decision
    ) and not _allows_inferred_result_followup_patch(decision):
        return None
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"run_id": reference.artifact_id},
    )
    patched = patched_draft_from_candidate(
        anchor=anchor,
        candidate=decision.candidate_strategy_draft,
    )
    if patched is None:
        return None
    if (
        decision.semantic_turn_act == "result_followup"
        and not _result_followup_patch_changes_executable_result_fields(patched)
    ):
        return None
    return _stage_result_from_result_artifact_patch(
        decision=decision,
        patched=patched,
        reason_code="artifact_patch_from_latest_result",
    )


def _deterministic_result_artifact_patch_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
) -> StageResult | None:
    reference = (
        snapshot.latest_backtest_result_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    del current_user_message
    if _result_followup_target_was_inferred_non_patch(decision):
        return None
    date_range = decision.candidate_strategy_draft.date_range
    if not isinstance(date_range, dict) or not (
        date_range.get("start") and date_range.get("end")
    ):
        return None
    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"run_id": reference.artifact_id},
    )
    planned_asset_universe = _planned_asset_universe_for_result_patch(
        decision=decision,
        anchor_draft=anchor.draft,
    )
    patch_fields = {"date_range"}
    if planned_asset_universe is not None:
        patch_fields.add("asset_universe")
    if not _decision_allows_deterministic_result_patch(
        decision,
        patch_fields=frozenset(patch_fields),
    ):
        return None
    patch = ArtifactPatch(
        source="user_patch",
        date_range=date_range,
        asset_universe=planned_asset_universe,
        asset_universe_operation=(
            "replace" if planned_asset_universe is not None else None
        ),
    )
    patched = apply_patch_to_anchor(anchor, patch)
    if patched is None:
        return None
    return _stage_result_from_result_artifact_patch(
        decision=decision,
        patched=patched,
        reason_code="artifact_patch_from_latest_result",
        additional_reason_codes=("artifact_date_patch_from_current_message",),
    )


def _planned_asset_universe_for_result_patch(
    *,
    decision: InterpretDecision,
    anchor_draft: StrategySummary | None,
) -> list[str] | None:
    """Asset change a result patch must carry instead of discarding.

    Rebuilding the card from the result anchor keeps its assets; when the
    typed edit planner already resolved a different asset set for this turn
    ("try NVDA over the same period"), dropping it would let inherited
    context overwrite an explicit user constraint.
    """

    if "artifact_assumption_edit_planned" not in decision.reason_codes:
        return None
    draft_assets = [
        symbol
        for symbol in decision.candidate_strategy_draft.asset_universe
        if str(symbol).strip()
    ]
    if not draft_assets or anchor_draft is None:
        return None

    if same_asset_universe(draft_assets, anchor_draft.asset_universe):
        return None
    return list(draft_assets)


def _result_followup_patch_changes_executable_result_fields(
    patched: StrategySummary,
) -> bool:
    return bool(
        artifact_patch_changed_fields(patched)
        & RESULT_FOLLOWUP_EXECUTABLE_PATCH_FIELDS
    )


def _result_followup_target_was_inferred_non_patch(
    decision: InterpretDecision,
) -> bool:
    if RESULT_FOLLOWUP_TARGET_INFERRED not in decision.reason_codes:
        return False
    # A draft gap the result patch cannot fill from the anchor marks a
    # question or a new idea, not an executable edit of the completed run.
    draft_gaps = set(
        missing_required_fields_for_strategy(
            decision.candidate_strategy_draft,
            contract=build_default_capability_contract(),
        )
    )
    if draft_gaps - (RESULT_FOLLOWUP_EXECUTABLE_PATCH_FIELDS | {"strategy_thesis"}):
        return True
    return strategy_has_structured_non_patch_evidence(
        strategy=decision.candidate_strategy_draft,
        patch_fields=frozenset({"strategy_type"})
        | RESULT_FOLLOWUP_EXECUTABLE_PATCH_FIELDS,
    )


def _allows_inferred_result_followup_patch(decision: InterpretDecision) -> bool:
    return (
        decision.semantic_turn_act == "result_followup"
        and decision.artifact_target == "latest_result"
        and RESULT_FOLLOWUP_TARGET_INFERRED in decision.reason_codes
    )


def _decision_allows_deterministic_result_patch(
    decision: InterpretDecision,
    *,
    patch_fields: frozenset[str],
) -> bool:
    if decision.artifact_target in {"active_confirmation", "pending_refinement"}:
        return False
    if decision.capability_question_focus is not None:
        return False
    if decision.context_question_focus is not None:
        return False
    if decision.intent == "unsupported_or_out_of_scope" or (
        decision.semantic_turn_act == "unsupported_request"
    ):
        return not strategy_has_structured_non_patch_evidence(
            strategy=decision.candidate_strategy_draft,
            patch_fields=patch_fields,
        )
    if decision.intent in {"beginner_guidance", "collection_management"}:
        return False
    if decision.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if decision.artifact_target == "latest_result":
        return True
    return (
        decision.intent in {"backtest_execution", "strategy_drafting"}
        or decision.task_relation == "refine"
        or decision.semantic_turn_act
        in {"answer_pending_need", "refine_current_idea", "result_followup"}
    )


def _stage_result_from_result_artifact_patch(
    *,
    decision: InterpretDecision,
    patched: StrategySummary,
    reason_code: str,
    additional_reason_codes: tuple[str, ...] = (),
) -> StageResult:
    missing_fields = missing_required_fields_for_strategy(
        patched,
        contract=build_default_capability_contract(),
    )
    missing_fields = executable_artifact_patch_missing_fields(
        strategy=patched,
        missing_fields=missing_fields,
    )
    unsupported_constraints = relevant_unsupported_constraints_for_artifact_patch(
        strategy=patched,
        constraints=decision.unsupported_constraints,
    )
    has_blocking_validation = bool(
        missing_fields
        or decision.ambiguous_fields
        or unsupported_constraints
    )
    refined_decision = decision.model_copy(
        update={
            "intent": "backtest_execution",
            "task_relation": "refine",
            "requires_clarification": has_blocking_validation,
            "candidate_strategy_draft": patched,
            "missing_required_fields": list(missing_fields),
            "unsupported_constraints": list(unsupported_constraints),
            "semantic_turn_act": "refine_current_idea",
            "result_followup_focus": None,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *decision.reason_codes,
                        reason_code,
                        *additional_reason_codes,
                    ]
                )
            ),
        }
    )
    stage_patch: dict[str, Any] = {
        "candidate_strategy_draft": patched.model_dump(mode="python"),
        "missing_required_fields": list(missing_fields),
    }
    return StageResult(
        outcome=(
            "needs_clarification"
            if has_blocking_validation
            else "ready_for_confirmation"
        ),
        decision=refined_decision,
        stage_patch=stage_patch,
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
