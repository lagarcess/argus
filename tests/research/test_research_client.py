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
    assert packet.usage.finance_search_invocations == 1
    assert packet.usage.web_search_invocations == 0
    assert packet.usage.fetch_url_invocations == 0
    assert packet.usage.input_tokens == 1_000
    assert packet.usage.output_tokens == 500
    assert packet.usage.model == "openai/gpt-5.6-sol"
    assert packet.usage.cost_usd == pytest.approx(0.025)
    # Provider hosts are scrubbed; public sources survive as typed citations.
    assert [source.url for source in packet.sources] == ["https://www.sec.gov/a"]
    # NOT_FOUND and header rows never become candidates.
    assert [pair.symbol for pair in packet.name_pairs] == ["DIS"]


def test_usage_cost_uses_served_model_tokens_and_every_tool_count() -> None:
    client, transport = _client(
        [
            agent_response(
                model="anthropic/claude-opus-4-7",
                input_tokens=20_000,
                output_tokens=4_000,
                invocations=2,
                web_search_invocations=3,
                fetch_url_invocations=4,
            )
        ]
    )

    packet = client.run_research("compare", RESEARCH_CONFIG_SPECS["fast"])

    assert request_body(transport.requests[0])["model"] == "openai/gpt-5.6-sol"
    assert packet.usage.model == "anthropic/claude-opus-4-7"
    assert packet.usage.input_tokens == 20_000
    assert packet.usage.output_tokens == 4_000
    assert packet.usage.finance_search_invocations == 2
    assert packet.usage.web_search_invocations == 3
    assert packet.usage.fetch_url_invocations == 4
    assert packet.usage.invocations == 2
    assert packet.usage.cost_usd == pytest.approx(0.2185)


def test_unknown_served_model_rate_fails_loudly() -> None:
    client, _ = _client([agent_response(model="vendor/new-model")])

    with pytest.raises(ResearchUnavailableError) as excinfo:
        client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])

    assert excinfo.value.reason == "unknown_model_rate"
    assert excinfo.value.detail == "vendor/new-model"


def test_missing_required_token_usage_is_malformed() -> None:
    response = agent_response()
    del response["usage"]["input_tokens"]
    client, _ = _client([response])

    with pytest.raises(ResearchUnavailableError) as excinfo:
        client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])

    assert excinfo.value.reason == "malformed_response"


@pytest.mark.parametrize(
    ("input_tokens", "expected_cost_usd"),
    [
        (272_000, 1.39),
        (272_001, 2.76501),
    ],
)
def test_gpt_5_6_sol_uses_the_documented_long_context_rate(
    input_tokens: int, expected_cost_usd: float
) -> None:
    client, _ = _client(
        [
            agent_response(
                input_tokens=input_tokens,
                output_tokens=1_000,
                invocations=0,
            )
        ]
    )

    packet = client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])

    assert packet.usage.cost_usd == pytest.approx(expected_cost_usd)


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
