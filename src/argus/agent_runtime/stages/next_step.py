from __future__ import annotations

from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState

RESULT_NEXT_ACTIONS = [
    "show_breakdown",
    "refine_strategy",
    "save_strategy",
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


async def next_step_stage_async(*, state: RunState) -> StageResult:
    return next_step_stage(state=state)


def _resolve_next_actions(state: RunState) -> list[str]:
    if _has_result_or_summary(state):
        return list(RESULT_NEXT_ACTIONS)
    return []


def _has_result_or_summary(state: RunState) -> bool:
    payload = state.final_response_payload
    if payload is None:
        return False
    if isinstance(payload, dict):
        return bool(payload.get("result") or payload.get("summary"))
    return bool(payload.result or payload.summary)
