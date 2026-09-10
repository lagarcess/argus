"""Every research composition validates the same declared result identities."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
from argus.agent_runtime import research_grounded as grounded
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.market_data.tradability import TradableHistory
from argus.domain.research.contracts import ResearchNamePair
from argus.domain.tool_contracts import ToolCall, ToolResultCard

from tests.research.conftest import (
    agent_response,
    educational_interpretation,
    wire_grounded_client,
)
from tests.research.test_registered_research_tools import _context, _packet


@pytest.fixture(
    params=[
        ("AAPL", "Apple Inc.", "equity"),
        ("BTC", "Bitcoin", "crypto"),
        ("EURUSD", "Euro against US Dollar", "currency_pair"),
    ],
    ids=["equity", "crypto", "currency_pair"],
)
def catalog(request, monkeypatch):
    symbol, name, asset_class = request.param
    asset = ResolvedAsset(
        canonical_symbol=symbol, raw_symbol=symbol, name=name, asset_class=asset_class
    )
    control = SimpleNamespace(
        asset=asset, resolved=asset, verdict="tradable", lookups=[], history=[]
    )

    def resolve(candidate):
        control.lookups.append(candidate)
        assert candidate == asset.canonical_symbol
        return control.resolved

    def history(candidate, kind):
        control.history.append((candidate, kind))
        return TradableHistory(control.verdict)

    monkeypatch.setattr("argus.domain.market_data.resolve_asset", resolve)
    monkeypatch.setattr("argus.domain.market_data.tradable_history", history)
    monkeypatch.setattr(
        "argus.agent_runtime.research_rows._earliest_available",
        lambda *_: date(2020, 1, 2),
    )
    return control


def _named_packet(asset, origin: str):
    packet = _packet(asset.canonical_symbol)
    row = packet.rows[0].model_copy(update={"subject": asset.name})
    pair = ResearchNamePair(symbol=asset.canonical_symbol, name=asset.name)
    return packet.model_copy(
        update={
            "answer_markdown": f"{asset.name} ({asset.canonical_symbol}) is listed.",
            "rows": (row,) if origin in {"rows", "both"} else (),
            "unsourced_rows": (row.model_copy(update={"source_url": None}),)
            if origin == "unsourced_rows"
            else (),
            "name_pairs": (pair, pair) if origin in {"name_pairs", "both"} else (),
        }
    )


def _compose(packet, surface: str):
    if surface == "background":
        result = grounded.compose_completed_research(
            job_request={"capability_class": "thorough_research", "subjects": []},
            packet=packet,
        )
        return result["research"], result.get("next_experiments")
    result = grounded._packet_stage_result(
        packet=packet,
        subjects=[],
        shape="balanced",
        capability_class="screening" if surface == "survey" else "balanced_lookup",
        language="en",
        interpretation=educational_interpretation(),
        user=_context().user,
        cache_status="hit" if surface == "cached" else "miss",
        survey=surface == "survey",
    )
    return result.stage_patch["research"], result.stage_patch.get("next_experiments")


@pytest.mark.parametrize("surface", ["inline", "cached", "survey", "background"])
@pytest.mark.parametrize("origin", ["rows", "unsourced_rows", "name_pairs", "both"])
def test_typed_identities_share_canonical_verification(catalog, surface, origin):
    packet = _named_packet(catalog.asset, origin)
    research, actions = _compose(packet, surface)

    assert research.get("degraded") is None
    assert research["follow_up"]["subjects"] == [
        {
            "symbol": catalog.asset.canonical_symbol,
            "name": catalog.asset.name,
            "asset_class": catalog.asset.asset_class,
        }
    ]
    assert catalog.lookups == [catalog.asset.canonical_symbol]
    assert catalog.history == [
        (catalog.asset.canonical_symbol, catalog.asset.asset_class)
    ]
    assert research["rows"] == [row.model_dump() for row in packet.published_rows]
    if catalog.asset.asset_class == "currency_pair":
        assert actions is None, "the existing currency Try-next boundary is unchanged"
    else:
        assert actions["rows"][0]["kind"] == "research_test_single"


@pytest.mark.parametrize("failure", ["unresolved", "mismatch", "no_history", "unknown"])
def test_typed_names_never_override_catalog_or_history(catalog, failure):
    packet = _named_packet(catalog.asset, "rows")
    if failure == "unresolved":
        catalog.resolved = None
    elif failure == "mismatch":
        packet = packet.model_copy(
            update={
                "name_pairs": (
                    ResearchNamePair(
                        symbol=catalog.asset.canonical_symbol,
                        name="Unrelated biomedical issuer",
                    ),
                )
            }
        )
    else:
        catalog.verdict = failure

    research, actions = _compose(packet, "inline")

    assert research["follow_up"]["subjects"] == []
    assert research["peers"] == []
    assert actions is None
    assert catalog.lookups == [catalog.asset.canonical_symbol]
    if failure in {"unresolved", "mismatch"}:
        assert catalog.history == []


def test_plain_narrative_is_not_a_new_candidate_parser(catalog):
    packet = _named_packet(catalog.asset, "none")
    research, actions = _compose(packet, "inline")

    assert research["follow_up"]["subjects"] == []
    assert actions is None
    assert catalog.lookups == []


def test_missing_class_hint_does_not_bypass_pair_name_corroboration(monkeypatch):
    from argus.agent_runtime.research_rows import verified_peers

    asset = ResolvedAsset(
        canonical_symbol="BTC", raw_symbol="BTC", name="BTC/USD", asset_class="crypto"
    )
    lookups = []
    history = []
    monkeypatch.setattr(
        "argus.domain.market_data.resolve_asset",
        lambda symbol: lookups.append(symbol) or asset,
    )
    monkeypatch.setattr(
        "argus.domain.market_data.tradable_history",
        lambda *args: history.append(args) or TradableHistory("tradable"),
    )

    assert verified_peers([ResearchNamePair(symbol="BTC", name="Bitcoin")], exclude=set()) == []
    assert lookups == ["BTC"]
    assert history == []


@pytest.mark.asyncio()
async def test_declared_lookup_delivers_typed_names_on_fresh_and_cached_reads(
    catalog, monkeypatch
):
    from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async

    pair = ResearchNamePair(
        symbol=catalog.asset.canonical_symbol, name=catalog.asset.name
    )
    packet = _named_packet(catalog.asset, "name_pairs")
    document = agent_response(
        text=json.dumps(
            {
                "answer_markdown": packet.answer_markdown,
                "rows": [],
                "name_pairs": [pair.model_dump(), pair.model_dump()],
            }
        ),
        sources=[source.url for source in packet.sources],
    )
    transport = wire_grounded_client(monkeypatch, [document])
    context = _context()
    for call_id in ("named-fresh", "named-cached"):
        context.state.tool_calls = [
            ToolCall(
                call_id=call_id,
                tool_name="balanced_lookup",
                arguments={"request": "Read the named public-market assets"},
            )
        ]
        stage = await execute_tool_calls_async(
            state=context.state, tool=None, user=context.user
        )
        card = ToolResultCard.model_validate(
            stage.stage_patch["final_response_payload"]["tool_result_cards"][0]
        )

        assert card.outcome.status == "succeeded"
        assert card.outcome.result["subjects"] == [pair.model_dump()]
        assert card.presentation.answer.value == catalog.asset.canonical_symbol
        assert card.presentation.narrative.startswith(packet.answer_markdown)

    assert len(transport.requests) == 1
    assert catalog.lookups == [catalog.asset.canonical_symbol] * 2
    assert catalog.history == [
        (catalog.asset.canonical_symbol, catalog.asset.asset_class)
    ] * 2
