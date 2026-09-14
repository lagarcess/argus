"""An answer's calculation request advertises declared names and parses leniently."""

from __future__ import annotations

from argus.domain.calculations import get_calculation_declarations
from argus.domain.calculations.answer_request import (
    ANSWER_CALCULATION_INSTRUCTIONS,
    AnswerCalculation,
    calculation_argument_names,
    calculation_kinds,
    calculation_kinds_clause,
)


def test_the_schema_advertises_declared_kinds_and_names_and_requires_every_field() -> (
    None
):
    schema = AnswerCalculation.model_json_schema()
    assert schema["properties"]["kind"]["enum"] == list(calculation_kinds())
    assert set(schema["required"]) == set(schema["properties"])
    item = schema["$defs"]["AnswerCalculationInput"]
    assert item["properties"]["name"]["enum"] == list(calculation_argument_names())
    assert "currency" in item["properties"]["name"]["enum"]
    assert set(item["required"]) == set(item["properties"])
    assert item["properties"]["source"]["enum"] == [
        "page",
        "market_data",
        "user",
        "assumption",
    ]


def test_a_stray_name_or_kind_parses_so_the_runtime_can_drop_it_on_record() -> None:
    request = AnswerCalculation.model_validate(
        {
            "kind": "loan_wizard",
            "solve_for": None,
            "inputs": [{"name": "mystery", "value": 3, "source": "user"}],
        }
    )
    assert request.kind == "loan_wizard"
    assert request.inputs[0].value == 3
    offers = AnswerCalculation.model_validate(
        {
            "kind": "ranked_comparison",
            "inputs": [
                {
                    "name": "items",
                    "value": [{"label": "Card A", "symbol": None, "value": 24.9}],
                    "source": "page",
                }
            ],
        }
    )
    assert offers.inputs[0].value == [{"label": "Card A", "symbol": None, "value": 24.9}]
    assert (
        AnswerCalculation.model_validate(
            {
                "kind": "time_value",
                "inputs": [{"name": "direction", "value": True, "source": "user"}],
            }
        )
        .inputs[0]
        .value
        is True
    )


def test_the_catalogue_lists_every_kind_with_its_inputs_and_results() -> None:
    clause = calculation_kinds_clause()
    for declaration in get_calculation_declarations():
        assert f"- {declaration.name}: {declaration.description}" in clause
    assert "Results: " in clause and "total_interest" in clause
    assert "{{name}}" in ANSWER_CALCULATION_INSTRUCTIONS
    assert "—" not in ANSWER_CALCULATION_INSTRUCTIONS + clause


def test_the_provider_schema_carries_no_bound_a_strict_model_refuses() -> None:
    """Anthropic-backed research models refuse a strict schema with item or
    numeric bounds (recorded 2026-09-12: HTTP 400 until maxItems was removed),
    so limits are enforced at parse time instead."""
    import json

    from argus.domain.research.answer_contract import typed_answer_json_schema

    text = json.dumps(typed_answer_json_schema())
    for bound in ("maxItems", "minItems", "maximum", "minimum", "maxLength", "minLength"):
        assert f'"{bound}"' not in text, bound
    many = [{"name": "amount", "value": index, "source": "user"} for index in range(40)]
    assert (
        len(
            AnswerCalculation.model_validate(
                {"kind": "time_value", "inputs": many}
            ).inputs
        )
        == 16
    )


def test_historical_catalogue_exposes_observed_window_reference_names():
    line = next(
        line
        for line in calculation_kinds_clause().splitlines()
        if line.startswith("- historical_drawdown:")
    )
    results = line.split("Results: ", 1)[1]
    assert "observed_start_date" in results
    assert "observed_end_date" in results
