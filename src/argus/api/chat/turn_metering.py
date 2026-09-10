"""Post-terminal settlement and evidence for a turn, as one step.

Discovery usage settles here. Research capacity is already claimed at its
provider boundary; its terminal sidecar is recorded here with the same turn
identity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from argus.api.chat.discovery_evidence import settle_discovery_turn
from argus.api.chat.research_evidence import settle_research_turn

if TYPE_CHECKING:
    from argus.api.chat.tool_results import ToolExecutionEffect


def settle_metered_turn(
    runtime_result: dict[str, Any],
    *,
    discovery_usage: Any,
    user_id: str,
    is_guest: bool,
    client_identity: str | None,
    conversation_id: str | None,
    message_id: str | None,
    request_id: str | None,
    tool_call_id: str | None = None,
    tool_effects: list[ToolExecutionEffect] | None = None,
) -> None:
    sources: list[tuple[dict[str, Any], Any, str | None]] = (
        [
            (
                effect.stage_patch,
                effect.stage_patch.get("discovery_usage"),
                effect.call_id,
            )
            for effect in tool_effects
        ]
        if tool_effects
        else [(runtime_result, discovery_usage, tool_call_id)]
    )
    for result, usage, call_id in sources:
        settle_discovery_turn(
            usage=usage,
            user_id=user_id,
            is_guest=is_guest,
            client_identity=client_identity,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
        )
        settle_research_turn(
            result,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            **({"tool_call_id": call_id} if call_id is not None else {}),
        )
