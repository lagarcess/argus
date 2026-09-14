"""A stated amount scaled by a rate, with no invented annual time basis."""

from __future__ import annotations

from typing import Any

import pytest
from argus.domain.tool_contracts import ToolCall, ToolResultCard
from faker import Faker

fake = Faker()


def _card(**changes: Any) -> ToolResultCard:
    from argus.domain.calculations.scaled_amount import get_scaled_amount_declaration

    declaration = get_scaled_amount_declaration()
    arguments = {
        "currency": "DOP",
        "amount": 25_000,
        "rate": 2,
        "rate_unit": "percent",
        "operation": "multiply",
        **changes,
    }
    call = ToolCall(tool_name=declaration.name, call_id=fake.uuid4(), arguments=arguments)
    return declaration.result_card(
        call=call, outcome=declaration.invoke_sync(arguments), artifact_id=fake.uuid4()
    )


@pytest.mark.parametrize(
    ("changes", "expected", "currency"),
    [
        ({}, 500, "DOP"),
        ({"rate": 0}, 0, "DOP"),
        ({"amount": 0}, 0, "DOP"),
        ({"rate": 2.5, "rate_unit": "multiple"}, 62_500, "DOP"),
        ({"operation": "divide", "rate": 25}, 100_000, "DOP"),
        (
            {
                "rate": 62.5,
                "rate_unit": "multiple",
                "operation": "divide",
                "output_currency": "USD",
            },
            400,
            "USD",
        ),
        (
            {
                "amount": 400,
                "currency": "USD",
                "rate": 62.5,
                "rate_unit": "multiple",
                "output_currency": "DOP",
            },
            25_000,
            "DOP",
        ),
    ],
)
def test_scales_the_stated_amount_without_annualizing(
    changes: dict[str, Any], expected: float, currency: str
) -> None:
    card = _card(**changes)
    assert card.outcome.status == "succeeded"
    assert card.presentation.answer.value == pytest.approx(expected)
    assert card.presentation.answer.unit.interpolation_args == {"code": currency}
    assert card.outcome.result["output_currency"] == currency
    assert not card.presentation.rows


@pytest.mark.parametrize("operation", ["multiply", "divide"])
def test_exchange_rate_input_exposes_the_quotation_direction(operation: str) -> None:
    card = _card(
        rate_unit="multiple", rate=62.5, operation=operation, output_currency="USD"
    )
    rate = next(item for item in card.presentation.inputs if item.name == "rate")
    assert rate.unit.locale_key == "tools.calc.units.currency_ratio"
    assert rate.unit.interpolation_args == (
        {"numerator": "USD", "denominator": "DOP"}
        if operation == "multiply"
        else {"numerator": "DOP", "denominator": "USD"}
    )
    assert card.presentation.notes[0].locale_key == f"tools.calc.notes.scaled_{operation}"


def test_percent_rate_is_presented_as_percent() -> None:
    rate = next(item for item in _card().presentation.inputs if item.name == "rate")
    assert rate.value == 2
    assert rate.unit.locale_key == "chat.tools.units.percent"


def test_zero_divisor_names_the_rate_without_a_numerical_answer() -> None:
    card = _card(rate=0, operation="divide")
    assert card.outcome.failure.code == "division_by_zero"
    assert card.outcome.failure.fields == ["rate"]
    assert card.presentation.answer is None


@pytest.mark.parametrize("field", ["amount", "rate"])
def test_a_missing_number_requests_that_number(field: str) -> None:
    card = _card(**{field: None})
    assert card.outcome.failure.code == "missing_input"
    assert card.outcome.failure.fields == [field]
    assert card.presentation.answer is None


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": -1},
        {"rate": -1},
        {"rate_unit": "annual"},
        {"output_currency": "unknown"},
    ],
)
def test_invalid_inputs_do_not_return_an_answer(changes: dict[str, Any]) -> None:
    card = _card(**changes)
    assert card.outcome.status == "invalid"
    assert card.presentation.answer is None


def test_editing_the_rate_recomputes_the_same_amount_and_currency() -> None:
    from argus.domain.calculations.scaled_amount import get_scaled_amount_declaration

    declaration = get_scaled_amount_declaration()
    card = _card()
    revised = declaration.recompute_arguments(card.arguments, {"rate": 3})
    outcome = declaration.invoke_sync(revised)
    assert outcome.result["scaled_amount"] == pytest.approx(750)
    assert revised.currency == "DOP"
    assert revised.amount == card.arguments["amount"]
