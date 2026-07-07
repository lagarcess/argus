from __future__ import annotations

from pydantic import ValidationError

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.state.models import (
    ArtifactActionRecoveryFacts,
    ResponseIntent,
)


def artifact_action_recovery_message(intent: ResponseIntent) -> str | None:
    if intent.kind != "artifact_action_recovery":
        return None
    facts = _artifact_action_recovery_facts(intent)
    if facts is None:
        return recovery_message("artifact_action_invalid_state")
    if facts.status == "stale":
        return recovery_message("artifact_action_retry_stale")
    if facts.status == "missing_artifact_id":
        return recovery_message("artifact_action_retry_missing_artifact_id")
    if facts.status == "missing_payload":
        return recovery_message("artifact_action_retry_missing_payload")
    if facts.status == "non_retryable":
        message = facts.user_safe_message
        return recovery_message(
            "artifact_action_retry_non_retryable",
            user_safe_message=message.strip()
            if isinstance(message, str) and message.strip()
            else "",
        )
    if facts.status == "rebuilt_confirmation":
        return recovery_message("artifact_action_retry_rebuilt_confirmation")
    return recovery_message("artifact_action_retry_inactive")


def _artifact_action_recovery_facts(
    intent: ResponseIntent,
) -> ArtifactActionRecoveryFacts | None:
    try:
        return ArtifactActionRecoveryFacts.model_validate(intent.facts)
    except ValidationError:
        return None
