"""Repair must not drop what the user already stated (#367, spec §3.5).

``FocusedStrategyExtraction`` has no cost fields, so when the repair path
rebuilds the draft, everything the user stated that the focused schema cannot
carry must survive through the base merge. The loss was nondeterministic
end to end because repair only fires when the primary extraction under-fills;
these tests reproduce the loss deterministically at the drop site itself, and
through the repair pipeline with the provider mocked to under-fill.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter as interpreter_module
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    UserState,
)

STATED_MESSAGE = (
    "Buy and hold NFLX for 2023 with $10,000, 10 bps fee and 5 bps slippage"
)


def _request(message: str = STATED_MESSAGE) -> InterpretationRequest:
    return InterpretationRequest(
        user=UserState(user_id="user-367"),
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={},
    )


def _base_response_with_stated_costs() -> LLMInterpretationResponse:
    """The primary interpretation as it stands before repair replaces it:
    the user's costs are already grounded, provenance-owned, and validated."""
    draft = LLMStrategyDraft(
        raw_user_phrasing=STATED_MESSAGE,
        strategy_type="buy_and_hold",
        asset_universe=["NFLX"],
        asset_class="equity",
        date_range={"start": "2023-01-02", "end": "2023-12-29"},
        capital_amount=10000,
        recurring_contribution=None,
        extra_parameters={"fee_rate": 0.001, "slippage": 0.0005},
        field_provenance={
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
            "capital_amount": "starting_capital",
        },
        evidence_spans={
            "fee_rate": "10 bps fee",
            "slippage": "5 bps slippage",
        },
    )
    draft._validated_execution_cost_evidence["fee_rate"] = (0.001, "10 bps fee")
    draft._validated_execution_cost_evidence["slippage"] = (0.0005, "5 bps slippage")
    return LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test NFLX with stated modeled costs",
        candidate_strategy_draft=draft,
        semantic_turn_act="new_idea",
    )


def _costless_extraction() -> FocusedStrategyExtraction:
    """What the focused schema can express: everything except the costs."""
    return FocusedStrategyExtraction(
        is_testable_strategy=True,
        requires_clarification=False,
        user_goal_summary="Buy and hold NFLX through 2023",
        strategy_type="buy_and_hold",
        asset_universe=["NFLX"],
        asset_class="equity",
        date_range={"start": "2023-01-02", "end": "2023-12-29"},
        capital_amount=10000,
    )


def _assert_costs_survive(draft: LLMStrategyDraft) -> None:
    assert draft.extra_parameters.get("fee_rate") == 0.001, (
        "the stated 10 bps fee was dropped by repair"
    )
    assert draft.extra_parameters.get("slippage") == 0.0005, (
        "the stated 5 bps slippage was dropped by repair"
    )
    assert draft.field_provenance.get("fee_rate") == "explicit_user"
    assert draft.field_provenance.get("slippage") == "explicit_user"
    assert draft.evidence_spans.get("fee_rate") == "10 bps fee"
    assert draft.evidence_spans.get("slippage") == "5 bps slippage"
    assert draft._validated_execution_cost_evidence.get("fee_rate") == (
        0.001,
        "10 bps fee",
    )
    assert draft._validated_execution_cost_evidence.get("slippage") == (
        0.0005,
        "5 bps slippage",
    )


def test_focused_repair_preserves_stated_costs_at_the_merge_site() -> None:
    """The deterministic reproduction: the drop site is the base merge."""
    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=_costless_extraction(),
        request=_request(),
        base_response=_base_response_with_stated_costs(),
    )
    _assert_costs_survive(response.candidate_strategy_draft)


def test_focused_repair_preserves_recurring_contribution_and_rules() -> None:
    """The enumerated-field fix would miss these; the class fix cannot.

    A DCA contribution and a stated indicator threshold are user statements
    the old merge list never carried.
    """
    base = _base_response_with_stated_costs()
    base.candidate_strategy_draft.recurring_contribution = 250.0
    base.candidate_strategy_draft.sizing_mode = "capital_amount"
    base.candidate_strategy_draft.entry_threshold = 25.0
    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=_costless_extraction(),
        request=_request(),
        base_response=base,
    )
    draft = response.candidate_strategy_draft
    assert draft.recurring_contribution == 250.0
    assert draft.sizing_mode == "capital_amount"
    assert draft.entry_threshold == 25.0


def test_repair_result_does_not_echo_base_values_the_extraction_replaced() -> None:
    """Preservation fills gaps only; the repair's own values stay
    authoritative when it states them."""
    base = _base_response_with_stated_costs()
    base.candidate_strategy_draft.capital_amount = 7000
    extraction = _costless_extraction()
    extraction.capital_amount = 12000
    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=_request(),
        base_response=base,
    )
    assert response.candidate_strategy_draft.capital_amount == 12000


@pytest.mark.anyio
async def test_repair_pipeline_preserves_stated_costs_with_underfilling_model() -> None:
    """The trigger path: the repair provider answers without costs, and the
    pipeline still returns a draft carrying the user's stated costs."""

    async def _underfilled_extraction(**_kwargs: Any) -> FocusedStrategyExtraction:
        return _costless_extraction()

    original = interpreter_module.invoke_openrouter_json_schema
    interpreter_module.invoke_openrouter_json_schema = _underfilled_extraction
    try:
        response = await interpreter_module._repair_incomplete_strategy_extraction(
            failed_response=_base_response_with_stated_costs(),
            preferred_model="test-model",
            request=_request(),
        )
    finally:
        interpreter_module.invoke_openrouter_json_schema = original
    assert response is not None
    _assert_costs_survive(response.candidate_strategy_draft)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
