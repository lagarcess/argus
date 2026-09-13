"""A choice that turns on a future figure nobody can cite is answered with the
recent past: the research instructions ask for it, and an answer that follows
them publishes Argus's computation over cited, dated figures as history."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.calculation_rows import MARKET_COUNTERFACTUAL_KIND
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.config import (
    RETRIEVAL_INSTRUCTIONS,
    SCENARIO_RETRIEVAL_INSTRUCTIONS,
)
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import (
    RecordingTransport,
    agent_response,
    set_research_query,
    typed_answer_text,
)

HISTORY_LINE = (
    "When a choice turns on a future figure nobody can cite, such as an exchange "
    "rate or a price, do not project it; show what the recent past did with cited "
    "figures, computed by Argus and labeled as history, not a forecast."
)
READER = UserState(
    user_id="research-do", language_preference="es-419", country="DO", currency="DOP"
)
YEAR_AGO = "https://www.example.com.do/tasas/2025-09-10"
TODAY = "https://www.example.com.do/tasas/2026-09-10"
QUESTION = "¿Guardo mis ahorros en pesos o en euros?"
PROSE = (
    "Nadie puede citar el tipo de cambio del próximo año. **Como historia, no como "
    "pronóstico:** el euro pasó de {{start_value}} a {{end_value}} en un año, un "
    "cambio de {{annual_rate_pct}}."
)


def _history() -> dict[str, Any]:
    """The past year of a rate from two dated pages, its change left to Argus."""
    return {
        "name": "euro_last_year",
        "kind": "growth_projection",
        "solve_for": "annual_rate_pct",
        "inputs": [
            {
                "name": "start_value",
                "value": 64.10,
                "source": "page",
                "source_url": YEAR_AGO,
                "as_of": "2025-09-10",
                "currency": "DOP",
            },
            {
                "name": "end_value",
                "value": 68.90,
                "source": "page",
                "source_url": TODAY,
                "as_of": "2026-09-10",
                "currency": "DOP",
            },
            {"name": "periods", "value": 1, "source": "assumption"},
            {"name": "periods_per_year", "value": 1, "source": "assumption"},
        ],
    }


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="currency choice",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
    )


def test_the_research_instructions_ask_for_the_recent_past_instead_of_a_projection() -> (
    None
):
    assert RETRIEVAL_INSTRUCTIONS.count(HISTORY_LINE) == 1
    assert SCENARIO_RETRIEVAL_INSTRUCTIONS.count(HISTORY_LINE) == 1


def test_a_choice_on_a_rate_nobody_can_cite_publishes_the_past_year_argus_computed(
    monkeypatch,
) -> None:
    set_research_query(monkeypatch, globals(), question_kind="concept", symbols=[])
    transport = RecordingTransport(
        [
            agent_response(
                text=typed_answer_text(
                    PROSE, [], _history(), source_urls=[YEAR_AGO, TODAY]
                ),
                sources=[YEAR_AGO, TODAY],
                tickers=[],
            )
        ]
    )
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )

    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(),
            state=RunState.new(current_user_message=QUESTION, recent_thread_history=[]),
            user=READER,
        )
    )

    assert result is not None
    sent = json.loads(transport.requests[0].content.decode())
    assert HISTORY_LINE in sent["instructions"]
    card = result.stage_patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "growth_projection"
    assert card["outcome"]["status"] == "succeeded"
    sources = card["arguments"]["sources"]
    assert (sources["start_value"]["url"], sources["start_value"]["date"]) == (
        YEAR_AGO,
        "2025-09-10",
    )
    assert (sources["end_value"]["url"], sources["end_value"]["date"]) == (
        TODAY,
        "2026-09-10",
    )
    assert card["presentation"]["answer"]["value"] == pytest.approx(
        (68.90 / 64.10 - 1) * 100, rel=1e-3
    )
    answer = result.stage_patch["assistant_response"]
    assert "Como historia, no como pronóstico" in answer
    assert "{{" not in answer
    assert "degraded" not in result.stage_patch["research"]
    rows = (result.stage_patch.get("next_experiments") or {}).get("rows") or []
    assert MARKET_COUNTERFACTUAL_KIND not in [row["kind"] for row in rows]
