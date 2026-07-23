"""Issue #241 future-performance executable boundary.

Invariant under test: a typed future-anchored horizon
(``date_range_intent.kind == "future_window"``) on a strategy-shaped turn can
never become an executable confirmation, a resolved historical date range, or
inherited dates after an explicit supported-alternative selection. The future
horizon survives only as original-intent evidence; compatible asset, capital,
and strategy facts are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest
from argus.agent_runtime.interpreter.pending_option import (
    _apply_pending_response_option_replacement,
    _llm_draft_from_strategy_summary,
)
from argus.agent_runtime.interpreter.unsupported_admission import (
    FUTURE_HORIZON_EVIDENCE_KEY,
    FUTURE_PERFORMANCE_ADMISSION_BLOCKED,
    FUTURE_PERFORMANCE_CATEGORY,
    RECOGNIZED_NON_EXECUTABLE_ADMISSION_BLOCKED,
)
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UserState,
)
from argus.nlp.natural_time import resolve_date_range_intent

EN_FUTURE_MESSAGE = (
    "If I invest $10,000 in NVDA using a golden cross strategy, how much will "
    "it be worth in ten years?"
)
ES_FUTURE_MESSAGE = (
    "Si invierto $10,000 en NVDA con una estrategia de cruce dorado, ¿cuánto "
    "tendré dentro de diez años?"
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
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.response


def _stub_equity_asset_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _run_interpret(*, message: str, response: StructuredInterpretation):
    interpreter = RecordingInterpreter(response)
    result = interpret_stage(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=interpreter,
    )
    return result


def _future_window_intent(evidence: str) -> dict[str, Any]:
    return {
        "kind": "future_window",
        "count": 10,
        "unit": "year",
        "anchor": "today",
        "confidence": 0.9,
        "evidence": evidence,
    }


def _future_interpretation(
    *,
    intent: str,
    evidence: str,
    semantic_turn_act: str = "new_idea",
    assistant_response: str | None = None,
    detected_user_language: str | None = None,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent=intent,
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asked what a golden-cross NVDA investment becomes in the future.",
        detected_user_language=detected_user_language,
        assistant_response=assistant_response,
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            asset_universe=["NVDA"],
            asset_class="equity",
            capital_amount=10000,
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
            extra_parameters={"date_range_intent": _future_window_intent(evidence)},
        ),
        semantic_turn_act=semantic_turn_act,
    )


def _assert_future_blocked(result, *, evidence: str) -> None:
    assert result.outcome == "needs_clarification"
    decision = result.decision
    assert decision is not None
    assert decision.requires_clarification is True
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED in decision.reason_codes
    categories = [item.category for item in decision.unsupported_constraints]
    assert FUTURE_PERFORMANCE_CATEGORY in categories
    constraint = next(
        item
        for item in decision.unsupported_constraints
        if item.category == FUTURE_PERFORMANCE_CATEGORY
    )
    replacement_fields = [
        option.replacement_values.get("requested_field")
        for option in constraint.simplification_options
    ]
    assert replacement_fields and all(
        field == "date_range" for field in replacement_fields
    )
    strategy = decision.candidate_strategy_draft
    # Compatible facts survive; the horizon does not become executable dates.
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.capital_amount == 10000
    assert strategy.date_range in (None, "", {}, [])
    extra = strategy.extra_parameters or {}
    assert "date_range_intent" not in extra
    horizon = extra.get(FUTURE_HORIZON_EVIDENCE_KEY)
    assert isinstance(horizon, dict)
    assert horizon.get("kind") == "future_window"
    assert horizon.get("evidence") == evidence
    assert "date_range" in decision.missing_required_fields
    patch = result.patch
    assert patch.get("confirmation_payload") is None


def test_backtest_execution_with_future_window_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reproduced J4 shape: supported strategy named inside a future ask."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="backtest_execution",
            evidence="in ten years",
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")


def _momentum_future_summary() -> StrategySummary:
    return StrategySummary(
        requested_strategy_template="momentum_breakout",
        strategy_type="buy_and_hold",
        strategy_thesis="Momentum breakout strategy on AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=10000,
        extra_parameters={
            "date_range_intent": _future_window_intent("ten years from now"),
        },
    )


def test_named_unsupported_strategy_precedes_future_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first recovery must address the unexecutable named strategy."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=(
            "Backtest a momentum breakout strategy on AAPL with $10,000 "
            "ten years from now."
        ),
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="Momentum breakout on AAPL ten years from now.",
            candidate_strategy_draft=_momentum_future_summary(),
            semantic_turn_act="new_idea",
        ),
    )

    assert result.outcome == "needs_clarification"
    decision = result.decision
    assert decision is not None
    assert RECOGNIZED_NON_EXECUTABLE_ADMISSION_BLOCKED in decision.reason_codes
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED not in decision.reason_codes
    assert [constraint.category for constraint in decision.unsupported_constraints] == [
        "unsupported_strategy_logic"
    ]
    draft = decision.candidate_strategy_draft
    assert draft.requested_strategy_template == "momentum_breakout"
    assert draft.strategy_type == "momentum_breakout"
    assert draft.asset_universe == ["AAPL"]
    assert draft.capital_amount == 10000
    future_intent = (draft.extra_parameters or {}).get("date_range_intent")
    assert isinstance(future_intent, dict)
    assert future_intent["kind"] == "future_window"
    assert FUTURE_HORIZON_EVIDENCE_KEY not in (draft.extra_parameters or {})
    assert result.patch.get("confirmation_payload") is None


def test_pending_summary_conversion_preserves_named_strategy_identity() -> None:
    pending = _momentum_future_summary().model_copy(
        update={"strategy_type": "momentum_breakout"}
    )

    draft = _llm_draft_from_strategy_summary(pending)

    assert draft.requested_strategy_template == "momentum_breakout"


def test_date_only_selection_does_not_replace_named_unsupported_strategy() -> None:
    pending = _momentum_future_summary().model_copy(
        update={"strategy_type": "momentum_breakout"}
    )
    draft = _llm_draft_from_strategy_summary(pending)

    result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={
            "requested_field": "date_range",
            "date_range": {"start": "2022-01-01", "end": "2025-01-01"},
        },
        current_missing=[],
    )

    repaired = result["draft"]
    assert repaired.requested_strategy_template == "momentum_breakout"
    assert repaired.strategy_type == "momentum_breakout"
    assert repaired.date_range == {"start": "2022-01-01", "end": "2025-01-01"}


@pytest.mark.parametrize(
    ("replacement_values", "expected_template", "expected_strategy_type"),
    [
        (
            {
                "strategy_type": "signal_strategy",
                "rule_family": "moving_average_crossover",
            },
            "moving_average_crossover",
            "signal_strategy",
        ),
        (
            {"simplify_logic": "rsi_only"},
            "rsi_mean_reversion",
            "indicator_threshold",
        ),
        (
            {"strategy_type": "buy_and_hold"},
            "buy_and_hold",
            "buy_and_hold",
        ),
    ],
)
def test_typed_supported_alternative_replaces_named_strategy_identity(
    replacement_values: dict[str, Any],
    expected_template: str,
    expected_strategy_type: str,
) -> None:
    pending = _momentum_future_summary().model_copy(
        update={"strategy_type": "momentum_breakout"}
    )
    draft = _llm_draft_from_strategy_summary(pending)

    result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values=replacement_values,
        current_missing=[],
    )

    repaired = result["draft"]
    assert repaired.requested_strategy_template == expected_template
    assert repaired.strategy_type == expected_strategy_type
    assert repaired.asset_universe == ["AAPL"]
    assert repaired.capital_amount == 10000
    assert (repaired.extra_parameters or {})["date_range_intent"]["kind"] == (
        "future_window"
    )


def test_buy_hold_replacement_outranks_stale_rule_identity() -> None:
    pending = _momentum_future_summary().model_copy(
        update={
            "strategy_type": "momentum_breakout",
            "entry_rule": {
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        }
    )

    result = _apply_pending_response_option_replacement(
        draft=_llm_draft_from_strategy_summary(pending),
        replacement_values={"strategy_type": "buy_and_hold"},
        current_missing=[],
    )

    repaired = result["draft"]
    assert repaired.requested_strategy_template == "buy_and_hold"
    assert repaired.strategy_type == "buy_and_hold"
    assert repaired.entry_rule is None


def test_supported_selection_then_future_then_dates_reaches_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The three typed boundaries run in order without losing known facts."""

    _stub_equity_asset_resolution(monkeypatch)
    pending = _momentum_future_summary().model_copy(
        update={"strategy_type": "momentum_breakout"}
    )
    replacement = _apply_pending_response_option_replacement(
        draft=_llm_draft_from_strategy_summary(pending),
        replacement_values={
            "strategy_type": "signal_strategy",
            "rule_family": "moving_average_crossover",
        },
        current_missing=[],
    )
    selected = StrategySummary.model_validate(
        replacement["draft"].model_dump(mode="python", exclude_none=True)
    )

    future_result = _run_interpret(
        message="Use the 50/200-day moving-average crossover instead.",
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="Use a supported moving-average crossover.",
            candidate_strategy_draft=selected,
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert future_result.outcome == "needs_clarification"
    future_decision = future_result.decision
    assert future_decision is not None
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED in future_decision.reason_codes
    future_draft = future_decision.candidate_strategy_draft
    assert future_draft.requested_strategy_template == "moving_average_crossover"
    assert future_draft.strategy_type == "signal_strategy"
    assert future_draft.asset_universe == ["AAPL"]
    assert future_draft.capital_amount == 10000
    assert "date_range" in future_decision.missing_required_fields
    horizon = (future_draft.extra_parameters or {}).get(FUTURE_HORIZON_EVIDENCE_KEY)
    assert isinstance(horizon, dict)
    assert horizon["kind"] == "future_window"
    assert future_result.patch.get("confirmation_payload") is None

    dated_draft = future_draft.model_copy(
        update={"date_range": {"start": "2022-01-01", "end": "2025-01-01"}}
    )
    confirmation_result = _run_interpret(
        message="Use January 1, 2022 through January 1, 2025.",
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="Use the supplied historical period.",
            candidate_strategy_draft=dated_draft,
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert confirmation_result.outcome == "ready_for_confirmation"
    confirmed = confirmation_result.decision
    assert confirmed is not None
    assert confirmed.candidate_strategy_draft.requested_strategy_template == (
        "moving_average_crossover"
    )
    assert confirmed.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert confirmed.candidate_strategy_draft.capital_amount == 10000
    assert confirmed.candidate_strategy_draft.date_range == {
        "start": "2022-01-01",
        "end": "2025-01-01",
    }
    assert (
        "momentum_breakout"
        not in (confirmed.candidate_strategy_draft.model_dump(mode="json")).values()
    )


def test_spanish_future_window_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=ES_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="backtest_execution",
            evidence="dentro de diez años",
            detected_user_language="es-419",
        ),
    )
    _assert_future_blocked(result, evidence="dentro de diez años")


def test_unsupported_verdict_with_future_window_uses_future_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that already refused still gets the typed future boundary, and
    even its refusal prose is regenerated: no typed field separates a refusal
    from a forecast, so the boundary trusts neither."""

    _stub_equity_asset_resolution(monkeypatch)
    refusal = "I cannot predict future performance, but I can test it historically."
    result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="unsupported_or_out_of_scope",
            semantic_turn_act="unsupported_request",
            evidence="in ten years",
            assistant_response=refusal,
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")
    assert result.patch.get("assistant_response") is None


def test_strategy_drafting_with_future_window_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="strategy_drafting",
            evidence="in ten years",
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")


def test_future_window_intent_never_resolves_to_dates() -> None:
    resolution = resolve_date_range_intent(
        _future_window_intent("in ten years"),
        today=date(2026, 7, 22),
    )
    assert resolution is None


def test_rolling_window_still_resolves_historically() -> None:
    resolution = resolve_date_range_intent(
        {
            "kind": "rolling_window",
            "count": 10,
            "unit": "year",
            "anchor": "today",
            "confidence": 0.9,
            "evidence": "last ten years",
        },
        today=date(2026, 7, 22),
    )
    assert resolution is not None
    assert resolution.payload == {"start": "2016-07-22", "end": "2026-07-22"}


def test_selection_after_future_recovery_asks_for_period() -> None:
    """Explicit alternative selection conserves facts and re-asks the period."""

    pending = StrategySummary(
        strategy_type="signal_strategy",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
        extra_parameters={
            FUTURE_HORIZON_EVIDENCE_KEY: _future_window_intent("in ten years"),
        },
    )
    draft = _llm_draft_from_strategy_summary(pending)
    replaced = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={"requested_field": "date_range"},
        current_missing=[],
    )
    repaired = replaced["draft"]
    assert repaired.asset_universe == ["NVDA"]
    assert repaired.capital_amount == 10000
    assert repaired.date_range in (None, "", {}, [])
    assert "date_range" in replaced["missing_fields"]


def test_future_performance_sidecar_reuses_public_unsupported_recovery_shape() -> None:
    """`future_performance` travels only as a reason_code value inside the
    existing `unsupported_recovery` sidecar kind — no new public shape."""

    from argus.agent_runtime.clarification_contract import typed_clarification_contract

    sidecar = typed_clarification_contract(
        response_intent={
            "kind": "unsupported_recovery",
            "semantic_needs": ["simplification_choice"],
            "requested_fields": ["unsupported_constraints"],
            "facts": {
                "unsupported_constraints": [
                    {
                        "category": FUTURE_PERFORMANCE_CATEGORY,
                        "raw_value": "in ten years",
                        "explanation": "Argus cannot predict future performance.",
                    }
                ],
            },
            "options": [
                {
                    "label": "Test this idea over a historical period",
                    "replacement_values": {"requested_field": "date_range"},
                },
            ],
        },
        strategy=StrategySummary(
            strategy_type="signal_strategy",
            asset_universe=["NVDA"],
            capital_amount=10000,
        ),
        prompt_source="llm_generated",
    )
    assert sidecar is not None
    assert sidecar["kind"] == "unsupported_recovery"
    assert sidecar["reason_code"] == FUTURE_PERFORMANCE_CATEGORY
    assert sidecar["prompt_source"] == "llm_generated"
    option_payloads = [option["replacement_values"] for option in sidecar["options"]]
    assert {"requested_field": "date_range"} in option_payloads


def test_historical_period_option_identity_is_stable_and_selectable() -> None:
    """PR #266 review T6: positional identity is deterministic and selectable.

    The contract template's option order is fixed, so the sidecar id is
    stable across builds and reloads; selection matching uses the exact
    replacement payload. A typed kind for `requested_field=date_range` would
    collide with coverage-recovery's identical `change_dates` payload because
    `_typed_options` prefers kinds over explicit ids."""

    from argus.agent_runtime.clarification_contract import typed_clarification_contract
    from argus.agent_runtime.simplification_option_contract import (
        simplification_option_matches_selection,
    )

    def _sidecar() -> dict[str, Any]:
        return typed_clarification_contract(
            response_intent={
                "kind": "unsupported_recovery",
                "semantic_needs": ["simplification_choice"],
                "requested_fields": ["unsupported_constraints"],
                "facts": {
                    "unsupported_constraints": [
                        {
                            "category": FUTURE_PERFORMANCE_CATEGORY,
                            "raw_value": "in ten years",
                            "explanation": "No prediction.",
                        }
                    ],
                },
                "options": [
                    {
                        "label": "Test this idea over a historical period",
                        "replacement_values": {"requested_field": "date_range"},
                    },
                    {
                        "label": "Compare with buy and hold historically",
                        "replacement_values": {
                            "strategy_type": "buy_and_hold",
                            "requested_field": "date_range",
                        },
                    },
                ],
            },
            strategy=StrategySummary(asset_universe=["NVDA"]),
            prompt_source="llm_generated",
        )

    first, second = _sidecar(), _sidecar()
    assert first["options"] == second["options"]
    assert [option["id"] for option in first["options"]] == [
        "option_0",
        "buy_and_hold",
    ]
    # Selection matches on the exact typed payload, independent of the id.
    assert simplification_option_matches_selection(
        option_replacement_values={"requested_field": "date_range"},
        selected_replacement_values={"requested_field": "date_range"},
    )
    # Coverage-recovery options with the identical payload keep their explicit
    # ids today; a requested_field-keyed kind would override them.
    coverage_sidecar = typed_clarification_contract(
        response_intent={
            "kind": "coverage_recovery",
            "semantic_needs": ["simplification_choice"],
            "requested_fields": ["date_range"],
            "facts": {
                "coverage": {"code": "no_common_data_window", "benchmark_symbol": "SPY"},
                "strategy": {"asset_universe": ["AAPL"]},
            },
            "options": [
                {
                    "id": "change_dates",
                    "replacement_values": {"requested_field": "date_range"},
                },
            ],
        },
        strategy=StrategySummary(asset_universe=["AAPL"]),
    )
    assert coverage_sidecar is not None
    assert [option["id"] for option in coverage_sidecar["options"]] == ["change_dates"]


def test_selection_to_buy_and_hold_conserves_capital_and_asks_period() -> None:
    pending = StrategySummary(
        strategy_type="signal_strategy",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        extra_parameters={
            FUTURE_HORIZON_EVIDENCE_KEY: _future_window_intent("in ten years"),
        },
    )
    draft = _llm_draft_from_strategy_summary(pending)
    replaced = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={
            "strategy_type": "buy_and_hold",
            "requested_field": "date_range",
        },
        current_missing=[],
    )
    repaired = replaced["draft"]
    assert repaired.strategy_type == "buy_and_hold"
    assert repaired.asset_universe == ["NVDA"]
    assert repaired.capital_amount == 10000
    assert repaired.date_range in (None, "", {}, [])
    assert "date_range" in replaced["missing_fields"]


FORECAST_PROSE = (
    "Based on historical growth, your $10,000 in NVDA could be worth about "
    "$150,000 in ten years. Running that projection now."
)


def test_educational_label_with_future_window_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typed future horizon is capability truth: an educational_question
    label may not suppress the strategy route, wipe the draft, and ship the
    model's forecast as a plain answer."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="conversation_followup",
            semantic_turn_act="educational_question",
            evidence="in ten years",
            assistant_response=FORECAST_PROSE,
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")
    assert result.patch.get("assistant_response") is None


def test_followup_label_with_future_window_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conversation-followup label (result_followup act) may not keep the
    strategy route unset and return the forecast unchanged."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message="And what would that be worth in ten years?",
        response=_future_interpretation(
            intent="conversation_followup",
            semantic_turn_act="result_followup",
            evidence="in ten years",
            assistant_response=FORECAST_PROSE,
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")
    assert result.patch.get("assistant_response") is None


def test_plain_educational_question_stays_suppressed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a typed future horizon, educational suppression is unchanged:
    the turn answers as prose with no clarification or artifact."""

    _stub_equity_asset_resolution(monkeypatch)
    answer = "A golden cross is a 50-day average crossing above the 200-day."
    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked what a golden cross is.",
        assistant_response=answer,
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            asset_universe=["NVDA"],
        ),
        semantic_turn_act="educational_question",
    )
    result = _run_interpret(
        message="What is a golden cross?",
        response=interpretation,
    )
    assert result.outcome == "ready_to_respond"
    assert result.patch.get("assistant_response") == answer
    assert result.patch.get("confirmation_payload") is None


DCA_STALE_EVIDENCE_SPANS = {
    "asset_universe": "Apple",
    "capital_amount": "$500 every month",
    "cadence": "every month",
    "date_range": "from January 2022 through January 2024",
}


def _dca_future_decision_draft() -> StrategySummary:
    return StrategySummary(
        strategy_type="dca_accumulation",
        asset_universe=["AAPL"],
        asset_class="equity",
        capital_amount=500,
        cadence="monthly",
        date_range={"start": "2022-01-01", "end": "2024-01-01"},
        extra_parameters={
            "date_range_intent": _future_window_intent("for the next two years"),
            "date_range_raw_text": "from January 2022 through January 2024",
            "evidence_spans": dict(DCA_STALE_EVIDENCE_SPANS),
            "field_provenance": {"capital_amount": "explicit_user"},
        },
        field_provenance={"capital_amount": "explicit_user"},
    )


def test_future_boundary_clears_stale_date_evidence_for_dca_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing a dated DCA draft to a future horizon must not leave stale
    date evidence behind: after the historical-period selection, the DCA
    contract may not rebuild the prior window and skip the date question."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message="Actually run that DCA for the next two years instead.",
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User pointed an existing DCA at a future window.",
            assistant_response=None,
            candidate_strategy_draft=_dca_future_decision_draft(),
            semantic_turn_act="refine_current_idea",
        ),
    )
    decision = result.decision
    assert decision is not None
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED in decision.reason_codes
    conserved = decision.candidate_strategy_draft
    assert conserved.date_range in (None, "", {}, [])
    extra = conserved.extra_parameters or {}
    assert "date_range_intent" not in extra
    assert "date_range_raw_text" not in extra
    spans = extra.get("evidence_spans") or {}
    assert "date_range" not in spans
    # Unrelated evidence and provenance survive.
    assert spans.get("asset_universe") == "Apple"
    assert spans.get("capital_amount") == "$500 every month"
    assert spans.get("cadence") == "every month"
    assert (extra.get("field_provenance") or {}).get("capital_amount") == (
        "explicit_user"
    )
    horizon = extra.get(FUTURE_HORIZON_EVIDENCE_KEY)
    assert isinstance(horizon, dict)
    assert horizon.get("evidence") == "for the next two years"
    assert conserved.capital_amount == 500
    assert conserved.cadence == "monthly"
    assert conserved.asset_universe == ["AAPL"]

    draft = _llm_draft_from_strategy_summary(conserved)
    replaced = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values={"requested_field": "date_range"},
        current_missing=list(decision.missing_required_fields),
    )
    repaired = replaced["draft"]
    assert repaired.date_range in (None, "", {}, [])
    assert "date_range" in replaced["missing_fields"]


def _future_recovery_clarify_state() -> RunState:
    state = RunState.new(
        current_user_message=EN_FUTURE_MESSAGE,
        recent_thread_history=[],
    )
    state.intent = "strategy_drafting"
    state.missing_required_fields = ["date_range"]
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="signal_strategy",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        extra_parameters={
            FUTURE_HORIZON_EVIDENCE_KEY: _future_window_intent("in ten years"),
        },
    )
    state.optional_parameter_status = {
        "unsupported_constraints": [
            {
                "category": FUTURE_PERFORMANCE_CATEGORY,
                "raw_value": "in ten years",
                "explanation": "Argus cannot predict future performance.",
                "simplification_options": [
                    {
                        "label": "Test this idea over a historical period",
                        "replacement_values": {"requested_field": "date_range"},
                    },
                    {
                        "label": "Compare with buy and hold historically",
                        "replacement_values": {
                            "strategy_type": "buy_and_hold",
                            "requested_field": "date_range",
                        },
                    },
                ],
            }
        ]
    }
    return state


def test_future_admission_never_propagates_interpreter_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interpreter's own prose is untrusted at the future boundary: on the
    guard route it can carry a numeric forecast, and no typed field can
    distinguish a forecast from a refusal. The blocked patch never prefills
    prose; the clarify stage owns the replacement voice."""

    _stub_equity_asset_resolution(monkeypatch)
    result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="backtest_execution",
            evidence="in ten years",
            assistant_response=FORECAST_PROSE,
        ),
    )
    _assert_future_blocked(result, evidence="in ten years")
    assert result.patch.get("assistant_response") is None


def test_future_recovery_prose_is_llm_clarification_owned() -> None:
    """With no prefilled prose, the existing clarification LLM voices the
    boundary; its output is carried byte-exactly with llm_generated provenance."""

    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.clarify import clarify_stage

    class RecordingClarifier:
        def __init__(self, question: str | None) -> None:
            self.question = question
            self.requests: list[Any] = []

        def __call__(self, request):
            self.requests.append(request)
            return self.question

    honest = (
        "I can't predict future performance, but I can test how the same "
        "golden-cross idea performed historically. Which period should I use?"
    )
    clarifier = RecordingClarifier(honest)
    result = clarify_stage(
        state=_future_recovery_clarify_state(),
        contract=build_default_capability_contract(),
        clarification_generator=clarifier,
        language="en",
        prefilled_assistant_prompt=None,
    )
    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == honest
    assert clarifier.requests
    clarification = result.patch["clarification"]
    assert clarification["kind"] == "unsupported_recovery"
    assert clarification["reason_code"] == FUTURE_PERFORMANCE_CATEGORY
    assert clarification["prompt_source"] == "llm_generated"


def test_future_recovery_generation_failure_uses_honest_fallback() -> None:
    """A clarification-generation failure falls back to the deterministic
    future-performance copy, never to interpreter prose."""

    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.clarify import clarify_stage

    result = clarify_stage(
        state=_future_recovery_clarify_state(),
        contract=build_default_capability_contract(),
        clarification_generator=None,
        language="en",
        prefilled_assistant_prompt=None,
    )
    assert result.outcome == "await_user_reply"
    prompt = result.patch["assistant_prompt"]
    assert "cannot predict future performance" in prompt
    assert "historical period" in prompt
    assert "$150,000" not in prompt
    clarification = result.patch["clarification"]
    assert clarification["reason_code"] == FUTURE_PERFORMANCE_CATEGORY
    assert clarification["prompt_source"] == "degraded_fallback"


def test_forecast_prose_full_route_reaches_honest_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end: future_window plus forecast prose becomes future_performance
    recovery whose visible prose carries no forecast, with facts conserved and
    no executable artifact."""

    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.clarify import clarify_stage

    _stub_equity_asset_resolution(monkeypatch)
    interpret_result = _run_interpret(
        message=EN_FUTURE_MESSAGE,
        response=_future_interpretation(
            intent="backtest_execution",
            evidence="in ten years",
            assistant_response=FORECAST_PROSE,
        ),
    )
    _assert_future_blocked(interpret_result, evidence="in ten years")
    assert interpret_result.patch.get("assistant_response") is None

    state = RunState.new(
        current_user_message=EN_FUTURE_MESSAGE,
        recent_thread_history=[],
    )
    patch_payload = {
        key: value
        for key, value in interpret_result.patch.items()
        if key in RunState.model_fields
    }
    state = state.model_copy(update=patch_payload)
    decision = interpret_result.decision
    assert decision is not None
    state.candidate_strategy_draft = decision.candidate_strategy_draft
    state.missing_required_fields = list(decision.missing_required_fields)

    clarify_result = clarify_stage(
        state=state,
        contract=build_default_capability_contract(),
        clarification_generator=None,
        language="en",
        prefilled_assistant_prompt=interpret_result.patch.get("assistant_response"),
    )
    prompt = clarify_result.patch["assistant_prompt"]
    assert "$150,000" not in prompt
    assert "cannot predict future performance" in prompt
    assert clarify_result.patch.get("confirmation_payload") is None
    clarification = clarify_result.patch["clarification"]
    assert clarification["reason_code"] == FUTURE_PERFORMANCE_CATEGORY
    strategy = clarification["payload"]["strategy"]
    assert strategy["asset_universe"] == ["NVDA"]
    assert strategy["capital_amount"] == 10000
    horizon = (strategy.get("extra_parameters") or {}).get(FUTURE_HORIZON_EVIDENCE_KEY)
    assert isinstance(horizon, dict)
    assert horizon.get("evidence") == "in ten years"
