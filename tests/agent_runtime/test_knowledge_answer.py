"""Locks for the grounded answer router: own data first, search for current
facts, concepts fall through to the interpreter's own prose, and every
grounded answer carries the Try next surface."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.search.contracts import SearchResult, SearchResultPacket

USER = UserState(user_id="ka", language_preference="es")


@pytest.fixture(autouse=True)
def legacy_knowledge_router(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")


def _interpretation(**overrides: Any) -> StructuredInterpretation:
    payload: dict[str, Any] = {
        "intent": "unsupported_or_out_of_scope",
        "task_relation": "new_task",
        "user_goal_summary": "stats",
        "semantic_turn_act": "unsupported_request",
        "requires_clarification": False,
        "candidate_strategy_draft": StrategySummary(
            asset_universe=["SPY"], asset_class="equity"
        ),
    }
    payload.update(overrides)
    return StructuredInterpretation(**payload)


def _run(
    interpretation: StructuredInterpretation,
    message: str = "Ayúdame con estadísticas sobre el S&P 500",
    metadata: dict[str, Any] | None = None,
) -> Any:
    return asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=USER,
            snapshot=None,
            selected_thread_metadata=metadata or {},
        )
    )


@pytest.fixture
def market_stats_route(monkeypatch):
    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        return ka.KnowledgeQueryExtraction(
            question_kind="market_stats",
            symbols=["SPY"],
            date_range_raw_text="del ultimo año para aca",
        )

    monkeypatch.setattr(ka, "_classify_question", classify)
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    async def voice(*, message, language, facts, fallback, user=None):
        return fallback

    monkeypatch.setattr(ka, "_voiced_answer", voice)


def test_market_stats_question_gets_grounded_numbers(market_stats_route) -> None:
    result = _run(_interpretation())

    assert result is not None
    text = result.stage_patch["assistant_response"]
    assert "SPY" in text
    assert "Total return" in text
    # The degrade path is formatted chat markdown, not a raw sentence.
    assert "**" in text
    assert result.decision.reason_codes == ["knowledge_answer_market_stats"]
    # The Try next surface rides along with a grounded answer.
    rows = result.stage_patch["next_experiments"]["rows"]
    assert [row["kind"] for row in rows] == [
        "compare_buy_and_hold",
        "recurring_monthly_buys",
    ]


def test_concept_question_falls_through_to_interpreter_prose(monkeypatch) -> None:
    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        return ka.KnowledgeQueryExtraction(question_kind="concept")

    monkeypatch.setattr(ka, "_classify_question", classify)

    concept = _interpretation(candidate_strategy_draft=StrategySummary())
    assert _run(concept, "¿Qué es un drawdown?") is None


def test_pending_reply_and_execution_turns_are_left_alone(monkeypatch) -> None:
    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        raise AssertionError("classification must not run for gated turns")

    monkeypatch.setattr(ka, "_classify_question", classify)

    assert (
        _run(
            _interpretation(),
            metadata={"last_stage_outcome": "await_user_reply"},
        )
        is None
    )
    assert (
        _run(_interpretation(intent="strategy_drafting", semantic_turn_act="new_idea"))
        is None
    )
    assert (
        _run(
            _interpretation(
                candidate_strategy_draft=StrategySummary(
                    strategy_type="buy_and_hold", asset_universe=["SPY"]
                )
            )
        )
        is None
    )


def test_current_external_question_answers_with_citations(monkeypatch) -> None:
    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        return ka.KnowledgeQueryExtraction(question_kind="current_external")

    monkeypatch.setattr(ka, "_classify_question", classify)

    class _Provider:
        def search(self, query: str, *, max_results: int, timeout_seconds: float):
            return SearchResultPacket(
                results=(
                    SearchResult(
                        title="S&P 500 today",
                        url="https://example.com/spx",
                        snippet="The index closed higher.",
                    ),
                ),
                retrieved_at=datetime.now(timezone.utc),
                latency_ms=10,
                provider_id="fake_provider",
            )

    monkeypatch.setattr(
        ka, "search_provider_for_config", lambda *, provider_id: _Provider()
    )

    async def voice(*, message, language, facts, fallback, user=None):
        return "El índice cerró al alza."

    monkeypatch.setattr(ka, "_voiced_answer", voice)

    result = _run(
        _interpretation(candidate_strategy_draft=StrategySummary()),
        "¿Qué pasó con los mercados hoy?",
    )

    assert result is not None
    assert "https://example.com/spx" in result.stage_patch["assistant_response"]
    assert result.decision.reason_codes == ["knowledge_answer_current_external"]


def test_market_data_failure_degrades_to_search(monkeypatch) -> None:
    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        return ka.KnowledgeQueryExtraction(question_kind="market_stats", symbols=["SPY"])

    monkeypatch.setattr(ka, "_classify_question", classify)

    async def broken_market(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(ka, "_market_stats_answer", broken_market)

    async def external(*, message, language, user=None):
        return "Respuesta con fuente https://example.com/spx"

    monkeypatch.setattr(ka, "_external_facts_answer", external)

    result = _run(_interpretation())

    assert result is not None
    assert result.decision.reason_codes == ["knowledge_answer_current_external"]


def test_palette_rendering_enforces_emphasis() -> None:
    voiced = ka.VoicedAnswer(
        lead="QQQ rose 16.57 % over the past year.",
        bullets=["Biggest drop was 0.0 %", "Volatility was 0.03 % annualized"],
        note="Window: 2025-08-06 to 2026-08-06",
    )

    rendered = voiced.as_markdown()

    assert "**16.57 %**" in rendered
    assert "**0.0 %**" in rendered
    assert rendered.strip().endswith("*")
    # Already-emphasized content is left alone.
    assert ka.VoicedAnswer(lead="QQQ rose **16.57%**.").as_markdown() == (
        "QQQ rose **16.57%**."
    )


def test_unsupported_run_request_is_never_answered_with_asset_stats(
    monkeypatch,
) -> None:
    # "Backtest weekly options on apple over 2024" arrives typed
    # unsupported_request with AAPL restored by the audits. A draw that reads
    # the turn as market_stats is exactly how the underlying stock's
    # statistics shipped as a fake options result, so the classifier is pinned
    # to that wrong answer here and the turn must still decline. The
    # classifier is still consulted first, because the act label can be wrong
    # too and a genuine question mislabelled unsupported_request must keep
    # reaching it (test_recognition_contract_guards.py). Two reads that misfire
    # in opposite directions: the classifier decides whether this is a
    # question, the typed refusal decides that a claimed one is not answered
    # from the underlying.
    calls: list[str] = []

    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        calls.append("classified")
        return ka.KnowledgeQueryExtraction(
            question_kind="market_stats",
            symbols=["AAPL"],
            date_range_raw_text="from 2024-01-01 to 2024-12-31",
        )

    monkeypatch.setattr(ka, "_classify_question", classify)

    run_request = _interpretation(
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            # The interpreter's record that the message carried the period.
            extra_parameters={
                "evidence_spans": {"date_range": "from 2024-01-01 to 2024-12-31"}
            },
        )
    )
    result = _run(
        run_request,
        "please backtest weekly options on apple from 2024-01-01 through 2024-12-31",
    )

    assert result is None
    # Consulted, then overridden: the classifier keeps owning whether a turn
    # is a question, and the typed refusal keeps a claimed one from being
    # answered with the underlying's statistics.
    assert calls == ["classified"]


def test_unsupported_turn_with_unavailable_classifier_declines(
    monkeypatch,
) -> None:
    # No classification, no claim: falling back to asset statistics would
    # fabricate an answer for a request the interpreter already ruled
    # unsupported.
    async def classify(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(ka, "_classify_question", classify)

    assert _run(_interpretation()) is None


def test_educational_turn_with_enriched_asset_uses_the_classifier(
    monkeypatch,
) -> None:
    # "What is SPY?" can arrive with SPY attached by provider enrichment; the
    # asset alone must not shortcut to statistics.
    calls: list[str] = []

    async def classify(**_kwargs: Any) -> ka.KnowledgeQueryExtraction:
        calls.append("classified")
        return ka.KnowledgeQueryExtraction(question_kind="concept")

    monkeypatch.setattr(ka, "_classify_question", classify)

    educational = _interpretation(
        intent="conversation_followup",
        semantic_turn_act="educational_question",
    )
    assert _run(educational, "¿Qué es SPY?") is None
    assert calls == ["classified"]


def test_unsupported_request_describing_a_test_keeps_its_recovery_route(
    market_stats_route,
) -> None:
    # "backtest weekly options on apple from 2024-01-01 to 2024-12-31": the
    # interpreter typed a resolved asset and the user's own window, so the
    # turn is a refusal with recovery options. Answering it from the
    # underlying's price history is how a run request became a readout.
    describes_a_test = _interpretation(
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            # The interpreter's own record that the message carried the
            # period; a bare date_range can be an inherited window.
            extra_parameters={
                "evidence_spans": {"date_range": "from 2024-01-01 to 2024-12-31"}
            },
        ),
    )

    assert _run(describes_a_test, "backtest weekly options on apple") is None


def test_unsupported_capability_question_still_reaches_the_answerer(
    market_stats_route,
) -> None:
    # The stand-down is keyed on a described test, not on the act label: a
    # plain capability question names no window and keeps its answer.
    assert _run(_interpretation()) is not None


def test_rail_claim_declines_only_an_unsupported_request_over_a_stated_window(
    monkeypatch,
) -> None:
    """Review #522: a window alone must not decline the rail claim.

    Declining on specificity gave the more precise user the worse turn:
    "compare PLTR to LMT over the last 3 years" got the builder's capital
    question while the same question without a period got an answer. Only an
    unsupported verdict over a window the user themselves stated is a
    described test.
    """
    monkeypatch.setattr(ka, "research_rail_enabled", lambda: True)
    span = {
        "evidence_spans": {"date_range": "over the last 3 years"},
        "field_provenance": {"strategy_type": "default"},
    }
    query = {"question_kind": "cross_company", "symbols": ["PLTR", "LMT"]}

    supported_with_window = _interpretation(
        semantic_turn_act="new_idea",
        requires_clarification=True,
        research_query=query,
        candidate_strategy_draft=StrategySummary(
            asset_universe=["PLTR", "LMT"],
            asset_class="equity",
            strategy_type="buy_and_hold",
            date_range={"start": "2023-01-01", "end": "2026-01-01"},
            extra_parameters=span,
        ),
    )
    assert ka.primary_research_query(supported_with_window) is not None
    assert not ka.refusal_route_survives_classification(supported_with_window)

    supported_without_window = _interpretation(
        semantic_turn_act="new_idea",
        requires_clarification=True,
        research_query=query,
        candidate_strategy_draft=StrategySummary(
            asset_universe=["PLTR", "LMT"],
            asset_class="equity",
            strategy_type="buy_and_hold",
            extra_parameters={"field_provenance": {"strategy_type": "default"}},
        ),
    )
    assert ka.primary_research_query(supported_without_window) is not None
    assert not ka.refusal_route_survives_classification(supported_without_window)

    unsupported_with_window = _interpretation(
        semantic_turn_act="unsupported_request",
        requires_clarification=True,
        research_query=query,
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AAPL"],
            asset_class="equity",
            strategy_type="buy_and_hold",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            extra_parameters=span,
        ),
    )
    assert ka.refusal_route_survives_classification(unsupported_with_window)

    # An inherited window is not a stated one: no evidence span, no decline.
    inherited = _interpretation(
        semantic_turn_act="unsupported_request",
        requires_clarification=True,
        research_query=query,
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AAPL"],
            asset_class="equity",
            strategy_type="buy_and_hold",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            extra_parameters={"field_provenance": {"strategy_type": "default"}},
        ),
    )
    assert ka.primary_research_query(inherited) is not None
    assert not ka.refusal_route_survives_classification(inherited)


def test_typed_draft_window_outranks_classifier_prose(monkeypatch) -> None:
    # The classifier hands back unparseable prose ("del ultimo año para aca")
    # while the draft carries the user's typed window. Letting the prose win
    # silently answers over a window nobody asked for.
    captured: dict[str, Any] = {}

    async def capture(*, message, language, facts, fallback, user=None):
        captured.update(facts)
        return fallback

    monkeypatch.setattr(ka, "_voiced_answer", capture)
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    result = asyncio.run(
        ka._market_stats_answer(
            query=ka.KnowledgeQueryExtraction(
                question_kind="market_stats",
                symbols=["SPY"],
                date_range_raw_text="del ultimo año para aca",
            ),
            interpretation=_interpretation(
                candidate_strategy_draft=StrategySummary(
                    asset_universe=["SPY"],
                    asset_class="equity",
                    date_range={"start": "2024-02-01", "end": "2024-06-30"},
                ),
            ),
            message="stats",
            language="es",
            user=USER,
        )
    )

    assert result is not None
    assert captured["start"] == "2024-02-01"
    assert captured["end"] == "2024-06-30"
