"""The Perplexity-facing retrieval contract is frozen against its recordings.

The interpreter fingerprint (tests/test_interpreter_prompt_freeze.py) covers
text the interpretation model reads. The retrieval instructions and the strict
response schema steer Perplexity instead, so they are measured the way that
provider can be measured: real responses recorded through the repository's
own client, committed under docs/reports/evidence/545/probes. A change to
either text has to travel with a new recording, or these locks fail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from argus.domain.research.config import (
    LOCAL_SOURCE_DOMAINS,
    RESEARCH_CONFIG_SPECS,
    RETRIEVAL_INSTRUCTIONS,
)
from argus.domain.research.contracts import typed_response_format
from argus.domain.research.perplexity_agent import _packet_from_response

PROBES = Path(__file__).resolve().parents[2] / "docs/reports/evidence/545/probes"


def _recording(name: str) -> dict[str, Any]:
    return json.loads((PROBES / f"{name}.json").read_text(encoding="utf-8"))


def _request(name: str) -> dict[str, Any]:
    return _recording(name)["exchanges"][0]["request"]


def _packet(name: str):
    response = _recording(name)["exchanges"][-1]["response"]
    return _packet_from_response(response, latency_ms=0, on_unpriced=lambda _: None)


@pytest.mark.parametrize(
    "name",
    [
        "fast_quote_typed",
        "typed_rows_current_external",
        "domain_filtered_local_source",
        "thorough_typed_background",
    ],
)
def test_the_recorded_request_is_the_request_the_code_builds_today(name: str) -> None:
    """Instructions and schema are frozen by these recordings: a change here
    has to be re-recorded, the way an interpreter change is re-measured."""
    request = _request(name)
    assert request["instructions"] == RETRIEVAL_INSTRUCTIONS
    assert request["response_format"] == typed_response_format()
    shape = _recording(name)["exchanges"][0]["request"]
    spec = RESEARCH_CONFIG_SPECS[
        "fast"
        if name == "fast_quote_typed"
        else "thorough"
        if name == "thorough_typed_background"
        else "balanced"
    ]
    assert shape["models"] == list(spec.models)
    assert shape["max_steps"] == spec.max_steps
    assert [tool["type"] for tool in shape["tools"]] == list(spec.tools)


def test_the_provider_answers_the_strict_schema_with_typed_rows() -> None:
    """The proof the board asked for: typed rows under a strict schema."""
    for name in ("fast_quote_typed", "typed_rows_current_external"):
        packet = _packet(name)
        assert packet.typed_answer, name
        assert packet.rows, name
        for row in packet.rows:
            assert isinstance(row.value, float)
            assert row.unit
    # The Anthropic path in background mode answers the same schema.
    thorough = _packet("thorough_typed_background")
    assert thorough.typed_answer and thorough.rows
    assert thorough.usage.model == RESEARCH_CONFIG_SPECS["thorough"].models[0]


def test_current_facts_arrive_with_dated_sources_inside_the_recency_window() -> None:
    """#545: every citation on a "why is it moving" answer carries the
    publisher's date, and the one-week filter keeps a year-old page out."""
    request = _request("typed_rows_current_external")
    assert request["tools"][0]["filters"] == {"search_recency_filter": "week"}
    packet = _packet("typed_rows_current_external")
    dated = [source for source in packet.sources if source.source_date]
    assert dated, "web citations carry the publisher's date"
    captured = _recording("typed_rows_current_external")["captured_at"][:10]
    for source in dated:
        assert source.source_date <= captured
        assert source.source_date >= "2026-08-25", source.url


def test_the_domain_filtered_call_cites_only_the_local_list() -> None:
    """The proof the board asked for: a domain-filtered call citing a local
    source. Every retrieved page is on the seeded list."""
    request = _request("domain_filtered_local_source")
    web_search = request["tools"][0]
    assert web_search["filters"]["search_domain_filter"] == list(
        LOCAL_SOURCE_DOMAINS["DO"]
    )
    assert web_search["user_location"] == {"country": "DO"}
    assert request["language_preference"] == "es"
    packet = _packet("domain_filtered_local_source")
    assert packet.sources, "the filtered search still found local pages"
    for source in packet.sources:
        host = urlparse(source.url).netloc.lower()
        assert any(
            host == domain or host.endswith(f".{domain}")
            for domain in LOCAL_SOURCE_DOMAINS["DO"]
        ), source.url


def test_an_unsupported_model_in_the_chain_is_a_request_error_not_a_fallback() -> None:
    """The fallback chain passes over a model that fails or is unavailable;
    a model id the provider does not support fails validation up front."""
    recording = _recording("models_fallback_forced")
    exchange = recording["exchanges"][0]
    assert exchange["http_status"] == 400
    assert "not supported" in json.dumps(exchange["response"])
    assert recording["error"] == "http_error: http 400"


def test_tool_choice_is_accepted_and_ignored() -> None:
    """#404 asked for a documentation check and a live probe before anyone
    builds on tool_choice. The request is accepted, the response echoes
    tool_choice auto, so it is not a lever."""
    recording = _recording("tool_choice_required")
    assert recording["request_overrides"] == {"tool_choice": "required"}
    assert recording["exchanges"][0]["http_status"] == 200
    assert recording["exchanges"][0]["response"]["tool_choice"] == "auto"


def test_the_vaguest_survey_never_asserts_a_figure_it_did_not_retrieve() -> None:
    """#404 on the rail's own path: the vaguest phrasing retrieves, the
    concrete retry fires once when no figure came back, and a turn that
    still has no cited figure degrades honestly instead of stating one."""
    recording = _recording("market_pulse_vaguest_rail")
    assert len(recording["exchanges"]) == 2, "one concrete retry, never a loop"
    retry = recording["exchanges"][1]["request"]["input"]
    assert str(retry).startswith("Retrieve today's top gainers")
    for exchange in recording["exchanges"]:
        packet = _packet_from_response(
            exchange["response"], latency_ms=0, on_unpriced=lambda _: None
        )
        assert packet.tool_results, "both attempts retrieved"
        assert packet.uncited_rows == 0
    turn = recording["turn"]
    sidecar = turn["research"]
    if not sidecar["rows"]:
        assert sidecar["degraded"]["code"] in {
            "survey_synthesis_incomplete",
            "survey_not_grounded",
        }
        assert "%" not in turn["assistant_response"]
        assert "$" not in turn["assistant_response"]
    assert "http" not in turn["assistant_response"]


def test_the_finance_tool_refusal_is_the_provider_not_the_request_shape() -> None:
    """The concrete movers ask with only the finance tool available is not
    called under any request shape, the pre-lane prose shape included, and
    the answer says so rather than inventing figures."""
    for name in (
        "market_pulse_retry_finance_only",
        "retry_variant_prose",
        "retry_variant_no_instructions",
        "retry_variant_instructions_v2",
    ):
        recording = _recording(name)
        assert recording["exchanges"][0]["http_status"] == 200
        packet = _packet(name)
        assert packet.tool_results == (), name
        assert packet.rows == (), name
        assert "could not retrieve" in packet.answer_markdown.lower(), name
