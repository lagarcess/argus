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


@pytest.mark.parametrize(
    "language,phrase",
    [
        ("en", "from August 16 to August 19 just a few days this year"),
        ("es-419", "del 16 de agosto al 19 de agosto solo unos días este año"),
    ],
)
@pytest.mark.parametrize("kind", ["calendar_year", "year_to_date"])
@pytest.mark.parametrize("focused", [False, True])
def test_rejects_whole_year_even_when_both_model_reads_agree(
    freeze_new_york_clock,
    language,
    phrase,
    kind,
    focused,
):
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.interpreter.date_window_repair import (
        _response_from_focused_date_window_extraction,
    )
    from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
    from argus.agent_runtime.llm_interpreter_types import (
        FocusedDateWindowExtraction,
        InterpretationContractError,
    )

    freeze_new_york_clock(datetime(2026, 9, 14, 12, tzinfo=EASTERN))
    intent = LLMDateRangeIntent(kind=kind, year=2026, evidence=phrase)
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary="Test MRNA.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MRNA"],
            asset_class="equity",
            capital_amount=100,
            date_range_raw_text=phrase,
            date_range_intent=intent,
            date_range={"start": "2026-01-01", "end": "2026-12-31"},
        ),
    )
    request = InterpretationRequest(
        current_user_message=phrase,
        user=UserState(user_id="test-user", language_preference=language),
    )
    if focused:
        response = _response_from_focused_date_window_extraction(
            response=response,
            request=request,
            extraction=FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_intent=intent,
                date_range_raw_text=phrase,
                confidence=0.9,
            ),
        )
        assert response is not None
    with pytest.raises(InterpretationContractError, match="date_range_precision"):
        OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract()
        )._to_runtime_interpretation(response, request=request)
