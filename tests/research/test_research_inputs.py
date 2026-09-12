"""Any grounded math, step 10: retrieval supplies typed inputs, Argus computes.

The vocabulary the retrieval ask spells out is the declarations' own argument
names; a row feeds an input only under that exact name. The user's stated
inputs win over retrieved ones, a scenario read with no calculation defaults to
the valuation declaration and records it, and the cache identity names the
inputs an ask retrieves.
"""

from __future__ import annotations

from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.interpreter.calculation_request import CalculationRequest
from argus.agent_runtime.research_inputs import (
    RETRIEVAL_MEANINGS,
    SCENARIO_CALCULATION_DEFAULTED_REASON_CODE,
    arguments_from_rows,
    retrieval_inputs,
    scenario_calculation,
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import StrategySummary
from argus.domain.capability_registry import get_tool_catalog
from argus.domain.research.contracts import ResearchPacket, RetrievedRow

CATALOG = get_tool_catalog()


def _read(calculation: dict | None) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="scenario",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
        calculation=(
            CalculationRequest.model_validate(calculation) if calculation else None
        ),
        research_query=ResearchQueryExtraction(
            question_kind="company_lookup", symbols=["NVDA"], scenario_question=True
        ),
    )


def _row(label: str, value: float, *, url: str | None, as_of: str | None = "2026-09-03"):
    return RetrievedRow(
        subject="NVIDIA",
        symbol="NVDA",
        label=label,
        value=value,
        kind="currency",
        unit="USD",
        as_of=as_of,
        source_url=url,
    )


def test_every_retrieval_meaning_names_a_declared_argument() -> None:
    for kind, meanings in RETRIEVAL_MEANINGS.items():
        declaration = CATALOG.get(kind)
        assert declaration is not None, kind
        declared = set(declaration.arguments_type.model_fields)
        assert set(meanings) <= declared, (kind, set(meanings) - declared)
        for meaning in meanings.values():
            assert meaning and "—" not in meaning


def test_the_ask_names_the_reads_inputs_minus_what_the_user_stated() -> None:
    declaration = CATALOG.get("valuation_scenarios")
    read = CalculationRequest(
        kind="valuation_scenarios",
        inputs={"symbol": "NVDA", "amount": 10000, "horizon_years": 10, "price": 200},
        retrieve=["per_share", "growth_base_pct", "price", "not_an_input"],
    )
    assert [name for name, _ in retrieval_inputs(read, declaration)] == [
        "per_share",
        "growth_base_pct",
    ]
    everything = CalculationRequest(kind="valuation_scenarios", inputs={"amount": 1})
    assert [name for name, _ in retrieval_inputs(everything, declaration)] == list(
        RETRIEVAL_MEANINGS["valuation_scenarios"]
    )


def test_a_scenario_read_without_a_calculation_defaults_to_valuation_and_records_it() -> None:
    read = _read(None)
    request = scenario_calculation(read)
    assert request.kind == "valuation_scenarios"
    assert request.retrieve == list(RETRIEVAL_MEANINGS["valuation_scenarios"])
    assert SCENARIO_CALCULATION_DEFAULTED_REASON_CODE in read.reason_codes

    typed = _read({"kind": "valuation_scenarios", "inputs": {"amount": 500}})
    assert scenario_calculation(typed) is typed.calculation
    assert SCENARIO_CALCULATION_DEFAULTED_REASON_CODE not in typed.reason_codes

    stated_kind_without_pages = _read(
        {"kind": "debt_to_income", "inputs": {"monthly_income": 5000}}
    )
    request = scenario_calculation(stated_kind_without_pages)
    assert request.kind == "valuation_scenarios"
    assert request.inputs == {"monthly_income": 5000}


def test_rows_feed_inputs_only_under_their_exact_names_and_the_user_wins() -> None:
    declaration = CATALOG.get("valuation_scenarios")
    read = CalculationRequest(
        kind="valuation_scenarios",
        inputs={"amount": 10000, "horizon_years": 10, "growth_base_pct": 12},
    )
    packet = ResearchPacket(
        answer_markdown="",
        rows=(
            _row("Price", 218.36, url=None, as_of="2026-09-10"),
            _row("per_share", 4.5, url="https://example.com/eps"),
            _row("growth_base_pct", 25.0, url="https://example.com/growth"),
            _row("analyst price target", 300.0, url="https://example.com/target"),
            _row("multiple_high", 40.0, url="https://example.com/pe", as_of="Sept 2026"),
        ),
    )
    arguments = arguments_from_rows(
        packet, read, declaration, currency="USD", symbol="nvda"
    )
    assert arguments["symbol"] == "nvda"
    assert arguments["currency"] == "USD"
    assert arguments["price"] == 218.36
    assert arguments["per_share"] == 4.5
    assert arguments["growth_base_pct"] == 12, "the user's stated input wins"
    assert arguments["multiple_high"] == 40.0
    assert "analyst price target" not in arguments
    assert set(arguments["sources"]) == {"price", "per_share", "multiple_high"}
    assert arguments["sources"]["price"] == {
        "kind": "page",
        "title": "NVIDIA Price",
        "date": "2026-09-10",
    }
    assert arguments["sources"]["multiple_high"] == {
        "kind": "page",
        "title": "NVIDIA multiple_high",
        "url": "https://example.com/pe",
    }


def test_the_cache_identity_names_the_calculation_and_the_inputs_it_asks_for() -> None:
    query = ResearchQueryExtraction(
        question_kind="company_lookup", symbols=["NVDA"], scenario_question=True
    )
    subjects = [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}]

    def key(computation):
        return grounded._cache_key_for(
            query=query,
            subjects=subjects,
            shape="balanced",
            capability_class="balanced_lookup",
            message="what will NVDA be worth",
            language="en",
            country=None,
            scenario=True,
            computation=computation,
        )

    everything = grounded._scenario_computation(_read(None))
    fewer = grounded._scenario_computation(
        _read(
            {
                "kind": "valuation_scenarios",
                "inputs": {"price": 200},
                "retrieve": ["per_share", "growth_base_pct"],
            }
        )
    )
    assert key(everything) != key(fewer)
    assert key(everything) == key(grounded._scenario_computation(_read(None)))
