"""One typed reachability decision for artifact readers, never prose matching."""

from collections.abc import Mapping
from typing import Any, Literal

ArtifactPresentationKind = Literal["result", "breakdown", "assumptions", "confirmation"]


def artifact_presentation_kind(
    metadata: Mapping[str, Any],
) -> ArtifactPresentationKind | None:
    intent = metadata.get("response_intent")
    intent_kind = intent.get("kind") if isinstance(intent, Mapping) else None
    if intent_kind == "artifact_assumptions":
        return "assumptions"
    action = metadata.get("chat_action")
    action_type = action.get("type") if isinstance(action, Mapping) else action
    if (
        intent_kind == "result_breakdown"
        or action_type == "show_breakdown"
        or "result_breakdown_source" in metadata
    ):
        return "breakdown"
    if any(isinstance(metadata.get(key), Mapping) for key in ("result_card", "run")):
        return "result"
    if (
        "result_fact_bank" in metadata
        and intent_kind in (None, "result")
        and action_type != "save_strategy"
    ):
        return "result"
    if (
        metadata.get("result_run_id")
        and metadata.get("conversation_mode") == "result_review"
        and action_type != "save_strategy"
    ):
        return "result"
    if "confirmation_card" in metadata:
        return "confirmation"
    return None
