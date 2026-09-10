"""Bind background research completion to its original declared tool card."""

from __future__ import annotations

from typing import Any

from argus.domain.tool_contracts import (
    ToolCall,
    ToolFailure,
    ToolOutcome,
)
from argus.domain.tool_job_binding import (
    bind_tool_job_call,
    tool_card_for_job_completion,
)


def with_research_tool_binding(
    job_request: dict[str, Any],
    *,
    call_id: str | None,
    tool_name: str | None,
    artifact_id: str | None,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    """Only the private job request carries executable identity and arguments."""
    if call_id is None:
        return job_request
    if tool_name is None or artifact_id is None or arguments is None:
        raise ValueError("A registered research job needs its complete tool binding")
    call = ToolCall(
        call_id=call_id,
        tool_name=tool_name,
        arguments=arguments,
    )
    return {
        **job_request,
        "tool_binding": bind_tool_job_call(call=call, artifact_id=artifact_id),
    }


def research_tool_card_for_completion(
    job_request: dict[str, Any],
    stage_patch: dict[str, Any],
    *,
    failure_code: str | None = None,
) -> dict[str, Any] | None:
    """A background result uses its bound card version and original inputs."""
    binding = job_request.get("tool_binding")
    if not isinstance(binding, dict):
        return None
    from argus.agent_runtime.research_tools import research_outcome_from_patch

    outcome = (
        ToolOutcome(status="unavailable", failure=ToolFailure(code=failure_code))
        if failure_code is not None
        else research_outcome_from_patch(stage_patch)
    )
    card = tool_card_for_job_completion(binding, outcome)
    return card.model_dump(mode="json")
