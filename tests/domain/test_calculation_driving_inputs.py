"""A calculation card marks the few inputs that drive its result, never a blank,
and a source names market data or an assumption without a citation."""

from __future__ import annotations

import pytest
from argus.domain.calculations import get_calculation_declarations, is_free_calculation
from argus.domain.tool_contracts import LocalizedText, ToolFactSource, ToolInputFact
from argus.domain.tool_declaration import MAX_DRIVING_INPUTS, ToolPolicy

from tests.domain.calculations import WORKED_ARGUMENTS
from tests.domain.calculations.support import run_calculation


def test_every_declaration_names_editable_driving_inputs() -> None:
    for declaration in get_calculation_declarations():
        if not is_free_calculation(declaration):
            continue
        policy = declaration.policy
        assert set(policy.driving_fields) <= set(policy.editable_fields)
        if declaration.name != "ranked_comparison":
            assert policy.driving_fields, declaration.name


@pytest.mark.parametrize("name", sorted(WORKED_ARGUMENTS))
def test_a_card_marks_at_most_five_driving_inputs_and_never_a_blank(name: str) -> None:
    card = run_calculation(name, WORKED_ARGUMENTS[name])
    driving = [fact for fact in card.presentation.inputs if fact.driving]
    assert len(driving) <= MAX_DRIVING_INPUTS
    assert all(fact.value is not None and not fact.unknown for fact in driving)


def test_the_driving_inputs_follow_the_declared_order_and_skip_the_unknown() -> None:
    loan = run_calculation("time_value", WORKED_ARGUMENTS["time_value"])
    assert {fact.name for fact in loan.presentation.inputs if fact.driving} == {
        "present_value",
        "future_value",
        "annual_rate_pct",
        "periods",
    }
    scenarios = run_calculation(
        "valuation_scenarios", WORKED_ARGUMENTS["valuation_scenarios"]
    )
    assert {fact.name for fact in scenarios.presentation.inputs if fact.driving} == {
        "price",
        "per_share",
        "growth_base_pct",
        "horizon_years",
        "multiple_base",
    }


def test_market_data_carries_its_date_and_an_assumption_carries_nothing() -> None:
    assert ToolFactSource(kind="market_data", date="2026-09-11").date == "2026-09-11"
    assert ToolFactSource(kind="assumption").model_dump(mode="json") == {
        "kind": "assumption"
    }
    for invalid in (
        {"kind": "market_data", "url": "https://example.com"},
        {"kind": "assumption", "date": "2026-09-11"},
        {"kind": "user", "title": "Rate sheet"},
    ):
        with pytest.raises(ValueError):
            ToolFactSource.model_validate(invalid)


def test_a_driving_input_always_carries_a_value_and_is_editable() -> None:
    with pytest.raises(ValueError):
        ToolInputFact(
            name="price", label=LocalizedText(locale_key="x"), value=None, driving=True
        )
    with pytest.raises(ValueError):
        ToolPolicy(editable_fields=("price",), driving_fields=("per_share",))
