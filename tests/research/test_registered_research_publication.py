"""Declared calls publish the shared answer policy without weakening typed facts."""

from __future__ import annotations

import pytest
from argus.agent_runtime.research_tools import (
    ResearchToolResult,
    get_research_declarations,
    research_result_from_patch,
)
from argus.domain.research.contracts import (
    ResearchNamePair,
    ResearchPacket,
    ResearchSource,
)
from argus.domain.research.evidence_policy import build_research_evidence_policy
from argus.domain.tool_contracts import ToolCall
from pydantic import ValidationError

from tests.research.test_registered_research_tools import _context, _packet, _wire


def test_packet_owns_the_published_row_projection_without_a_new_wire_field() -> None:
    packet = _packet()
    uncited = packet.rows[0].model_copy(update={"source_url": None})
    packet = packet.model_copy(update={"unsourced_rows": (uncited,)})

    assert packet.published_rows == (*packet.rows, uncited)
    assert packet.published_rows[0] is packet.rows[0]
    assert packet.published_rows[1] is packet.unsourced_rows[0]
    assert "published_rows" not in packet.model_dump()
    assert "published_rows" not in ResearchPacket.model_json_schema()["properties"]


@pytest.mark.parametrize("has_policy", [False, True])
def test_result_preserves_the_runtime_evidence_policy_and_legacy_absence(has_policy):
    packet = _packet()
    policy = build_research_evidence_policy(
        question_kind=None,
        data_class="fundamentals",
        period_start_date=packet.retrieved_at.date(),
        question_as_of_date=packet.retrieved_at.date(),
    )
    sidecar = {"evidence_policy": policy.model_dump(mode="json")} if has_policy else {}

    result = research_result_from_patch(
        {"assistant_response": packet.answer_markdown, "research": sidecar}
    )

    assert result.evidence_policy == (policy if has_policy else None)
    if has_policy:
        assert (
            result.model_dump(mode="json")["evidence_policy"]
            == sidecar["evidence_policy"]
        )
        with pytest.raises(ValidationError):
            ResearchToolResult(status="pending", evidence_policy=policy)


def test_result_rejects_an_invalid_evidence_policy_instead_of_ignoring_it() -> None:
    policy = build_research_evidence_policy(question_kind=None).model_dump(mode="json")
    policy["max_age_seconds"] = -1.0
    with pytest.raises(ValidationError):
        research_result_from_patch(
            {
                "assistant_response": _packet().answer_markdown,
                "research": {"evidence_policy": policy},
            }
        )


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
        row.model_dump(mode="json") for row in packet.published_rows
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
