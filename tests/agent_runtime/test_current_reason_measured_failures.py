"""Free boundary replays of the failures measured at 4c4e7a00.

The recorded provider validation fragments are exact. Remaining payload fields
are authored typed fixtures, not a claim that full raw provider JSON was saved.
"""

from datetime import date

import pytest
from argus.agent_runtime.interpreter.date_window_repair import (
    _focused_date_window_extraction_messages,
    _response_from_focused_date_window_extraction,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    FocusedStrategyExtraction,
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import ResponseProfileOverrides, UserState
from argus.nlp import natural_time
from faker import Faker

fake = Faker()


def test_nullable_partial_date_preserves_monthly_buying_read():
    response = LLMInterpretationResponse.model_validate(
        {
            "intent": "strategy_drafting",
            "task_relation": "new_task",
            "user_goal_summary": "Test monthly buying with a contribution ceiling",
            "semantic_turn_act": "new_idea",
            "requires_clarification": True,
            "candidate_strategy_draft": {
                "strategy_type": "dca_accumulation",
                "asset_universe": ["VOO"],
                "cadence": "monthly",
                "total_capital": 5000,
                "date_range": {"start": None, "end": "2024-12-31"},
            },
            "missing_required_fields": ["capital_amount"],
            "unsupported_constraints": [
                {
                    "category": "unsupported_dca_contribution_ceiling",
                    "raw_value": "5000",
                    "explanation": "A contribution ceiling is not executable.",
                }
            ],
        }
    )
    assert response.intent == "strategy_drafting"
    assert response.candidate_strategy_draft.date_range == {"end": "2024-12-31"}
    assert response.candidate_strategy_draft.asset_universe == ["VOO"]
    assert response.candidate_strategy_draft.cadence == "monthly"
    assert response.missing_required_fields == ["capital_amount"]
    assert (
        response.unsupported_constraints[0].category
        == "unsupported_dca_contribution_ceiling"
    )


def test_null_optional_profile_keeps_pending_dca_amount_edit():
    response = LLMInterpretationResponse.model_validate(
        {
            "intent": "strategy_drafting",
            "task_relation": "continue",
            "user_goal_summary": "Use the supplied monthly contribution",
            "semantic_turn_act": "answer_pending_need",
            "response_profile_overrides": None,
            "candidate_strategy_draft": {
                "strategy_type": "dca_accumulation",
                "asset_universe": ["KO"],
                "recurring_contribution": 200,
                "cadence": "monthly",
            },
        }
    )
    assert response.intent == "strategy_drafting"
    assert response.semantic_turn_act == "answer_pending_need"
    assert response.response_profile_overrides == ResponseProfileOverrides()
    assert response.candidate_strategy_draft.asset_universe == ["KO"]
    assert response.candidate_strategy_draft.recurring_contribution == 200
    assert response.candidate_strategy_draft.cadence == "monthly"


@pytest.mark.parametrize(
    "schema", [LLMStrategyDraft, FocusedStrategyExtraction, FocusedDateWindowExtraction]
)
def test_every_date_extraction_boundary_treats_null_as_an_absent_endpoint(schema):
    value = schema.model_validate(
        {
            "date_range": {"start": None, "end": "2024-12-31"},
            "is_testable_strategy": True,
            "user_goal_summary": fake.sentence(),
            "has_date_window": True,
        }
    )
    assert value.date_range == {"end": "2024-12-31"}


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("encoded_year", ["2024", "--"])
@pytest.mark.parametrize("kind", ["explicit_range", "since"])
def test_focused_yearless_endpoints_take_the_new_york_year(
    monkeypatch, language, encoded_year, kind
):
    monkeypatch.setattr(natural_time, "new_york_today", lambda: date(2026, 9, 15))
    start = "2024-08-16" if encoded_year == "2024" else "--08-16"
    end = "2024-08-19" if encoded_year == "2024" else "--08-19"
    extraction = FocusedDateWindowExtraction(
        has_date_window=True,
        date_range_intent=LLMDateRangeIntent(
            kind=kind,
            start=start,
            end=end,
            year_reference="current_year",
        ),
        confidence=1,
    )
    request = InterpretationRequest(
        current_user_message=fake.sentence(),
        user=UserState(user_id=fake.uuid4(), language_preference=language),
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Test the stated range",
    )
    repaired = _response_from_focused_date_window_extraction(
        response=response, extraction=extraction, request=request
    )
    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": "2026-08-16",
        "end": "2026-08-19",
    }


@pytest.mark.parametrize("today", [date(2026, 12, 31), date(2027, 1, 1)])
def test_current_year_is_resolved_at_the_clock_owner(monkeypatch, today):
    monkeypatch.setattr(natural_time, "new_york_today", lambda: today)
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="explicit_range",
            start="2024-08-16",
            end="2024-08-19",
            year_reference="current_year",
        )
    )
    assert result.payload == {
        "start": f"{today.year}-08-16",
        "end": f"{today.year}-08-19",
    }


def test_explicit_historical_year_is_preserved():
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(kind="explicit_range", start="2024-08-16", end="2024-08-19"),
        today=date(2026, 9, 15),
    )
    assert result.payload == {"start": "2024-08-16", "end": "2024-08-19"}


@pytest.mark.parametrize("kind", ["explicit_range", "year_to_date", "since"])
def test_current_year_does_not_clamp_an_invalid_leap_day(kind):
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind=kind,
            start="2024-02-28",
            end="2024-02-29",
            year_reference="current_year",
        ),
        today=date(2026, 9, 15),
    )
    assert result is None


def test_focused_date_writer_requires_the_clock_owned_year_contract():
    request = InterpretationRequest(
        current_user_message=fake.sentence(), user=UserState(user_id=fake.uuid4())
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Test dates",
    )
    messages = _focused_date_window_extraction_messages(
        response=response, request=request
    )
    assert "year_reference=current_year" in messages[0]["content"]


@pytest.mark.parametrize("kind", ["calendar_year", "year_to_date", "since"])
@pytest.mark.parametrize("encoded_year", [2024, None])
def test_whole_current_year_intents_use_the_same_clock_owner(
    monkeypatch, kind, encoded_year
):
    today = date(2026, 9, 15)
    monkeypatch.setattr(natural_time, "new_york_today", lambda: today)
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(kind=kind, year=encoded_year, year_reference="current_year")
    )
    assert result is not None
    assert result.payload == {"start": "2026-01-01", "end": today.isoformat()}


def test_current_year_to_date_binds_an_explicit_endpoint_to_the_same_year():
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="year_to_date",
            year=2024,
            end="2024-08-19",
            year_reference="current_year",
        ),
        today=date(2026, 9, 15),
    )
    assert result.payload == {"start": "2026-01-01", "end": "2026-08-19"}


@pytest.mark.parametrize("encoded_start", ["--08-16", "2024-08-16"])
@pytest.mark.parametrize("current_year", [True, False])
def test_since_window_uses_the_typed_year_and_defaults_end_to_today(
    monkeypatch, encoded_start, current_year
):
    today = date(2026, 9, 15)
    monkeypatch.setattr(natural_time, "new_york_today", lambda: today)
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="since",
            start=encoded_start,
            year_reference="current_year" if current_year else None,
        )
    )
    if not current_year and encoded_start.startswith("--"):
        assert result is None
    else:
        assert result is not None
        expected_year = (
            today.year if current_year else date.fromisoformat(encoded_start).year
        )
        assert result.payload == {
            "start": date(expected_year, 8, 16).isoformat(),
            "end": today.isoformat(),
        }


@pytest.mark.parametrize("encoded_end", ["--08-19", "2024-08-19"])
def test_rolling_window_binds_its_typed_endpoint_before_date_math(encoded_end):
    from datetime import timedelta

    today = date(2026, 9, 15)
    end = date(today.year, 8, 19)
    days = 10
    result = natural_time.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=days,
            unit="day",
            end=encoded_end,
            year_reference="current_year",
        ),
        today=today,
    )
    assert result is not None
    assert result.payload == {
        "start": (end - timedelta(days=days)).isoformat(),
        "end": end.isoformat(),
    }
