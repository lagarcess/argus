"""Router locks: shape selection, honest degradation, one classifier call."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
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


def _state(
    message: str, *, allowance: bool = True, guest_exhausted: bool = False
) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.research_allowance_available = allowance
    state.research_guest_allowance_exhausted = guest_exhausted
    return state


def _wire_client(monkeypatch: pytest.MonkeyPatch, documents) -> RecordingTransport:
    transport = RecordingTransport(documents)
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    return transport


def _run(
    message: str, *, user=USER, allowance: bool = True, guest_exhausted: bool = False
):
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state(message, allowance=allowance, guest_exhausted=guest_exhausted),
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
    assert body["tools"] == [
        {"type": "web_search"},
        {"type": "finance_search"},
        {"type": "fetch_url"},
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
    assert retry_body["tools"] == [
        {"type": "web_search"},
        {"type": "fetch_url"},
    ]
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
    ra.store_research_packet_for_job(job_request, packet)

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

    result = _run("What is Apple at?", allowance=False)

    assert result is not None
    assert transport.requests == [], "an exhausted ceiling must not spend"
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_capacity_exhausted"}
    assert "capacity" in result.stage_patch["assistant_response"].lower()
    assert result.stage_patch["next_experiments"]["rows"]


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

    result = _run("What is Apple at?", user=user, allowance=False, guest_exhausted=True)

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

    result = _run("What is Apple at?", user=user, allowance=False)

    assert result is not None
    assert must_say in result.stage_patch["assistant_response"].lower()
