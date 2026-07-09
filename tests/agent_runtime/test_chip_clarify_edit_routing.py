"""Chip-clarify answers route through the typed edit contract (issue #188).

A confirmation-card chip (change_asset, change_dates, adjust_assumptions)
opens a field-scoped clarification. The ANSWER turn must be planned exactly
like the equivalent natural-language edit: the chip's ``requested_field`` is
display scope, never the reply's routing contract. These tests encode the
founder-session repros (conversation 44a80f99) as typed state asserts:

- Repro A: an assumption-chip capital answer must land the same typed state
  as the identical no-chip turn (two doors, one contract).
- Repro B: a remove on a multi-asset card must keep the remainder set and
  must never transiently empty pending assets.
- Repro C: a compound remove+replace must apply set-complete.
- Changed-mind: a chip answered with a DIFFERENT field's edit applies that
  edit (capital/dates/assets cross-answers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
)
from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)

EQUITY_SYMBOLS = {"TGT", "WSM", "COST", "AAPL", "NVDA", "MSFT"}


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response
        self.requests: list[Any] = []

    def __call__(self, request):
        self.requests.append(request)
        return self.response


def _stub_equity_resolution(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        cleaned = symbol.strip().upper()
        if cleaned in EQUITY_SYMBOLS:
            return ResolvedAssetStub(cleaned, "equity")
        raise ValueError("unsupported_symbol")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _stub_edit_planner(monkeypatch, plan: ArtifactAssumptionEditPlan | None):
    from argus.agent_runtime.stages import interpret as interpret_module

    calls: list[dict[str, Any]] = []

    async def plan_stub(**kwargs: Any) -> ArtifactAssumptionEditPlan | None:
        calls.append(kwargs)
        return plan

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    return calls


def _validated_confirmation_payload(strategy: StrategySummary) -> dict[str, Any]:
    symbol = strategy.asset_universe[0] if strategy.asset_universe else "SPY"
    return {
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": strategy.strategy_type or "buy_and_hold",
            "symbol": symbol,
            "symbols": list(strategy.asset_universe),
            "timeframe": "1D",
            "date_range": (
                strategy.date_range
                if isinstance(strategy.date_range, dict)
                else {"start": "2025-01-01", "end": "2025-12-31"}
            ),
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": (
                strategy.capital_amount if strategy.capital_amount is not None else 1000
            ),
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }


def _snapshot_with_confirmation(strategy: StrategySummary) -> TaskSnapshot:
    reference = confirmation_artifact_reference(
        confirmation_id="confirmation-188",
        confirmation_payload=_validated_confirmation_payload(strategy),
    )
    return TaskSnapshot(
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )


def _run_chip_answer(
    *,
    message: str,
    pending: StrategySummary,
    interpretation: StructuredInterpretation,
    requested_field: str | None,
):
    metadata: dict[str, Any] = {"last_stage_outcome": "await_user_reply"}
    if requested_field is not None:
        metadata["requested_field"] = requested_field
        metadata["missing_required_fields"] = [requested_field]
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    return interpret_stage(
        state=state,
        user=UserState(user_id="u1"),
        latest_task_snapshot=_snapshot_with_confirmation(pending),
        selected_thread_metadata=metadata,
        structured_interpreter=RecordingInterpreter(interpretation),
    )


def _pending_three_assets() -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Target, Williams-Sonoma, and Costco.",
        asset_universe=["TGT", "WSM", "COST"],
        asset_class="equity",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        capital_amount=1000,
    )


def _planned_edit_interpretation(draft: StrategySummary) -> StructuredInterpretation:
    """The shape the typed edit planner hands the stage for a chip answer."""

    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User changed a visible confirmation assumption.",
        candidate_strategy_draft=draft,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act="answer_pending_need",
    )


def _planned_asset_replace_draft(symbols: list[str]) -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=list(symbols),
        extra_parameters={
            "asset_universe_operation": "replace",
            "field_provenance": {"asset_universe": "explicit_user"},
        },
    )


def test_change_asset_chip_remove_applies_planned_remainder_set_complete(
    monkeypatch,
) -> None:
    """Repro B: 'remove TGT' on {TGT, WSM, COST} keeps {WSM, COST} and never
    empties pending assets."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="I would like to remove TGT",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=_planned_edit_interpretation(
            _planned_asset_replace_draft(["WSM", "COST"])
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["WSM", "COST"]
    assert "asset_universe" not in result.decision.missing_required_fields
    assert strategy.capital_amount == 1000
    assert strategy.date_range == {"start": "2025-01-01", "end": "2025-12-31"}


def test_change_asset_chip_raw_remove_remainder_does_not_wipe_pending_assets(
    monkeypatch,
) -> None:
    """Repro B without the planner: a raw remainder draft on a multi-asset
    card must not be re-derived into a wipe by the requested_field corridor."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="I would like to remove TGT",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User removed Target from the traded set.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["WSM", "COST"],
            ),
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["WSM", "COST"]
    assert "asset_universe" not in result.decision.missing_required_fields


def test_change_asset_chip_bare_symbol_answer_on_multi_asset_card_clarifies(
    monkeypatch,
) -> None:
    """A bare new symbol answering the asset chip on a multi-asset card is
    add-or-replace ambiguous: keep the clarification open with pending state
    intact instead of silently reconfirming the unchanged card."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="MSFT",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the asset question.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TGT", "WSM", "COST"]
    assert "asset_universe" in result.decision.missing_required_fields
    assert result.patch.get("assistant_response")


def test_change_asset_chip_compound_remove_replace_applies_set_complete(
    monkeypatch,
) -> None:
    """Repro C: 'remove TGT and replace it for WSM and COST' applies both
    replacement symbols, not just the first."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Target.",
        asset_universe=["TGT"],
        asset_class="equity",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        capital_amount=1000,
    )
    result = _run_chip_answer(
        message="remove TGT and replace it for WSM and COST",
        pending=pending,
        requested_field="asset_universe",
        interpretation=_planned_edit_interpretation(
            _planned_asset_replace_draft(["WSM", "COST"])
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["WSM", "COST"]


def _planned_capital_draft(amount: float) -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        capital_amount=amount,
        extra_parameters={
            "initial_capital": amount,
            "field_provenance": {
                "initial_capital": "starting_capital",
                "capital_amount": "starting_capital",
            },
        },
    )


def test_adjust_assumptions_chip_capital_answer_lands_same_state_as_no_chip(
    monkeypatch,
) -> None:
    """Repro A: the same planned capital edit must land the same typed state
    through the chip door and the no-chip door."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        capital_amount=1000,
    )

    chip_result = _run_chip_answer(
        message="change the capital to $10,000",
        pending=pending,
        requested_field="assumption",
        interpretation=_planned_edit_interpretation(_planned_capital_draft(10000)),
    )
    no_chip_result = _run_chip_answer(
        message="change the capital to $10,000",
        pending=pending,
        requested_field=None,
        interpretation=_planned_edit_interpretation(_planned_capital_draft(10000)),
    )

    assert chip_result.outcome == "ready_for_confirmation"
    assert no_chip_result.outcome == "ready_for_confirmation"
    chip_strategy = chip_result.decision.candidate_strategy_draft
    no_chip_strategy = no_chip_result.decision.candidate_strategy_draft
    assert chip_strategy.capital_amount == 10000
    assert no_chip_strategy.capital_amount == 10000
    assert chip_strategy.asset_universe == ["AAPL"]
    # The demotion fingerprint: the chip door must not reroute the answer
    # into optional_parameter_status while nulling the draft's own field.
    chip_optional_status = chip_result.patch.get("optional_parameter_status") or {}
    assert "initial_capital" not in chip_optional_status


def test_change_asset_chip_answered_with_capital_edit_applies_that_edit(
    monkeypatch,
) -> None:
    """Changed-mind: a capital answer inside the change-asset clarification
    applies the capital edit and leaves the traded set untouched."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="actually make it $5,000",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=_planned_edit_interpretation(_planned_capital_draft(5000)),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TGT", "WSM", "COST"]
    assert strategy.capital_amount == 5000


def test_change_asset_chip_answered_with_date_edit_applies_that_edit(
    monkeypatch,
) -> None:
    """Changed-mind: a date answer inside the change-asset clarification
    applies the date edit and leaves the traded set untouched."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="change the dates to 2024 instead",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=_planned_edit_interpretation(
            StrategySummary(
                strategy_type="buy_and_hold",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                extra_parameters={
                    "field_provenance": {"date_range": "explicit_user"},
                },
            )
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TGT", "WSM", "COST"]
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}


def test_adjust_assumptions_chip_answered_with_asset_edit_applies_that_edit(
    monkeypatch,
) -> None:
    """Changed-mind: an asset answer inside the adjust-assumptions
    clarification applies the asset edit and keeps the prior capital."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        capital_amount=1000,
    )
    result = _run_chip_answer(
        message="switch it to NVDA instead",
        pending=pending,
        requested_field="assumption",
        interpretation=_planned_edit_interpretation(
            _planned_asset_replace_draft(["NVDA"])
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.capital_amount == 1000


def test_change_dates_chip_capital_answer_replans_through_edit_planner(
    monkeypatch,
) -> None:
    """Changed-mind through the dates chip: a raw capital answer re-enters the
    typed edit planner instead of dying in requested_field preservation."""

    _stub_equity_resolution(monkeypatch)
    calls = _stub_edit_planner(
        monkeypatch,
        ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the starting capital.",
            operations=[
                EditOperation(op="set", target="capital", number=5000),
            ],
            confidence=0.9,
        ),
    )

    result = _run_chip_answer(
        message="actually make it $5,000",
        pending=_pending_three_assets(),
        requested_field="date_range",
        interpretation=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User changed the starting capital.",
            candidate_strategy_draft=StrategySummary(capital_amount=5000),
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert calls, "the chip answer must reach the typed edit planner"
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 5000
    assert strategy.asset_universe == ["TGT", "WSM", "COST"]
    assert "artifact_assumption_edit_planned" in result.decision.reason_codes


def test_change_dates_chip_capital_answer_survives_planner_outage(
    monkeypatch,
) -> None:
    """When the replan planner yields nothing, a chip answer whose draft
    carries explicit typed money must flow like the no-chip turn instead of
    being dropped by requested_field preservation."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="actually make it $5,000",
        pending=_pending_three_assets(),
        requested_field="date_range",
        interpretation=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User changed the starting capital.",
            candidate_strategy_draft=StrategySummary(
                capital_amount=5000,
                extra_parameters={
                    "field_provenance": {"capital_amount": "starting_capital"},
                },
            ),
            semantic_turn_act="answer_pending_need",
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.capital_amount == 5000
    assert strategy.asset_universe == ["TGT", "WSM", "COST"]


def test_planned_asset_patch_is_not_blocked_by_stale_action_rejection(
    monkeypatch,
) -> None:
    """A stale action-rejection constraint from the interpreter must not turn
    an applied typed asset patch into a spurious clarification."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    interpretation = _planned_edit_interpretation(
        _planned_asset_replace_draft(["WSM", "COST"])
    )
    interpretation = interpretation.model_copy(
        update={
            "unsupported_constraints": [
                UnsupportedConstraint(
                    category="action",
                    raw_value="remove TGT",
                    explanation="Buttons cannot be clicked from chat.",
                )
            ]
        }
    )
    result = _run_chip_answer(
        message="I would like to remove TGT",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=interpretation,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["WSM", "COST"]
    assert not result.decision.unsupported_constraints


def test_change_asset_chip_planned_edit_over_symbol_limit_still_clarifies(
    monkeypatch,
) -> None:
    """Typed-edit precedence does not bypass deterministic validation: a
    planned replace beyond the 5-symbol limit still clarifies."""

    _stub_equity_resolution(monkeypatch)
    _stub_edit_planner(monkeypatch, None)

    result = _run_chip_answer(
        message="test all six of these",
        pending=_pending_three_assets(),
        requested_field="asset_universe",
        interpretation=_planned_edit_interpretation(
            _planned_asset_replace_draft(
                ["TGT", "WSM", "COST", "AAPL", "NVDA", "MSFT"]
            )
        ),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.requires_clarification
    assert any(
        constraint.category == "asset_universe_limit"
        for constraint in result.decision.unsupported_constraints
    )


def test_chip_clarify_fields_cover_the_three_chip_actions() -> None:
    """The clarify-scope set is derived from the chip action map; pin its
    contents so an accidental map edit cannot silently change routing."""

    from argus.agent_runtime.stages.interpret_internal.interpreter_unavailable_continuity import (
        CONFIRMATION_EDIT_CLARIFY_FIELDS,
    )

    assert CONFIRMATION_EDIT_CLARIFY_FIELDS == frozenset(
        {"asset_universe", "date_range", "assumption"}
    )


