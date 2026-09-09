"""Backtest response adapter for the shared artifact edit-outcome contract.

Routing preserves typed refusal behavior. Generic completion is owned by
``domain.edit_contract`` and is independent of this response/model vocabulary.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifact_edit_outcomes import artifact_edit_disclosure
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
)
from argus.agent_runtime.artifacts.asset_edits import normalized_asset_symbols
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)


def build_artifact_edit_response(
    *,
    plan: ArtifactAssumptionEditPlan,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
    materialized_targets: set[str],
    has_changes: bool,
    artifact_target: str | None,
    primary_draft: LLMStrategyDraft | None,
    resolved: ResolvedArtifactEdit | None,
    current_asset_universe: list[str],
) -> LLMInterpretationResponse:
    if plan.outcome == "ready_to_confirm":
        if plan.operations and not field_provenance and not extra_parameters:
            # Every operation was refused. When a refusal is impossible
            # against the card state ("Quita TSLA" with no TSLA in the
            # basket), no restatement can fix it, so the honest §3.2 shape is
            # the same card re-issued with the typed disclosure; a
            # clarification here gets swallowed by the stage because
            # 'assumption' is not a contract field, and the card would
            # re-issue clean. A refused cost is different: the value is
            # correctable, so asking helps and the clarification reply stays
            # (the #271 contract), as it does for refusals without a typed
            # record (an indicator op dropped after the resolver).
            disclosure_record = draft.extra_parameters.get("edit_disclosure")
            discloses_impossible_change = isinstance(disclosure_record, dict) and any(
                isinstance(entry, dict)
                and entry.get("target") not in ("fees", "slippage")
                for entry in disclosure_record.get("unapplied") or []
            )
            if not discloses_impossible_change:
                return LLMInterpretationResponse(
                    intent="follow_up",
                    task_relation="continue",
                    requires_clarification=True,
                    user_goal_summary=(
                        plan.user_goal_summary
                        or "The requested assumption change cannot be applied here."
                    ),
                    candidate_strategy_draft=draft,
                    assistant_response=(
                        plan.assistant_response
                        or "I can change RSI thresholds only on an active RSI confirmation card."
                    ),
                    confidence=plan.confidence,
                    reason_codes=["artifact_assumption_edit_planned"],
                    semantic_turn_act="unsupported_request",
                    artifact_target=artifact_target,
                )
    disclosure = artifact_edit_disclosure(
        plan,
        current_asset_universe=current_asset_universe,
        materialized_targets=materialized_targets,
        has_changes=has_changes,
        existing=draft.extra_parameters.get("edit_disclosure"),
        resolved=resolved,
    )
    if disclosure is not None:
        draft.extra_parameters["edit_disclosure"] = disclosure

    if plan.outcome == "ready_to_confirm":
        applied_reason_codes = ["artifact_assumption_edit_planned"]
        if primary_draft is not None and (
            set(normalized_asset_symbols(primary_draft.asset_universe))
            & set(normalized_asset_symbols(primary_draft.asset_exclusions))
        ):
            # Turn-correlated receipt: the exclusions-outrank override fired.
            applied_reason_codes.append("asset_exclusions_outranked_universe_copy")
        return LLMInterpretationResponse(
            intent="calculate",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary=(
                plan.user_goal_summary
                or "User changed a visible confirmation assumption."
            ),
            candidate_strategy_draft=draft,
            assistant_response=plan.assistant_response,
            confidence=plan.confidence,
            reason_codes=applied_reason_codes,
            semantic_turn_act="answer_pending_need",
            artifact_target=artifact_target,
        )

    return LLMInterpretationResponse(
        intent=(
            "cannot"
            if plan.outcome == "unsupported"
            else "follow_up"
        ),
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary=(
            plan.user_goal_summary
            or "The requested assumption change needs clarification."
        ),
        candidate_strategy_draft=draft,
        missing_required_fields=list(plan.missing_required_fields),
        assistant_response=plan.assistant_response,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act=(
            "unsupported_request"
            if plan.outcome == "unsupported"
            else "answer_pending_need"
        ),
        artifact_target=artifact_target,
    )
