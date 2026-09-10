"""#520: erase delivery while retaining correct routing and draft facts.

These are deterministic fault injections, not claims about live model quality.
The unchanged base accepts these empty turns; each strengthened fixture must
reject its corresponding mutation through the real expectation comparator.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace
from typing import Any

import pytest

from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_outcome import offered_to_user

SWEEP_CASES = [
    case
    for case in harness.load_eval_cases()
    if case.expected.semantic_turn_act != "asset_discovery"
]


def _correct_routing(case: harness.EvalCase) -> dict[str, Any]:
    # Keep every existing typed assertion satisfied, including strategy facts.
    # Only delivery is removed. This models the exact false-green blind spot.
    outcome = asdict(case.expected)
    for key, value in outcome.items():
        if isinstance(value, tuple):
            outcome[key] = list(value)
    if isinstance(outcome["intent"], list):
        outcome["intent"] = outcome["intent"][0]
    return outcome


@pytest.mark.parametrize("case", SWEEP_CASES, ids=lambda case: case.id)
def test_each_case_rejects_a_turn_that_delivers_nothing(case: harness.EvalCase) -> None:
    outcome = _correct_routing(case)
    outcome["offered"] = offered_to_user(
        final_patch={},
        interpret_patch={},
        launch_payload={},
        assistant_text="",
    )
    routing_only_case = replace(case, expected=replace(case.expected, offered=None))
    assert (
        harness.typed_expectation_failures(case=routing_only_case, outcome=outcome) == []
    )
    failures = harness.typed_expectation_failures(case=case, outcome=outcome)
    assert failures and all(f.startswith("offered.") for f in failures), case.id


@pytest.mark.parametrize(
    "removed_field",
    [
        "symbols",
        "date_range",
        "capital_amount",
        "starting_capital",
        "recurring_contribution",
        "cadence",
    ],
)
def test_dca_draft_cannot_cover_up_a_missing_launch_fact(removed_field: str) -> None:
    case = next(
        c
        for c in SWEEP_CASES
        if c.id == "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455"
    )
    expected = case.expected
    launch = {
        "symbols": list(expected.assets),
        "asset_class": expected.asset_class,
        "strategy_type": expected.strategy_type,
        "benchmark_symbol": expected.benchmark_symbol,
        "date_range": expected.effective_date_range,
        "capital_amount": expected.capital_amount,
        "starting_capital": expected.starting_capital,
        "recurring_contribution": expected.recurring_contribution,
        "cadence": expected.contribution_period,
    }
    outcome = _correct_routing(case)
    outcome["offered"] = offered_to_user(
        final_patch={}, interpret_patch={}, launch_payload=launch
    )
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []
    incomplete = deepcopy(launch)
    del incomplete[removed_field]
    outcome["offered"] = offered_to_user(
        final_patch={}, interpret_patch={}, launch_payload=incomplete
    )
    failures = harness.typed_expectation_failures(case=case, outcome=outcome)
    assert any(f.startswith(f"offered.launch_payload.{removed_field}") for f in failures)


@pytest.mark.parametrize("cleared_value", [None, {}])
def test_cleared_final_surface_cannot_resurrect_an_interpret_proposal(
    cleared_value: Any,
) -> None:
    proposal = {"discovery": {"candidates": [{"symbol": "SPY"}]}}
    final = {} if cleared_value == {} else {"discovery": cleared_value}
    offered = offered_to_user(
        final_patch=final, interpret_patch=proposal, launch_payload={}
    )
    assert not offered["actionable"]


REFUSAL_CASES = [
    c
    for c in SWEEP_CASES
    if c.expected.stage_outcomes[:2] == ("ready_for_confirmation", "needs_clarification")
]


@pytest.mark.parametrize("case", REFUSAL_CASES, ids=lambda case: case.id)
@pytest.mark.parametrize("through_followup", [False, True], ids=["initial", "followup"])
def test_confirmation_refusal_reaches_the_real_clarification(
    case: harness.EvalCase, monkeypatch: Any, through_followup: bool
) -> None:
    from argus.agent_runtime.stages.launch_validation_recovery import (
        _tagged_launch_validation_failure,
    )

    if through_followup:
        case = replace(
            case,
            followup_prompt=case.prompt,
            expected=replace(
                case.expected,
                stage_outcomes=(
                    "needs_clarification",
                    "await_user_reply",
                    *case.expected.stage_outcomes,
                ),
            ),
        )
    expected = case.expected
    draft = {
        "asset_universe": list(expected.assets),
        "asset_class": expected.asset_class,
        "strategy_type": "dca_accumulation",
        "capital_amount": expected.capital_amount,
        "cadence": expected.contribution_period,
    }
    interpret_calls = 0

    def interpret_stage(**_kwargs: Any) -> Any:
        nonlocal interpret_calls
        interpret_calls += 1
        pending = through_followup and interpret_calls == 1
        return SimpleNamespace(
            outcome="needs_clarification" if pending else "ready_for_confirmation",
            patch={
                "intent": "backtest_execution",
                "candidate_strategy_draft": draft,
                "missing_required_fields": ["cadence"] if pending else [],
            },
        )

    monkeypatch.setattr(harness, "interpret_stage", interpret_stage)
    code = expected.launch_validation_code or "contribution_period_exceeds_window"
    monkeypatch.setattr(
        harness,
        "confirm_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="needs_clarification",
            patch={
                k: v
                for k, v in _tagged_launch_validation_failure(code).items()
                if k != "outcome"
            },
        ),
    )
    result = harness.run_eval_case(
        replace(case, degraded_mode={"clarifier": "offline"}), run_prose_judge=False
    )
    assert result["status"] == "passed", result
    assert result["typed_outcome"]["offered"]["response"]
    assert result["typed_outcome"]["offered"]["clarification"]["reason_code"] == code
