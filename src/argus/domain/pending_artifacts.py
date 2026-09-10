"""Pending artifact liveness and guarded mutation, independent of its content.

The persisted message owns liveness. Adapters supply its metadata layout,
content assembly, storage and optional projection; this owner supplies the
same admission/edit race and consumption/restoration rules to every artifact.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

DEAD_ARTIFACT_STATES = frozenset({"cancelled", "canceled", "superseded", "consumed"})
CONSUMED_ARTIFACT_STATE = "consumed"
ACTIVE_ARTIFACT_STATE = "active"


@dataclass(frozen=True)
class PendingArtifactLayout:
    """Where an artifact stores its card and the shared reference envelopes."""

    card_key: str
    card_state_key: str
    reference_key: str
    references_key: str
    reference_type: str
    artifact_id: str | None = None


def _layout_cards(
    metadata: dict[str, Any], layout: PendingArtifactLayout
) -> list[dict[str, Any]]:
    value = metadata.get(layout.card_key)
    cards = value if isinstance(value, list) else [value]
    return [
        card
        for card in cards
        if isinstance(card, dict)
        and (layout.artifact_id is None or card.get("artifact_id") == layout.artifact_id)
    ]


@dataclass(frozen=True)
class PendingArtifactUpdate:
    """Adapter-built content and metadata to merge into the existing message."""

    content: str
    metadata: dict[str, Any]


class DeadPendingArtifactError(ValueError):
    """A consumed or closed artifact cannot be edited; nothing was written."""


def artifact_state_is_dead(value: Any) -> bool:
    return str(value or "").strip().casefold() in DEAD_ARTIFACT_STATES


def pending_artifact_state(
    metadata: dict[str, Any], *, layout: PendingArtifactLayout
) -> str:
    cards = _layout_cards(metadata, layout)
    value = cards[0].get(layout.card_state_key) if len(cards) == 1 else None
    return str(value or "").strip().casefold()


def pending_artifact_is_dead(
    metadata: dict[str, Any] | None, *, layout: PendingArtifactLayout
) -> bool:
    if not isinstance(metadata, dict):
        return False
    if artifact_state_is_dead(pending_artifact_state(metadata, layout=layout)):
        return True
    reference = metadata.get(layout.reference_key)
    return isinstance(reference, dict) and artifact_state_is_dead(
        reference.get("artifact_status")
    )


def stamp_pending_artifact(
    metadata: dict[str, Any], *, state: str, layout: PendingArtifactLayout
) -> dict[str, Any]:
    stamped = copy.deepcopy(metadata)
    for card in _layout_cards(stamped, layout):
        card[layout.card_state_key] = state
    reference = stamped.get(layout.reference_key)
    if isinstance(reference, dict):
        reference["artifact_status"] = state
    references = stamped.get(layout.references_key)
    if isinstance(references, list):
        for item in references:
            if (
                isinstance(item, dict)
                and item.get("artifact_type") == layout.reference_type
                and (
                    layout.artifact_id is None
                    or item.get("artifact_id") == layout.artifact_id
                )
            ):
                item["artifact_status"] = state
    return stamped


def _write_artifact_state(
    message: Any, *, state: str, layout: PendingArtifactLayout, write: Callable[..., Any]
) -> None:
    write(
        message_id=message.id,
        content=message.content,
        metadata=stamp_pending_artifact(message.metadata, state=state, layout=layout),
        expected_source_metadata=message.metadata,
        expected_latest_message_id=None,
    )


def consume_pending_artifact(
    *,
    layout: PendingArtifactLayout,
    load: Callable[[], Any | None],
    write: Callable[..., Any],
    conflict_error: type[Exception],
    can_consume: Callable[[dict[str, Any]], bool] | None = None,
) -> str:
    """Consume once, re-reading after a lost race before deciding again.

    Unreadable or unwritable legacy rows remain unstamped; adapters retain
    their existing admission fallback. A conflicting edit or stale admission
    basis returns ``stale_artifact`` and must not dispatch.
    """
    for _ in range(2):
        message = load()
        if message is None or not isinstance(message.metadata, dict):
            return "unstamped"
        if pending_artifact_is_dead(message.metadata, layout=layout):
            return "already_consumed"
        if can_consume is not None and not can_consume(message.metadata):
            return "stale_artifact"
        try:
            _write_artifact_state(
                message, state=CONSUMED_ARTIFACT_STATE, layout=layout, write=write
            )
            return "consumed"
        except conflict_error:
            continue
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning(
                "Artifact consumption stamp could not be written; "
                "proceeding unstamped with legacy liveness",
                message_id=message.id,
            )
            return "unstamped"
    return "stale_artifact"


def restore_pending_artifact(
    *,
    layout: PendingArtifactLayout,
    load: Callable[[], Any | None],
    write: Callable[..., Any],
    conflict_error: type[Exception],
) -> bool:
    """Only consumed artifacts can restore; cancellation and supersession win."""
    for _ in range(2):
        message = load()
        if message is None or not isinstance(message.metadata, dict):
            return False
        state = pending_artifact_state(message.metadata, layout=layout)
        if state == ACTIVE_ARTIFACT_STATE:
            return True
        if state != CONSUMED_ARTIFACT_STATE:
            return False
        try:
            _write_artifact_state(
                message, state=ACTIVE_ARTIFACT_STATE, layout=layout, write=write
            )
            return True
        except conflict_error:
            continue
        except Exception:  # noqa: BLE001
            break
    logger.warning("Could not restore the consumed artifact to active")
    return False


def apply_pending_artifact_update(
    *,
    layout: PendingArtifactLayout,
    source_message: Any,
    expected_source_metadata: dict[str, Any] | None,
    expected_latest_message_id: str | None,
    prepare: Callable[[], PendingArtifactUpdate | None],
    write: Callable[..., Any],
    metadata_extra: dict[str, Any] | None = None,
    after_write: Callable[[], None] | None = None,
) -> Any | None:
    """Refuse dead artifacts and preserve both row and activity write guards.

    Preparation happens only after the liveness check. A losing write raises
    its store's conflict error and never projects stale data into a checkpoint.
    """
    if pending_artifact_is_dead(source_message.metadata, layout=layout) or (
        expected_source_metadata is not None
        and pending_artifact_is_dead(expected_source_metadata, layout=layout)
    ):
        raise DeadPendingArtifactError(
            "The artifact is no longer pending; nothing was written."
        )
    prepared = prepare()
    if prepared is None:
        return None
    metadata = {**source_message.metadata, **prepared.metadata}
    for key, value in (metadata_extra or {}).items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    updated = write(
        message_id=source_message.id,
        content=prepared.content,
        metadata=metadata,
        expected_source_metadata=expected_source_metadata,
        expected_latest_message_id=expected_latest_message_id,
    )
    if after_write is not None:
        after_write()
    return updated
