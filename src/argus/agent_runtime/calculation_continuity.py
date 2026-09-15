"""Read prior calculation arguments only from assistant artifact history."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from loguru import logger

from argus.domain.calculation_turn_facts import CALCULATION_HISTORY_KEY
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.capability_registry import get_tool_catalog


def prior_calculation_arguments(
    request: AnswerCalculation, history: Sequence[Any]
) -> dict[str, Any] | None:
    """An explicit artifact reference is scoped to the loaded conversation.

    No positional or name fallback: two cards may compute the same primitive.
    The latest revision of the referenced card owns its inputs.
    """
    if not request.prior_artifact_id:
        return None
    declaration = get_tool_catalog().get(request.kind)
    supplied = {item.name for item in request.inputs if item.value is not None}
    if (
        declaration is None
        or set(request.updated_fields) - set(declaration.policy.editable_fields)
        or set(request.updated_fields) - supplied
    ):
        return None
    for turn in reversed(history):
        role = (
            turn.get("role") if isinstance(turn, Mapping) else getattr(turn, "role", None)
        )
        content = (
            turn.get("content")
            if isinstance(turn, Mapping)
            else getattr(turn, "content", None)
        )
        if role != "assistant" or not isinstance(content, str):
            continue
        try:
            document = json.loads(content)
        except (ValueError, TypeError):
            continue
        if not isinstance(document, dict):
            continue
        cards = document.get(CALCULATION_HISTORY_KEY)
        if not isinstance(cards, list):
            continue
        for card in cards:
            if (
                not isinstance(card, dict)
                or card.get("artifact_id") != request.prior_artifact_id
            ):
                continue
            if card.get("kind") != request.kind or card.get("status") != "succeeded":
                return None
            result = card.get("result") or {}
            if result.get("solved_field") != request.solve_for:
                return None
            arguments = card.get("arguments")
            return dict(arguments) if isinstance(arguments, Mapping) else None
    return None


def normalize_calculation_edits(
    request: AnswerCalculation, notes: list[str]
) -> AnswerCalculation:
    """updated_fields owns which supplied values are explicit user changes.

    Pending and completed cards must agree on that declaration. A second source
    label cannot silently replace an explicit edit with the stored assumption.
    """
    changed = {
        item.name
        for item in request.inputs
        if item.name in request.updated_fields
        and item.value is not None
        and item.source != "user"
    }
    if not changed:
        return request
    code = "calculation_edit_source_normalized"
    if code not in notes:
        notes.append(code)
    logger.info(
        "Calculation edit sources normalized", fields=sorted(changed), reason_code=code
    )
    return request.model_copy(
        update={
            "inputs": [
                item.model_copy(
                    update={"source": "user", "source_url": None, "as_of": None}
                )
                if item.name in changed
                else item
                for item in request.inputs
            ]
        }
    )
