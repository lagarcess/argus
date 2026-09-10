"""Declared calls publish the shared answer policy without weakening typed facts."""

from __future__ import annotations

import pytest
from argus.agent_runtime.research_tools import (
    get_research_declarations,
)
from argus.domain.research.contracts import (
    ResearchNamePair,
    ResearchSource,
)
from argus.domain.tool_contracts import ToolCall

from tests.research.test_registered_research_tools import _context, _packet, _wire


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("fast_quote", {"symbols": ["AAPL"]}),
        ("balanced_lookup", {"symbols": ["AAPL"]}),
        ("screening", {"criteria": ["has a quoted share price"]}),
    ],
)
@pytest.mark.parametrize(
    "row_mode,typed_answer", [("none", False), ("none", True), ("unsourced", True)]
)
async def test_inline_declaration_publishes_the_shared_answer_and_optional_rows(
    monkeypatch, tool_name, arguments, row_mode, typed_answer
) -> None:
    packet = _packet()
    packet = packet.model_copy(
        update={
            "name_pairs": (ResearchNamePair(symbol="AAPL", name="Apple"),),
            "typed_answer": typed_answer,
            "rows": (),
            "unsourced_rows": (
                (packet.rows[0].model_copy(update={"source_url": None}),)
                if row_mode == "unsourced"
                else ()
            ),
        }
    )
    client = _wire(monkeypatch, packet, packet)
    context = _context()
    declaration = next(
        item for item in get_research_declarations() if item.name == tool_name
    )
    call = ToolCall(
        tool_name=tool_name,
        call_id="published-read",
        arguments={"request": "Read the quoted public-market facts", **arguments},
    )

    outcome = await declaration.invoke(call.arguments, context=context)

    assert outcome.status == "succeeded"
    assert outcome.result["status"] == "completed"
    assert outcome.result["rows"] == [
        row.model_dump(mode="json") for row in (*packet.rows, *packet.unsourced_rows)
    ]
    published = context.stage_result.stage_patch["assistant_response"]
    assert "degraded" not in context.stage_result.stage_patch["research"]
    assert outcome.result["answer"] == published
    assert published.startswith(packet.answer_markdown)
    card = declaration.result_card(call=call, outcome=outcome, artifact_id="read-card")
    assert card.presentation.narrative == published
    assert card.presentation.sources == [
        ResearchSource.model_validate(source)
        for source in context.stage_result.stage_patch["research"]["sources"]
    ]
    assert [source.url for source in card.presentation.sources] == [
        source.url for source in packet.sources
    ]
    if row_mode == "unsourced":
        assert outcome.result["rows"][0]["source_url"] is None
        assert len(published) > len(packet.answer_markdown)
    assert client.calls


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "invalid_row_update", [{"value": "unknown"}, {"value": float("nan")}, {"unit": "ZZZ"}]
)
async def test_optional_rows_still_fail_the_callable_contract_when_invalid(
    monkeypatch, invalid_row_update
) -> None:
    # A malformed stored packet must not evade the same return validation
    # merely because a published answer is allowed to have no numeric rows.
    packet = _packet()
    packet = packet.model_copy(
        update={"rows": (packet.rows[0].model_copy(update=invalid_row_update),)}
    )
    _wire(monkeypatch, packet)
    declaration = next(
        item for item in get_research_declarations() if item.name == "fast_quote"
    )

    outcome = await declaration.invoke(
        {"request": "Read AAPL's quote", "symbols": ["AAPL"]}, context=_context()
    )

    assert outcome.status == "unavailable"
    assert outcome.result is None
    assert outcome.failure.code == "tool_execution_failed"
