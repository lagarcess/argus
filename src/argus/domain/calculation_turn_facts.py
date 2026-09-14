"""Compact runtime history derived from the calculation cards a reader saw."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from argus.domain.tool_contracts import ToolResultCard

CALCULATION_HISTORY_KEY = "calculation_cards"


def calculation_turn_facts(metadata: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(metadata, Mapping):
        return []
    raw_cards = metadata.get("tool_result_cards")
    if not isinstance(raw_cards, list):
        return []
    from argus.domain.calculations import get_calculation_declarations

    kinds = {item.name for item in get_calculation_declarations()}
    template = metadata.get("answer_text_template")
    names = template.get("cards", {}) if isinstance(template, Mapping) else {}
    names = names if isinstance(names, Mapping) else {}
    facts = []
    for raw in raw_cards:
        try:
            card = ToolResultCard.model_validate(raw)
        except (ValidationError, TypeError):
            continue
        if card.tool_name not in kinds or card.artifact_state != "active":
            continue
        facts.append(
            {
                "artifact_id": card.artifact_id,
                "name": next(
                    (name for name, value in names.items() if value == card.artifact_id),
                    "",
                ),
                "kind": card.tool_name,
                "input_revision": card.input_revision,
                "arguments": card.arguments,
                "status": card.outcome.status,
                # Paths and schedules are visual detail, not another copy of the
                # scalar result the next calculation needs.
                "result": {
                    name: value
                    for name, value in (card.outcome.result or {}).items()
                    if not isinstance(value, (list, dict))
                },
                "failure": card.outcome.failure.model_dump(mode="json")
                if card.outcome.failure
                else None,
            }
        )
    return facts


def calculation_turn_history_text(facts: list[dict[str, Any]], content: str) -> str:
    # Keep qualitative context (for example a spending goal); numeric inputs
    # and results have their own structured owner alongside it.
    return json.dumps(
        {CALCULATION_HISTORY_KEY: facts, "answer_text": content},
        separators=(",", ":"),
        ensure_ascii=False,
    )
