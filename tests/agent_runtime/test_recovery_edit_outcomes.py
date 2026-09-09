"""Recovery planning must carry every edit outcome into the resulting card."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import artifact_edit_planner as planner
from argus.agent_runtime import llm_interpreter as interpreter
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages import confirm as confirm_module
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_internal.interpreter_unavailable_continuity import (
    planned_active_confirmation_edit_interpretation,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState
from faker import Faker

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub
from tests.agent_runtime.test_compound_edit_contract import _request


@pytest.fixture
def recovery_request(monkeypatch: pytest.MonkeyPatch) -> InterpretationRequest:
    fake = Faker()
    request = _request("Change the requested assumptions", requested_field="assumption")
    request.user.user_id = fake.uuid4()
    strategy = request.latest_task_snapshot.pending_strategy_summary
    strategy.date_range["start"] = "2023-01-03"

    def resolve_asset(symbol: str, **_kwargs: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpreter, "resolve_asset", resolve_asset)
    monkeypatch.setattr(confirm_module, "fetch_alpaca_market_clock", lambda: None)
    monkeypatch.setattr(
        planner, "openrouter_structured_model_candidates", lambda: ["test-model"]
    )
    return request


async def _recover(
    request: InterpretationRequest,
    plan_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> StructuredInterpretation | None:
    async def invoke(
        *, schema_model: type, **_kwargs: Any
    ) -> planner.ArtifactAssumptionEditPlan:
        assert schema_model is planner.ArtifactAssumptionEditPlan
        return schema_model(**plan_data)

    monkeypatch.setattr(planner, "invoke_openrouter_json_schema", invoke)
    return await planned_active_confirmation_edit_interpretation(
        snapshot=request.latest_task_snapshot,
        current_user_message=request.current_user_message,
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
        plan_artifact_assumption_edit_fn=planner.plan_artifact_assumption_edit,
    )


async def _recover_and_confirm(
    request: InterpretationRequest,
    plan_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    response = await _recover(request, plan_data, monkeypatch)
    assert response is not None, "the real planner must admit this recovery edit"
    state = RunState.new(
        current_user_message=request.current_user_message, recent_thread_history=[]
    )
    interpreted = await interpret_stage_async(
        state=state,
        user=request.user,
        latest_task_snapshot=request.latest_task_snapshot,
        selected_thread_metadata=request.selected_thread_metadata,
        structured_interpreter=lambda _: response,
    )
    assert interpreted.outcome == "ready_for_confirmation"
    state = state.model_copy(update=interpreted.stage_patch)
    state.candidate_strategy_draft = interpreted.decision.candidate_strategy_draft
    confirmed = confirm_stage(state=state, contract=build_default_capability_contract())
    assert confirmed.outcome == "await_approval"
    return confirmed.stage_patch["confirmation_payload"]


def test_reordered_equal_weight_assets_are_explicitly_unchanged(
    recovery_request, monkeypatch
):
    prior = recovery_request.latest_task_snapshot.pending_strategy_summary
    prior.asset_universe = [*prior.asset_universe, "AAPL"]
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [
            {
                "op": "replace",
                "target": "asset",
                "symbols": list(reversed(prior.asset_universe)),
            }
        ],
    }
    card = asyncio.run(_recover_and_confirm(recovery_request, plan, monkeypatch))
    assert set(card["strategy"]["asset_universe"]) == set(prior.asset_universe)
    assert card["edit_disclosure"]["unapplied"][0]["reason"] == "no_change_applied"
    main = interpreter._response_from_artifact_assumption_edit_plan(
        plan=planner.ArtifactAssumptionEditPlan(**plan),
        request=recovery_request,
        asset_symbol_resolver=lambda symbol: symbol,
    )
    assert (
        main.candidate_strategy_draft.extra_parameters["edit_disclosure"]
        == card["edit_disclosure"]
    )


@pytest.mark.parametrize("changed", [False, True])
def test_partial_indicator_projection_compares_the_requested_parameter(
    recovery_request, monkeypatch, changed
):
    prior = recovery_request.latest_task_snapshot.pending_strategy_summary
    prior.strategy_type = "indicator_threshold"
    parameters = {
        "indicator": "rsi",
        "indicator_period": 14,
        "entry_threshold": 30,
        "exit_threshold": 70,
    }
    prior.extra_parameters["indicator_parameters"] = parameters
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [
            {
                "op": "set",
                "target": "indicator_entry_threshold",
                "number": parameters["entry_threshold"] + int(changed),
            }
        ],
    }
    card = asyncio.run(_recover_and_confirm(recovery_request, plan, monkeypatch))
    if changed:
        assert not card.get("edit_disclosure")
    else:
        assert card["edit_disclosure"]["unapplied"][0]["reason"] == "no_change_applied"


@pytest.mark.parametrize(
    "case",
    [
        "typed-refusal",
        "note-refusal",
        "flat-cost",
        "mixed-carriers-cost",
        "flat-recurring",
        "copied-capital",
    ],
)
def test_recovery_reissue_discloses_every_unapplied_change(
    case: str,
    recovery_request: InterpretationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = recovery_request.latest_task_snapshot.pending_strategy_summary
    capital = prior.capital_amount * 0.9
    data: dict[str, Any] = {"outcome": "ready_to_confirm"}
    expected: dict[str, Any] = {"unapplied": []}
    if case in {"typed-refusal", "note-refusal"}:
        data["operations"] = [{"op": "set", "target": "capital", "number": capital}]
        if case == "typed-refusal":
            data["operations"].append(
                {"op": "remove", "target": "asset", "symbols": ["TSLA"]}
            )
            expected["unapplied"] = [
                {"op": "remove", "target": "asset", "reason": "unsupported_operation"}
            ]
        else:
            data["assistant_response"] = "Short selling cannot be applied."
            expected["note"] = data["assistant_response"]
    elif case in {"flat-cost", "mixed-carriers-cost", "flat-recurring"}:
        if case == "mixed-carriers-cost":
            data["operations"] = [{"op": "set", "target": "capital", "number": capital}]
        else:
            data["initial_capital"] = capital
        if case in {"flat-cost", "mixed-carriers-cost"}:
            data["fee_rate"] = 0.001
            target = "fees"
        else:
            prior.strategy_type = "dca_accumulation"
            prior.cadence = "monthly"
            prior.capital_amount /= 20
            prior.extra_parameters["recurring_contribution"] = prior.capital_amount
            data["recurring_contribution_amount"] = prior.capital_amount * 2
            target = "recurring_contribution"
        expected["unapplied"] = [
            {"op": "set", "target": target, "reason": "not_materialized"}
        ]
    else:
        data["initial_capital"] = prior.capital_amount
        capital = prior.capital_amount
        expected["unapplied"] = [
            {"op": "edit", "target": "requested_change", "reason": "no_change_applied"}
        ]

    card = asyncio.run(_recover_and_confirm(recovery_request, data, monkeypatch))

    assert card.get("edit_disclosure") == expected
    strategy = card["strategy"]
    assert strategy["asset_universe"] == prior.asset_universe
    if case == "flat-recurring":
        assert strategy["extra_parameters"]["initial_capital"] == capital
        assert strategy["capital_amount"] == prior.capital_amount
        assert (
            strategy["extra_parameters"]["recurring_contribution"] == prior.capital_amount
        )
    else:
        assert strategy["capital_amount"] == capital
    if case in {"flat-cost", "mixed-carriers-cost"}:
        assert "fee_rate" not in strategy["extra_parameters"]


@pytest.mark.parametrize("typed", [False, True])
def test_recovery_fully_applied_edit_needs_no_disclosure(
    typed: bool,
    recovery_request: InterpretationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capital = (
        recovery_request.latest_task_snapshot.pending_strategy_summary.capital_amount
    )
    changed = capital * 0.9
    fields = (
        {"operations": [{"op": "set", "target": "capital", "number": changed}]}
        if typed
        else {"initial_capital": changed}
    )
    card = asyncio.run(
        _recover_and_confirm(
            recovery_request, {"outcome": "ready_to_confirm", **fields}, monkeypatch
        )
    )
    assert card["strategy"]["capital_amount"] == changed
    assert "edit_disclosure" not in card


@pytest.mark.parametrize("typed,value", [(True, "7D"), (False, "7D"), (False, " ")])
@pytest.mark.parametrize("with_capital_change", [False, True])
def test_recovery_discloses_timeframe_discarded_by_runtime(
    typed: bool,
    value: str,
    with_capital_change: bool,
    recovery_request: InterpretationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = recovery_request.latest_task_snapshot.pending_strategy_summary
    capital = prior.capital_amount * (0.9 if with_capital_change else 1)
    fields: dict[str, Any] = {"outcome": "ready_to_confirm"}
    if typed:
        fields["operations"] = [{"op": "set", "target": "timeframe", "value": value}]
        if with_capital_change:
            fields["operations"].append(
                {"op": "set", "target": "capital", "number": capital}
            )
    else:
        fields["timeframe"] = value
        if with_capital_change:
            fields["initial_capital"] = capital

    card = asyncio.run(_recover_and_confirm(recovery_request, fields, monkeypatch))
    assert card["strategy"]["capital_amount"] == capital
    assert card["launch_payload"]["timeframe"] == prior.timeframe
    assert card.get("edit_disclosure") == {
        "unapplied": [{"op": "set", "target": "timeframe", "reason": "not_materialized"}]
    }


def test_recovery_copied_timeframe_alias_is_not_reported_as_a_change(
    recovery_request: InterpretationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = asyncio.run(
        _recover_and_confirm(
            recovery_request,
            {"outcome": "ready_to_confirm", "timeframe": "1d"},
            monkeypatch,
        )
    )
    assert card["launch_payload"]["timeframe"] == "1D"
    assert card.get("edit_disclosure") == {
        "unapplied": [
            {"op": "edit", "target": "requested_change", "reason": "no_change_applied"}
        ]
    }


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"outcome": "unsupported", "assistant_response": "This cannot be applied."},
        {"outcome": "needs_clarification", "assistant_response": "Which assumption?"},
        {"operations": [{"op": "set", "target": "fees", "number": 0.001}]},
        {
            "operations": [
                {"op": "set", "target": "capital", "number": 9000},
                {"op": "clear", "target": "benchmark"},
            ]
        },
    ],
    ids=["empty-plan", "unsupported", "clarification", "ungrounded-cost", "partial"],
)
def test_recovery_declines_remain_declines(
    fields: dict[str, Any],
    recovery_request: InterpretationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = asyncio.run(
        _recover(recovery_request, {"outcome": "ready_to_confirm", **fields}, monkeypatch)
    )
    assert response is None
