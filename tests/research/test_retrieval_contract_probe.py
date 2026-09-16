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
from argus.domain.research.answer_contract import typed_answer_response_format
from argus.domain.research.config import (
    RESEARCH_CONFIG_SPECS,
    RETRIEVAL_INSTRUCTIONS,
    SCENARIO_RETRIEVAL_INSTRUCTIONS,
    retrieval_spec,
)
from argus.domain.research.perplexity_agent import _packet_from_response

PROBES = Path(__file__).resolve().parents[2] / "docs/reports/evidence/545/probes"
# Any grounded math: the scenario contract retrieves the inputs a declared
# calculation names and computes nothing; frozen by its own recording, captured
# through the same client on the balanced configuration.
SCENARIO_PROBE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/grounded-math/probes/scenario_inputs_balanced.json"
)
# The calculations schema, one calculation per option the reader weighs, frozen
# by its own recording of a concept question on the balanced configuration.
CALCULATIONS_PROBE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/grounded-math/probes/typed_answer_calculations_options.json"
)


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
    assert request["response_format"] == typed_answer_response_format()
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


def test_a_domain_filtered_call_cites_only_the_filtered_domains() -> None:
    """What the provider does with a domain filter, as recorded: every page a
    filtered call retrieves is on the filter. No shape sends one today."""
    request = _request("domain_filtered_local_source")
    web_search = request["tools"][0]
    domains = web_search["filters"]["search_domain_filter"]
    assert domains
    assert web_search["user_location"] == {"country": "DO"}
    assert request["language_preference"] == "es"
    # The behavior as #568 recorded it; the request above is today's. Recorded
    # again on 2026-09-12, the filtered search returned no results twice.
    packet = _packet("domain_filtered_local_source_568")
    assert packet.sources, "the filtered search still found pages"
    for source in packet.sources:
        host = urlparse(source.url).netloc.lower()
        assert any(
            host == domain or host.endswith(f".{domain}") for domain in domains
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
        assert packet.unsourced_rows == ()
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


def test_the_scenario_recording_is_the_request_the_code_builds_today() -> None:
    """The scenario contract travels with its own recording: a change to
    SCENARIO_RETRIEVAL_INSTRUCTIONS, the answer calculation contract, the
    balanced configuration or the typed answer schema has to be re-recorded,
    like every other retrieval text."""
    from argus.agent_runtime.research_grounded import _research_prompt

    recording = json.loads(SCENARIO_PROBE.read_text(encoding="utf-8"))
    request = recording["exchanges"][0]["request"]
    spec = retrieval_spec(
        "balanced",
        question_kind="company_lookup",
        language_tag="en",
        country=None,
        scenario=True,
    )
    assert request["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert request["instructions"] == spec.instructions
    assert request["response_format"] == typed_answer_response_format()
    assert request["models"] == list(spec.models)
    assert request["max_steps"] == spec.max_steps
    assert [tool["type"] for tool in request["tools"]] == list(spec.tools)
    assert request["input"] == _research_prompt(
        message=recording["question"],
        subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
        period="ten years",
        language="en",
        question_kind=None,
        publisher_sources_required=True,
        scenario=True,
    )


def test_the_provider_returns_its_calculation_and_argus_computes_the_scenarios() -> None:
    """What the answer contract buys: the answer names its calculation with each
    input's source, the current price from market data, a figure from a page it
    retrieved and assumptions it states, writes every figure as a reference, and
    the valuation declaration computes a card from exactly those inputs."""
    from argus.agent_runtime.answer_calculation import publish_calculations
    from argus.agent_runtime.research_calculation import retrieved_pages
    from argus.domain.calculations.answer_request import AnswerCalculation
    from argus.domain.capability_registry import get_tool_catalog

    recording = json.loads(SCENARIO_PROBE.read_text(encoding="utf-8"))
    assert recording["error"] is None
    packet = _packet_from_response(
        recording["exchanges"][-1]["response"], latency_ms=0, on_unpriced=lambda _: None
    )
    request = AnswerCalculation.model_validate(packet.calculations[0])
    assert request.kind == "valuation_scenarios"
    sources = {item.name: item.source for item in request.inputs}
    assert sources["price"] == "market_data"
    assert "page" in sources.values() and "assumption" in sources.values()
    assert "{{price}}" in packet.answer_markdown
    notes: list[str] = []
    published = publish_calculations(
        [request],
        template=packet.answer_markdown,
        language="en",
        catalog=get_tool_catalog(),
        retrieved=retrieved_pages(packet),
        currency="USD",
        subject_symbol="NVDA",
        market_close=lambda symbol: (218.29, "2026-09-11"),
        notes=notes,
        evidence=[row for row in packet.rows if row.source_url is None],
    )
    assert published is not None and not published.not_looked_up, notes
    # The recorded prose references inputs, but never its completed primary result.
    assert published.template is None
    assert "answer_figures_replaced" in notes
    from argus.agent_runtime.answer_calculation import cards_in, figure_text

    assert (
        figure_text(cards_in(published.patch)[0].presentation.answer)
        in published.answer_text
    )
    card = published.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["outcome"]["status"] == "succeeded"
    assert card["arguments"]["amount"] == 10000
    assert card["arguments"]["sources"]["price"] == {
        "kind": "market_data",
        "date": "2026-09-11",
    }
    assert card["arguments"]["sources"]["growth_base_pct"] == {"kind": "assumption"}
    page = card["arguments"]["sources"]["per_share"]
    # A page this answer retrieved names its URL; a figure read from the
    # provider's finance data names its subject and date instead.
    assert page["kind"] == "page" and page["date"]
    assert (page.get("url") or "").startswith("https://") or page.get("title")
    rows = {fact["name"]: fact for fact in card["presentation"]["rows"]}
    assert rows["value_at_horizon_base"]["value"] > 0
    assert "{{" not in published.answer_text


def test_the_calculations_recording_is_the_request_the_code_builds_today() -> None:
    """The calculations schema travels with its own recording: a concept question
    under today's research instructions, schema and balanced configuration."""
    from argus.agent_runtime.research_grounded import _research_prompt

    recording = json.loads(CALCULATIONS_PROBE.read_text(encoding="utf-8"))
    request = recording["exchanges"][0]["request"]
    spec = retrieval_spec(
        "balanced", question_kind="concept", language_tag="en", country=None
    )
    assert request["instructions"] == RETRIEVAL_INSTRUCTIONS == spec.instructions
    assert request["response_format"] == typed_answer_response_format()
    assert (
        request["response_format"]["json_schema"]["name"]
        == "argus_typed_answer_calculations"
    )
    assert request["models"] == list(spec.models)
    assert request["max_steps"] == spec.max_steps
    assert [tool["type"] for tool in request["tools"]] == list(spec.tools)
    assert request["input"] == _research_prompt(
        message=recording["question"],
        subjects=[],
        period=None,
        language="en",
        question_kind="concept",
    )


def test_the_provider_returns_one_calculation_per_option_and_argus_computes_each() -> (
    None
):
    """What the calculations schema buys: an answer weighing two options returns
    one named calculation for each, refers to each figure by its option's name,
    and Argus computes a card per option from exactly those inputs."""
    from argus.agent_runtime.answer_calculation import publish_calculations
    from argus.agent_runtime.research_calculation import retrieved_pages
    from argus.domain.calculations.answer_request import AnswerCalculation
    from argus.domain.capability_registry import get_tool_catalog

    recording = json.loads(CALCULATIONS_PROBE.read_text(encoding="utf-8"))
    assert recording["error"] is None
    packet = _packet_from_response(
        recording["exchanges"][-1]["response"], latency_ms=0, on_unpriced=lambda _: None
    )
    requests = [AnswerCalculation.model_validate(item) for item in packet.calculations]
    assert [request.name for request in requests] == ["cd", "savings"]
    assert {request.kind for request in requests} == {"growth_projection"}
    assert "{{cd.end_value}}" in packet.answer_markdown
    assert "{{savings.end_value}}" in packet.answer_markdown
    notes: list[str] = []
    published = publish_calculations(
        requests,
        template=packet.answer_markdown,
        language="en",
        catalog=get_tool_catalog(),
        retrieved=retrieved_pages(packet),
        currency="USD",
        subject_symbol=None,
        market_close=lambda symbol: None,
        notes=notes,
        evidence=[row for row in packet.rows if row.source_url is None],
    )
    assert published is not None and not published.not_looked_up, notes
    assert published.template is not None, notes
    cards = published.patch["final_response_payload"]["tool_result_cards"]
    assert [card["outcome"]["status"] for card in cards] == ["succeeded", "succeeded"]
    assert [card["presentation"]["answer"]["value"] for card in cards] == pytest.approx(
        [20820.0, 20760.0]
    )
    assert "{{" not in published.answer_text
