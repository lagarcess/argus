"""Every primitive against a worked example, and every no-answer as a typed outcome."""

from __future__ import annotations

import math

import pytest
from argus.domain.finance import (
    Money,
    NoSolution,
    bonds,
    comparison,
    dcf,
    growth,
    ratios,
    tvm,
    valuation,
)
from argus.domain.finance.outcomes import solved
from faker import Faker

fake = Faker()


# --- Money --------------------------------------------------------------------


def test_money_carries_its_currency_and_refuses_to_mix() -> None:
    pesos = Money(1_000, "DOP")
    assert pesos + Money(500, "DOP") == Money(1_500, "DOP")
    assert pesos.scaled(2).amount == 2_000
    with pytest.raises(ValueError, match="one currency"):
        pesos + Money(1, "USD")
    with pytest.raises(ValueError, match="ISO 4217"):
        Money(1, "dollars")
    with pytest.raises(ValueError, match="finite"):
        Money(math.inf, "USD")


# --- Time value of money -----------------------------------------------------


def test_loan_payment_matches_the_published_mortgage_table() -> None:
    # A 200,000 loan at 6 percent over 30 years costs 1,199.10 a month.
    monthly = tvm.payment(200_000, 0.0, 0.06 / 12, 360)
    assert solved(monthly) == pytest.approx(-1_199.10, abs=0.005)


def test_savings_future_value_matches_the_annuity_formula() -> None:
    # 500 a month at 5 percent, compounded monthly, for ten years.
    ending = tvm.future_value(0.0, -500.0, 0.05 / 12, 120)
    assert ending == pytest.approx(77_641.14, abs=0.01)
    # Payments at the start of each period earn one more month.
    early = tvm.future_value(0.0, -500.0, 0.05 / 12, 120, timing=1)
    assert early == pytest.approx(77_641.14 * (1 + 0.05 / 12), abs=0.01)


def test_every_unknown_round_trips_through_the_same_balance() -> None:
    rate, periods, pv, pmt = 0.004, 48, -12_000.0, -150.0
    fv = tvm.future_value(pv, pmt, rate, periods)
    assert tvm.present_value(fv, pmt, rate, periods) == pytest.approx(pv)
    assert solved(tvm.payment(pv, fv, rate, periods)) == pytest.approx(pmt)
    assert solved(tvm.periods(pv, pmt, fv, rate)) == pytest.approx(periods)
    assert solved(tvm.rate(pv, pmt, fv, periods)) == pytest.approx(rate, abs=1e-9)


def test_zero_rate_is_a_known_input_not_a_missing_one() -> None:
    assert tvm.future_value(-1_000.0, -100.0, 0.0, 10) == pytest.approx(2_000.0)
    assert solved(tvm.periods(-1_000.0, -100.0, 2_000.0, 0.0)) == pytest.approx(10)
    assert solved(tvm.payment(-1_000.0, 2_000.0, 0.0, 10)) == pytest.approx(-100.0)


def test_rate_solves_the_doubling_question() -> None:
    doubling = solved(tvm.rate(-1_000.0, 0.0, 2_000.0, 10))
    assert doubling == pytest.approx(2 ** (1 / 10) - 1, abs=1e-9)


@pytest.mark.parametrize(
    ("payment", "expected_code"),
    [
        (-2_000.0, "payment_never_balances"),  # below the monthly interest of 2,100
        (0.0, "payment_never_balances"),
    ],
)
def test_a_payment_that_never_clears_a_loan_names_the_payment(
    payment: float, expected_code: str
) -> None:
    outcome = tvm.periods(180_000.0, payment, 0.0, 0.14 / 12)
    assert isinstance(outcome, NoSolution)
    assert outcome.field == "payment"
    assert outcome.code == expected_code


def test_no_rate_fits_when_the_flows_cannot_balance() -> None:
    # Money that goes in and never comes back has no rate; a loss has a negative one.
    outcome = tvm.rate(-1_000.0, 0.0, 0.0, 10)
    assert isinstance(outcome, NoSolution)
    assert (outcome.field, outcome.code) == ("rate", "no_rate_fits")
    assert solved(tvm.rate(-1_000.0, -100.0, 500.0, 10)) < 0
    assert isinstance(tvm.rate(-1_000.0, 0.0, 2_000.0, 0), NoSolution)


def test_paying_extra_shortens_the_loan_and_cuts_interest() -> None:
    balance, rate = 180_000.0, 0.14 / 12
    baseline = solved(tvm.periods(balance, -5_000.0, 0.0, rate))
    faster = solved(tvm.periods(balance, -6_000.0, 0.0, rate))
    assert faster < baseline
    schedule = tvm.amortization_schedule(balance, rate, 5_000.0, math.ceil(baseline))
    assert schedule[0].interest == pytest.approx(2_100.0)
    assert schedule[0].principal == pytest.approx(2_900.0)
    assert schedule[-1].balance == pytest.approx(0.0, abs=5_000.0)
    assert all(
        later.balance < earlier.balance
        for earlier, later in zip(schedule, schedule[1:], strict=False)
    )


def test_savings_path_ends_where_future_value_says() -> None:
    path = tvm.savings_path(0.0, 0.05 / 12, 500.0, 120)
    assert len(path) == 120
    assert path[-1] == pytest.approx(77_641.14, abs=0.01)


# --- Growth ---------------------------------------------------------------------


def test_real_return_follows_fisher_not_subtraction() -> None:
    assert solved(growth.real_rate(0.07, 0.03)) == pytest.approx(0.038835, abs=1e-6)
    assert solved(growth.real_value(1_000.0, 0.03, 10)) == pytest.approx(744.09, abs=0.01)
    assert isinstance(growth.real_rate(0.07, -1.5), NoSolution)


def test_growth_rate_and_periods_invert_compounding() -> None:
    ending = growth.compound(1_000.0, 0.07, 10)
    assert ending == pytest.approx(1_967.15, abs=0.01)
    assert solved(growth.growth_rate(1_000.0, ending, 10)) == pytest.approx(0.07)
    assert solved(growth.growth_periods(1_000.0, ending, 0.07)) == pytest.approx(10.0)
    assert solved(growth.start_for_target(ending, 0.07, 10)) == pytest.approx(1_000.0)


def test_growth_names_the_input_that_makes_the_question_unanswerable() -> None:
    assert growth.growth_periods(1_000.0, 2_000.0, 0.0) == NoSolution(
        field="rate", code="rate_never_reaches_target"
    )
    assert (
        growth.growth_periods(1_000.0, 2_000.0, -0.02).code == "rate_never_reaches_target"
    )
    assert growth.growth_rate(0.0, 2_000.0, 10).field == "start_value"
    assert growth.growth_rate(1_000.0, 2_000.0, 0).field == "periods"


# --- Ratios -----------------------------------------------------------------------


def test_ratios_against_textbook_figures() -> None:
    assert solved(ratios.price_to_earnings(150.0, 6.0)) == pytest.approx(25.0)
    assert solved(ratios.income_yield(4.0, 100.0)) == pytest.approx(0.04)
    assert solved(ratios.effective_annual_rate(0.12, 12)) == pytest.approx(
        0.126825, abs=1e-6
    )
    assert solved(ratios.nominal_from_effective(0.126825, 12)) == pytest.approx(
        0.12, abs=1e-5
    )
    assert solved(ratios.debt_to_income(1_500.0, 5_000.0)) == pytest.approx(0.30)
    assert solved(ratios.expense_ratio(50.0, 10_000.0)) == pytest.approx(0.005)


def test_effective_apr_includes_fees_the_lender_keeps() -> None:
    # 10,000 at a 10 percent nominal rate over 36 months is 322.67 a month;
    # a 300 fee lifts the true annual cost above 12 percent.
    payment = -solved(tvm.payment(10_000.0, 0.0, 0.10 / 12, 36))
    assert payment == pytest.approx(322.67, abs=0.01)
    assert solved(ratios.effective_apr(10_000.0, 0.0, payment, 36, 12)) == pytest.approx(
        0.10, abs=1e-6
    )
    assert solved(ratios.effective_apr(10_000.0, 300.0, payment, 36, 12)) > 0.12
    assert ratios.effective_apr(10_000.0, 10_000.0, payment, 36, 12).field == "fees"


def test_expense_cost_compounds_the_drag() -> None:
    cost = ratios.expense_cost(10_000.0, 0.005, 0.07, 30)
    assert cost.ending_without_fee == pytest.approx(76_122.55, abs=0.01)
    assert cost.ending_with_fee < cost.ending_without_fee
    assert cost.cost == pytest.approx(cost.ending_without_fee - cost.ending_with_fee)


@pytest.mark.parametrize(
    ("function", "arguments", "field"),
    [
        (ratios.price_to_earnings, (150.0, 0.0), "earnings_per_share"),
        (ratios.income_yield, (4.0, 0.0), "price"),
        (ratios.debt_to_income, (1.0, 0.0), "monthly_income"),
        (ratios.expense_ratio, (1.0, 0.0), "assets"),
    ],
)
def test_a_zero_denominator_names_its_field(function, arguments, field) -> None:
    outcome = function(*arguments)
    assert isinstance(outcome, NoSolution)
    assert (outcome.field, outcome.code) == (field, "division_by_zero")


# --- Comparison ------------------------------------------------------------------


def test_ranking_keeps_ties_and_measures_the_gap_to_the_best() -> None:
    ranked = comparison.rank_by_key(
        [("Card A", 24.9), ("Card B", 18.5), ("Card C", 18.5)], prefer="lower"
    )
    assert [(item.label, item.rank) for item in ranked] == [
        ("Card B", 1),
        ("Card C", 1),
        ("Card A", 3),
    ]
    assert ranked[-1].gap_to_best == pytest.approx(6.4)
    highest = comparison.rank_by_key([("x", 1.0), ("y", 3.0)], prefer="higher")
    assert highest[0].label == "y" and highest[1].gap_to_best == pytest.approx(-2.0)
    assert comparison.rank_by_key([], prefer="lower") == []


# --- Valuation --------------------------------------------------------------------


def test_scenarios_span_low_to_high_and_return_the_implied_annual_rate() -> None:
    scenarios = solved(
        valuation.valuation_scenarios(
            price=150.0,
            per_share=6.0,
            growth=(0.03, 0.08, 0.12),
            multiples=(18.0, 22.0, 28.0),
            horizon=5,
        )
    )
    assert [scenario.label for scenario in scenarios] == ["low", "base", "high"]
    assert scenarios[1].price_at_horizon == pytest.approx(193.95, abs=0.01)
    assert scenarios[1].annual_return == pytest.approx(0.05274, abs=1e-5)
    assert scenarios[0].price_at_horizon < scenarios[1].price_at_horizon
    assert scenarios[1].price_at_horizon < scenarios[2].price_at_horizon
    assert (
        valuation.valuation_scenarios(
            price=0.0, per_share=6.0, growth=(0, 0, 0), multiples=(1, 1, 1), horizon=5
        ).field
        == "price"
    )


# --- Bonds ---------------------------------------------------------------------


def test_bond_price_and_yield_invert_each_other() -> None:
    # A 1,000 face, 5 percent semiannual coupon, ten years, priced to yield 6.
    price = solved(bonds.bond_price(1_000.0, 0.05, 0.06, 10, 2))
    assert price == pytest.approx(925.61, abs=0.01)
    assert solved(bonds.bond_yield(1_000.0, 0.05, price, 10, 2)) == pytest.approx(
        0.06, abs=1e-6
    )
    assert solved(bonds.current_yield(1_000.0, 0.05, price)) == pytest.approx(
        0.054, abs=1e-3
    )
    assert solved(bonds.bond_price(1_000.0, 0.05, 0.0, 10, 2)) == pytest.approx(1_500.0)
    assert bonds.bond_price(1_000.0, 0.05, 0.06, 0, 2).field == "years"
    assert bonds.bond_yield(1_000.0, 0.05, 0.0, 10, 2).field == "price"


# --- DCF ---------------------------------------------------------------------------


def test_dcf_matches_a_hand_discounting_and_reverses_to_its_growth() -> None:
    value = solved(dcf.dcf_value(100.0, 0.05, 0.10, 5, 0.02))
    assert value == pytest.approx(1_446.21, abs=0.01)
    assert solved(dcf.implied_growth(value, 100.0, 0.10, 5, 0.02)) == pytest.approx(
        0.05, abs=1e-6
    )
    assert dcf.dcf_value(100.0, 0.05, 0.02, 5, 0.03) == NoSolution(
        field="discount_rate", code="discount_below_terminal_growth"
    )
    assert dcf.implied_growth(0.0, 100.0, 0.10, 5, 0.02).field == "cash_flow"


def test_solved_refuses_to_unwrap_a_no_solution() -> None:
    with pytest.raises(ValueError, match="rate"):
        solved(NoSolution(field="rate", code="no_rate_fits"))
