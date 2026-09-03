"""Research work and outcome, derived from the settled research sidecar.

``capability_class`` is the research work kind, independent of execution shape.
``product_capability`` is the separate guest funnel product activity taxonomy.
See docs/API_CONTRACT.md section 17.1 for the naming and migration contract.
"""

from __future__ import annotations

import asyncio
from typing import Any, get_args

from argus.domain.research.contracts import CapabilityClass
from argus.observability.envelope import build_event_envelope, capture_event
from argus.observability.product_events import actor_hash_for_user


def capture_research_turn_event(
    *,
    research: dict[str, Any],
    user_id: str,
    conversation_id: str | None,
    message_id: str | None,
) -> None:
    """Emit bounded dimensions; never send the sidecar or spend ledger to analytics."""
    capability_class = research.get("capability_class")
    if capability_class not in get_args(CapabilityClass):
        capability_class = "unknown"
    usage = research.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    cache_status = usage.get("cache_status")
    if cache_status not in ("miss", "hit", "bypass"):
        cache_status = "unknown"
    degraded = research.get("degraded")
    is_degraded = isinstance(degraded, dict) and bool(degraded.get("code"))
    envelope = build_event_envelope(
        event_type="research",
        event_action="failed" if is_degraded else "completed",
        feature_area=(
            "research_deep" if research.get("shape") == "thorough" else "research_light"
        ),
        actor_hash=actor_hash_for_user(user_id),
        conversation_id=conversation_id,
        message_id=message_id,
        status="degraded" if is_degraded else "completed",
        attributes={
            "capability_class": capability_class,
            "cache_status": cache_status,
        },
    )
    # Settlement can run inside the streaming event loop. Build the snapshot
    # now, but let the existing bounded, best-effort sink do network I/O off-loop.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        capture_event(envelope)
    else:
        loop.create_task(asyncio.to_thread(capture_event, envelope))
