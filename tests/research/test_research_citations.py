"""Citations reach the panel, from the channels the provider actually uses.

These run against a real captured Agent API response, not a hand-written
fixture, because the defect they cover was a channel nobody had looked at:
web search citations arrive in their own output items (and, for some models,
as annotations on the answer chunk), while only the finance channel had been
read. Argus discarded 45 publisher URLs and then told the reader there were
no source links to open.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argus.agent_runtime.research_grounded import typed_sources
from argus.domain.research.perplexity_agent import _packet_from_response

from tests.research.conftest import agent_response

PROBES = Path(__file__).resolve().parents[2] / "docs/reports/evidence/377/probes"


def _probe(name: str) -> dict:
    document = json.loads((PROBES / f"{name}.json").read_text(encoding="utf-8"))
    return document.get("response", document)


def test_web_search_citations_reach_the_typed_panel() -> None:
    """The captured sector-radar run: web search fired, and its citations
    are real publisher pages, including the CIBR/HACK comparison the answer
    leaned on."""
    document = _probe("sector_radar_web_search_citations")
    # The run genuinely used web search; an empty citation list here would
    # mean the channel never fired, not that the channel is empty.
    assert any(
        item.get("type") == "search_results" for item in document.get("output", [])
    )

    packet = _packet_from_response(document, latency_ms=100)
    assert packet.sources, "web search citations must survive parsing"

    panel = typed_sources(packet)
    assert panel, "citations must reach the surface the panel renders"
    for entry in panel:
        assert entry["url"].startswith("https://")
        assert entry["domain"] and entry["domain"] in entry["url"]
        # The publisher's own title, never an invented one.
        assert entry["title"]
    domains = {entry["domain"] for entry in panel}
    assert any("yahoo" in domain or "etfcentral" in domain for domain in domains)
    titles = " ".join(entry["title"] for entry in panel)
    assert "CIBR" in titles


def test_provider_identity_never_becomes_a_citation() -> None:
    """finance_search cites its own provider pages; those stay scrubbed even
    now that the other channels are read."""
    for name in ("etf_spy_constituents_steps3", "equity_steps2"):
        packet = _packet_from_response(_probe(name), latency_ms=10)
        for source in packet.sources:
            assert "perplexity.ai" not in source.url


@pytest.mark.parametrize(
    "name",
    ["equity_control_quote", "fx_eurusd_steps3", "crypto_btc_quote"],
)
def test_pure_finance_answers_legitimately_have_nothing_to_link(name: str) -> None:
    """These runs never called web search, so an empty citation list is the
    truth rather than a parsing gap; the honest empty line belongs here."""
    document = _probe(name)
    assert not any(
        item.get("type") == "search_results" for item in document.get("output", [])
    )
    packet = _packet_from_response(document, latency_ms=10)
    assert typed_sources(packet) == []


def test_annotations_on_the_answer_chunk_are_read_too() -> None:
    """Some models carry citations as annotations on the output_text chunk
    rather than as search_results items. Same evidence, same surface."""
    document = _probe("equity_control_quote")
    for item in document.get("output", []):
        if item.get("type") == "message":
            item["content"][0]["annotations"] = [
                {
                    "url": "https://www.reuters.com/markets/example",
                    "title": "Example market report",
                    "last_updated": "2026-08-08",
                },
                {"url": "https://www.perplexity.ai/finance/AAPL", "title": "provider"},
            ]
    packet = _packet_from_response(document, latency_ms=10)
    panel = typed_sources(packet)
    assert [entry["url"] for entry in panel] == [
        "https://www.reuters.com/markets/example"
    ]
    assert panel[0]["title"] == "Example market report"
    assert panel[0]["source_date"] == "2026-08-08"


def test_thorough_tier_citations_reach_the_panel_too() -> None:
    """Captured background comparison run: web search fired and its
    publisher pages survive into the panel."""
    document = _probe("thorough_comparison_web_search_citations")
    assert any(
        item.get("type") == "search_results" for item in document.get("output", [])
    )
    panel = typed_sources(_packet_from_response(document, latency_ms=100))
    assert panel
    assert all(entry["url"].startswith("https://") for entry in panel)
    assert all("perplexity.ai" not in entry["url"] for entry in panel)


def test_a_run_where_web_search_never_fired_is_legitimately_empty() -> None:
    """The discipline this whole defect came from: an empty citation list
    means nothing until you check whether the tool that fills it ran. This
    captured thorough run used only the finance channel, so empty is true."""
    document = _probe("thorough_comparison_no_web_search")
    tool_costs = (
        (document.get("usage") or {}).get("cost", {}).get("tool_calls_cost_details", {})
    )
    assert "search_web" not in tool_costs
    assert not any(
        item.get("type") == "search_results" for item in document.get("output", [])
    )
    assert typed_sources(_packet_from_response(document, latency_ms=100)) == []


def test_packet_retains_sources_beyond_the_public_drawer_cap() -> None:
    """Selection happens after parsing, so early repeats from one publisher
    cannot erase later outlets before publisher deduplication runs."""
    document = agent_response(sources=[])
    search_results = {
        "type": "search_results",
        "results": [
            {
                "url": f"https://publisher-{index}.example/story",
                "title": f"Publisher {index}",
                "date": "2026-08-12",
            }
            for index in range(7)
        ],
    }
    document["output"].insert(1, search_results)

    packet = _packet_from_response(document, latency_ms=10)

    assert len(packet.sources) == 7
    assert len(typed_sources(packet)) == 5
