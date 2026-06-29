"""Pending-need route-repair helpers.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _strategy_has_execution_anchor,
    _strategy_has_fresh_execution_detail,
)
from argus.agent_runtime.stages.interpret_internal.contextual_merge import (
    _strategy_with_contextual_merge,
)
from argus.agent_runtime.stages.interpret_internal.shared import _field_base
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import TaskSnapshot


def _repair_retry_route_when_pending_need_is_active(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    if interpretation.semantic_turn_act != "retry_failed_action":
        return interpretation
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return interpretation
    if snapshot.latest_failed_action_reference is not None:
        return interpretation
    requested_field = _field_base(str(selected_thread_metadata.get("requested_field") or ""))
    prior_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    if not requested_field and prior_outcome != "await_user_reply":
        return interpretation
    return interpretation.model_copy(
        update={
            "intent": "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": False,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "reason_codes": [
                *interpretation.reason_codes,
                "retry_route_repaired_to_pending_need",
            ],
        }
    )


def _repair_fresh_restatement_route_when_pending_need_is_active(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return interpretation
    if snapshot.latest_backtest_result_reference is not None:
        return interpretation
    if interpretation.semantic_turn_act in {
        "approval",
        "new_idea",
        "retry_failed_action",
        "unsupported_request",
    }:
        return interpretation
    if interpretation.intent not in {"conversation_followup", "strategy_drafting"}:
        return interpretation
    prior_outcome = str(selected_thread_metadata.get("last_stage_outcome") or "")
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if (
        prior_outcome not in {"await_user_reply", "needs_clarification"}
        and not requested_field
        and selected_thread_metadata.get("fallback_source")
        != "pending_strategy_metadata"
    ):
        return interpretation
    prior = snapshot.pending_strategy_summary
    candidate = _strategy_with_contextual_merge(
        strategy=interpretation.candidate_strategy_draft,
        snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act="new_idea",
        task_relation="new_task",
        reason_codes=interpretation.reason_codes,
    )
    if not _strategy_has_execution_anchor(candidate):
        return interpretation
    if not candidate.strategy_type or not candidate.asset_universe or not candidate.date_range:
        return interpretation
    if not _strategy_has_fresh_execution_detail(strategy=candidate, prior=prior):
        return interpretation
    return interpretation.model_copy(
        update={
            "intent": "backtest_execution",
            "task_relation": "new_task",
            "requires_clarification": False,
            "assistant_response": None,
            "candidate_strategy_draft": candidate,
            "missing_required_fields": [],
            "semantic_turn_act": "new_idea",
            "result_followup_focus": None,
            "artifact_target": "none",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *interpretation.reason_codes,
                        "fresh_restatement_followup_route_repaired",
                    ]
                )
            ),
        }
    )
