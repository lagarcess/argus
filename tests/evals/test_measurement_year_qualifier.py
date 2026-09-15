"""Current-year expectations must age with the user's current year."""

from datetime import datetime

import pytest
from argus.domain.market_data.capabilities import EASTERN

from tests.evals.measurement_assertions import _compare_date_range
from tests.evals.measurement_eval_harness import load_eval_cases


@pytest.mark.parametrize("year", [2026, 2027])
def test_year_qualifier_cases_compare_actual_dates(freeze_new_york_clock, year):
    freeze_new_york_clock(datetime(year, 9, 14, 12, tzinfo=EASTERN))
    cases = [
        case
        for case in load_eval_cases()
        if case.id.endswith("explicit_end_survives_year_qualifier")
    ]
    assert {case.user_language for case in cases} == {"en", "es-419"}
    for case in cases:
        failures = []
        _compare_date_range(
            "date_range",
            case.expected.date_range,
            {"start": f"{year}-08-16", "end": f"{year}-08-19"},
            failures,
        )
        assert failures == []
        _compare_date_range(
            "date_range",
            case.expected.date_range,
            {"start": f"{year}-08-16", "end": f"{year}-12-31"},
            failures,
        )
        assert len(failures) == 1


def test_september_2026_date_cases_expect_trading_window_and_no_prose(
    freeze_new_york_clock,
):
    freeze_new_york_clock(datetime(2026, 9, 14, 12, tzinfo=EASTERN))
    for case in load_eval_cases():
        if not case.id.endswith("explicit_end_survives_year_qualifier"):
            continue
        assert case.expected.effective_date_range == {
            "start": "2026-08-17",
            "end": "2026-08-19",
        }
        assert case.expected.offered["response"] is False
        assert case.prose_judge_criteria == ()


def test_confirmation_expectation_rejects_unexpected_prose():
    from tests.evals.measurement_outcome import compare_offered

    failures = []
    compare_offered({"response": False}, {"response": True}, failures)
    assert failures == ["offered.response: confirmation turn unexpectedly carried prose"]
