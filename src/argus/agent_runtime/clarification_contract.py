from __future__ import annotations

from argus.agent_runtime.recovery_messages import recovery_message

OFFLINE_CLARIFICATION_FALLBACK = recovery_message(
    "clarification_generation_unavailable",
    language="en",
)


def offline_clarification_fallback(*, language: str | None = None) -> str:
    return recovery_message(
        "clarification_generation_unavailable",
        language=language,
    )
