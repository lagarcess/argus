"""Router locks: shape selection, honest degradation, one classifier call."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.admission import (
    ResearchAttemptAdmission,
    research_attempt_admission_context,
)
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.contracts import ResearchUnavailableError
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import RecordingTransport, agent_response, set_research_query

USER = UserState(user_id="research-user", language_preference="en")
SPANISH_USER = UserState(user_id="research-es", language_preference="es")


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="question",
        semantic_turn_act="educational_question",
        requires_clarification=False,
        candidate_strategy_draft=StrategySummary(),
    )


def _state(message: str) -> RunState:
    return RunState.new(current_user_message=message, recent_thread_history=[])


def _classify(monkeypatch: pytest.MonkeyPatch, **fields: Any) -> None:
    """Inject the primary payload for research tests sharing this helper."""
    set_research_query(monkeypatch, globals(), **fields)


def _wire_client(monkeypatch: pytest.MonkeyPatch, documents) -> RecordingTransport:
    transport = RecordingTransport(documents)
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    return transport


def _run(message: str, *, user=USER):
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state(message),
            user=user,
        )
    )


def test_flag_off_returns_none_before_any_classification(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    async def explode(**_kwargs: Any):
        raise AssertionError("classifier must not run with the rail off")

    monkeypatch.setattr(ra, "_dispatch", explode)
    assert _run("What is Apple at?") is None


def test_primary_schema_marks_narrative_clauses_in_any_language() -> None:
    from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse

    schema = LLMInterpretationResponse.model_json_schema()
    query = schema["$defs"]["ResearchQueryExtraction"]["properties"]
    assert "growth drivers" in query["question_kind"]["description"]
    assert "not live_quote in any language" in query["question_kind"]["description"]
    assert "publisher page" in query["requires_publisher_sources"]["description"]
    assert "period_start_date" in query


def test_classifier_rejects_a_malformed_period_start_date() -> None:
    with pytest.raises(ValueError):
        ra.ResearchQueryExtraction(
            question_kind="company_lookup",
            period_start_date="last quarter",
        )


def test_fast_quote_shape_grounds_and_classifies(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    result = _run("What is Apple trading at right now?")

    assert result is not None
    assert transport.requests, "the fast shape must call the provider"
    sidecar = result.stage_patch["research"]
    assert sidecar["capability_class"] == "fast_quote"
    assert sidecar["shape"] == "fast"
    assert sidecar["usage"]["cache_status"] == "miss"
    assert result.stage_patch["assistant_response"].startswith("Apple closed")
    assert result.decision.reason_codes == ["research_answer_fast_quote"]
    # Runnable rows ride along; the sidecar carries anchors and peers so the
    # persisted transcript can serve later confirmation cards.
    assert result.stage_patch["next_experiments"]["rows"]
    assert sidecar["anchor_symbols"] == ["AAPL"]
    assert "research_peers" not in result.stage_patch


def test_narrative_clause_can_never_use_the_fast_configuration(monkeypatch) -> None:
    """The semantic classifier owns language. The typed narrative fact is
    the deterministic guard if it ever returns a quote-shaped kind anyway."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="live_quote",
        symbols=["AAPL"],
        requires_publisher_sources=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Services and iPhone sales drove Apple's growth.",
                sources=["https://www.apple.com/newsroom/earnings/"],
            )
        ],
    )

    result = _run("What were Apple's main growth drivers?")

    assert result is not None
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert [tool["type"] for tool in body["tools"]] == [
        "web_search",
        "finance_search",
        "fetch_url",
    ]
    assert body["max_steps"] == RESEARCH_CONFIG_SPECS["balanced"].max_steps
    assert result.stage_patch["research"]["shape"] == "balanced"
    assert result.stage_patch["research"]["capability_class"] == "balanced_lookup"
    assert result.stage_patch["research"]["sources"]


def test_second_identical_question_serves_from_cache(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    first = _run("What is Apple trading at right now?")
    second = _run("What is Apple trading at right now?")

    assert len(transport.requests) == 1, "the cache must absorb the second call"
    assert second is not None
    assert second.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert (
        second.stage_patch["assistant_response"]
        == first.stage_patch["assistant_response"]
    )


def test_company_lookup_uses_the_balanced_configuration(monkeypatch) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["NFLX"],
        period_of_interest="last fiscal year",
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Netflix revenue grew because membership and pricing rose.",
                sources=["https://ir.netflix.net/financials/quarterly-earnings/"],
            )
        ],
    )

    result = _run("How has Netflix's revenue changed?")

    assert result is not None
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["max_steps"] == RESEARCH_CONFIG_SPECS["balanced"].max_steps
    assert result.stage_patch["research"]["capability_class"] == "balanced_lookup"


def test_company_claims_fail_closed_when_no_publisher_source_survives(
    monkeypatch,
) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["NFLX"],
        requires_publisher_sources=True,
    )
    provider_only = agent_response(
        text="Advertising drove Netflix's growth.",
        sources=["https://www.perplexity.ai/finance/NFLX"],
    )
    transport = _wire_client(monkeypatch, [provider_only, provider_only])

    result = _run("What were Netflix's main growth drivers?")

    assert result is not None
    assert len(transport.requests) == 2
    sidecar = result.stage_patch["research"]
    assert sidecar["sources"] == []
    assert sidecar["degraded"] == {"code": "research_unavailable_missing_public_sources"}
    answer = result.stage_patch["assistant_response"]
    assert "Advertising drove" not in answer
    assert answer.startswith("I couldn't verify that explanation with a public source")


def test_company_claim_retries_without_the_provider_only_citation_channel(
    monkeypatch,
) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["AAPL"],
        requires_publisher_sources=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="iPhone sales drove Apple's growth.",
                sources=["https://www.perplexity.ai/finance/AAPL"],
            ),
            agent_response(
                text="iPhone sales drove Apple's growth.",
                sources=["https://www.apple.com/newsroom/earnings/"],
            ),
        ],
    )

    result = _run("What were Apple's main growth drivers?")

    assert result is not None
    assert len(transport.requests) == 2
    retry_body = __import__("json").loads(transport.requests[1].content.decode())
    assert [tool["type"] for tool in retry_body["tools"]] == ["web_search", "fetch_url"]
    assert result.stage_patch["research"]["sources"] == [
        {
            "title": "www.apple.com",
            "domain": "www.apple.com",
            "url": "https://www.apple.com/newsroom/earnings/",
            "source_date": None,
        }
    ]
    assert result.stage_patch["assistant_response"].startswith("iPhone sales drove")


def test_cross_company_returns_a_background_job_request(monkeypatch) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="cross_company",
        symbols=["NFLX", "AAPL"],
        period_start_date="2023-08-12",
        requires_publisher_sources=True,
    )
    transport = _wire_client(monkeypatch, [])

    result = _run("Compare Netflix and Apple over three years")

    assert result is not None
    assert transport.requests == [], "thorough runs never call in-turn"
    job_request = result.stage_patch["research_job_request"]
    assert job_request["shape"] == "thorough"
    assert job_request["capability_class"] == "thorough_research"
    assert job_request["question"] == "Compare Netflix and Apple over three years"
    assert [s["symbol"] for s in job_request["subjects"]] == ["NFLX", "AAPL"]
    assert job_request["period_start_date"] == "2023-08-12"
    assert job_request["requires_publisher_sources"] is True
    # The key computed at classification time rides the request so completion
    # paths store the packet under the exact identity later turns look up.
    assert job_request["cache_key"]
    assert "research" not in result.stage_patch


def test_thorough_cache_hit_answers_inline_without_a_job(monkeypatch) -> None:
    """An identical thorough question after a finalized job answers from the
    shared cache: no job request, no provider call, no wait."""
    set_research_query(
        monkeypatch, globals(), question_kind="cross_company", symbols=["NFLX", "AAPL"]
    )
    transport = _wire_client(monkeypatch, [])

    first = _run("Compare Netflix and Apple over three years")
    assert first is not None
    job_request = first.stage_patch["research_job_request"]

    from argus.domain.research.perplexity_agent import _packet_from_response

    packet = _packet_from_response(
        agent_response(
            text="Thorough comparison of NFLX and AAPL.",
            tickers=["NFLX", "AAPL"],
            lookup_rows=[("Microsoft", "MSFT", "Microsoft Corporation")],
        ),
        latency_ms=1200,
    )
    composed = ra.compose_completed_research(job_request=job_request, packet=packet)
    ra.store_research_packet_for_job(job_request, packet, composed)

    second = _run("Compare Netflix and Apple over three years", user=SPANISH_USER)
    assert second is not None
    # The cache is keyed by language: the Spanish user misses and gets a job.
    assert "research_job_request" in second.stage_patch

    # A different user with the same question hits: shared by design.
    third = _run(
        "Compare Netflix and Apple over three years",
        user=UserState(user_id="another-user", language_preference="en"),
    )
    assert third is not None
    assert transport.requests == [], "a cache hit must not touch the provider"
    assert "research_job_request" not in third.stage_patch
    sidecar = third.stage_patch["research"]
    assert sidecar["shape"] == "thorough"
    assert sidecar["usage"]["cache_status"] == "hit"
    assert "Thorough comparison" in third.stage_patch["assistant_response"]
    # Verified peers from the cached packet still become runnable rows.
    assert sidecar["peers"] and sidecar["peers"][0]["symbol"] == "MSFT"


def test_screening_grounds_instead_of_queueing_a_background_job(monkeypatch) -> None:
    """A screen is a survey of current market data, so it grounds in the turn
    and comes back with names; it is not thorough multi-year research."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="screening",
        symbols=[],
        screening_criteria=["under a 20 P/E", "semiconductors"],
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Intel (INTC) trades under a 20 P/E.",
                tickers=["INTC"],
                lookup_rows=[("Intel", "INTC", "Intel Corporation")],
            )
        ],
    )

    result = _run("Show me semiconductor stocks under a 20 P/E")

    assert result is not None
    assert "research_job_request" not in result.stage_patch
    sidecar = result.stage_patch["research"]
    assert sidecar["capability_class"] == "screening"
    assert sidecar["usage"]["cache_status"] == "miss"
    # The stated conditions reach the provider verbatim, so the screen can
    # actually apply them instead of quietly ignoring them.
    body = __import__("json").loads(transport.requests[0].content.decode())
    prompt = body["input"] if isinstance(body.get("input"), str) else str(body)
    assert "under a 20 P/E" in prompt and "semiconductors" in prompt
    # A survey names no subject, so the verified name it found is runnable.
    assert result.stage_patch["next_experiments"]["rows"]


def test_crypto_never_reaches_finance_search(monkeypatch) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="live_quote",
        symbols=["BTC"],
        asset_class_hint="crypto",
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    result = _run("What is Bitcoin trading at right now?")

    assert result is not None
    assert transport.requests == [], "crypto must not route to finance_search"
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "asset_class_not_covered"}
    text = result.stage_patch["assistant_response"]
    assert "BTC" in text
    # Honest coverage note plus a runnable next step, never a dead end.
    assert result.stage_patch["next_experiments"]["rows"]


def test_a_scenario_question_sends_the_scenario_contract(monkeypatch) -> None:
    """Decision 10: the typed scenario signal swaps the provider instructions
    for the variant that lets computed figures through; a plain company read
    keeps the recorded contract."""
    from argus.domain.research.config import (
        RETRIEVAL_INSTRUCTIONS,
        SCENARIO_RETRIEVAL_INSTRUCTIONS,
    )

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Bear $2,300 to $5,500; base $29,000 to $38,000; bull higher.",
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )

    result = _run("what will $10,000 in NVDA be worth in ten years?")

    assert result is not None
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert "scenarios you compute" in body["input"]
    assert body["instructions"] != RETRIEVAL_INSTRUCTIONS


def _scenario_rows(*, cited: bool) -> list[dict]:
    from tests.research.conftest import retrieved_row

    return [
        retrieved_row(
            subject="NVIDIA",
            symbol="NVDA",
            label="average twelve-month analyst price target",
            value=327.18,
            kind="currency",
            unit="USD",
            source_url="https://www.reuters.com/markets/nvidia-outlook/"
            if cited
            else None,
        )
    ]


def _run_scenario(monkeypatch, *, cited: bool):
    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear $2,300 to $5,500; base $29,000 to $38,000; bull higher.",
                    _scenario_rows(cited=cited),
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )
    return _run("what will $10,000 in NVDA be worth in ten years?")


def test_a_scenario_publishes_on_a_cited_input_row(monkeypatch) -> None:
    result = _run_scenario(monkeypatch, cited=True)
    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert "Bear" in result.stage_patch["assistant_response"]


def test_a_scenario_with_no_cited_input_is_withheld_not_computed(monkeypatch) -> None:
    """Decision 10: the arithmetic is only as grounded as its inputs. A page
    in sources proves retrieval, not that a forecast was read from it; with no
    input row citing a public page the range is withheld, on the inline path
    and (below) the background one."""
    result = _run_scenario(monkeypatch, cited=False)
    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "scenario_inputs_uncited"}
    text = result.stage_patch["assistant_response"]
    assert "Bear" not in text
    assert "won't compute a range" in text
    # The subject the user named stays testable.
    assert result.stage_patch["next_experiments"]["rows"]


def test_the_background_scenario_applies_the_same_input_gate() -> None:
    from argus.domain.research.contracts import (
        ResearchPacket,
        ResearchSource,
        ResearchUsage,
    )

    packet = ResearchPacket(
        answer_markdown="Bear to bull ranges written from memory.",
        sources=(ResearchSource(url="https://www.reuters.com/markets/nvidia-outlook/"),),
        usage=ResearchUsage(web_search_invocations=1),
    )
    job_request = {
        "capability_class": "thorough_research",
        "language": "en",
        "question_kind": "cross_company",
        "scenario_question": True,
        "requires_publisher_sources": True,
        "subjects": [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
    }
    composed = grounded.compose_completed_research(job_request=job_request, packet=packet)
    assert composed["research"]["degraded"] == {"code": "scenario_inputs_uncited"}
    assert "won't compute a range" in composed["answer"]


def test_a_thorough_scenario_cache_hit_keeps_the_input_gate(monkeypatch) -> None:
    """A withheld scenario is cached so the same question is not billed
    twice; the repeat question composes from that cache and must be withheld
    the same way, never published with the gate off."""
    from argus.domain.research.perplexity_agent import _packet_from_response

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="cross_company",
        symbols=["NVDA", "AMD"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(monkeypatch, [])

    first = _run("Which of NVDA or AMD will be worth more in ten years?")
    assert first is not None
    job_request = first.stage_patch["research_job_request"]
    assert job_request["scenario_question"] is True

    packet = _packet_from_response(
        agent_response(
            text=typed_answer_text(
                "NVDA bear to bull ranges written from memory.",
                _scenario_rows(cited=False),
            ),
            sources=["https://www.reuters.com/markets/nvidia-outlook/"],
            tickers=["NVDA", "AMD"],
        ),
        latency_ms=1200,
    )
    composed = ra.compose_completed_research(job_request=job_request, packet=packet)
    assert composed["research"]["degraded"] == {"code": "scenario_inputs_uncited"}
    ra.store_research_packet_for_job(job_request, packet, composed)

    repeat = _run("Which of NVDA or AMD will be worth more in ten years?")
    assert repeat is not None
    assert transport.requests == [], "a cache hit must not touch the provider"
    assert "research_job_request" not in repeat.stage_patch
    sidecar = repeat.stage_patch["research"]
    assert sidecar["usage"]["cache_status"] == "hit"
    assert sidecar["degraded"] == {"code": "scenario_inputs_uncited"}
    assert "written from memory" not in repeat.stage_patch["assistant_response"]


def test_a_typed_horizon_alone_selects_the_scenario_contract(monkeypatch) -> None:
    """The interpreter typed the future horizon on the draft but left the
    scenario bit unset: the scenario contract still applies, so the request
    carries the scenario instructions and the answer needs a cited input."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["NVDA"],
        period_of_interest="ten years",
    )
    original = globals()["_interpretation"]

    def with_horizon(*args, **kwargs):
        read = original(*args, **kwargs)
        return read.model_copy(
            update={
                "candidate_strategy_draft": StrategySummary(
                    extra_parameters={
                        "date_range_intent": {
                            "kind": "future_window",
                            "count": 10,
                            "unit": "year",
                            "anchor": "today",
                            "confidence": 0.9,
                            "evidence": "in ten years",
                        }
                    }
                )
            }
        )

    monkeypatch.setitem(globals(), "_interpretation", with_horizon)
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "A range written from memory.", _scenario_rows(cited=False)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )

    result = _run("what will $10,000 in NVDA be worth in ten years?")

    assert result is not None
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert result.stage_patch["research"]["degraded"] == {
        "code": "scenario_inputs_uncited"
    }
    # The compensation reaches the persisted turn through the decision.
    from argus.agent_runtime.research_grounded import SCENARIO_FROM_HORIZON_REASON_CODE

    assert SCENARIO_FROM_HORIZON_REASON_CODE in result.decision.reason_codes


def test_a_crypto_scenario_typed_only_by_its_horizon_is_grounded(monkeypatch) -> None:
    """The off-coverage branch reads the shared scenario owner: a crypto
    comparison with a typed future horizon and no scenario bit is grounded on
    public pages under the scenario contract, never answered with closes."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="cross_company",
        symbols=["BTC", "ETH"],
        asset_class_hint="crypto",
        period_of_interest="ten years",
    )
    original = globals()["_interpretation"]

    def with_horizon(*args, **kwargs):
        return original(*args, **kwargs).model_copy(
            update={
                "candidate_strategy_draft": StrategySummary(
                    extra_parameters={
                        "date_range_intent": {
                            "kind": "future_window",
                            "count": 10,
                            "unit": "year",
                            "anchor": "today",
                            "confidence": 0.9,
                            "evidence": "in ten years",
                        }
                    }
                )
            }
        )

    monkeypatch.setitem(globals(), "_interpretation", with_horizon)
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges.", _scenario_rows(cited=True)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["BTC"],
            )
        ],
    )

    result = _run("Which of BTC or ETH will be worth more in ten years?")

    assert result is not None
    assert len(transport.requests) == 1
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert "finance_search" not in [tool["type"] for tool in body["tools"]]
    assert result.stage_patch["research"].get("degraded") != {
        "code": "asset_class_not_covered"
    }


def test_a_failed_scenario_records_the_shape_it_was_selected_for(monkeypatch) -> None:
    """A crypto scenario forced onto the balanced shape that then fails on the
    provider is recorded as the balanced lookup it attempted, not as the
    thorough research its question kind would map to."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="cross_company",
        symbols=["BTC", "ETH"],
        asset_class_hint="crypto",
        period_of_interest="ten years",
        scenario_question=True,
    )
    _wire_client(monkeypatch, [])  # the transport answers 500 to every call

    result = _run("Which of BTC or ETH will be worth more in ten years?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"]["code"].startswith("research_unavailable_")
    assert sidecar["shape"] == "balanced"
    assert sidecar["capability_class"] == "balanced_lookup"


def test_a_crypto_claim_is_grounded_on_public_pages_without_the_finance_tool(
    monkeypatch,
) -> None:
    """Decision 10: a forecast about Bitcoin is a claim, not a figure Argus's
    own data can answer, so it is grounded on publishers with the finance tool
    (which never covered crypto) left out of the request."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="company_lookup",
        symbols=["BTC"],
        asset_class_hint="crypto",
        requires_publisher_sources=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Analyst targets for Bitcoin range widely; base case shown.",
                sources=["https://www.reuters.com/markets/bitcoin-outlook/"],
                tickers=["BTC"],
            )
        ],
    )

    result = _run("How has Bitcoin's adoption changed over the last year?")

    assert result is not None
    assert len(transport.requests) == 1
    body = __import__("json").loads(transport.requests[0].content.decode())
    tools = [tool["type"] for tool in body["tools"]]
    assert "finance_search" not in tools
    assert "web_search" in tools
    assert body["max_steps"] == RESEARCH_CONFIG_SPECS["balanced"].max_steps
    sidecar = result.stage_patch["research"]
    assert sidecar.get("degraded") != {"code": "asset_class_not_covered"}
    assert sidecar["capability_class"] == "balanced_lookup"


def test_currency_pairs_degrade_honestly(monkeypatch) -> None:
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="live_quote",
        symbols=["EURUSD"],
        asset_class_hint="currency_pair",
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    result = _run("What is the euro dollar rate?")

    assert result is not None
    assert transport.requests == []
    assert result.stage_patch["research"]["degraded"]["code"] == "asset_class_not_covered"


def test_exhausted_ceiling_is_an_honest_note_not_a_disappearance(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    with research_attempt_admission_context(
        lambda: ResearchAttemptAdmission(available=False)
    ):
        result = _run("What is Apple at?")

    assert result is not None
    assert transport.requests == [], "an exhausted ceiling must not spend"
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_capacity_exhausted"}
    assert "capacity" in result.stage_patch["assistant_response"].lower()
    assert result.stage_patch["next_experiments"]["rows"]


def test_atomic_claim_denial_stops_an_inline_provider_call(monkeypatch) -> None:
    """A turn admitted before a rival spent the last slot must re-check at
    the billable boundary and degrade without touching the provider."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)
    with research_attempt_admission_context(
        lambda: ResearchAttemptAdmission(
            available=False,
            guest_exhausted=True,
        )
    ):
        result = _run("What is Apple at?")

    assert result is not None
    assert transport.requests == []
    assert "free research" in result.stage_patch["assistant_response"]
    assert result.stage_patch["research"]["usage"]["cache_status"] == "bypass"


def test_cache_hit_never_claims_research_capacity(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response()])
    assert _run("What is Apple trading at right now?") is not None

    def reject_claim() -> ResearchAttemptAdmission:
        raise AssertionError("a cache hit must not claim capacity")

    with research_attempt_admission_context(reject_claim):
        result = _run("What is Apple trading at right now?")

    assert result is not None
    assert len(transport.requests) == 1
    assert result.stage_patch["research"]["usage"]["cache_status"] == "hit"


def test_provider_failure_degrades_without_fabricating(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )

    class FailingClient:
        def run_research(self, prompt, spec):
            raise ResearchUnavailableError("timeout")

    monkeypatch.setattr(grounded, "_client", lambda: FailingClient())

    result = _run("What is Apple at?")

    assert result is not None
    text = result.stage_patch["assistant_response"]
    assert "won't quote live figures" in text
    assert (
        result.stage_patch["research"]["degraded"]["code"]
        == "research_unavailable_timeout"
    )


def test_concept_and_none_fall_through(monkeypatch) -> None:
    set_research_query(monkeypatch, globals(), question_kind="concept", symbols=[])
    assert _run("What is a drawdown?") is None


def test_spanish_turn_carries_the_language_into_the_prompt(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    transport = _wire_client(monkeypatch, [agent_response(text="Apple cerró...")])

    result = _run("¿A cuánto está Apple?", user=SPANISH_USER)

    assert result is not None
    prompt = __import__("json").loads(transport.requests[0].content.decode())["input"]
    assert "es-419" in prompt


@pytest.mark.parametrize(
    ("user", "must_say", "must_not_say"),
    [
        (USER, "free research", "shared research capacity"),
        (SPANISH_USER, "gratis", "capacidad compartida"),
    ],
)
def test_a_guest_who_spent_their_own_allowance_is_told_so(
    monkeypatch, user, must_say, must_not_say
) -> None:
    """A guest's three are their own. Telling them the shared capacity ran out
    would be a more flattering story than the true one."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    with research_attempt_admission_context(
        lambda: ResearchAttemptAdmission(available=False, guest_exhausted=True)
    ):
        result = _run("What is Apple at?", user=user)

    assert result is not None
    answer = result.stage_patch["assistant_response"].lower()
    assert must_say in answer
    assert must_not_say not in answer
    # Still ends somewhere runnable: an exhausted meter is not a dead end.
    assert result.stage_patch["next_experiments"]["rows"]


@pytest.mark.parametrize(
    ("user", "must_say"),
    [(USER, "shared research capacity"), (SPANISH_USER, "capacidad compartida")],
)
def test_a_shared_outage_still_says_shared(monkeypatch, user, must_say) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    _wire_client(monkeypatch, [agent_response()])

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    from argus.agent_runtime import knowledge_answer as ka

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    with research_attempt_admission_context(
        lambda: ResearchAttemptAdmission(available=False)
    ):
        result = _run("What is Apple at?", user=user)

    assert result is not None
    assert must_say in result.stage_patch["assistant_response"].lower()
