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
            "assistant_prompt": _build_next_step_prompt(next_actions),
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


def _build_next_step_prompt(next_actions: list[str]) -> str:
    labels = [_next_action_label(action) for action in next_actions]
    return "Next step options:\n" + "\n".join(labels)


def _next_action_label(action: str) -> str:
    labels: dict[str, str] = {
        "refine_strategy": "Refine the strategy",
        "compare_benchmark": "Compare it with the benchmark",
        "save_to_collection": "Save it to a collection",
        "provide_missing_details": "Provide the missing strategy details",
        "simplify_strategy": "Simplify the strategy setup",
        "ask_for_example": "Ask for a concrete example",
        "share_example_strategy": "See an example strategy",
        "explain_backtests": "Explain what a backtest does",
        "start_simple": "Start with a simple idea",
    }
    return labels.get(action, action.replace("_", " ").capitalize())
