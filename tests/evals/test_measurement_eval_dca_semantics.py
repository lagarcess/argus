"""Mocked checks for the dca_capital_semantics measurement category.

The typed outcome reads both DCA money roles and the period from the launch
payload under their own names, so these tests prove a role swap or a refusal
degrading to the generic code is a visible eval failure, without spending a
single LLM token. Lives beside test_measurement_eval_harness.py rather than
inside it because that file's modularity budget is already spent.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.evals import measurement_eval_harness as harness


def _dca_case(
    *,
    capability_verdict: str = "executable",
    stage_outcomes: tuple[str, ...] = ("ready_for_confirmation", "await_approval"),
    starting_capital: float | None = 0,
    recurring_contribution: float | None = 200,
    contribution_period: str | None = "monthly",
    capital_amount: float | None = 200,
    launch_validation_code: str | None = None,
    requested_field: str | None = None,
) -> harness.EvalCase:
    return harness.EvalCase(
        id="dca-capital-semantics-check",
        category="dca_capital_semantics",
        prompt="I'll start by putting in $200 a month into SPY for 2024.",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict=capability_verdict,
            assets=("SPY",),
            strategy_type=(
                "dca_accumulation" if capability_verdict == "executable" else None
            ),
            capital_amount=capital_amount,
            starting_capital=starting_capital,
            recurring_contribution=recurring_contribution,
            contribution_period=contribution_period,
            launch_validation_code=launch_validation_code,
            requested_field=requested_field,
            stage_outcomes=stage_outcomes,
        ),
    )


def test_typed_outcome_extracts_dca_capital_roles_from_launch_payload() -> None:
    case = _dca_case()
    interpret_result = SimpleNamespace(
        outcome="ready_for_confirmation",
        patch={
            "intent": "backtest_execution",
            "candidate_strategy_draft": {
                "strategy_type": "dca_accumulation",
                "asset_universe": ["SPY"],
                "asset_class": "equity",
                "cadence": "monthly",
                "capital_amount": 200,
            },
        },
    )
    confirm_result = SimpleNamespace(
        outcome="await_approval",
        patch={
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": ["SPY"],
                    "asset_class": "equity",
                    "cadence": "monthly",
                    "capital_amount": 200.0,
                },
                "launch_payload": {
                    "strategy_type": "dca_accumulation",
                    "symbols": ["SPY"],
                    "asset_class": "equity",
                    "capital_amount": 200.0,
                    "starting_capital": 0.0,
                    "recurring_contribution": 200.0,
                    "cadence": "monthly",
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True},
            },
        },
    )

    outcome = harness._typed_outcome(
        case=case,
        interpret_result=interpret_result,
        confirm_result=confirm_result,
        clarify_result=None,
    )

    assert outcome["starting_capital"] == 0.0
    assert outcome["recurring_contribution"] == 200.0
    assert outcome["contribution_period"] == "monthly"
    assert outcome["capital_amount"] == 200.0
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


def test_dca_expectations_flag_contribution_captured_as_seed() -> None:
    # The over-capture symptom PR #491 named as its biggest risk: the stated
    # monthly amount lands in the seed role and the contribution goes missing.
    case = _dca_case()
    outcome = {
        "intent": "backtest_execution",
        "capability_verdict": "needs_clarification",
        "assets": ["SPY"],
        "stage_outcomes": ["needs_clarification", "await_user_reply"],
        "capital_amount": None,
        "starting_capital": 200.0,
        "recurring_contribution": None,
        "contribution_period": "monthly",
        "requested_field": "capital_amount",
    }

    failures = harness.typed_expectation_failures(case=case, outcome=outcome)

    assert any(failure.startswith("starting_capital:") for failure in failures)
    assert any(failure.startswith("recurring_contribution:") for failure in failures)
    assert any(failure.startswith("stage_outcomes:") for failure in failures)


def test_dca_refusal_expectations_require_the_named_code() -> None:
    case = _dca_case(
        capability_verdict="needs_clarification",
        stage_outcomes=("ready_for_confirmation", "needs_clarification"),
        starting_capital=None,
        recurring_contribution=None,
        contribution_period="quarterly",
        capital_amount=500,
        launch_validation_code="contribution_period_exceeds_window",
        requested_field="cadence",
    )
    named = {
        "intent": "backtest_execution",
        "capability_verdict": "needs_clarification",
        "assets": ["SPY"],
        "stage_outcomes": ["ready_for_confirmation", "needs_clarification"],
        "capital_amount": 500,
        "contribution_period": "quarterly",
        "launch_validation_code": "contribution_period_exceeds_window",
        "requested_field": "cadence",
    }
    assert harness.typed_expectation_failures(case=case, outcome=named) == []

    generic = {
        **named,
        "launch_validation_code": "missing_rule_group",
        "requested_field": "entry_logic",
    }
    failures = harness.typed_expectation_failures(case=case, outcome=generic)
    assert any(failure.startswith("launch_validation_code:") for failure in failures)
    assert any(failure.startswith("requested_field:") for failure in failures)
