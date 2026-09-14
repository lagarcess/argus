"""The time value declaration against worked examples, and its typed failures."""

from __future__ import annotations

import pytest
from faker import Faker

from tests.domain.calculations.support import (
    answer_value,
    declaration,
    row_value,
    run_calculation,
)

fake = Faker()


def _loan(**overrides):
    return {
        "direction": "borrow",
        "currency": "USD",
        "present_value": 200_000,
        "payment": None,
        "future_value": 0,
        "annual_rate_pct": 6,
        "periods": 360,
        **overrides,
    }


def test_the_mortgage_table_payment_with_totals_and_a_balance_path() -> None:
    card = run_calculation("time_value", _loan(start_date="2026-09-11"))
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(1_199.10)
    assert card.presentation.answer.unit.interpolation_args == {"code": "USD"}
    assert row_value(card, "total_interest") == pytest.approx(231_676.38, abs=0.01)
    assert card.presentation.visual is not None
    assert card.presentation.visual.kind == "value_path"
    assert card.presentation.visual.series[0].time == "2026-10-11"
    assert card.presentation.visual.series[-1].value == pytest.approx(0.0, abs=0.01)


def test_the_savings_goal_answers_the_monthly_deposit_in_the_stated_currency() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "MXN",
            "present_value": 0,
            "payment": None,
            "future_value": 25_000,
            "annual_rate_pct": 5,
            "periods": 10,
        },
    )
    assert answer_value(card) == pytest.approx(2_453.48)
    assert card.presentation.answer.unit.interpolation_args == {"code": "MXN"}
    inputs = {fact.name: fact for fact in card.presentation.inputs}
    assert inputs["payment"].unknown and inputs["payment"].source.kind == "computed"
    assert (
        inputs["future_value"].editable and inputs["future_value"].source.kind == "user"
    )
    assert card.presentation.visual is None


def test_paying_extra_is_worth_it_and_the_card_says_by_how_much() -> None:
    baseline = run_calculation(
        "time_value",
        {
            "direction": "borrow",
            "currency": "DOP",
            "present_value": 180_000,
            "payment": 5_000,
            "future_value": 0,
            "annual_rate_pct": 14,
            "periods": None,
        },
    )
    faster = run_calculation(
        "time_value", {**baseline.arguments, "payment": 6_000, "sources": {}}
    )
    assert answer_value(baseline) == pytest.approx(47.0)
    assert answer_value(faster) < answer_value(baseline)
    assert row_value(faster, "total_interest") < row_value(baseline, "total_interest")


def test_a_payment_below_interest_names_the_field_and_offers_a_repair() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "borrow",
            "currency": "DOP",
            "present_value": 180_000,
            "payment": 2_000,
            "future_value": 0,
            "annual_rate_pct": 14,
            "periods": None,
        },
    )
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "payment_below_interest"
    assert card.outcome.failure.fields == ["payment"]
    repair = card.outcome.failure.repair
    assert repair is not None and repair.kind == "set_inputs"
    assert repair.changes["payment"] > 2_100
    assert card.presentation.answer is None
    # The inputs stay on the card, typeable, when the answer is withheld.
    assert {fact.name for fact in card.presentation.inputs} >= {"payment", "periods"}
    repaired = run_calculation("time_value", {**card.arguments, **repair.changes})
    assert repaired.outcome.status == "succeeded"


def test_a_goal_already_covered_is_a_zero_payment_with_a_note_not_a_guess() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "USD",
            "present_value": 100_000,
            "payment": None,
            "future_value": 25_000,
            "annual_rate_pct": 5,
            "periods": 10,
        },
    )
    assert answer_value(card) == 0.0
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.already_covered"
    ]


def test_zero_stays_a_known_input_and_two_blanks_are_invalid() -> None:
    zero_rate = run_calculation("time_value", _loan(annual_rate_pct=0))
    assert answer_value(zero_rate) == pytest.approx(200_000 / 360, abs=0.005)
    two_blanks = run_calculation("time_value", _loan(annual_rate_pct=None))
    assert two_blanks.outcome.status == "invalid"
    assert two_blanks.outcome.failure.code == "exactly_one_unknown"


def test_the_declaration_is_free_local_editable_and_solves_one_unknown() -> None:
    item = declaration("time_value")
    assert item.policy.execution == "local"
    assert item.policy.confirmation == "never"
    assert item.policy.external_calls == 0
    assert set(item.policy.editable_fields) >= {
        "present_value",
        "payment",
        "future_value",
        "annual_rate_pct",
        "periods",
    }
    assert [rule.fields for rule in item.rules] == [
        ("present_value", "payment", "future_value", "annual_rate_pct", "periods")
    ]


def test_recompute_keeps_the_unknown_and_marks_the_edited_input_as_stated() -> None:
    item = declaration("time_value")
    original = _loan(
        sources={
            "present_value": {"kind": "page", "title": "Rate sheet", "date": "2026-09-01"}
        }
    )
    revised = item.recompute_arguments(original, {"present_value": 150_000})
    assert revised.present_value == 150_000
    assert revised.payment is None
    assert revised.sources["present_value"].kind == "user"
    with pytest.raises(ValueError, match="unknown"):
        item.recompute_arguments(original, {"payment": 1_000})


def test_a_yearly_plan_solves_its_periods_in_years() -> None:
    card = run_calculation(
        "time_value",
        {
            "currency": "USD",
            "direction": "save",
            "present_value": 0,
            "payment": 1_000,
            "future_value": 5_000,
            "annual_rate_pct": 0,
            "periods": None,
            "periods_per_year": 1,
        },
    )
    assert card.outcome.status == "succeeded"
    answer = card.presentation.answer
    assert answer is not None and answer.value == pytest.approx(5.0)
    assert answer.unit is not None and answer.unit.locale_key == "tools.calc.units.years"


def test_a_savings_target_already_met_takes_no_periods() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "USD",
            "present_value": 10_000,
            "payment": 0,
            "future_value": 10_000,
            "annual_rate_pct": 5,
            "periods": None,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(0.0)
    assert card.outcome.result["notes"] == ["already_covered"]


def test_a_covered_savings_plan_ends_where_its_inputs_take_it() -> None:
    plan = {"direction": "save", "currency": "USD", "annual_rate_pct": 0, "periods": 12}
    deposits = run_calculation(
        "time_value",
        {**plan, "present_value": None, "payment": 100, "future_value": 1_000},
    )
    balance = run_calculation(
        "time_value",
        {**plan, "present_value": 2_000, "payment": None, "future_value": 1_000},
    )
    assert row_value(deposits, "future_value") == pytest.approx(1_200.0)
    assert row_value(deposits, "total_growth") == pytest.approx(0.0)
    assert row_value(balance, "future_value") == pytest.approx(2_000.0)
    assert row_value(balance, "total_growth") == pytest.approx(0.0)


def test_payments_that_clear_a_loan_early_stop_there() -> None:
    loan = {"direction": "borrow", "currency": "USD", "future_value": None}
    flat = run_calculation(
        "time_value",
        {
            **loan,
            "present_value": 1_000,
            "payment": 200,
            "annual_rate_pct": 0,
            "periods": 12,
        },
    )
    car = run_calculation(
        "time_value",
        {
            **loan,
            "present_value": 180_000,
            "payment": 5_000,
            "annual_rate_pct": 14,
            "periods": 60,
        },
    )
    assert answer_value(flat) == pytest.approx(0.0)
    assert row_value(flat, "total_payments") == pytest.approx(1_000.0)
    assert row_value(flat, "total_interest") == pytest.approx(0.0)
    assert row_value(car, "total_payments") == pytest.approx(234_814.73, abs=0.01)
    assert min(car.outcome.result["balances"]) == 0.0


def test_a_target_already_met_draws_no_schedule() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "USD",
            "present_value": 10_000,
            "payment": 0,
            "future_value": 10_000,
            "annual_rate_pct": 5,
            "periods": None,
            "start_date": "2026-09-11",
        },
    )
    assert card.outcome.status == "succeeded"
    assert card.outcome.result["balances"] == []
    assert card.presentation.visual is None


def test_a_solved_fractional_period_chart_ends_at_the_reported_balance() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "USD",
            "present_value": 100,
            "payment": 0,
            "future_value": 200,
            "annual_rate_pct": 120,
            "periods": None,
            "start_date": "2026-09-11",
        },
    )
    assert answer_value(card) == pytest.approx(7.3, abs=0.05)
    balances = card.outcome.result["balances"]
    assert len(balances) == 8
    assert balances[-1] == pytest.approx(200.0)
    assert card.presentation.visual.series[-1].value == pytest.approx(200.0)


def test_a_savings_balance_already_past_its_target_takes_no_periods() -> None:
    card = run_calculation(
        "time_value",
        {
            "direction": "save",
            "currency": "USD",
            "present_value": 1_200,
            "payment": 0,
            "future_value": 1_000,
            "annual_rate_pct": 12,
            "periods": None,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(0.0)
    assert card.outcome.result["balances"] == []
    assert row_value(card, "total_growth") == pytest.approx(0.0)
