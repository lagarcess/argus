"""Issue #241: untyped temporal evidence cannot become a historical window.

Live candidate QA reproduced this route: the primary interpretation captured
bounded date evidence ("ten years") but left ``date_range_intent`` empty, and
the strategy builder synthesized a past-anchored ``rolling_window`` from the
directionless span — so a future-performance request entered ordinary drafting
with a 2016->2026 window and no no-prediction boundary.

Contract: semantic temporal direction is established only by typed intent —
from the primary interpretation or the existing focused date-window
extraction. Untyped evidence fails closed to a date clarification; it never
creates a window or a card.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.interpreter.date_window_repair import (
    _response_from_focused_date_window_extraction,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import RunState, UserState

BTC_FUTURE_MESSAGE = (
    "If I invest $10,000 in Bitcoin and just hold it, what will it be worth in "
    "ten years?"
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response

    def __call__(self, request):
        return self.response


def _stub_crypto_asset_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _untyped_evidence_draft() -> LLMStrategyDraft:
    return LLMStrategyDraft(
        strategy_type="buy_and_hold",
        raw_user_phrasing=BTC_FUTURE_MESSAGE,
        asset_universe=["BTC"],
        asset_class="crypto",
        capital_amount=10000,
        date_range_raw_text="ten years",
        evidence_spans={"date_range": "ten years"},
    )


def _interpretation_request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
    )


def _focused_extraction_response() -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Future value question for a BTC hold.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["BTC"],
            asset_class="crypto",
            capital_amount=10000,
        ),
        missing_required_fields=["date_range"],
    )


def test_focused_prompt_conditions_rolling_window_on_historical_lookback() -> None:
    """The focused prompt may never instruct rolling_window unconditionally.

    A forward-looking period must be taught as future_window, and every
    rolling_window instruction must be scoped to a historical lookback so the
    two rules cannot contradict each other."""

    from argus.agent_runtime.interpreter.date_window_repair import (
        _focused_date_window_extraction_messages,
    )

    messages = _focused_date_window_extraction_messages(
        response=_focused_extraction_response(),
        request=_interpretation_request(BTC_FUTURE_MESSAGE),
    )
    prompt = messages[0]["content"]

    future_sentences = [
        sentence for sentence in prompt.split(". ") if "future_window" in sentence
    ]
    assert future_sentences, "prompt must teach kind=future_window"
    assert any(
        "forward" in sentence for sentence in future_sentences
    ), "future_window must be tied to forward-looking periods"

    rolling_sentences = [
        sentence for sentence in prompt.split(". ") if "kind=rolling_window" in sentence
    ]
    assert rolling_sentences, "prompt must keep the historical rolling_window rule"
    for sentence in rolling_sentences:
        assert "lookback" in sentence, (
            "every rolling_window instruction must be conditioned on a "
            f"historical lookback; unconditional sentence: {sentence!r}"
        )


def test_builder_does_not_synthesize_direction_from_untyped_evidence() -> None:
    """Directionless evidence never becomes a typed historical window."""

    strategy = _strategy_from_llm(_untyped_evidence_draft())
    extra_parameters = strategy.extra_parameters or {}
    assert "date_range_intent" not in extra_parameters
    # Evidence survives as provenance only.
    assert extra_parameters.get("date_range_raw_text") == "ten years"


def test_untyped_evidence_fails_closed_to_date_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composed route asks for the period instead of building a card."""

    _stub_crypto_asset_resolution(monkeypatch)
    strategy = _strategy_from_llm(_untyped_evidence_draft())
    result = interpret_stage(
        state=RunState.new(
            current_user_message=BTC_FUTURE_MESSAGE, recent_thread_history=[]
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="Future value question for a BTC hold.",
                candidate_strategy_draft=strategy,
                semantic_turn_act="new_idea",
            )
        ),
    )
    assert result.patch.get("confirmation_payload") is None
    assert result.outcome == "needs_clarification"
    assert "date_range" in [
        str(field) for field in result.decision.missing_required_fields
    ]


def test_focused_extraction_future_window_is_preserved_for_admission() -> None:
    """The existing focused corridor may establish the future direction."""

    repaired = _response_from_focused_date_window_extraction(
        response=_focused_extraction_response(),
        extraction=FocusedDateWindowExtraction(
            has_date_window=True,
            date_range_raw_text="in ten years",
            date_range_intent=LLMDateRangeIntent(
                kind="future_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.9,
                evidence="in ten years",
            ),
            confidence=0.9,
        ),
        request=_interpretation_request(BTC_FUTURE_MESSAGE),
    )
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.date_range_intent is not None
    assert draft.date_range_intent.kind == "future_window"
    # The future horizon never materializes as calendar dates.
    assert draft.date_range in (None, "", {}, [])


def test_focused_extraction_rolling_window_keeps_historical_path() -> None:
    repaired = _response_from_focused_date_window_extraction(
        response=_focused_extraction_response(),
        extraction=FocusedDateWindowExtraction(
            has_date_window=True,
            date_range_raw_text="last ten years",
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.9,
                evidence="last ten years",
            ),
            confidence=0.9,
        ),
        request=_interpretation_request("Test BTC over the last ten years."),
    )
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.date_range_intent is not None
    assert draft.date_range_intent.kind == "rolling_window"
    assert isinstance(draft.date_range, dict)
    assert draft.date_range.get("start") and draft.date_range.get("end")


def test_focused_future_window_full_route_fails_closed_at_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR #266 review T1: the applier's intermediate promotion is not an escape.

    The focused applier may leave `intent=backtest_execution` and
    `requires_clarification=False` on a windowless future turn; the complete
    stage route must still convert it to typed future_performance recovery
    with no confirmation payload."""

    _stub_crypto_asset_resolution(monkeypatch)
    repaired = _response_from_focused_date_window_extraction(
        response=_focused_extraction_response(),
        extraction=FocusedDateWindowExtraction(
            has_date_window=True,
            date_range_raw_text="in ten years",
            date_range_intent=LLMDateRangeIntent(
                kind="future_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.9,
                evidence="in ten years",
            ),
            confidence=0.9,
        ),
        request=_interpretation_request(BTC_FUTURE_MESSAGE),
    )
    assert repaired is not None
    strategy = _strategy_from_llm(repaired.candidate_strategy_draft)
    result = interpret_stage(
        state=RunState.new(
            current_user_message=BTC_FUTURE_MESSAGE, recent_thread_history=[]
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent=repaired.intent,
                task_relation=repaired.task_relation,
                requires_clarification=repaired.requires_clarification,
                user_goal_summary=repaired.user_goal_summary,
                candidate_strategy_draft=strategy,
                semantic_turn_act=repaired.semantic_turn_act or "new_idea",
            )
        ),
    )
    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    decision = result.decision
    assert decision.requires_clarification is True
    assert "future_performance" in [
        item.category for item in decision.unsupported_constraints
    ]
    conserved = decision.candidate_strategy_draft
    assert conserved.asset_universe == ["BTC"]
    assert conserved.capital_amount == 10000
    assert conserved.date_range in (None, "", {}, [])
    assert "date_range" in decision.missing_required_fields


def test_future_edit_on_active_confirmation_is_not_silently_dropped() -> None:
    """PR #266 review T2: a future-window date edit must not be amputated.

    'Change the amount to $5,000 and run it 10 years into the future' on an
    active confirmation must preserve the typed future horizon for the
    admission boundary instead of applying only the capital edit."""

    from argus.agent_runtime.artifact_edit_planner import ResolvedArtifactEdit
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _apply_resolved_edit_to_draft,
    )

    draft = LLMStrategyDraft(
        strategy_type="signal_strategy",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        date_range={"start": "2020-01-01", "end": "2023-12-31"},
    )
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    _apply_resolved_edit_to_draft(
        ResolvedArtifactEdit(
            date_window=LLMDateRangeIntent(
                kind="future_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.9,
                evidence="10 years into the future",
            ),
            initial_capital=5000,
        ),
        draft=draft,
        field_provenance=field_provenance,
        extra_parameters=extra_parameters,
    )
    # The capital edit applies; the future horizon stays typed for admission.
    assert draft.initial_capital == 5000
    assert draft.date_range_intent is not None
    assert draft.date_range_intent.kind == "future_window"


def test_future_edit_full_route_reaches_future_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.artifact_edit_planner import ResolvedArtifactEdit
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _apply_resolved_edit_to_draft,
    )

    _stub_crypto_asset_resolution(monkeypatch)
    draft = LLMStrategyDraft(
        strategy_type="buy_and_hold",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        date_range={"start": "2020-01-01", "end": "2023-12-31"},
    )
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    _apply_resolved_edit_to_draft(
        ResolvedArtifactEdit(
            date_window=LLMDateRangeIntent(
                kind="future_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.9,
                evidence="10 years into the future",
            ),
            initial_capital=5000,
        ),
        draft=draft,
        field_provenance=field_provenance,
        extra_parameters=extra_parameters,
    )
    draft.field_provenance = {**(draft.field_provenance or {}), **field_provenance}
    draft.extra_parameters = {**(draft.extra_parameters or {}), **extra_parameters}
    strategy = _strategy_from_llm(draft)
    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Change the amount to $5,000 and run it 10 years into the future."
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent="backtest_execution",
                task_relation="refine",
                requires_clarification=False,
                user_goal_summary="Edit capital and run ten years forward.",
                candidate_strategy_draft=strategy,
                semantic_turn_act="refine_current_idea",
            )
        ),
    )
    assert result.outcome == "needs_clarification"
    assert result.patch.get("confirmation_payload") is None
    assert "future_performance" in [
        item.category for item in result.decision.unsupported_constraints
    ]
    conserved = result.decision.candidate_strategy_draft
    assert conserved.asset_universe == ["NVDA"]
    assert (conserved.extra_parameters or {}).get("initial_capital") == 5000
    assert conserved.date_range in (None, "", {}, [])


def test_dateless_future_intent_strategy_cannot_reach_confirmation() -> None:
    """PR #266 review T3: the default-window fallback is unreachable.

    A strategy with no executable date range always lists date_range as a
    required missing field, so it clarifies instead of confirming; the
    resolver's past-year default is never consumed for a future-typed draft."""

    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.state.models import StrategySummary
    from argus.agent_runtime.strategy_contract import resolve_executable_date_range
    from argus.agent_runtime.strategy_requirements import (
        missing_required_fields_for_strategy,
    )

    strategy = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["BTC"],
        asset_class="crypto",
        capital_amount=10000,
        extra_parameters={
            "date_range_intent": {
                "kind": "future_window",
                "count": 10,
                "unit": "year",
                "anchor": "today",
                "confidence": 0.9,
                "evidence": "in ten years",
            }
        },
    )
    missing = missing_required_fields_for_strategy(
        strategy,
        contract=build_default_capability_contract(),
    )
    assert "date_range" in missing
    # The resolver alone would default; the required-field boundary above is
    # what keeps that default unreachable from confirmation or execution.
    resolution = resolve_executable_date_range(
        None,
        extra_parameters=strategy.extra_parameters,
    )
    assert resolution.used_default is True


def test_low_confidence_focused_extraction_cannot_create_a_window() -> None:
    repaired = _response_from_focused_date_window_extraction(
        response=_focused_extraction_response(),
        extraction=FocusedDateWindowExtraction(
            has_date_window=True,
            date_range_raw_text="ten years",
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=10,
                unit="year",
                anchor="today",
                confidence=0.4,
                evidence="ten years",
            ),
            confidence=0.4,
        ),
        request=_interpretation_request(BTC_FUTURE_MESSAGE),
    )
    assert repaired is None
