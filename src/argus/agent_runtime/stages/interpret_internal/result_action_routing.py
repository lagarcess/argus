"""Typed result-card action routing kept outside the main interpret stage."""

from __future__ import annotations

from argus.agent_runtime.next_experiments import continuity_next_experiment_kind
from argus.agent_runtime.stages.interpret_internal.recommendation_continuity import (
    change_date_range_recommendation_result,
    compare_buy_and_hold_recommendation_result,
)
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.state.models import RunState, TaskSnapshot

TRANSPORT_RESULT_ACTION_TYPES = {"show_breakdown", "save_strategy"}


def typed_result_action_stage_result_if_applicable(
    *,
    state: RunState,
    snapshot: TaskSnapshot | None,
    language: str,
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
    kind = continuity_next_experiment_kind(
        action_type=action.type,
        action_payload=action.payload,
    )
    if kind == "change_date_range":
        return change_date_range_recommendation_result(
            state=state,
            snapshot=snapshot,
            language=language,
        )
    if kind == "compare_buy_and_hold":
        return compare_buy_and_hold_recommendation_result(
            state=state,
            snapshot=snapshot,
            language=language,
        )
    return None
