from __future__ import annotations

from typing import Any


def preserve_typed_discovery_act(
    *,
    primary_discovery: Any | None,
    audited: Any,
) -> Any:
    """Audits repair strategy shape; they never own act demotion. A primary
    parse that typed asset_discovery with its payload keeps the act."""
    if primary_discovery is None or audited.semantic_turn_act == "asset_discovery":
        return audited
    return audited.model_copy(
        update={
            "semantic_turn_act": "asset_discovery",
            "asset_discovery": primary_discovery,
            "intent": "conversation_followup",
            "requires_clarification": False,
            "missing_required_fields": [],
            "reason_codes": list(
                dict.fromkeys(
                    [*audited.reason_codes, "typed_discovery_act_restored"]
                )
            ),
        }
    )
