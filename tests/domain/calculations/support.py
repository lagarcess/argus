"""Run a declared calculation the way chat and every re-run do: through its declaration."""

from __future__ import annotations

import asyncio
from typing import Any

from argus.domain.calculations import get_calculation_declarations
from argus.domain.tool_contracts import ToolCall, ToolResultCard
from argus.domain.tool_declaration import ToolDeclaration

_DECLARATIONS = {item.name: item for item in get_calculation_declarations()}


def declaration(name: str) -> ToolDeclaration:
    return _DECLARATIONS[name]


def run_calculation(name: str, arguments: dict[str, Any]) -> ToolResultCard:
    """Invoke and project the card exactly as the execute stage and recompute do."""
    item = declaration(name)
    call = ToolCall(tool_name=name, call_id=f"call-{name}", arguments=arguments)
    outcome = asyncio.run(item.invoke(call.arguments))
    return item.result_card(call=call, outcome=outcome, artifact_id=f"artifact-{name}")


def answer_value(card: ToolResultCard) -> float | int | str | bool | None:
    assert card.presentation.answer is not None, card.outcome
    return card.presentation.answer.value


def row_value(card: ToolResultCard, name: str) -> float | int | str | bool | None:
    return next(row.value for row in card.presentation.rows if row.name == name)
