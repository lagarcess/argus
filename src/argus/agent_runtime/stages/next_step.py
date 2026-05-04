from __future__ import annotations

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState

SUCCESS_NEXT_ACTIONS = [
    "refine_strategy",
    "compare_benchmark",
    "save_to_collection",
]
FAILURE_NEXT_ACTIONS = [
    "provide_missing_details",
    "simplify_strategy",
    "ask_for_example",
]
BEGINNER_NEXT_ACTIONS = [
    "share_example_strategy",
    "explain_backtests",
    "start_simple",
]


def next_step_stage(*, state: RunState) -> StageResult:
    next_actions = _resolve_next_actions(state)
    return StageResult(
        outcome="end_run",
        stage_patch={
            "next_actions": next_actions,
            "assistant_prompt": None,
        },
    )


def _resolve_next_actions(state: RunState) -> list[str]:
    if state.intent == "beginner_guidance":
        return list(BEGINNER_NEXT_ACTIONS)
    if state.failure_classification or state.requires_clarification:
        return list(FAILURE_NEXT_ACTIONS)
    if _has_result_or_summary(state):
        return list(SUCCESS_NEXT_ACTIONS)
    return list(SUCCESS_NEXT_ACTIONS)


def _has_result_or_summary(state: RunState) -> bool:
    payload = state.final_response_payload
    if payload is None:
        return False
    if isinstance(payload, dict):
        return bool(payload.get("result") or payload.get("summary"))
    return bool(payload.result or payload.summary)

