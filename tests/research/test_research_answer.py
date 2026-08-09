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

from tests.research.conftest import RecordingTransport, agent_response

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


def _state(message: str, *, allowance: bool = True) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.research_allowance_available = allowance
    return state


def _classify(monkeypatch: pytest.MonkeyPatch, **fields: Any) -> None:
    async def classify(**_kwargs: Any) -> ra.ResearchQueryExtraction:
        return ra.ResearchQueryExtraction(**fields)

    monkeypatch.setattr(ra, "_classify_research_question", classify)


def _wire_client(monkeypatch: pytest.MonkeyPatch, documents) -> RecordingTransport:
    transport = RecordingTransport(documents)
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    return transport


def _run(message: str, *, user=USER, allowance: bool = True):
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=_state(message, allowance=allowance),
            user=user,
        )
    )


def test_flag_off_returns_none_before_any_classification(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    async def explode(**_kwargs: Any):
        raise AssertionError("classifier must not run with the rail off")

    monkeypatch.setattr(ra, "_classify_research_question", explode)
    assert _run("What is Apple at?") is None


def test_fast_quote_shape_grounds_and_classifies(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])
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


def test_second_identical_question_serves_from_cache(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])
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
    _classify(
        monkeypatch,
        question_kind="company_lookup",
        symbols=["NFLX"],
        period_of_interest="last fiscal year",
    )
    transport = _wire_client(monkeypatch, [agent_response(text="Netflix revenue...")])

    result = _run("How has Netflix's revenue changed?")

    assert result is not None
    body = __import__("json").loads(transport.requests[0].content.decode())
    assert body["max_steps"] == RESEARCH_CONFIG_SPECS["balanced"].max_steps
    assert result.stage_patch["research"]["capability_class"] == "balanced_lookup"


def test_cross_company_returns_a_background_job_request(monkeypatch) -> None:
    _classify(
        monkeypatch,
        question_kind="cross_company",
        symbols=["NFLX", "AAPL"],
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
    # The key computed at classification time rides the request so completion
    # paths store the packet under the exact identity later turns look up.
    assert job_request["cache_key"]
    assert "research" not in result.stage_patch


def test_thorough_cache_hit_answers_inline_without_a_job(monkeypatch) -> None:
    """An identical thorough question after a finalized job answers from the
    shared cache: no job request, no provider call, no wait."""
    _classify(monkeypatch, question_kind="cross_company", symbols=["NFLX", "AAPL"])
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
    _classify(
        monkeypatch,
        question_kind="screening",
        symbols=[],
        screening_criteria=["under a 20 P/E", "semiconductors"],
    )
    transport = _wire_client(
        monkeypatch,
        [
            agent_response(
                text="Three semiconductor names trade under a 20 P/E.",
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
    _classify(
        monkeypatch,
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
    _classify(
        monkeypatch,
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
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])
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
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])

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
    _classify(monkeypatch, question_kind="concept", symbols=[])
    assert _run("What is a drawdown?") is None


def test_spanish_turn_carries_the_language_into_the_prompt(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])
    transport = _wire_client(monkeypatch, [agent_response(text="Apple cerró...")])

    result = _run("¿A cuánto está Apple?", user=SPANISH_USER)

    assert result is not None
    prompt = __import__("json").loads(transport.requests[0].content.decode())["input"]
    assert "es-419" in prompt
