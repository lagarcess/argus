from __future__ import annotations

from pathlib import Path
from typing import Any

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

    assert any(
        case.expected_fail is not None and case.expected_fail.issue == "#142"
        for case in expected_failures
    )
    for case in expected_failures:
        assert case.expected_fail is not None
        assert case.expected_fail.issue.startswith("#")
        assert case.expected_fail.reason


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
    ]

    scorecard = scorecard_for_results(results)

    assert scorecard["category_pass_rates"]["messy_english"] == {
        "passed": 1,
        "failed": 1,
        "expected_failed": 0,
        "skipped": 0,
        "pass_rate": 0.5,
    }
    assert scorecard["category_pass_rates"]["messy_spanish"] == {
        "passed": 0,
        "failed": 0,
        "expected_failed": 1,
        "skipped": 0,
        "pass_rate": 1.0,
    }
