"""A broad year phrase cannot overwrite narrower dates read by the interpreter."""

from __future__ import annotations

from datetime import datetime

import pytest
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_with_resolved_runtime_date_range,
)
from argus.agent_runtime.interpreter.shared import (
    _date_range_from_intent_or_bounded_evidence,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.domain.market_data.capabilities import EASTERN


@pytest.mark.parametrize(
    "language,phrase",
    [
        ("en", "from August 16 to August 19 just a few days this year"),
        ("es-419", "del 16 de agosto al 19 de agosto solo unos días este año"),
        ("en", "from March 2 to March 5 for a few days this year"),
        ("es-419", "del 2 de marzo al 5 de marzo solo unos días este año"),
    ],
)
@pytest.mark.parametrize("year", [2026, 2027])
@pytest.mark.parametrize("model_end_correct", [False, True])
def test_stated_endpoints_survive_year_qualifier(
    freeze_new_york_clock,
    language,
    phrase,
    year,
    model_end_correct,
) -> None:
    freeze_new_york_clock(datetime(year, 9, 14, 12, tzinfo=EASTERN))
    month, first, last = (8, 16, 19) if "16" in phrase else (3, 2, 5)
    expected = {
        "start": f"{year}-{month:02}-{first:02}",
        "end": f"{year}-{month:02}-{last:02}",
    }
    draft = LLMStrategyDraft(
        strategy_type="buy_and_hold",
        asset_universe=["MRNA"],
        asset_class="equity",
        capital_amount=100,
        date_range_raw_text=phrase,
        date_range={
            **expected,
            "end": expected["end"] if model_end_correct else f"{year}-12-31",
        },
        date_range_intent=LLMDateRangeIntent(
            kind="explicit_range", **expected, evidence=phrase
        ),
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary="Test a short stated date range.",
        candidate_strategy_draft=draft,
    )
    request = InterpretationRequest(
        current_user_message=f"MRNA $100 {phrase}",
        user=UserState(user_id="test-user", language_preference=language),
    )
    normalized = _response_with_resolved_runtime_date_range(
        response=response, request=request
    )
    assert normalized.candidate_strategy_draft.date_range == expected
    assert (
        _date_range_from_intent_or_bounded_evidence(draft, language=language) == expected
    )
    if not model_end_correct:
        assert "runtime_date_range_normalization" in normalized.reason_codes


@pytest.mark.parametrize("polite_prefix", ["", "May I "])
def test_calendar_year_reading_does_not_reask_over_modal_may(polite_prefix):
    from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm

    expected = {"start": "2024-01-01", "end": "2024-12-31"}
    draft = LLMStrategyDraft(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=100,
        date_range=expected,
        date_range_intent=LLMDateRangeIntent(
            kind="calendar_year", year=2024, evidence="calendar year 2024"
        ),
    )
    result = _strategy_from_llm(
        draft, f"{polite_prefix}backtest Apple for calendar year 2024?"
    )
    assert result.date_range == expected
