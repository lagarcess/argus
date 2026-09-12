"""A computed answer's dossier, projected from the message that owns it.

Nothing here calls a model or retrieval: the card on the message already
holds what Argus used, with its sources, and what came out; the decision
comes from ``decision_notes``; the question is the owner's own user message
just before the answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from argus.api.decision_contract import DecisionActionAvailability, DecisionState
from argus.api.schemas import AnswerDecisionAction, AnswerDossier, SearchDossierDecision
from argus.domain.decision_attachment import computation_from_message_metadata
from argus.domain.run_dossiers import message_metadata, row_activity, text
from argus.domain.tool_contracts import ToolResultCard

_DECISION_STATES: tuple[DecisionState, ...] = (
    "promising",
    "watching",
    "rejected",
    "revisit_later",
)
_MAX_ASKED = 500


def computed_answer_card(message: Mapping[str, Any]) -> ToolResultCard | None:
    """The card the answer's declared computation names, or ``None``."""
    metadata = message_metadata(message)
    computation = computation_from_message_metadata(metadata)
    if computation is None or message.get("role") != "assistant":
        return None
    raw_cards = metadata.get("tool_result_cards")
    if not isinstance(raw_cards, list):
        return None
    for raw in raw_cards:
        try:
            card = ToolResultCard.model_validate(raw)
        except ValueError:
            continue
        if card.tool_name == computation.kind and card.arguments == computation.inputs:
            return card
    return None


def latest_computed_answer(
    messages: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ToolResultCard] | None:
    """The newest assistant message whose marker and card agree."""
    ordered = sorted(
        messages,
        key=lambda row: (row_activity(row), text(row.get("id")) or ""),
        reverse=True,
    )
    for message in ordered:
        card = computed_answer_card(message)
        if card is not None:
            return message, card
    return None


def question_before(
    answer: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]
) -> str | None:
    """The owner's user message just before the answer; owner-authored text only."""
    answer_key = (row_activity(answer), text(answer.get("id")) or "")
    earlier = [
        row
        for row in messages
        if row.get("role") == "user"
        and (row_activity(row), text(row.get("id")) or "") < answer_key
    ]
    if not earlier:
        return None
    latest = max(earlier, key=lambda row: (row_activity(row), text(row.get("id")) or ""))
    asked = text(latest.get("content"))
    return asked[:_MAX_ASKED] if asked else None


def current_answer_decision(
    message_id: str, decisions: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    return max(
        (row for row in decisions if text(row.get("source_message_id")) == message_id),
        key=lambda row: (row_activity(row), text(row.get("id")) or ""),
        default=None,
    )


def project_answer_dossier(
    *,
    message: Mapping[str, Any],
    card: ToolResultCard,
    asked: str | None,
    decision: Mapping[str, Any] | None,
    decision_action_availability: DecisionActionAvailability | None,
) -> AnswerDossier:
    message_id = text(message.get("id"))
    conversation_id = text(message.get("conversation_id"))
    if message_id is None or conversation_id is None:
        raise ValueError("An answer dossier needs its message and conversation ids.")
    computation = computation_from_message_metadata(message_metadata(message))
    assert computation is not None  # computed_answer_card already required it.
    state = decision.get("decision_state") if decision is not None else None
    typed_state = cast(DecisionState, state) if state in _DECISION_STATES else None
    note = decision.get("note") if decision is not None else None
    bounded_note = note[:2000] if isinstance(note, str) else None
    actions = (
        [
            AnswerDecisionAction(
                availability=decision_action_availability,
                message_id=message_id,
                decision_state=typed_state,
                note=bounded_note,
            )
        ]
        if decision_action_availability is not None
        else []
    )
    return AnswerDossier(
        message_id=message_id,
        conversation_id=conversation_id,
        asked=asked,
        computed_at=row_activity(message),
        kind=computation.kind,
        symbols=list(computation.symbols),
        card=card.model_dump(mode="json"),
        decision=(
            SearchDossierDecision(state=typed_state, note=bounded_note)
            if typed_state is not None
            else None
        ),
        decision_id=text(decision.get("id")) if decision is not None else None,
        actions=actions,
    )


def computed_symbols(message: Mapping[str, Any]) -> list[str]:
    computation = computation_from_message_metadata(message_metadata(message))
    return list(computation.symbols) if computation is not None else []
