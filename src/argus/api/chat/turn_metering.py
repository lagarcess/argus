"""Post-terminal settlement and evidence for a turn, as one step.

Discovery usage settles here. Research capacity is already claimed at its
provider boundary; its terminal sidecar is recorded here with the same turn
identity.
"""

from __future__ import annotations

from typing import Any

from argus.api.chat.discovery_evidence import settle_discovery_turn
from argus.api.chat.research_evidence import settle_research_turn


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
) -> None:
    settle_discovery_turn(
        usage=discovery_usage,
        user_id=user_id,
        is_guest=is_guest,
        client_identity=client_identity,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )
    settle_research_turn(
        runtime_result,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )
