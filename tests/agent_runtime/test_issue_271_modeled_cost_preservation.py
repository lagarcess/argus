"""Regression coverage for issue #271 modeled-cost continuity."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.artifacts.drafts import draft_from_confirmation_payload
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.domain.backtesting.rules import (
    rule_spec_from_moving_average_crossover_rules,
)

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub


class _RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    def __call__(self, request: Any) -> StructuredInterpretation:
        del request
        return self.response


def _completed_result_reference(assets: list[str]) -> ArtifactReference:
    realism = {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-271-source",
        artifact_status="completed",
        metadata={
            "asset_class": "equity",
            "symbols": list(assets),
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": list(assets),
                "timeframe": "1D",
                "date_range": {
                    "start": "2023-01-03",
                    "end": "2024-12-31",
                },
                "benchmark_symbol": "SPY",
                "resolved_strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold the selected equities.",
                    "asset_universe": list(assets),
                    "asset_class": "equity",
                    "entry_rule": {"type": "start_of_period"},
                    "exit_rule": {"type": "end_of_period"},
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "date_range": {
                        "start": "2023-01-03",
                        "end": "2024-12-31",
                    },
                    "sizing_mode": "capital_amount",
                    "capital_amount": 12000,
                    "benchmark_symbol": "SPY",
                    "engine_config": {"_execution_realism": dict(realism)},
                },
                "engine_config": {"_execution_realism": dict(realism)},
            },
        },
    )


def _asset_patch_response(assets: list[str]) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="Change the assets and keep the other assumptions.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=list(assets),
            extra_parameters={
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
        ),
        semantic_turn_act="answer_pending_need",
        artifact_target="latest_result",
        reason_codes=["artifact_assumption_edit_planned"],
    )


def _cost_strategy() -> StrategySummary:
    return StrategySummary(
        requested_strategy_template="buy_and_hold",
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold MSFT with modeled execution costs.",
        asset_universe=["MSFT"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-03", "end": "2024-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        entry_rule={"type": "start_of_period"},
        exit_rule={"type": "end_of_period"},
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        },
    )


def test_unprovenanced_llm_costs_stay_idealized_at_canonical_boundary() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            capital_amount=12000,
            extra_parameters={
                "fee_rate": 0.001,
                "slippage": 0.0005,
            },
        )
    )

    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    assert "field_provenance" not in strategy.extra_parameters


def test_evidence_backed_llm_costs_gain_explicit_provenance() -> None:
    message = (
        "Build a daily MSFT test and model a 10 bps fee and 5 bps slippage."
    )
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            raw_user_phrasing="Model-normalized strategy summary.",
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            capital_amount=12000,
            evidence_spans={
                "fee_rate": "10 bps fee",
                "slippage": "5 bps slippage",
            },
            extra_parameters={
                "fee_rate": 0.001,
                "slippage": 0.0005,
            },
        ),
        current_user_message=message,
    )

    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["evidence_spans"] == {
        "fee_rate": "10 bps fee",
        "slippage": "5 bps slippage",
    }
    assert strategy.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }


def test_model_declared_cost_provenance_without_spans_is_rejected() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            capital_amount=12000,
            field_provenance={
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
            extra_parameters={
                "fee_rate": 0.001,
                "slippage": 0.0005,
            },
        ),
        current_user_message=(
            "Build a daily MSFT test with a 10 bps fee and 5 bps slippage."
        ),
    )

    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    assert "field_provenance" not in strategy.extra_parameters


def test_invented_cost_evidence_spans_are_rejected() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            evidence_spans={
                "fee_rate": "20 bps fee",
                "slippage": "2 bps slippage",
            },
            field_provenance={
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
            extra_parameters={
                "fee_rate": 0.001,
                "slippage": 0.0005,
            },
        ),
        current_user_message=(
            "Build a daily MSFT test with a 10 bps fee and 5 bps slippage."
        ),
    )

    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    assert "field_provenance" not in strategy.extra_parameters
    assert "evidence_spans" not in strategy.extra_parameters


def test_bounded_zero_cost_spans_preserve_intentional_clears() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            evidence_spans={
                "fee_rate": "0 bps fee",
                "slippage": "0 bps slippage",
            },
            extra_parameters={
                "fee_rate": 0.0,
                "slippage": 0.0,
            },
        ),
        current_user_message="Set a 0 bps fee and 0 bps slippage.",
    )

    assert strategy.extra_parameters["fee_rate"] == 0.0
    assert strategy.extra_parameters["slippage"] == 0.0
    assert strategy.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }


def test_unprovenanced_zero_llm_costs_remain_canonical_defaults() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            extra_parameters={
                "fee_rate": 0.0,
                "slippage": 0.0,
            },
        )
    )

    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    assert "field_provenance" not in strategy.extra_parameters


def test_flag_off_llm_costs_do_not_gain_explicit_provenance(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")

    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            date_range={"start": "2023-01-03", "end": "2024-12-31"},
            extra_parameters={
                "fee_rate": 0.001,
                "slippage": 0.0005,
            },
        )
    )

    assert "field_provenance" not in strategy.extra_parameters
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters


def _active_confirmation_snapshot(strategy: StrategySummary) -> TaskSnapshot:
    payload = {
        "confirmation_id": "confirmation-271",
        "artifact_id": "confirmation-271",
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": strategy.strategy_type,
            "symbol": strategy.asset_universe[0],
            "symbols": list(strategy.asset_universe),
            "asset_class": strategy.asset_class,
            "timeframe": strategy.timeframe,
            "date_range": strategy.date_range,
            "sizing_mode": "capital_amount",
            "capital_amount": strategy.capital_amount,
            "position_size": None,
            "cadence": strategy.cadence,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": strategy.comparison_baseline,
            "_execution_realism": {
                "enabled": True,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
            },
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }
    reference = confirmation_artifact_reference(
        confirmation_id="confirmation-271",
        confirmation_payload=payload,
    )
    return TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )


def _cost_patch_response(
    *,
    fee_rate: float,
    slippage: float,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Change the modeled execution costs.",
        candidate_strategy_draft=StrategySummary(
            extra_parameters={
                "fee_rate": fee_rate,
                "slippage": slippage,
                "field_provenance": {
                    "fee_rate": "explicit_user",
                    "slippage": "explicit_user",
                },
            }
        ),
        semantic_turn_act="answer_pending_need",
        artifact_target="active_confirmation",
        reason_codes=["artifact_assumption_edit_planned"],
    )


@pytest.mark.parametrize(
    ("source_assets", "next_assets"),
    [
        (["MSFT"], ["MSFT", "AAPL"]),
        (["MSFT", "AAPL"], ["MSFT"]),
        (["MSFT"], ["NVDA"]),
    ],
    ids=["add", "remove", "replace"],
)
def test_post_result_asset_edits_preserve_modeled_costs(
    monkeypatch: pytest.MonkeyPatch,
    source_assets: list[str],
    next_assets: list[str],
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol, **kwargs: ResolvedAssetStub(
            symbol.strip().upper(),
            "equity",
        ),
    )
    source = _completed_result_reference(source_assets)
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Change the assets and keep every other assumption.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="backtest_execution",
            completed=True,
            latest_backtest_result_reference=source,
            artifact_references=[source],
        ),
        selected_thread_metadata={
            "latest_task_type": "backtest_execution",
            "last_stage_outcome": "ready_to_respond",
            "latest_run_id": source.artifact_id,
        },
        structured_interpreter=_RecordingInterpreter(_asset_patch_response(next_assets)),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == next_assets
    assert strategy.capital_amount == 12000
    assert strategy.date_range == {
        "start": "2023-01-03",
        "end": "2024-12-31",
    }
    assert strategy.timeframe == "1D"
    assert strategy.comparison_baseline == "SPY"
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["field_provenance"]["fee_rate"] == ("explicit_user")
    assert strategy.extra_parameters["field_provenance"]["slippage"] == ("explicit_user")
    assert "backtest_job" not in result.patch
    assert source.artifact_status == "completed"


@pytest.mark.parametrize(
    ("source_assets", "next_assets"),
    [
        (["MSFT"], ["MSFT", "AAPL"]),
        (["MSFT", "AAPL"], ["MSFT"]),
        (["MSFT"], ["NVDA"]),
    ],
    ids=["add", "remove", "replace"],
)
def test_active_confirmation_asset_edits_preserve_modeled_costs(
    source_assets: list[str],
    next_assets: list[str],
) -> None:
    strategy = _cost_strategy().model_copy(
        update={"asset_universe": list(source_assets)},
        deep=True,
    )
    response = _asset_patch_response(next_assets).model_copy(
        update={"artifact_target": "active_confirmation"},
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Change the assets and keep every other assumption.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=_active_confirmation_snapshot(strategy),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=_RecordingInterpreter(response),
    )

    assert result.outcome == "ready_for_confirmation"
    edited = result.decision.candidate_strategy_draft
    assert edited.asset_universe == next_assets
    assert edited.extra_parameters["fee_rate"] == 0.001
    assert edited.extra_parameters["slippage"] == 0.0005
    assert edited.extra_parameters["field_provenance"]["fee_rate"] == ("explicit_user")
    assert edited.extra_parameters["field_provenance"]["slippage"] == ("explicit_user")
    assert "backtest_job" not in result.patch


def test_confirmation_launch_card_and_hydration_share_canonical_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    strategy = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold MSFT with modeled execution costs.",
        asset_universe=["MSFT"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-03", "end": "2024-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        },
    )
    state = RunState.new(
        current_user_message="Keep my modeled costs.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = strategy

    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.outcome == "await_approval"
    payload = result.patch["confirmation_payload"]
    assert payload["optional_parameters"]["fees"]["value"] == 0.001
    assert payload["optional_parameters"]["fees"]["source"] == "user"
    assert payload["optional_parameters"]["slippage"]["value"] == 0.0005
    assert payload["optional_parameters"]["slippage"]["source"] == "user"
    assert (
        "Modeled costs: 10 bps fee + 5 bps slippage"
        in (payload["strategy"]["assumptions"])
    )
    assert "No fees" not in payload["strategy"]["assumptions"]
    assert "No slippage" not in payload["strategy"]["assumptions"]
    assert payload["strategy"]["extra_parameters"]["fee_rate"] == 0.001
    assert payload["strategy"]["extra_parameters"]["slippage"] == 0.0005
    assert payload["strategy"]["extra_parameters"]["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }
    assert payload["launch_payload"]["_execution_realism"] == {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }

    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": payload,
        }
    )
    assert card is not None
    assert card["display_facts"]["fees"] == 0.001
    assert card["display_facts"]["slippage"] == 0.0005
    assert "Modeled costs: 10 bps fee + 5 bps slippage" in card["assumptions"]

    hydrated = draft_from_confirmation_payload(payload)
    assert hydrated.extra_parameters["fee_rate"] == 0.001
    assert hydrated.extra_parameters["slippage"] == 0.0005
    assert hydrated.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }


def test_confirmation_does_not_model_unprovenanced_strategy_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    strategy = _cost_strategy()
    strategy.extra_parameters.pop("field_provenance")
    state = RunState.new(
        current_user_message="Test this idea.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = strategy

    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert result.outcome == "await_approval"
    payload = result.patch["confirmation_payload"]
    assert payload["optional_parameters"]["fees"]["value"] == 0.0
    assert payload["optional_parameters"]["fees"]["source"] == "default"
    assert payload["optional_parameters"]["slippage"]["value"] == 0.0
    assert payload["optional_parameters"]["slippage"]["source"] == "default"
    assert "_execution_realism" not in payload["launch_payload"]
    assert "No fees" in payload["strategy"]["assumptions"]
    assert "No slippage" in payload["strategy"]["assumptions"]


def test_launch_projection_uses_exact_basis_points_for_decimal_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    strategy = _cost_strategy()
    strategy.extra_parameters.update(
        {
            "fee_rate": 0.0011,
            "slippage": 0.0006,
        }
    )
    state = RunState.new(
        current_user_message="Use 11 bps fees and 6 bps slippage.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = strategy

    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    payload = result.patch["confirmation_payload"]
    assert payload["strategy"]["extra_parameters"]["fee_rate"] == 0.0011
    assert payload["strategy"]["extra_parameters"]["slippage"] == 0.0006
    assert payload["launch_payload"]["_execution_realism"] == {
        "enabled": True,
        "fee_bps": 11.0,
        "slippage_bps": 6.0,
    }


@pytest.mark.parametrize(
    "message",
    [
        "Use 0.13% fees and 0.07% slippage.",
        "Set fees to 0.13% and slippage to 0.07% per trade.",
    ],
    ids=["natural-language", "card-edit-costs"],
)
def test_cost_edit_surfaces_converge_on_canonical_state(message: str) -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message=message,
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=_active_confirmation_snapshot(_cost_strategy()),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=_RecordingInterpreter(
            _cost_patch_response(
                fee_rate=0.0013,
                slippage=0.0007,
            )
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.capital_amount == 12000
    assert strategy.extra_parameters["fee_rate"] == 0.0013
    assert strategy.extra_parameters["slippage"] == 0.0007
    assert strategy.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }
    assert "backtest_job" not in result.patch


def test_explicit_zero_costs_clear_launch_realism() -> None:
    result = interpret_stage(
        state=RunState.new(
            current_user_message=("Set fees to 0% and slippage to 0% per trade."),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=_active_confirmation_snapshot(_cost_strategy()),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=_RecordingInterpreter(
            _cost_patch_response(fee_rate=0.0, slippage=0.0)
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.extra_parameters["fee_rate"] == 0.0
    assert strategy.extra_parameters["slippage"] == 0.0
    assert strategy.extra_parameters["field_provenance"] == {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }

    confirmation_state = RunState.new(
        current_user_message="Keep both costs at zero.",
        recent_thread_history=[],
    )
    confirmation_state.candidate_strategy_draft = strategy
    confirmation = confirm_stage(
        state=confirmation_state,
        contract=build_default_capability_contract(),
    )
    assert confirmation.outcome == "await_approval"
    payload = confirmation.patch["confirmation_payload"]
    assert payload["optional_parameters"]["fees"]["value"] == 0.0
    assert payload["optional_parameters"]["slippage"]["value"] == 0.0
    assert payload["strategy"]["extra_parameters"]["fee_rate"] == 0.0
    assert payload["strategy"]["extra_parameters"]["slippage"] == 0.0
    assert "No fees" in payload["strategy"]["assumptions"]
    assert "No slippage" in payload["strategy"]["assumptions"]
    assert "_execution_realism" not in payload["launch_payload"]


@pytest.mark.parametrize("edit_kind", ["capital", "dates", "strategy"])
def test_unrelated_supported_edits_preserve_modeled_costs(
    edit_kind: str,
) -> None:
    candidate = StrategySummary()
    if edit_kind == "capital":
        candidate.capital_amount = 15000
        candidate.extra_parameters = {
            "field_provenance": {"capital_amount": "starting_capital"}
        }
    elif edit_kind == "dates":
        candidate.date_range = {"start": "2023-02-01", "end": "2024-11-30"}
        candidate.extra_parameters = {"field_provenance": {"date_range": "explicit_user"}}
    else:
        entry_rule = {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        }
        exit_rule = {**entry_rule, "direction": "bearish"}
        rule_spec = rule_spec_from_moving_average_crossover_rules(
            entry_rule=entry_rule,
            exit_rule=exit_rule,
        )
        assert rule_spec is not None
        candidate.requested_strategy_template = "moving_average_crossover"
        candidate.strategy_type = "signal_strategy"
        candidate.entry_rule = entry_rule
        candidate.exit_rule = exit_rule
        candidate.rule_spec = rule_spec
        candidate.extra_parameters = {
            "field_provenance": {
                "requested_strategy_template": "explicit_user",
                "strategy_type": "explicit_user",
                "entry_rule": "explicit_user",
                "exit_rule": "explicit_user",
            }
        }

    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="Change one supported assumption.",
        candidate_strategy_draft=candidate,
        semantic_turn_act="answer_pending_need",
        artifact_target="active_confirmation",
        reason_codes=["artifact_assumption_edit_planned"],
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Change one assumption and keep everything else.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=_active_confirmation_snapshot(_cost_strategy()),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=_RecordingInterpreter(response),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["MSFT"]
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["field_provenance"]["fee_rate"] == ("explicit_user")
    assert strategy.extra_parameters["field_provenance"]["slippage"] == ("explicit_user")
    assert "backtest_job" not in result.patch


def test_pending_option_selection_preserves_modeled_costs() -> None:
    pending = _cost_strategy().model_copy(
        update={"date_range": None},
        deep=True,
    )
    selected_date_range = {"start": "2023-01-03", "end": "2024-12-31"}
    replacement_values = {"date_range": selected_date_range}
    response_intent = {
        "kind": "clarification",
        "semantic_needs": ["period"],
        "requested_fields": ["date_range"],
        "facts": {"strategy": pending.model_dump(mode="python")},
        "options": [
            {
                "id": "fixed-window",
                "label": "Use the fixed window",
                "replacement_values": replacement_values,
            }
        ],
    }
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Use the fixed window",
            recent_thread_history=[],
            action_context={
                "type": "select_response_option",
                "label": "Use the fixed window",
                "payload": {
                    "source_assistant_id": "assistant-271",
                    "validated_source_assistant_id": "assistant-271",
                    "replacement_values": replacement_values,
                },
            },
        ),
        user=UserState(user_id="u-271"),
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "validated_source_assistant_id": "assistant-271",
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
            "response_intent": response_intent,
        },
        structured_interpreter=_RecordingInterpreter(
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="The period is unresolved.",
                candidate_strategy_draft=pending,
                missing_required_fields=["date_range"],
                semantic_turn_act="answer_pending_need",
            )
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == selected_date_range
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["field_provenance"]["fee_rate"] == ("explicit_user")
    assert strategy.extra_parameters["field_provenance"]["slippage"] == ("explicit_user")
    assert "pending_response_option_selected" in result.decision.reason_codes
    assert "backtest_job" not in result.patch
