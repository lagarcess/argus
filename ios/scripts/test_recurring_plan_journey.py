"""Pure guards for the recurring-plan journey: derivation, oracles and refusals."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "recurring_plan_journey", Path(__file__).with_name("recurring-plan-journey.py")
)
journey = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(journey)

CHECKING = {"id": "acct-1", "type": "checking", "currency": "DOP"}


def movement(**changes):
    return {
        "kind": "expense",
        "currency": "DOP",
        "amount": "1500.00",
        "note": "Internet Claro",
        "occurred_at": "2026-09-23T05:00:00Z",
    } | changes


def test_movement_becomes_a_monthly_bill_on_the_same_account():
    body = journey.expectation_from_movement(movement(), CHECKING, date(2026, 10, 5))
    assert body == {
        "kind": "bill",
        "title": "Internet Claro",
        "currency": "DOP",
        "amount": "1500.00",
        "account_id": "acct-1",
        "schedule": {"cadence": "monthly", "start_date": "2026-10-23"},
    }


def test_income_title_truncation_and_account_eligibility():
    long_note = "x" * 130
    body = journey.expectation_from_movement(
        movement(kind="income", note=long_note),
        CHECKING | {"type": "credit_card"},
        date(2026, 10, 5),
    )
    assert (body["kind"], body["title"], "account_id" in body) == (
        "income",
        "x" * 100,
        False,
    )
    other = journey.expectation_from_movement(
        movement(), CHECKING | {"currency": "USD"}, date(2026, 10, 5)
    )
    assert "account_id" not in other
    assert "category_id" not in body["schedule"] and "category_id" not in body


@pytest.mark.parametrize(
    "movement_day, today, expected",
    [
        (date(2026, 9, 23), date(2026, 10, 5), date(2026, 10, 23)),
        (date(2026, 9, 23), date(2026, 10, 23), date(2026, 10, 23)),
        (date(2026, 1, 31), date(2026, 2, 15), date(2026, 2, 28)),
        (date(2026, 1, 31), date(2026, 3, 1), date(2026, 3, 31)),
        (date(2026, 10, 5), date(2026, 10, 5), date(2026, 11, 5)),
    ],
)
def test_first_cadence_date_after_the_movement_and_not_before_today(
    movement_day, today, expected
):
    assert journey.next_cadence_date(movement_day, today) == expected


def test_month_end_oracle_clamps_without_drift_through_a_leap_february():
    assert journey.month_dates(date(2027, 12, 5), date(2028, 12, 4), (31,)) == [
        "2027-12-31",
        "2028-01-31",
        "2028-02-29",
        "2028-03-31",
        "2028-04-30",
        "2028-05-31",
        "2028-06-30",
        "2028-07-31",
        "2028-08-31",
        "2028-09-30",
        "2028-10-31",
        "2028-11-30",
    ]


def test_twice_monthly_and_fortnight_oracles():
    assert journey.month_dates(date(2026, 1, 20), date(2026, 3, 31), (15, 31)) == [
        "2026-01-31",
        "2026-02-15",
        "2026-02-28",
        "2026-03-15",
        "2026-03-31",
    ]
    assert journey.fortnight_dates(date(2026, 10, 5), date(2026, 11, 20)) == [
        "2026-10-05",
        "2026-10-19",
        "2026-11-02",
        "2026-11-16",
    ]


def test_a_mismatch_names_the_check_and_both_values():
    checks = journey.Checks()
    checks.begin("window")
    checks.eq(30, 30, "days")
    with pytest.raises(journey.Refused, match="window: days: got 29, expected 30"):
        checks.eq(29, 30, "days")
    assert checks.total == 2


@pytest.mark.parametrize(
    "path",
    [
        "https://hosted.invalid/financial-plan",
        "/financial-plan/../me",
        "//hosted.invalid",
        "/chat",
        "/financial-planning",
    ],
)
def test_unexpected_paths_are_refused_before_http(path):
    with pytest.raises(journey.Refused):
        journey.validate_path(path)


def test_known_paths_are_accepted():
    journey.validate_path("/financial-plan?start_date=2026-10-05&end_date=2026-11-04")
    journey.validate_path("/financial-activities/abc/preview")


@pytest.mark.parametrize(
    "api_url, users",
    [("https://hosted.invalid/api/v1", 3), ("http://127.0.0.1:59800/api/v1", 2)],
)
def test_wrong_endpoint_or_identity_count_is_refused(
    tmp_path, monkeypatch, api_url, users
):
    monkeypatch.setattr(journey, "ROOT", tmp_path)
    work = tmp_path / "ios/.build/accounts-local-59800"
    work.mkdir(parents=True)
    fixture = work / "client.json"
    fixture.write_text(
        json.dumps(
            {
                "apiURL": api_url,
                "supabaseURL": "http://127.0.0.1:59801",
                "users": [{}] * users,
            }
        )
    )
    fixture.chmod(0o600)
    with pytest.raises(journey.Refused):
        journey.Client(59800)
