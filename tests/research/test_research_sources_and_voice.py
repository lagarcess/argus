"""Sources are evidence, and internal names are never the user's problem.

Two locks the founder review asked for after seeing three different source
behaviors across shapes and a screening answer that named provider tools:

1. No rail shape may ask the model to author a source line, and every shape
   emits its sources through the one typed surface grounded discovery uses.
2. No assistant-facing prose may contain a declared provider tool name, and
   the guard derives from the configuration rather than a hand list.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.config import declared_tool_names
from argus.domain.research.perplexity_agent import (
    PerplexityAgentClient,
    strip_mechanism_narration,
)

from tests.research.conftest import RecordingTransport, agent_response

REPO_ROOT = Path(__file__).resolve().parents[2]
USER = UserState(user_id="sources", language_preference="en")


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="question",
        semantic_turn_act="educational_question",
        requires_clarification=False,
        candidate_strategy_draft=StrategySummary(),
    )


def _run(message: str, monkeypatch: pytest.MonkeyPatch, **fields: Any):
    async def classify(**_kwargs: Any) -> ra.ResearchQueryExtraction:
        return ra.ResearchQueryExtraction(**fields)

    monkeypatch.setattr(ra, "_classify_research_question", classify)
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.research_allowance_available = True
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(), state=state, user=USER
        )
    )


def test_sources_reach_the_typed_surface_in_the_shape_the_panel_renders(
    monkeypatch,
) -> None:
    document = agent_response(
        text="NVIDIA leads the tape.",
        tickers=["NVDA"],
        lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
        sources=["https://example.com/movers", "https://other.example/report"],
    )
    monkeypatch.setattr(
        grounded,
        "_client",
        lambda: PerplexityAgentClient("k", transport=RecordingTransport([document])),
    )

    result = _run("What's moving today?", monkeypatch, question_kind="market_pulse")

    assert result is not None
    sources = result.stage_patch["research"]["sources"]
    # Same typed fields grounded discovery emits, so one panel serves both.
    assert sources == [
        {
            "title": "example.com",
            "domain": "example.com",
            "url": "https://example.com/movers",
            "source_date": None,
        },
        {
            "title": "other.example",
            "domain": "other.example",
            "url": "https://other.example/report",
            "source_date": None,
        },
    ]
    # Nothing enters the typed path that the packet did not return.
    assert all(
        source["url"] in document["output"][1]["results"][0]["sources"]
        for source in sources
    )


def test_market_pulse_drawer_excludes_explicitly_stale_sources(monkeypatch) -> None:
    document = agent_response(
        text="NVIDIA (NVDA) leads today's movers.",
        tickers=["NVDA"],
        lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
        sources=[],
        web_search_invocations=1,
    )
    document["output"].insert(
        2,
        {
            "type": "search_results",
            "results": [
                {
                    "url": "https://www.cnbc.com/2016/06/16/old-movers.html",
                    "title": "Old movers",
                    "date": "2016-06-16",
                },
                {
                    "url": "https://www.slickcharts.com/gainers",
                    "title": "April gainers",
                    "date": "2026-04-01",
                },
                {
                    "url": "https://www.nasdaq.com/market-activity/stocks/screener",
                    "title": "Today's market activity",
                    "date": "2026-08-12",
                },
            ],
        },
    )
    monkeypatch.setattr(
        grounded,
        "_client",
        lambda: PerplexityAgentClient("k", transport=RecordingTransport([document])),
    )

    result = _run(
        "What's moving today?",
        monkeypatch,
        question_kind="market_pulse",
        period_start_date="2026-08-12",
    )

    assert result is not None
    assert [source["url"] for source in result.stage_patch["research"]["sources"]] == [
        "https://www.nasdaq.com/market-activity/stocks/screener"
    ]


def test_a_pure_quote_without_public_links_stays_silent_about_the_drawer(
    monkeypatch,
) -> None:
    """A quote needs provider provenance, not a fake publisher link. The
    provider receipt owns that provenance, so user copy must not narrate an
    empty source drawer."""
    monkeypatch.setattr(
        grounded,
        "_client",
        lambda: PerplexityAgentClient(
            "k",
            transport=RecordingTransport(
                [agent_response(text="Apple closed at $312.41.", sources=[])]
            ),
        ),
    )

    result = _run(
        "What is Apple trading at?",
        monkeypatch,
        question_kind="live_quote",
        symbols=["AAPL"],
    )

    assert result is not None
    assert result.stage_patch["research"]["sources"] == []
    answer = result.stage_patch["assistant_response"]
    assert answer == "Apple closed at $312.41."
    assert "source" not in answer.lower()


def test_no_rail_prompt_asks_the_model_for_sources_or_names_a_tool() -> None:
    """Fix the invitation, not just the symptom: a prompt that asks about
    tools or citations gets exactly that back. Checked on the prompts that
    are actually sent, for every shape."""
    subjects = [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}]
    for kind in (
        "market_pulse",
        "screening",
        "sector_radar",
        "company_lookup",
        "live_quote",
        "cross_company",
        "etf_constituents",
    ):
        prompt = grounded._research_prompt(
            message="what is moving today",
            subjects=subjects,
            period=None,
            language="en",
            question_kind=kind,
            criteria=["under a 20 P/E"],
            sector="semiconductors",
        )
        for tool in declared_tool_names():
            assert tool not in prompt, f"{kind} prompt names the tool {tool!r}"
        assert "Do not write a sources or citations line" in prompt
        assert "Never name tools, providers, models, or internal systems" in prompt

    retry = grounded._survey_retry_prompt(
        question_kind="market_pulse", message="anything moving", language="en"
    )
    for tool in declared_tool_names():
        assert tool not in retry
    assert "Do not write a sources line" in retry

    publisher_retry = grounded._publisher_source_retry_prompt(
        "Explain Apple's growth.", language="en"
    )
    for tool in declared_tool_names():
        assert tool not in publisher_retry
    assert "Do not write a sources or citations line" in publisher_retry


@pytest.mark.parametrize(
    "prose",
    [
        "The requested finance_search tool was not available, so I checked "
        "20 tickers using finance_quotes data.",
        "I confirmed classifications with finance_company_profile.",
        "I used web_search for this.",
        "Retrieved with fetch_url.",
    ],
)
def test_declared_tool_vocabulary_never_reaches_the_reader(prose: str) -> None:
    cleaned = strip_mechanism_narration(f"Chips led the tape. {prose}")
    assert "Chips led the tape." in cleaned
    for tool in declared_tool_names():
        assert tool not in cleaned
    # The families around the declared names go too: the leak that prompted
    # this guard named finance_quotes and finance_company_profile, neither of
    # which is declared.
    assert "finance_quotes" not in cleaned
    assert "finance_company_profile" not in cleaned


def test_ordinary_finance_prose_survives_the_guard() -> None:
    prose = (
        "Revenue grew 12% year over year. Margins held near 43%. "
        "Free cash flow was $3.4B."
    )
    assert strip_mechanism_narration(prose) == prose


def test_the_guard_follows_the_configuration_not_a_hand_list() -> None:
    declared = declared_tool_names()
    assert declared, "the rail must declare the tools it uses"
    guard = (REPO_ROOT / "src/argus/domain/research/perplexity_agent.py").read_text(
        encoding="utf-8"
    )
    guard_body = guard[guard.index("def _provider_vocabulary_pattern") :]
    for tool in declared:
        assert f'"{tool}"' not in guard_body, (
            f"{tool!r} is hardcoded in the guard; derive it from the config "
            "so a newly configured tool is covered the day it is added"
        )
