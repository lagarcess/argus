"""Read-time decision state for messages, from the rows that own it.

``decision_notes`` is the one owner of whether an answer has a decision. A
result card's stored stamp and a computed answer's message metadata are
transport copies, so the transcript read derives the current decision from
the owner and overlays it, never trusting a copy that may have missed its
write or been overtaken by a later one. One bounded load, no persistence
changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from argus.api.decision_contract import DecisionNote
from argus.api.schemas import Message
from argus.domain.decision_attachment import (
    DECISION_NOTE_ID_METADATA_KEY,
    DECISION_STATE_METADATA_KEY,
    computation_from_message_metadata,
    decision_message_metadata,
)
from argus.domain.evidence import attach_decision_to_result_card

LoadDecisions = Callable[[list[str], list[str]], Mapping[str, DecisionNote] | None]
"""Current decisions keyed by attachment id: evidence artifact ids and message ids.
A loader answers ``None`` when the owner cannot be read at all."""


def _result_card_artifact_id(metadata: Mapping[str, Any]) -> str | None:
    card = metadata.get("result_card")
    if not isinstance(card, Mapping):
        return None
    artifact_id = card.get("evidence_artifact_id")
    return artifact_id if isinstance(artifact_id, str) and artifact_id else None


def _without_decision_stamp(metadata: Mapping[str, Any]) -> dict[str, Any]:
    cleared = {
        key: value
        for key, value in metadata.items()
        if key not in (DECISION_NOTE_ID_METADATA_KEY, DECISION_STATE_METADATA_KEY)
    }
    card = cleared.get("result_card")
    if isinstance(card, Mapping):
        cleared["result_card"] = {
            key: value
            for key, value in card.items()
            if key not in (DECISION_NOTE_ID_METADATA_KEY, DECISION_STATE_METADATA_KEY)
        }
    return cleared


def repair_message_decisions(
    messages: list[Message],
    *,
    load_decisions: LoadDecisions,
) -> list[Message]:
    """Overlay each answer's current decision from the rows that own it."""
    artifact_ids: dict[str, str] = {}
    answer_ids: set[str] = set()
    for message in messages:
        if message.role != "assistant":
            continue
        metadata = message.metadata or {}
        artifact_id = _result_card_artifact_id(metadata)
        if artifact_id is not None:
            artifact_ids[message.id] = artifact_id
        if computation_from_message_metadata(metadata) is not None:
            answer_ids.add(message.id)
    if not artifact_ids and not answer_ids:
        return messages
    decisions = load_decisions(sorted(set(artifact_ids.values())), sorted(answer_ids))
    if decisions is None:
        # The owner is unreadable, so the transcript keeps the copy it has
        # rather than presenting a decided answer as undecided.
        return messages
    repaired: list[Message] = []
    for message in messages:
        artifact_id = artifact_ids.get(message.id)
        if artifact_id is None and message.id not in answer_ids:
            repaired.append(message)
            continue
        metadata = _without_decision_stamp(message.metadata or {})
        decision = decisions.get(artifact_id) if artifact_id is not None else None
        if decision is not None and decision.evidence_artifact_id == artifact_id:
            card = metadata.get("result_card")
            if isinstance(card, Mapping):
                metadata["result_card"] = attach_decision_to_result_card(
                    dict(card),
                    decision_id=decision.id,
                    decision_state=decision.decision_state,
                )
            metadata = decision_message_metadata(metadata, decision=decision)
        answer_decision = decisions.get(message.id) if message.id in answer_ids else None
        if (
            answer_decision is not None
            and answer_decision.source_message_id == message.id
        ):
            metadata = decision_message_metadata(metadata, decision=answer_decision)
        repaired.append(message.model_copy(update={"metadata": metadata}))
    return repaired


def owned_message_decisions(
    messages: list[Message],
    *,
    user_id: str,
) -> list[Message]:
    from loguru import logger

    from argus.api import state as api_state

    def load_decisions(
        artifact_ids: list[str], message_ids: list[str]
    ) -> Mapping[str, DecisionNote] | None:
        if api_state.supabase_gateway is not None:
            try:
                return api_state.supabase_gateway.current_decisions_for_attachments(
                    user_id=user_id,
                    artifact_ids=artifact_ids,
                    message_ids=message_ids,
                )
            except Exception:
                logger.warning("Current decisions unavailable during reader projection")
                return None
        wanted_artifacts = set(artifact_ids)
        wanted_messages = set(message_ids)
        current: dict[str, DecisionNote] = {}
        for decision in api_state.store.decision_notes.values():
            if api_state.store.decision_note_owners.get(decision.id) != user_id:
                continue
            if decision.evidence_artifact_id in wanted_artifacts:
                current[decision.evidence_artifact_id] = _latest(
                    current.get(decision.evidence_artifact_id), decision
                )
            if decision.source_message_id in wanted_messages:
                current[decision.source_message_id] = _latest(
                    current.get(decision.source_message_id), decision
                )
        return current

    return repair_message_decisions(messages, load_decisions=load_decisions)


def _latest(current: DecisionNote | None, candidate: DecisionNote) -> DecisionNote:
    if current is None or (candidate.updated_at, candidate.id) > (
        current.updated_at,
        current.id,
    ):
        return candidate
    return current
