"""Retrieval parameters: configuration per question shape, typed rows, one owner.

Grounded-finance board, "Retrieval parameters". The provider is shaped by the
parameters the spec derives for each call; the answer comes back as cited
rows; a row survives only when its citation is a page the same response
retrieved. Nothing here is a route: the interpreter still owns the kind.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.config import (
    LOCAL_SOURCE_DOMAINS,
    MAX_FALLBACK_MODELS,
    MAX_SOURCE_DOMAINS,
    RESEARCH_CONFIG_SPECS,
    RETRIEVAL_INSTRUCTIONS,
    ResearchConfigSpec,
    home_location,
    iso_language,
    normalized_source_domains,
    retrieval_spec,
)
from argus.domain.research.contracts import (
    TYPED_RETRIEVAL_SCHEMA_NAME,
    typed_response_format,
    typed_retrieval_json_schema,
)
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.research.pricing import MODEL_RATE_TABLE_USD_PER_MILLION
from pydantic import ValidationError

from tests.research.conftest import (
    RecordingTransport,
    agent_response,
    request_body,
    retrieved_row,
    search_results_item,
    set_research_query,
    typed_answer_text,
)

USER = UserState(user_id="retrieval", language_preference="en")
SPANISH = UserState(user_id="retrieval-es", language_preference="es-419")
PUBLISHER = "https://www.barrons.com/articles/nvidia-nvda-stock-price"
PROVIDER_PAGE = "https://www.perplexity.ai/finance/NVDA"


@pytest.fixture(autouse=True)
def no_home_market(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARGUS_RESEARCH_HOME_COUNTRY", raising=False)


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="question",
        semantic_turn_act="educational_question",
        requires_clarification=False,
        candidate_strategy_draft=StrategySummary(),
    )


def _wire(monkeypatch: pytest.MonkeyPatch, documents: list[dict[str, Any]]):
    transport = RecordingTransport(documents)
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    return transport


def _run(message: str, *, user: UserState = USER):
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=user,
        )
    )


# --- configuration ---------------------------------------------------------


def test_every_shape_names_a_priced_fallback_chain() -> None:
    """A provider hiccup on the primary is served by the other priced model,
    never by nothing and never by an unpriced invoice."""
    for spec in RESEARCH_CONFIG_SPECS.values():
        assert len(spec.models) == 2
        assert spec.model == spec.models[0]
        for model in spec.models:
            assert model in MODEL_RATE_TABLE_USD_PER_MILLION, model
    assert (
        RESEARCH_CONFIG_SPECS["fast"].models == RESEARCH_CONFIG_SPECS["balanced"].models
    )
    assert RESEARCH_CONFIG_SPECS["thorough"].models == tuple(
        reversed(RESEARCH_CONFIG_SPECS["balanced"].models)
    )


@pytest.mark.parametrize("count", [0, MAX_FALLBACK_MODELS + 1])
def test_the_fallback_chain_is_bounded_by_the_provider(count: int) -> None:
    chain = tuple(f"vendor/model-{i}" for i in range(count))
    with pytest.raises(ValidationError):
        ResearchConfigSpec.model_validate(
            RESEARCH_CONFIG_SPECS["fast"].model_dump() | {"models": chain}
        )


def test_the_domain_filter_is_normalized_and_bounded() -> None:
    assert normalized_source_domains(
        ("https://Www.Example.com/rates", "example.org/", "www.example.com")
    ) == ("www.example.com", "example.org")
    with pytest.raises(ValueError):
        normalized_source_domains(
            tuple(f"bank-{i}.example" for i in range(MAX_SOURCE_DOMAINS + 1))
        )


def test_every_local_list_fits_the_provider_ceiling() -> None:
    for country, domains in LOCAL_SOURCE_DOMAINS.items():
        assert len(country) == 2 and country.isupper()
        assert domains, country
        assert normalized_source_domains(domains) == domains


@pytest.mark.parametrize(
    ("question_kind", "closed_period", "recency"),
    [
        ("market_pulse", False, "week"),
        ("current_external", False, "week"),
        ("live_quote", False, "week"),
        ("cross_company", False, "month"),
        ("company_lookup", False, None),
        ("etf_constituents", False, None),
        ("company_lookup", True, None),
        ("market_pulse", True, None),
    ],
)
def test_recency_follows_the_section_7_data_class(
    question_kind: str, closed_period: bool, recency: str | None
) -> None:
    """Freshness has one owner: how fast the answer goes stale. A closed
    window is never filtered to the past week."""
    spec = retrieval_spec(
        "balanced", question_kind=question_kind, closed_period=closed_period
    )
    assert spec.recency == recency


def test_home_market_comes_from_the_release_contract(monkeypatch) -> None:
    assert home_location() is None
    monkeypatch.setenv("ARGUS_RESEARCH_HOME_COUNTRY", " do ")
    location = home_location()
    assert location is not None and location.country == "DO"
    monkeypatch.setenv("ARGUS_RESEARCH_HOME_COUNTRY", "Dominican Republic")
    assert home_location() is None, "a malformed market sends no location"


def test_local_sources_need_a_market_with_a_list(monkeypatch) -> None:
    assert (
        retrieval_spec(
            "balanced", question_kind="current_external", local_sources=True
        ).source_domains
        == ()
    )
    monkeypatch.setenv("ARGUS_RESEARCH_HOME_COUNTRY", "US")
    assert (
        retrieval_spec(
            "balanced", question_kind="current_external", local_sources=True
        ).source_domains
        == ()
    )
    monkeypatch.setenv("ARGUS_RESEARCH_HOME_COUNTRY", "DO")
    assert (
        retrieval_spec(
            "balanced", question_kind="current_external", local_sources=True
        ).source_domains
        == LOCAL_SOURCE_DOMAINS["DO"]
    )
    assert (
        retrieval_spec("balanced", question_kind="current_external").source_domains == ()
    ), "a market alone never restricts the web"


@pytest.mark.parametrize(
    ("tag", "code"), [("es-419", "es"), ("en", "en"), ("EN-us", "en"), (None, "en")]
)
def test_the_response_language_is_iso_639_1(tag: str | None, code: str) -> None:
    assert iso_language(tag) == code
    assert (
        retrieval_spec("fast", question_kind="live_quote", language_tag=tag).language
        == code
    )


def test_the_thorough_job_rebuilds_its_parameters_from_the_typed_request() -> None:
    spec = grounded.retrieval_spec_for_job(
        {
            "question_kind": "cross_company",
            "language": "es-419",
            "period_is_closed_window": True,
        }
    )
    assert spec.shape == "thorough"
    assert spec.background is True
    assert spec.models == RESEARCH_CONFIG_SPECS["thorough"].models
    assert spec.language == "es"
    assert spec.recency is None, "a closed window is never recency-filtered"
    assert spec.search_context_size == "high"


# --- the request -----------------------------------------------------------


def test_the_request_carries_every_retrieval_parameter(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_HOME_COUNTRY", "DO")
    spec = retrieval_spec(
        "balanced",
        question_kind="current_external",
        language_tag="es-419",
        local_sources=True,
    )
    client = PerplexityAgentClient("k", transport=RecordingTransport([agent_response()]))

    client.run_research("¿Qué tasa paga el Banco Popular?", spec)

    body = request_body(client._transport.requests[0])  # type: ignore[union-attr]
    assert body["models"] == list(spec.models)
    assert "model" not in body
    assert body["language_preference"] == "es"
    assert body["instructions"] == RETRIEVAL_INSTRUCTIONS
    assert body["response_format"] == typed_response_format()
    assert body["response_format"]["json_schema"]["name"] == TYPED_RETRIEVAL_SCHEMA_NAME
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["tools"] == [
        {
            "type": "web_search",
            "search_context_size": "medium",
            "filters": {
                "search_recency_filter": "week",
                "search_domain_filter": ["popularenlinea.com"],
            },
            "user_location": {"country": "DO"},
        },
        {"type": "finance_search"},
        {"type": "fetch_url"},
    ]


def test_the_fast_shape_sends_no_web_options_and_no_location() -> None:
    spec = retrieval_spec("fast", question_kind="live_quote")
    client = PerplexityAgentClient("k", transport=RecordingTransport([agent_response()]))

    client.run_research("What is Apple at?", spec)

    body = request_body(client._transport.requests[0])  # type: ignore[union-attr]
    assert body["tools"] == [{"type": "finance_search"}]
    assert body["language_preference"] == "en"
    assert "response_format" in body


def test_prose_output_can_be_configured_off_per_shape() -> None:
    spec = RESEARCH_CONFIG_SPECS["fast"].model_copy(update={"typed_output": False})
    client = PerplexityAgentClient("k", transport=RecordingTransport([agent_response()]))

    client.run_research("q", spec)

    body = request_body(client._transport.requests[0])  # type: ignore[union-attr]
    assert "response_format" not in body
    assert "instructions" not in body


def test_the_strict_schema_closes_every_object_and_requires_every_field() -> None:
    """Provider strict mode: no open objects, no optional properties, no
    references, nothing Pydantic adds for its own use."""
    schema = typed_retrieval_json_schema()
    objects: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            assert "$ref" not in node and "$defs" not in node
            assert "title" not in node and "default" not in node
            if node.get("type") == "object":
                objects.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    assert len(objects) == 2, "the answer envelope and the row"
    for node in objects:
        assert node["additionalProperties"] is False
        assert node["required"] == list(node["properties"])
        for name, prop in node["properties"].items():
            assert prop.get("description"), f"{name} needs a description"
    row = schema["properties"]["rows"]["items"]
    assert list(row["properties"]) == [
        "label",
        "value",
        "unit",
        "as_of",
        "symbol",
        "source_url",
    ]
    assert row["properties"]["value"] == {
        "type": "number",
        "description": row["properties"]["value"]["description"],
    }


def test_the_instructions_never_name_a_declared_tool() -> None:
    from argus.domain.research.config import declared_tool_names

    for tool in declared_tool_names():
        assert tool not in RETRIEVAL_INSTRUCTIONS
    for prop in typed_retrieval_json_schema()["properties"]["rows"]["items"][
        "properties"
    ].values():
        for tool in declared_tool_names():
            assert tool not in prop["description"]


# --- the answer ------------------------------------------------------------


def _typed_document(rows: list[dict[str, Any]], *, answer: str) -> dict[str, Any]:
    document = agent_response(
        text=typed_answer_text(answer, rows),
        tickers=["NVDA"],
        sources=[PROVIDER_PAGE],
        web_search_invocations=1,
    )
    document["output"].insert(
        1,
        search_results_item(
            {"url": PUBLISHER, "title": "Nvidia stock falls", "date": "2026-09-04"}
        ),
    )
    return document


def test_a_typed_answer_is_read_into_rows_cited_to_retrieved_pages() -> None:
    client = PerplexityAgentClient(
        "k",
        transport=RecordingTransport(
            [
                _typed_document(
                    [
                        retrieved_row(source_url=PUBLISHER),
                        retrieved_row(label="NVDA last price", value=176.2, unit="USD"),
                        retrieved_row(
                            label="Invented", value=1.0, source_url="https://x.example/"
                        ),
                        retrieved_row(label="Uncited", value=2.0, source_url=None),
                    ],
                    answer="NVIDIA fell **4.3%** today.",
                )
            ]
        ),
    )

    packet = client.run_research("why", RESEARCH_CONFIG_SPECS["balanced"])

    assert packet.typed_answer is True
    assert packet.answer_markdown == "NVIDIA fell **4.3%** today."
    assert [row.label for row in packet.rows] == [
        "NVIDIA share price change today",
        "NVDA last price",
    ]
    # The publisher citation survives; the provider-host citation keeps its
    # evidence in the tool result and loses the URL, like every provider host.
    assert packet.rows[0].source_url == PUBLISHER
    assert packet.rows[1].source_url is None
    assert packet.uncited_rows == 2
    assert [source.url for source in packet.sources] == [PUBLISHER]


def test_fenced_json_is_still_a_typed_answer() -> None:
    document = _typed_document([retrieved_row(source_url=PUBLISHER)], answer="Fell.")
    text = document["output"][-1]["content"][0]["text"]
    document["output"][-1]["content"][0]["text"] = f"```json\n{text}\n```"
    client = PerplexityAgentClient("k", transport=RecordingTransport([document]))

    packet = client.run_research("why", RESEARCH_CONFIG_SPECS["balanced"])

    assert packet.typed_answer is True
    assert packet.answer_markdown == "Fell."
    assert len(packet.rows) == 1


def test_prose_under_a_typed_request_is_delivered_as_prose() -> None:
    client = PerplexityAgentClient(
        "k",
        transport=RecordingTransport([agent_response(text="Apple closed at $312.41.")]),
    )

    packet = client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])

    assert packet.typed_answer is False
    assert packet.rows == ()
    assert packet.uncited_rows == 0
    assert packet.answer_markdown == "Apple closed at $312.41."


def test_a_malformed_typed_row_makes_the_whole_answer_prose() -> None:
    """A row missing a required field is not the schema; the text is then
    prose and is sanitized like any other, never half-parsed."""
    broken = typed_answer_text("Fell.", [{"label": "x"}])
    client = PerplexityAgentClient(
        "k", transport=RecordingTransport([agent_response(text=broken)])
    )

    packet = client.run_research("q", RESEARCH_CONFIG_SPECS["fast"])

    assert packet.typed_answer is False
    assert packet.rows == ()


# --- the rail --------------------------------------------------------------


def test_why_it_is_moving_grounds_through_the_balanced_shape(monkeypatch) -> None:
    """#545: current external facts persist typed, dated sources and rows in
    the ordinary sidecar, and never write publisher URLs into the prose."""
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=["NVDA"]
    )
    transport = _wire(
        monkeypatch,
        [
            _typed_document(
                [retrieved_row(source_url=PUBLISHER)],
                answer=(
                    "NVIDIA fell **4.3%** today after a report that it paused "
                    "part of a partnership program."
                ),
            )
        ],
    )

    result = _run("Why is NVDA moving this week?")

    assert result is not None
    assert len(transport.requests) == 1
    body = request_body(transport.requests[0])
    assert body["tools"][0] == {
        "type": "web_search",
        "search_context_size": "medium",
        "filters": {"search_recency_filter": "week"},
    }
    sidecar = result.stage_patch["research"]
    assert sidecar["shape"] == "balanced"
    assert sidecar["capability_class"] == "balanced_lookup"
    assert "degraded" not in sidecar
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    assert sidecar["sources"][0]["source_date"] == "2026-09-04"
    assert sidecar["rows"] == [retrieved_row(source_url=PUBLISHER)]
    assert "http" not in result.stage_patch["assistant_response"]
    assert result.decision.reason_codes == ["research_answer_balanced_lookup"]


def test_why_it_is_moving_fails_closed_without_a_publisher_page(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=["NVDA"]
    )
    provider_only = agent_response(
        text=typed_answer_text("NVDA fell 4.3% today.", [retrieved_row()]),
        tickers=["NVDA"],
        sources=[PROVIDER_PAGE],
    )
    transport = _wire(monkeypatch, [provider_only, provider_only])

    result = _run("Why is NVDA moving this week?")

    assert result is not None
    assert len(transport.requests) == 2, "one retry without the provider channel"
    assert [tool["type"] for tool in request_body(transport.requests[1])["tools"]] == [
        "web_search",
        "fetch_url",
    ]
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_unavailable_missing_public_sources"}
    assert sidecar["sources"] == []
    assert sidecar["rows"] == []
    assert "NVDA fell" not in result.stage_patch["assistant_response"]
    assert "http" not in result.stage_patch["assistant_response"]


def test_a_survey_reads_the_symbols_its_rows_name(monkeypatch) -> None:
    """Typed rows carry the ticker, so a survey no longer depends on the
    model drawing a table to end runnable."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    document = agent_response(
        text=typed_answer_text(
            "NVIDIA (NVDA) leads today's gainers, up 4.2% as of 3:15pm ET.",
            [retrieved_row(label="NVDA change today", value=4.2)],
        ),
        sources=[PROVIDER_PAGE],
    )
    _wire(monkeypatch, [document])

    result = _run("what is moving today")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert sidecar["anchor_symbols"] == ["NVDA"]
    assert sidecar["rows"][0]["symbol"] == "NVDA"
    assert sidecar["rows"][0]["source_url"] is None
    assert result.stage_patch["next_experiments"]["rows"]


def test_degraded_turns_carry_an_empty_row_list(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    monkeypatch.setattr(grounded, "_client", lambda: None)

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_unavailable_not_configured"}
    assert sidecar["rows"] == []


def test_the_spec_is_one_object_per_call() -> None:
    """The retrieval facts ride the spec the client already receives, so no
    second parameter object can drift from it."""
    fields = set(ResearchConfigSpec.model_fields)
    assert {"models", "language", "location", "recency", "source_domains"} <= fields
