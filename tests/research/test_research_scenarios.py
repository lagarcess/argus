"""Decision 10: forward-looking and valuation questions answered as scenarios.

Router and composition locks for the scenario contract: the typed signal
selects the scenario instructions and the balanced shape on every kind, the
answer publishes only on cited inputs on the inline, background and cache-hit
paths, a claim about crypto is grounded on public pages, and a failed
scenario is recorded under the shape it was selected for.
"""

from __future__ import annotations

import asyncio

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import RecordingTransport, agent_response, set_research_query

USER = UserState(user_id="research-user", language_preference="en")


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


def test_a_scenario_typed_as_market_stats_is_grounded_not_voiced_from_history(
    monkeypatch,
) -> None:
    """A forward question the interpreter typed as market_stats still takes the
    scenario contract: the legacy statistics path would default the future
    window to the past year and voice history as the answer."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="market_stats",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges.", _scenario_rows(cited=True)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )

    result = _run("what return will NVDA have in ten years?")

    assert result is not None
    assert len(transport.requests) == 1, "the scenario must reach the provider"
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert result.stage_patch["research"]["shape"] == "balanced"
    assert "Bear" in result.stage_patch["assistant_response"]


def test_a_scenario_about_named_subjects_is_a_fact_question_whatever_its_kind(
    monkeypatch,
) -> None:
    """The scenario bit on a read left at kind none still reaches the
    scenario owner when it names its subjects; without subjects it is a
    projection on the user's own numbers and stays arithmetic."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="none",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges.", _scenario_rows(cited=True)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )

    result = _run("what will $10,000 in NVDA be worth in ten years?")

    assert result is not None
    assert len(transport.requests) == 1
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert result.stage_patch["research"]["shape"] == "balanced"

    set_research_query(
        monkeypatch, globals(), question_kind="none", symbols=[], scenario_question=True
    )
    assert _run("If I save $500 a month at 5%, how much will I have in 20 years?") is None


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


def test_a_scenario_typed_as_a_survey_is_not_handled_as_one(monkeypatch) -> None:
    """A scenario typed as a survey kind gets no survey guidance, no screening
    class and no verified-ticker withhold: the stale kind reclassifies nothing
    downstream of the scenario owner."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="sector_radar",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges with no ticker named in the prose.",
                    _scenario_rows(cited=True),
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
    assert "Retrieve these figures from current market data" not in body["input"]
    sidecar = result.stage_patch["research"]
    assert sidecar["capability_class"] == "balanced_lookup"
    assert "degraded" not in sidecar
    assert "Bear" in result.stage_patch["assistant_response"]


def test_a_subjectless_scenario_stays_arithmetic_whatever_its_kind(monkeypatch) -> None:
    """A projection on the user's own numbers misread as market_stats with the
    scenario bit set is not a research turn: it keeps the interpreter's
    arithmetic answer."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="market_stats",
        symbols=[],
        scenario_question=True,
    )
    transport = _wire_client(monkeypatch, [agent_response()])
    assert _run("If I save $500 a month at 5%, how much will I have in 20 years?") is None
    assert transport.requests == []


def test_a_failed_survey_typed_scenario_is_not_filed_as_screening(monkeypatch) -> None:
    """The derived survey fact reaches the failure paths too: a scenario
    typed as a survey kind whose provider fails is recorded as the balanced
    lookup it attempted, never as screening."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="screening",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    _wire_client(monkeypatch, [])  # the transport answers 500 to every call

    result = _run("what will $10,000 in NVDA be worth in ten years?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"]["code"].startswith("research_unavailable_")
    assert sidecar["shape"] == "balanced"
    assert sidecar["capability_class"] == "balanced_lookup"


def test_a_discovery_act_with_a_named_scenario_is_dispatched_not_found(
    monkeypatch,
) -> None:
    """The discovery entry reads the scenario owner before its kind diversion:
    a discovery act carrying a screening-typed scenario about a named subject
    is a scenario, never the find operation."""
    from argus.domain.research.config import SCENARIO_RETRIEVAL_INSTRUCTIONS

    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="screening",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges.", _scenario_rows(cited=True)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    interpretation = _interpretation().model_copy(
        update={"semantic_turn_act": "asset_discovery"}
    )
    decision = grounded.research_decision(interpretation, USER, "test").model_copy(
        update={"semantic_turn_act": "asset_discovery"}
    )

    result = asyncio.run(
        ra.discovery_turn_stage_result(
            interpretation=interpretation,
            decision=decision,
            state=_state("what will $10,000 in NVDA be worth in ten years?"),
            user=USER,
        )
    )

    assert result is not None
    assert len(transport.requests) == 1
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["instructions"] == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert result.stage_patch["research"]["shape"] == "balanced"


def test_a_survey_typed_scenario_keeps_a_dated_analyst_page(monkeypatch) -> None:
    """Source freshness reads the derived survey fact: a scenario typed as a
    survey kind keeps a publisher page dated before the question day instead
    of being withheld for missing public sources."""
    from tests.research.conftest import typed_answer_text

    set_research_query(
        monkeypatch,
        globals(),
        question_kind="market_pulse",
        symbols=["NVDA"],
        period_of_interest="ten years",
        scenario_question=True,
    )
    _wire_client(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "Bear to bull ranges.", _scenario_rows(cited=True)
                ),
                sources=["https://www.reuters.com/markets/nvidia-outlook/"],
                tickers=["NVDA"],
            )
        ],
    )

    result = _run("what will $10,000 in NVDA be worth in ten years?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert sidecar["sources"], "the dated analyst page is kept"
