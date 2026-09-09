"""Cited research entities and executable asset identities must agree."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.discovery.validation import resolution_matches_named_asset
from argus.agent_runtime.research_rows import verified_peers
from argus.agent_runtime.research_tools import research_outcome_from_patch
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.research.contracts import ResearchNamePair
from argus.domain.tool_contracts import ToolCall, ToolResultCard

from tests.research.conftest import (
    agent_response,
    educational_interpretation,
    retrieved_row,
    typed_answer_text,
    wire_grounded_client,
)
from tests.research.test_registered_research_tools import _context, _packet


@pytest.mark.parametrize("source_name", ["NVIDIA", "Nvidia Corp"])
@pytest.mark.parametrize(
    "provider_name,expected",
    [("NVIDIA Corporation", True), ("NVIDIA Technologies Corporation", False)],
)
def test_listing_name_normalization_requires_the_same_named_entity(
    source_name, provider_name, expected
) -> None:
    asset = ResolvedAsset(
        canonical_symbol="NVDA",
        asset_class="equity",
        name=provider_name,
        raw_symbol="NVDA",
    )
    assert (
        resolution_matches_named_asset(
            display_name=source_name,
            symbol_guess=asset.canonical_symbol,
            resolved=asset,
            asset_class=asset.asset_class,
            asset_class_hint=None,
        )
        is expected
    )


@pytest.fixture
def valvoline_catalog(monkeypatch):
    """The real collision captured in the registry A/B, without provider I/O."""
    asset = ResolvedAsset(
        canonical_symbol="VVV",
        asset_class="equity",
        name="Valvoline Inc.",
        raw_symbol="VVV",
    )
    history_probes = []

    def resolve(symbol):
        if symbol != asset.canonical_symbol:
            raise ValueError("invalid_symbol")
        return asset

    def history(symbol, asset_class):
        history_probes.append((symbol, asset_class))
        return SimpleNamespace(is_tradable=True)

    monkeypatch.setattr("argus.domain.market_data.resolve_asset", resolve)
    monkeypatch.setattr("argus.domain.market_data.tradable_history", history)
    monkeypatch.setattr(
        "argus.agent_runtime.research_rows._earliest_available",
        lambda *_: date(2020, 1, 2),
    )
    return asset, history_probes


@pytest.mark.parametrize(
    "names",
    [
        ("VVV", "Venice Token"),
        ("Venice Token", "VVV"),
        ("Valvoline Inc.", "Venice Token", "VVV"),
    ],
)
def test_bare_ticker_cannot_override_a_contradicted_named_entity(
    valvoline_catalog, names
) -> None:
    asset, history_probes = valvoline_catalog
    candidates = [
        ResearchNamePair(symbol=asset.canonical_symbol, name=name) for name in names
    ]

    assert verified_peers(candidates, exclude=set()) == []
    assert history_probes == [], "identity must agree before probing testability"


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "subject,publisher,can_offer_test",
    [
        (
            "Venice Token",
            "https://www.coingecko.com/en/highlights/trending-crypto",
            False,
        ),
        (
            "Valvoline Inc.",
            "https://www.nasdaq.com/market-activity/stocks/vvv",
            True,
        ),
    ],
)
async def test_screening_keeps_cited_figures_and_only_offers_the_same_entity(
    monkeypatch, valvoline_catalog, subject, publisher, can_offer_test
) -> None:
    asset, _ = valvoline_catalog
    row = retrieved_row(
        subject=subject,
        symbol=asset.canonical_symbol,
        label="trending search rank",
        value=1.0,
        kind="count",
        unit="rank",
        source_url=publisher,
    )
    answer = f"{row['subject']} ({row['symbol']}): {row['label']} {row['value']}."
    transport = wire_grounded_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(answer, [row]),
                tickers=[asset.canonical_symbol],
                # A bare metadata pair must not erase the row's named entity.
                lookup_rows=[("VVV", "VVV", "VVV")],
                sources=[publisher],
            )
        ],
    )
    context = _context()
    for call_id in ("retrieved-screen", "cached-screen"):
        call = ToolCall(
            tool_name="screening",
            call_id=call_id,
            arguments={"request": "Read the current screen", "criteria": ["trending"]},
        )
        context.state.tool_calls = [call]
        result = await execute_tool_calls_async(
            state=context.state, tool=None, user=context.user
        )
        card = ToolResultCard.model_validate(
            result.stage_patch["final_response_payload"]["tool_result_cards"][0]
        )
        effect = result.stage_patch["tool_effects"][0]["stage_patch"]
        assert card.outcome.status == "succeeded"
        assert card.outcome.result["rows"] == [row]
        assert card.presentation.answer.value == row["value"]
        assert card.presentation.narrative == answer
        assert card.presentation.sources[0].url == publisher
        if can_offer_test:
            assert card.outcome.result["subjects"] == [
                {"name": asset.name, "symbol": asset.canonical_symbol}
            ]
            assert effect["next_experiments"]["rows"][0]["kind"] == "research_test_single"
        else:
            assert card.outcome.result["subjects"] == []
            assert card.outcome.result["peers"] == []
            assert effect["research"]["follow_up"]["subjects"] == []
            assert not effect.get("next_experiments")
    assert len(transport.requests) == 1, "the second call is a shared-cache read"


def test_thorough_completion_keeps_cited_identity_without_a_collision_action(
    valvoline_catalog,
) -> None:
    asset, _ = valvoline_catalog
    packet = _packet(asset.canonical_symbol)
    row = packet.rows[0].model_copy(update={"subject": "Venice Token"})
    answer = f"{row.subject} ({row.symbol}) is {row.value} {row.unit}."
    packet = packet.model_copy(
        update={
            "answer_markdown": answer,
            "rows": (row,),
            "name_pairs": (
                ResearchNamePair(
                    name=asset.canonical_symbol, symbol=asset.canonical_symbol
                ),
            ),
        }
    )

    composed = grounded.compose_completed_research(
        job_request={"capability_class": "thorough_research", "subjects": []},
        packet=packet,
    )
    outcome = research_outcome_from_patch(
        {"assistant_response": composed["answer"], "research": composed["research"]}
    )

    assert outcome.status == "succeeded"
    assert outcome.result["answer"] == answer
    assert outcome.result["rows"][0]["subject"] == row.subject
    assert outcome.result["subjects"] == []
    assert outcome.result["peers"] == []
    assert not composed.get("next_experiments")


@pytest.mark.parametrize("surface", ["fresh", "cached", "completion"])
@pytest.mark.parametrize(
    "source_subject,can_offer_test", [("Venice Token", False), ("Valvoline Inc.", True)]
)
def test_pre_resolved_subject_must_match_the_packet_before_a_test_offer(
    valvoline_catalog, surface, source_subject, can_offer_test
) -> None:
    asset, _ = valvoline_catalog
    subject = {
        "symbol": asset.canonical_symbol,
        "name": asset.name,
        "asset_class": asset.asset_class,
    }
    packet = _packet(asset.canonical_symbol)
    row = packet.rows[0].model_copy(update={"subject": source_subject})
    answer = f"{row.subject} ({row.symbol}) is {row.value} {row.unit}."
    packet = packet.model_copy(update={"answer_markdown": answer, "rows": (row,)})
    if surface == "completion":
        composed = grounded.compose_completed_research(
            job_request={"capability_class": "thorough_research", "subjects": [subject]},
            packet=packet,
        )
        patch = {**composed, "assistant_response": composed["answer"]}
    else:
        context = _context()
        result = grounded._packet_stage_result(
            packet=packet,
            subjects=[subject],
            shape="balanced",
            capability_class="balanced_lookup",
            language="en",
            interpretation=educational_interpretation(),
            user=context.user,
            cache_status="hit" if surface == "cached" else "miss",
        )
        patch = result.stage_patch
    outcome = research_outcome_from_patch(patch)

    assert outcome.status == "succeeded"
    assert outcome.result["answer"] == answer
    assert outcome.result["rows"][0]["subject"] == source_subject
    assert outcome.result["peers"] == []
    assert outcome.result["subjects"] == (
        [{"symbol": asset.canonical_symbol, "name": asset.name}] if can_offer_test else []
    )
    assert bool(patch.get("next_experiments")) is can_offer_test
    assert patch["research"]["follow_up"]["subjects"] == (
        [subject] if can_offer_test else []
    )
