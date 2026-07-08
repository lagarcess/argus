"""Result-artifact patch routing for interpret stage decisions.

Behavior-preserving relocation from stages/interpret_actions.py: building the
next executable draft from the completed run's anchor, and deciding when a
turn's own draft must not be patched onto that anchor."""

from __future__ import annotations

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
from argus.agent_runtime.stages.artifact_context import (
    RESULT_FOLLOWUP_TARGET_INFERRED,
    decision_allows_result_artifact_patch,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
)
from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot
from argus.agent_runtime.strategy_requirements import missing_required_fields_for_strategy


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


