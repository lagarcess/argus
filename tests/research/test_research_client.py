"""Perplexity Agent client parsing locks: deterministic, sanitized, bounded."""

from __future__ import annotations

import pytest
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.contracts import ResearchUnavailableError
from argus.domain.research.perplexity_agent import (
    PerplexityAgentClient,
    _sanitize_answer,
)

from tests.research.conftest import RecordingTransport, agent_response, request_body


def _client(documents) -> tuple[PerplexityAgentClient, RecordingTransport]:
    transport = RecordingTransport(documents)
    return PerplexityAgentClient("test-key", transport=transport), transport


def test_run_research_builds_documented_request_and_parses_packet() -> None:
    client, transport = _client(
        [
            agent_response(
                lookup_rows=[
                    ("The Walt Disney Company", "DIS", "The Walt Disney Company"),
                    ("EUR/USD exchange rate", "NOT_FOUND", ""),
                    ("header", "TICKER", "name"),
                ],
                sources=[
                    "https://www.perplexity.ai/finance/AAPL",
                    "https://www.sec.gov/a",
                ],
            )
        ]
    )
    packet = client.run_research("What is Apple at?", RESEARCH_CONFIG_SPECS["fast"])

    body = request_body(transport.requests[0])
    assert body["model"] == "openai/gpt-5.6-sol"
    assert body["tools"] == [{"type": "finance_search"}]
    assert body["max_steps"] == RESEARCH_CONFIG_SPECS["fast"].max_steps
    assert body["max_output_tokens"] == 1024
    assert packet.usage.invocations == 1
    assert packet.usage.cost_usd == pytest.approx(0.005)
    # Provider hosts are scrubbed; public sources survive.
    assert packet.sources == ("https://www.sec.gov/a",)
    # NOT_FOUND and header rows never become candidates.
    assert [pair.symbol for pair in packet.name_pairs] == ["DIS"]


def test_balanced_spec_sends_reasoning_and_all_three_tools() -> None:
    client, transport = _client([agent_response()])
    client.run_research("history", RESEARCH_CONFIG_SPECS["balanced"])
    body = request_body(transport.requests[0])
    assert body["reasoning"] == {"effort": "low"}
    assert body["tools"] == [
        {"type": "web_search"},
        {"type": "finance_search"},
        {"type": "fetch_url"},
    ]


def test_empty_answer_raises_unavailable() -> None:
    client, _ = _client([agent_response(text="  ")])
    with pytest.raises(ResearchUnavailableError) as excinfo:
        client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])
    assert excinfo.value.reason == "empty_answer"


def test_auth_errors_map_to_not_configured() -> None:
    transport = RecordingTransport([])
    transport.documents = []

    class Denied(RecordingTransport):
        def handle_request(self, request):  # type: ignore[override]
            return __import__("httpx").Response(401, json={})

    client = PerplexityAgentClient("k", transport=Denied([]))
    with pytest.raises(ResearchUnavailableError) as excinfo:
        client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])
    assert excinfo.value.reason == "not_configured"


def test_missing_key_never_sends_a_request() -> None:
    transport = RecordingTransport([agent_response()])
    client = PerplexityAgentClient("   ", transport=transport)
    with pytest.raises(ResearchUnavailableError) as excinfo:
        client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])
    assert excinfo.value.reason == "not_configured"
    assert transport.requests == []


def test_background_submit_and_poll_lifecycle() -> None:
    completed = agent_response(text="Deep answer", status="completed")
    client, transport = _client(
        [
            {"id": "resp_bg1", "status": "queued"},
            {"id": "resp_bg1", "status": "in_progress"},
            completed,
        ]
    )
    # The submit consumes the first canned document; the polls consume the rest.
    spec = RESEARCH_CONFIG_SPECS["thorough"]
    background_id = client.submit_background("compare", spec)
    assert background_id == "resp_bg1"
    assert request_body(transport.requests[0])["background"] is True

    first = client.poll_background(background_id)
    assert first.status in ("queued", "in_progress") and not first.terminal
    final = client.poll_background(background_id)
    assert final.terminal and final.status == "completed"
    assert final.packet is not None and final.packet.answer_markdown == "Deep answer"


def test_failed_background_poll_reports_detail() -> None:
    client, _ = _client([{"id": "x", "status": "failed", "error": {"message": "boom"}}])
    poll = client.poll_background("x")
    assert poll.terminal and poll.status == "failed"
    assert poll.packet is None
    assert "boom" in (poll.failure_detail or "")


def test_sanitizer_strips_provider_links_and_typographic_dashes() -> None:
    text = (
        "Revenue grew from $245B—a 14.9% rise. Window 2019–2024. "
        "[Source](https://www.perplexity.ai/finance/MSFT) and "
        "[SEC filing](https://www.sec.gov/f). "
        "| FY2022 | $31.6B | — |"
    )
    cleaned = _sanitize_answer(text)
    assert "perplexity.ai" not in cleaned
    assert "—" not in cleaned and "–" not in cleaned
    assert "2019-2024" in cleaned
    assert "$245B, a 14.9% rise" in cleaned
    # A lone dash cell stays an empty-value marker, not punctuation.
    assert "| - |" in cleaned
    assert "[SEC filing](https://www.sec.gov/f)" in cleaned
