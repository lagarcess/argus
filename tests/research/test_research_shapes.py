"""Section 2's five shapes are one rail: each reaches it and ends runnable.

Section 13 requires a natural question of each shape to return a grounded,
sourced answer with no menu and no capability discovery. These locks cover
the routing and the contract each shape owes: grounded data, a runnable next
step, the right capability class, and the right section 7 cache class.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UserState,
)
from argus.domain.research.cache import data_class_for
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import RecordingTransport, agent_response

USER = UserState(user_id="shapes", language_preference="en")
SPANISH = UserState(user_id="shapes-es", language_preference="es-419")


def _interpretation(**overrides: Any) -> StructuredInterpretation:
    fields: dict[str, Any] = {
        "intent": "unsupported_or_out_of_scope",
        "task_relation": "new_task",
        "user_goal_summary": "question",
        "semantic_turn_act": "educational_question",
        "requires_clarification": False,
        "candidate_strategy_draft": StrategySummary(),
    }
    fields.update(overrides)
    return StructuredInterpretation(**fields)


def _state(message: str) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.research_allowance_available = True
    return state


def _classify(monkeypatch: pytest.MonkeyPatch, **fields: Any) -> None:
    async def classify(**_kwargs: Any) -> ra.ResearchQueryExtraction:
        return ra.ResearchQueryExtraction(**fields)

    monkeypatch.setattr(ra, "_classify_research_question", classify)


def _wire(monkeypatch: pytest.MonkeyPatch, documents) -> RecordingTransport:
    transport = RecordingTransport(documents)
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    return transport


def _prompt_sent(transport: RecordingTransport) -> str:
    body = json.loads(transport.requests[0].content.decode())
    return str(body.get("input") or "")


def _run(message: str, *, user: UserState = USER):
    return asyncio.run(
        ra.research_answer_stage_result(
            interpretation=_interpretation(), state=_state(message), user=user
        )
    )


MOVERS = agent_response(
    text="NVIDIA (NVDA) leads today's gainers, up 4.2% to $198.40 as of 3:15pm ET.",
    tickers=["NVDA"],
    lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
)


def _web_sources_without_assets(*, text: str) -> dict[str, Any]:
    document = agent_response(
        text=text,
        tickers=[],
        sources=[],
        invocations=0,
        web_search_invocations=1,
    )
    finance_results = next(
        item for item in document["output"] if item.get("type") == "finance_results"
    )
    finance_results["tickers"] = []
    finance_results["results"] = []
    document["output"].insert(
        2,
        {
            "type": "search_results",
            "results": [
                {
                    "url": f"https://publisher-{index}.example/movers",
                    "title": f"Market source {index}",
                    "date": "2026-08-12",
                }
                for index in range(5)
            ],
        },
    )
    return document


def test_market_pulse_grounds_and_ends_runnable(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    transport = _wire(monkeypatch, [MOVERS])

    result = _run("What are the biggest movers today?")

    assert result is not None
    assert transport.requests, "market pulse must ground, not answer from memory"
    sidecar = result.stage_patch["research"]
    assert sidecar["capability_class"] == "screening"
    assert sidecar["usage"]["invocations"] == 1
    # The provider's own verified name becomes the runnable next step.
    rows = result.stage_patch["next_experiments"]["rows"]
    assert rows and "NVDA" in json.dumps(rows)
    assert data_class_for(question_kind="market_pulse") == "movers"


@pytest.mark.parametrize(
    ("user", "provider_text", "expected"),
    [
        pytest.param(
            USER,
            "Treat these figures as general background. None of these assets qualify.",
            "I found sources, but could not extract today's market movers from them.",
            id="english",
        ),
        pytest.param(
            SPANISH,
            "Trátalas como referencia general. Ninguno de estos activos califica.",
            "Encontré fuentes, pero no pude extraer de ellas los movimientos del mercado de hoy.",
            id="es-419",
        ),
    ],
)
def test_retrieval_without_a_concrete_mover_has_one_precise_recovery(
    monkeypatch,
    user: UserState,
    provider_text: str,
    expected: str,
) -> None:
    _classify(
        monkeypatch,
        question_kind="market_pulse",
        symbols=[],
        period_start_date="2026-08-12",
    )
    transport = _wire(
        monkeypatch,
        [_web_sources_without_assets(text=provider_text)],
    )

    result = _run("What are today's market movers?", user=user)

    assert result is not None
    assert len(transport.requests) == 1, "web retrieval is retrieval, not a retry signal"
    assert result.stage_patch["assistant_response"] == expected
    assert result.stage_patch["research"]["degraded"] == {
        "code": "survey_synthesis_incomplete"
    }
    assert len(result.stage_patch["research"]["sources"]) == 5
    assert "next_experiments" not in result.stage_patch
    answer = result.stage_patch["assistant_response"].lower()
    assert "these figures" not in answer
    assert "estos activos" not in answer


def test_screening_carries_every_stated_condition_to_the_provider(
    monkeypatch,
) -> None:
    _classify(
        monkeypatch,
        question_kind="screening",
        symbols=[],
        screening_criteria=["yielding over 4 percent", "dividend stocks"],
    )
    transport = _wire(
        monkeypatch,
        [
            agent_response(
                text="Intel (INTC) yields above 4%.",
                tickers=["INTC"],
                lookup_rows=[("Intel", "INTC", "Intel Corporation")],
            )
        ],
    )

    result = _run("Find dividend stocks yielding over 4 percent")

    assert result is not None
    prompt = _prompt_sent(transport)
    # A screen that silently drops the user's threshold is worse than none.
    assert "yielding over 4 percent" in prompt
    assert "dividend stocks" in prompt
    assert result.stage_patch["research"]["capability_class"] == "screening"
    assert result.stage_patch["next_experiments"]["rows"]


def test_sector_radar_asks_for_analysis_not_a_list_of_names(monkeypatch) -> None:
    _classify(
        monkeypatch,
        question_kind="sector_radar",
        symbols=[],
        sector_of_interest="cybersecurity",
    )
    transport = _wire(
        monkeypatch,
        [
            agent_response(
                text=(
                    "Microsoft (MSFT) is up 6% this month as federal "
                    "contracts support cybersecurity demand."
                ),
                tickers=["MSFT"],
                lookup_rows=[("Microsoft", "MSFT", "Microsoft Corporation")],
            )
        ],
    )

    result = _run("What's happening in cybersecurity stocks?")

    assert result is not None
    prompt = _prompt_sent(transport)
    assert "cybersecurity" in prompt
    # Sector analysis, explicitly not a list of company descriptions.
    assert "what is actually happening in this sector" in prompt
    assert "sector analysis" in prompt
    sidecar = result.stage_patch["research"]
    assert sidecar["capability_class"] == "screening"
    assert result.stage_patch["next_experiments"]["rows"]
    # A sector answer is not the find operation: no discovery sidecar.
    assert "discovery" not in result.stage_patch


def test_survey_shapes_degrade_honestly_when_the_provider_is_unavailable(
    monkeypatch,
) -> None:
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    monkeypatch.setattr(grounded, "_client", lambda: None)

    result = _run("What's moving in the market?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"]["code"] == "research_unavailable_not_configured"
    answer = result.stage_patch["assistant_response"]
    # Honest, and never fabricated figures.
    assert "couldn't complete" in answer.lower()
    assert "%" not in answer
    assert "none of these" not in answer.lower()
    assert "next_experiments" not in result.stage_patch


def test_survey_synthesis_requires_an_unambiguous_short_ticker_token() -> None:
    assets = [
        {"symbol": "A", "name": "Agilent", "asset_class": "equity"},
        {"symbol": "IT", "name": "Gartner", "asset_class": "equity"},
    ]

    assert (
        grounded._named_verified_symbols(
            "Subió a máximos. It rose with the market.", assets
        )
        == set()
    )
    assert (
        grounded._named_verified_symbols(
            "A rally followed earnings. IT spending increased.", assets
        )
        == set()
    )
    assert (
        grounded._named_verified_symbols(
            "Agilent reported results.\nA rally followed earnings.\n"
            "Gartner published a forecast.\nIT spending increased.",
            assets,
        )
        == set()
    )
    assert grounded._named_verified_symbols(
        "Agilent (A) and Gartner (IT) led the gainers.", assets
    ) == {"A", "IT"}
    assert grounded._named_verified_symbols(
        "Agilent A led the gainers. Gartner IT lagged.", assets
    ) == {"A", "IT"}
    assert grounded._named_verified_symbols(
        "| TICKER | COMPANY |\n| --- | --- |\n| A | Agilent |\n| IT | Gartner |",
        assets,
    ) == {"A", "IT"}


def test_survey_shapes_answer_natively_in_spanish(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="sector_radar", sector_of_interest="banca")
    transport = _wire(
        monkeypatch,
        [
            agent_response(
                text="Apple (AAPL) sube 3% este mes.",
                tickers=["AAPL"],
                lookup_rows=[("Apple", "AAPL", "Apple Inc.")],
            )
        ],
    )

    result = _run("¿Qué está pasando en el sector bancario?", user=SPANISH)

    assert result is not None
    assert "español latinoamericano" in _prompt_sent(transport)
    assert result.stage_patch["next_experiments"]["rows"][0]["label"].startswith("Probar")


def test_a_bare_comparison_is_a_question_not_a_half_built_backtest(
    monkeypatch,
) -> None:
    """The P1: "Compare PLTR to LMT" carries no capital, window, or execution
    verb, yet the builder claimed it and asked for a date window. The same
    rail classifier now sees the turn before the clarification lands."""
    _classify(monkeypatch, question_kind="cross_company", symbols=["PLTR", "LMT"])
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=_interpretation(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                requires_clarification=True,
                missing_required_fields=["date_range"],
                # The interpreter injects this default for any two-asset
                # mention; it is what shut the rail out in production.
                candidate_strategy_draft=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["PLTR", "LMT"],
                ),
            ),
            state=_state("Compare PLTR to LMT"),
            user=USER,
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is not None, "a bare comparison must not reach the builder"
    # It answers as research and still ends one tap from a real test.
    assert "research_job_request" in result.stage_patch
    assert result.stage_patch["research_job_request"]["shape"] == "thorough"


def test_a_real_build_request_still_belongs_to_the_builder(monkeypatch) -> None:
    """The widened entry is the same classifier, not a land grab: a request
    to run something classifies as none and falls through untouched."""
    _classify(monkeypatch, question_kind="none", symbols=["AAPL"])
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=_interpretation(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                requires_clarification=True,
                missing_required_fields=["date_range"],
                candidate_strategy_draft=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                ),
            ),
            state=_state("Backtest Apple with $1000 a month"),
            user=USER,
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is None


def test_flag_off_keeps_the_builder_gate_exactly_as_it_was(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    async def explode(**_kwargs: Any):
        raise AssertionError("no classifier may run for a builder turn flag-off")

    monkeypatch.setattr(ra, "_classify_research_question", explode)
    monkeypatch.setattr(ka, "_classify_question", explode)
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=_interpretation(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                requires_clarification=True,
            ),
            state=_state("Compare PLTR to LMT"),
            user=USER,
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is None


def test_a_stated_amount_keeps_the_turn_with_the_builder(monkeypatch) -> None:
    """Real execution evidence is untouchable: capital, cadence, sizing, and
    rules all keep a turn on the strategy route, whatever the classifier
    would have said."""

    async def explode(**_kwargs: Any):
        raise AssertionError("a turn with real execution evidence never routes")

    monkeypatch.setattr(ra, "_classify_research_question", explode)
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=_interpretation(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                requires_clarification=True,
                candidate_strategy_draft=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["PLTR", "LMT"],
                    capital_amount=1000,
                ),
            ),
            state=_state("Compare PLTR to LMT with $1000"),
            user=USER,
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is None


def test_a_survey_that_never_called_the_tool_says_so(monkeypatch) -> None:
    """The one thing a market survey must not do is present model knowledge
    as the current state of the market."""
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    _wire(
        monkeypatch,
        [
            agent_response(
                text="Tech led the tape today.",
                tickers=["NVDA"],
                lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
                invocations=0,
            )
        ],
    )

    result = _run("What's moving in the market?")

    assert result is not None
    assert result.stage_patch["research"]["degraded"] == {"code": "survey_not_grounded"}
    answer = result.stage_patch["assistant_response"]
    assert answer == "I couldn't retrieve today's market movers."
    assert "these figures" not in answer.lower()
    assert "next_experiments" not in result.stage_patch


def test_survey_rows_may_come_from_the_results_not_only_a_lookup_table(
    monkeypatch,
) -> None:
    """Movers answers name their assets in the results; the resolver still
    gates every one, so nothing untradable becomes tappable."""
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    document = agent_response(text="NVDA leads.", tickers=["NVDA", "NOTAREALTICKER"])
    # No tickers_lookup table at all: the results are the only source of names.
    document["output"][1]["results"] = [
        {
            "category": "market_movers",
            "content": "| symbol | change |\n| --- | --- |\n| NVDA | +4.2% |",
            "sources": [],
            "tickers": ["NVDA", "NOTAREALTICKER"],
        }
    ]
    document["output"][1]["categories"] = ["market_movers"]
    _wire(monkeypatch, [document])

    result = _run("Which stocks are moving today?")

    assert result is not None
    rows = json.dumps(result.stage_patch["next_experiments"]["rows"])
    assert "NVDA" in rows
    assert "NOTAREALTICKER" not in rows


def test_a_survey_looks_past_untradable_movers_for_a_runnable_row(
    monkeypatch,
) -> None:
    """Movers lists lead with micro caps the catalog cannot trade. Ending on
    "nothing to test" while the answer names NVDA is a dead end, not honesty."""
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    untradable = [f"ZZZ{index}" for index in range(14)]
    document = agent_response(text="Small caps led; NVDA rose 2.3%.", tickers=[])
    document["output"][1]["results"] = [
        {
            "category": "market_movers",
            "content": "movers",
            "sources": [],
            "tickers": [*untradable, "NVDA"],
        }
    ]
    document["output"][1]["categories"] = ["market_movers"]
    document["output"][1]["tickers"] = [*untradable, "NVDA"]
    _wire(monkeypatch, [document])

    result = _run("What are the biggest movers today?")

    assert result is not None
    rows = result.stage_patch["next_experiments"]["rows"]
    assert rows, "a survey naming a tradable asset must end somewhere runnable"
    assert "NVDA" in json.dumps(rows)
    for symbol in untradable:
        assert symbol not in json.dumps(rows)


def test_a_survey_reads_the_symbols_its_own_tables_name(monkeypatch) -> None:
    """Movers answers often carry no typed ticker list at all: the assets
    live in the answer's tables. Reading those cells is the same
    deterministic markdown walk the lookup parser does, and the resolver
    still decides what becomes tappable."""
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    document = agent_response(text="", tickers=[])
    document["output"][1]["results"] = [
        {"category": "market_movers", "content": "movers", "sources": [], "tickers": []}
    ]
    document["output"][1]["categories"] = ["market_movers"]
    document["output"][1]["tickers"] = []
    document["output"][2]["content"][0]["text"] = (
        "Biggest gainers\n\n"
        "| TICKER | COMPANY | CHANGE |\n| --- | --- | --- |\n"
        "| ZZQQ | Nonexistent Corp | +180% |\n"
        "| NVDA | NVIDIA | +2.3% |\n"
    )
    _wire(monkeypatch, [document])

    result = _run("What are the biggest movers today?")

    assert result is not None
    rows = json.dumps(result.stage_patch["next_experiments"]["rows"])
    assert "NVDA" in rows
    assert "ZZQQ" not in rows


def test_an_ungrounded_survey_is_asked_again_concretely(monkeypatch) -> None:
    """A vague survey lets the model answer from memory however firmly the
    prompt asks for the tool, so the rail asks again with the concrete
    question the shape means. One retry, then honesty."""
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    transport = _wire(
        monkeypatch,
        [
            agent_response(text="Markets were mixed.", invocations=0),
            agent_response(
                text="NVDA +2.3%, TSLA -1.1%.",
                tickers=["NVDA"],
                lookup_rows=[("NVIDIA", "NVDA", "NVIDIA Corporation")],
                invocations=1,
            ),
        ],
    )

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2, "exactly one retry, never a loop"
    retry_prompt = str(
        json.loads(transport.requests[1].content.decode()).get("input") or ""
    )
    assert retry_prompt.startswith("Retrieve today's top gainers")
    # The user's words survive as context, never as the whole ask.
    assert "anything interesting moving today" in retry_prompt
    sidecar = result.stage_patch["research"]
    assert sidecar["usage"]["invocations"] == 1
    assert "degraded" not in sidecar
    assert "NVDA" in result.stage_patch["assistant_response"]


def test_a_survey_that_skips_the_tool_twice_stays_honest(monkeypatch) -> None:
    _classify(monkeypatch, question_kind="market_pulse", symbols=[])
    transport = _wire(
        monkeypatch,
        [
            agent_response(text="Markets were mixed.", invocations=0),
            agent_response(text="Still mixed.", invocations=0),
        ],
    )

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2, "the retry never loops"
    assert result.stage_patch["research"]["degraded"] == {"code": "survey_not_grounded"}
