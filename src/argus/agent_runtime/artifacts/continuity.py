from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from argus.agent_runtime.artifacts.drafts import (
    draft_from_confirmation_payload,
    draft_from_failed_launch_payload,
    draft_from_result_metadata,
)
from argus.agent_runtime.artifacts.patches import ArtifactPatch, apply_artifact_patch
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
)

ArtifactAnchorKind = Literal[
    "confirmation",
    "result",
    "saved_strategy",
    "failed_action",
    "none",
]


@dataclass(frozen=True)
class ArtifactAnchor:
    kind: ArtifactAnchorKind
    artifact_id: str | None
    draft: StrategySummary | None
    metadata: dict[str, Any] = field(default_factory=dict)


def resolve_artifact_anchor(
    *,
    snapshot: TaskSnapshot | None,
    action_payload: dict[str, Any] | None = None,
    retrying_failed_action: bool = False,
) -> ArtifactAnchor:
    if snapshot is None:
        return _empty_anchor()
    payload = dict(action_payload or {})
    if retrying_failed_action:
        return _failed_action_anchor(snapshot.latest_failed_action_reference)

    run_id = _payload_id(payload, "run_id", "runId")
    if run_id:
        return _matching_result_anchor(snapshot.latest_backtest_result_reference, run_id)

    confirmation_id = _payload_id(payload, "confirmation_id", "artifact_id")
    if confirmation_id:
        return _matching_confirmation_anchor(
            snapshot.active_confirmation_reference,
            confirmation_id,
        )

    if snapshot.active_confirmation_reference is not None:
        return _confirmation_anchor(snapshot.active_confirmation_reference)
    if snapshot.latest_backtest_result_reference is not None:
        return _result_anchor(snapshot.latest_backtest_result_reference)
    if snapshot.saved_strategy_reference is not None:
        return _saved_strategy_anchor(snapshot.saved_strategy_reference)
    return _empty_anchor()


def apply_patch_to_anchor(
    anchor: ArtifactAnchor,
    patch: ArtifactPatch,
) -> StrategySummary | None:
    if anchor.draft is None:
        return None
    return apply_artifact_patch(anchor.draft, patch)


def _matching_confirmation_anchor(
    reference: ArtifactReference | None,
    requested_id: str,
) -> ArtifactAnchor:
    if reference is None:
        return _empty_anchor()
    active_id = _confirmation_reference_id(reference)
    if active_id != requested_id:
        return _empty_anchor()
    return _confirmation_anchor(reference)


def _matching_result_anchor(
    reference: ArtifactReference | None,
    requested_id: str,
) -> ArtifactAnchor:
    if reference is None or reference.artifact_id != requested_id:
        return _empty_anchor()
    return _result_anchor(reference)


def _confirmation_anchor(reference: ArtifactReference) -> ArtifactAnchor:
    metadata = dict(reference.metadata)
    payload = _dict(metadata.get("confirmation_payload"))
    return ArtifactAnchor(
        kind="confirmation",
        artifact_id=_confirmation_reference_id(reference),
        draft=draft_from_confirmation_payload(payload),
        metadata=metadata,
    )


def _result_anchor(reference: ArtifactReference) -> ArtifactAnchor:
    metadata = dict(reference.metadata)
    return ArtifactAnchor(
        kind="result",
        artifact_id=reference.artifact_id,
        draft=draft_from_result_metadata(metadata),
        metadata=metadata,
    )


def _saved_strategy_anchor(reference: ArtifactReference) -> ArtifactAnchor:
    metadata = dict(reference.metadata)
    strategy = _dict(metadata.get("strategy"))
    return ArtifactAnchor(
        kind="saved_strategy",
        artifact_id=reference.artifact_id,
        draft=StrategySummary.model_validate(strategy) if strategy else None,
        metadata=metadata,
    )


def _failed_action_anchor(reference: ArtifactReference | None) -> ArtifactAnchor:
    if reference is None or reference.artifact_kind != "failed_action":
        return _empty_anchor()
    metadata = dict(reference.metadata)
    launch_payload = _dict(metadata.get("launch_payload"))
    if not launch_payload:
        return _empty_anchor()
    return ArtifactAnchor(
        kind="failed_action",
        artifact_id=reference.artifact_id,
        draft=draft_from_failed_launch_payload(launch_payload),
        metadata=metadata,
    )


def _confirmation_reference_id(reference: ArtifactReference) -> str:
    metadata = dict(reference.metadata)
    candidate = _string(metadata.get("confirmation_id"))
    return candidate or reference.artifact_id


def _payload_id(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        candidate = _string(payload.get(key))
        if candidate:
            return candidate
    return None


def _string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _empty_anchor() -> ArtifactAnchor:
    return ArtifactAnchor(kind="none", artifact_id=None, draft=None, metadata={})
