from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_eval_harness import (
    FIXTURE_DIR,
    LOCKED_EVAL_CATEGORIES,
    PROSE_JUDGE_RUBRIC_VERSION,
    load_eval_cases,
    scorecard_for_results,
)

EXPECTED_LOCKED_CATEGORIES = {
    "messy_english",
    "messy_spanish",
    "ui_user_language_mismatch",
    "action_chip_semantics",
    "capability_honesty",
    "backtest_metric_correctness",
    "graceful_recovery",
}

PHRASE_ASSERTION_KEYS = {
    "expected_phrase",
    "expected_phrasing",
    "expected_response",
    "expected_text",
    "must_include",
    "must_not_include",
}


def _walk(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        pairs = list(value.items())
        for nested in value.values():
            pairs.extend(_walk(nested))
        return pairs
    if isinstance(value, list):
        pairs: list[tuple[str, Any]] = []
        for nested in value:
            pairs.extend(_walk(nested))
        return pairs
    return []


def test_measurement_fixtures_cover_locked_categories_as_data() -> None:
    cases = load_eval_cases()

    assert LOCKED_EVAL_CATEGORIES == EXPECTED_LOCKED_CATEGORIES
    assert {case.category for case in cases} == EXPECTED_LOCKED_CATEGORIES
    assert {path.stem for path in FIXTURE_DIR.glob("*.yaml")} == (
        EXPECTED_LOCKED_CATEGORIES
    )

    for category in EXPECTED_LOCKED_CATEGORIES:
        category_cases = [case for case in cases if case.category == category]
        assert category_cases, category
        for case in category_cases:
            assert case.id
            assert case.prompt or case.action is not None
            assert case.expected.intent
            assert case.expected.capability_verdict


def test_measurement_fixtures_do_not_assert_expected_prose() -> None:
    for path in sorted(Path(FIXTURE_DIR).glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        assert "expected phrasing" not in raw.lower()

    cases = load_eval_cases()
    offending_keys: list[str] = []
    for case in cases:
        raw_case = case.raw
        for key, _value in _walk(raw_case):
            if key in PHRASE_ASSERTION_KEYS:
                offending_keys.append(f"{case.id}:{key}")

    assert offending_keys == []
    assert PROSE_JUDGE_RUBRIC_VERSION == "argus-prose-quality-v1"


def test_expected_fail_baselines_are_issue_tagged() -> None:
    expected_failures = [case for case in load_eval_cases() if case.expected_fail]

    for case in expected_failures:
        assert case.expected_fail is not None
        assert case.expected_fail.issue.startswith("#")
        assert case.expected_fail.reason
        assert case.expected_fail.allowed_failures


def test_expected_fail_only_masks_allowed_failure_prefixes() -> None:
    expected_fail = harness.ExpectedFail(
        issue="#142",
        reason="Known company-name asset drop.",
        allowed_failures=("assets:", "stage_outcomes:"),
    )

    assert (
        harness._result_status(
            [
                "assets: expected ['TGT', 'WMT', 'COST'], got []",
                "stage_outcomes: expected ['ready_for_confirmation'], got ['needs']",
            ],
            expected_fail=expected_fail,
        )
        == "expected_failed"
    )
    assert (
        harness._result_status(
            [
                "assets: expected ['TGT', 'WMT', 'COST'], got []",
                "benchmark_symbol: expected 'SPY', got 'QQQ'",
            ],
            expected_fail=expected_fail,
        )
        == "failed"
    )
    assert harness._result_status([], expected_fail=expected_fail) == "unexpected_pass"


def test_date_range_expectations_compare_iso_interval_and_dict_equivalently() -> None:
    dict_window = {"start": "2024-01-01", "end": "2024-12-31"}
    interval_window = "2024-01-01T00:00:00Z/2024-12-31T00:00:00Z"

    for expected_date_range, actual_date_range in (
        (dict_window, interval_window),
        (interval_window, dict_window),
    ):
        case = harness.EvalCase(
            id="date-range-normalization",
            category="messy_english",
            prompt="test Target, Walmart, and Costco in 2024",
            user_language="en",
            ui_language="en",
            expected=harness.TypedExpectations(
                intent="backtest_execution",
                capability_verdict="executable",
                date_range=expected_date_range,
            ),
        )

        failures = harness.typed_expectation_failures(
            case=case,
            outcome={
                "intent": "backtest_execution",
                "capability_verdict": "executable",
                "date_range": actual_date_range,
            },
        )

        assert failures == []


def test_prose_judge_cases_fail_when_assistant_text_is_missing(monkeypatch: Any) -> None:
    case = harness.EvalCase(
        id="missing-prose",
        category="messy_spanish",
        prompt="probar apple",
        user_language="es-419",
        ui_language="es-419",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            assets=("AAPL",),
            asset_class="equity",
            strategy_type="buy_and_hold",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            benchmark_symbol="SPY",
            stage_outcomes=("ready_for_confirmation", "await_approval"),
        ),
        prose_judge_criteria=("spanish_language_integrity",),
    )
    interpret_patch = {
        "intent": "backtest_execution",
        "candidate_strategy_draft": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "comparison_baseline": "SPY",
        },
    }
    confirm_patch = {
        "confirmation_payload": {
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbols": ["AAPL"],
                "asset_class": "equity",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "benchmark_symbol": "SPY",
            },
            "validation": {"executable": True},
        }
    }

    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="ready_for_confirmation",
            patch=interpret_patch,
        ),
    )
    monkeypatch.setattr(
        harness,
        "confirm_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="await_approval",
            patch=confirm_patch,
        ),
    )
    monkeypatch.setattr(
        harness,
        "judge_prose_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("missing prose should not call the LLM judge")
        ),
    )

    result = harness.run_eval_case(case)

    assert result["status"] == "failed"
    assert result["failed_checks"] == ["prose_judge:missing_assistant_text"]
    assert result["prose_judge"]["failed_criteria"] == ["missing_assistant_text"]


def test_followup_clarification_runs_clarify_stage(monkeypatch: Any) -> None:
    case = harness.EvalCase(
        id="followup-clarifies",
        category="action_chip_semantics",
        prompt="",
        followup_prompt="MSFT",
        user_language="en",
        ui_language="en",
        action=harness.EvalAction(
            type="change_asset",
            label="Change asset",
            presentation="confirmation",
            payload={"confirmation_id": "c1"},
        ),
        expected=harness.TypedExpectations(
            intent="strategy_drafting",
            capability_verdict="needs_clarification",
            stage_outcomes=(
                "needs_clarification",
                "await_user_reply",
                "needs_clarification",
                "await_user_reply",
            ),
            clarification={"direct_question": "Which asset set?"},
        ),
    )
    interpret_results = iter(
        [
            SimpleNamespace(
                outcome="needs_clarification",
                patch={
                    "candidate_strategy_draft": {"asset_universe": ["AAPL", "MSFT"]},
                    "requested_field": "asset_universe",
                    "missing_required_fields": ["asset_universe"],
                    "response_intent": {"kind": "clarification"},
                },
            ),
            SimpleNamespace(
                outcome="needs_clarification",
                patch={
                    "candidate_strategy_draft": {"asset_universe": ["AAPL", "MSFT"]},
                    "requested_field": "asset_universe",
                    "missing_required_fields": ["asset_universe"],
                    "response_intent": {"kind": "clarification"},
                },
            ),
        ]
    )
    clarify_calls: list[Any] = []

    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: next(interpret_results),
    )

    def clarify_stub(**_kwargs: Any) -> SimpleNamespace:
        clarify_calls.append(_kwargs)
        return SimpleNamespace(
            outcome="await_user_reply",
            patch={
                "assistant_response": "Which asset set?",
                "clarification": {"direct_question": "Which asset set?"},
            },
        )

    monkeypatch.setattr(harness, "clarify_stage", clarify_stub)

    result = harness.run_eval_case(case)

    assert len(clarify_calls) == 2
    assert result["status"] == "passed"
    assert result["typed_outcome"]["clarification"] == {
        "direct_question": "Which asset set?"
    }


def test_confirmation_payload_snapshot_uses_distinct_artifact_references() -> None:
    case = next(
        case
        for case in load_eval_cases()
        if case.id == "action_chip_change_asset_remove_aapl_issue_188"
    )

    assert case.snapshot is not None
    active = case.snapshot.active_confirmation_reference
    listed = case.snapshot.artifact_references[-1]
    assert active is not None
    assert listed.artifact_id == active.artifact_id
    assert listed is not active


def test_scorecard_reports_per_category_pass_rates() -> None:
    results = [
        {
            "id": "case-a",
            "category": "messy_english",
            "status": "passed",
        },
        {
            "id": "case-b",
            "category": "messy_english",
            "status": "failed",
        },
        {
            "id": "case-c",
            "category": "messy_spanish",
            "status": "expected_failed",
        },
        {
            "id": "case-d",
            "category": "messy_spanish",
            "status": "unexpected_pass",
        },
    ]

    scorecard = scorecard_for_results(results)

    assert scorecard["category_pass_rates"]["messy_english"] == {
        "passed": 1,
        "failed": 1,
        "expected_failed": 0,
        "unexpected_pass": 0,
        "skipped": 0,
        "pass_rate": 0.5,
    }
    assert scorecard["category_pass_rates"]["messy_spanish"] == {
        "passed": 0,
        "failed": 0,
        "expected_failed": 1,
        "unexpected_pass": 1,
        "skipped": 0,
        "pass_rate": 0.0,
    }
    assert scorecard["totals"]["unexpected_pass"] == 1
