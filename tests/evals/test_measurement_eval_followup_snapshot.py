"""A followup turn measures the reply against the setup the first turn built.

Without a declared snapshot the followup used to run with no pending strategy
at all, so a case could never measure whether a clarification reply keeps
what the user said in the first turn.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests.evals import measurement_eval_harness as harness


def test_followup_turn_runs_against_the_first_turns_pending_strategy(
    monkeypatch: Any,
) -> None:
    case = harness.EvalCase(
        id="followup-keeps-first-turn-facts",
        category="dca_capital_semantics",
        prompt="Test monthly DCA in AAPL for 2024 with $100 a month and $1,000 to start.",
        followup_prompt="Use $1,000 as starting capital only. Keep the dates.",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="strategy_drafting",
            capability_verdict="needs_clarification",
        ),
    )
    first_patch = {
        "intent": "strategy_drafting",
        "user_goal_summary": "Monthly DCA in AAPL for 2024.",
        "candidate_strategy_draft": {
            "strategy_type": "dca_accumulation",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "cadence": "monthly",
            "date_range": {"start": "2024-01-02", "end": "2024-12-31"},
            "capital_amount": 100.0,
            "extra_parameters": {
                "recurring_contribution": 100.0,
                "initial_capital": 1000.0,
            },
        },
        "missing_required_fields": ["capital_amount"],
        "response_intent": {"kind": "unsupported_recovery", "requested_fields": []},
    }
    interpret_calls: list[dict[str, Any]] = []

    def _interpret(**kwargs: Any) -> SimpleNamespace:
        interpret_calls.append(kwargs)
        return SimpleNamespace(outcome="needs_clarification", patch=dict(first_patch))

    monkeypatch.setattr(harness, "interpret_stage", _interpret)
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="await_user_reply",
            patch={"assistant_response": "Which direction should we go?"},
        ),
    )

    harness.run_eval_case(case, run_prose_judge=False)

    assert len(interpret_calls) == 2
    followup = interpret_calls[1]
    snapshot = followup["latest_task_snapshot"]
    assert snapshot is not None
    pending = snapshot.pending_strategy_summary
    assert pending is not None
    assert pending.asset_universe == ["AAPL"]
    assert pending.date_range == {"start": "2024-01-02", "end": "2024-12-31"}
    assert pending.extra_parameters["initial_capital"] == 1000.0
    assert snapshot.latest_task_type == "strategy_drafting"
    assert (
        followup["selected_thread_metadata"]["last_stage_outcome"] == "await_user_reply"
    )
    assert (
        followup["state"].recent_thread_history[-1].content
        == "Which direction should we go?"
    )


def test_declared_snapshot_still_wins_for_the_followup(monkeypatch: Any) -> None:
    declared = harness._snapshot_from_raw(
        {"pending_strategy": {"strategy_type": "buy_and_hold", "asset_universe": ["KO"]}}
    )
    case = harness.EvalCase(
        id="followup-declared-snapshot",
        category="dca_capital_semantics",
        prompt="What if I had bought Coca-Cola every month for five years?",
        followup_prompt="200$",
        user_language="en",
        ui_language="en",
        snapshot=declared,
        expected=harness.TypedExpectations(
            intent="strategy_drafting",
            capability_verdict="needs_clarification",
        ),
    )
    interpret_calls: list[dict[str, Any]] = []

    def _interpret(**kwargs: Any) -> SimpleNamespace:
        interpret_calls.append(kwargs)
        return SimpleNamespace(
            outcome="needs_clarification",
            patch={
                "candidate_strategy_draft": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": ["AAPL"],
                },
                "missing_required_fields": ["capital_amount"],
            },
        )

    monkeypatch.setattr(harness, "interpret_stage", _interpret)
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="await_user_reply", patch={"assistant_response": "How much?"}
        ),
    )

    harness.run_eval_case(case, run_prose_judge=False)

    assert interpret_calls[1]["latest_task_snapshot"] is declared
