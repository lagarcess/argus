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
from argus.domain.discovery_search.contracts import SearchResult, SearchResultPacket

USER = UserState(user_id="ka", language_preference="es")


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
        _run(
            _interpretation(
                intent="strategy_drafting", semantic_turn_act="new_idea"
            )
        )
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
