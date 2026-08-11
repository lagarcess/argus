"""Post-terminal settlement of a turn's meters, as one step.

Discovery and research settle together, from the same turn identity, at the
same moment. Keeping them in one call is what stops the two from drifting
apart: a turn that charges one meter against a visitor and the other against a
user id is the bug this shape exists to prevent.
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
    guest_research_visitor_key: str | None,
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
        guest_visitor_key=guest_research_visitor_key,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )
