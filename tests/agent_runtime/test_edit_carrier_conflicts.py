"""Both edit adapters account for conflicting representations of one field."""

import asyncio

import pytest
from argus.agent_runtime.artifact_edit_outcomes import artifact_edit_disclosure
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _response_from_artifact_assumption_edit_plan,
)

from tests.agent_runtime._pending_edit_outcome_support import card_for_edit_plan
from tests.agent_runtime.test_compound_edit_contract import _request
from tests.agent_runtime.test_recovery_edit_outcomes import _recover_and_confirm


@pytest.mark.parametrize("route", ["main", "recovery"])
@pytest.mark.parametrize(
    "base,operations,flat,mode,expected,conflict",
    [
        pytest.param(
            ["AAPL"],
            [("replace", ["MSFT"])],
            ["MSFT"],
            "append",
            ["MSFT"],
            True,
            id="replace-vs-append",
        ),
        pytest.param(
            ["AAPL"],
            [("replace", ["MSFT"])],
            ["MSFT"],
            "add",
            ["MSFT"],
            True,
            id="replace-vs-add-alias",
        ),
        pytest.param(
            ["AAPL", "MSFT"],
            [("remove", ["MSFT"])],
            ["AAPL"],
            "append",
            ["AAPL"],
            True,
            id="remove-vs-append",
        ),
        pytest.param(
            ["AAPL"],
            [("add", ["MSFT"])],
            ["MSFT"],
            "append",
            ["AAPL", "MSFT"],
            False,
            id="equivalent-add-append",
        ),
        pytest.param(
            ["AAPL"],
            [("add", ["MSFT"])],
            ["MSFT"],
            "add",
            ["AAPL", "MSFT"],
            False,
            id="equivalent-add-alias",
        ),
        pytest.param(
            ["AAPL"],
            [("replace", ["AAPL", "MSFT"])],
            ["msft", "MSFT"],
            "append",
            ["AAPL", "MSFT"],
            False,
            id="equivalent-replace-append",
        ),
        pytest.param(
            ["AAPL"],
            [("add", ["MSFT"])],
            ["MSFT", "AAPL"],
            "replace",
            ["AAPL", "MSFT"],
            False,
            id="equivalent-full-replacement",
        ),
        pytest.param(
            ["AAPL"],
            [("replace", ["MSFT"])],
            ["MSFT"],
            None,
            ["MSFT"],
            False,
            id="legacy-default-replacement",
        ),
        pytest.param(
            ["AAPL", "NVDA"],
            [("remove", ["AAPL"]), ("add", ["MSFT"])],
            ["NVDA", "MSFT"],
            "append",
            ["NVDA", "MSFT"],
            True,
            id="ordered-operations-vs-append",
        ),
    ],
)
def test_asset_carriers_compare_final_baskets(
    monkeypatch, route, base, operations, flat, mode, expected, conflict
):
    request = _request("Change the assets", requested_field="assumption")
    request.latest_task_snapshot.pending_strategy_summary.asset_universe = base
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [
            {"op": op, "target": "asset", "symbols": symbols}
            for op, symbols in operations
        ],
        "asset_universe": flat,
        "asset_universe_operation": mode,
    }
    if route == "main":
        outcome, card = asyncio.run(
            card_for_edit_plan(monkeypatch, plan, request=request)
        )
        assert outcome == "await_approval"
        actual = next(row["value"] for row in card["rows"] if row["key"] == "assets").split(
            ", "
        )
    else:
        card = asyncio.run(_recover_and_confirm(request, plan, monkeypatch))
        actual = card["strategy"]["asset_universe"]
    assert set(actual) == set(expected)
    if conflict:
        assert card["edit_disclosure"]["unapplied"] == [
            {"op": "set", "target": "asset", "reason": "conflicting_edit_carriers"}
        ]
    else:
        assert not card.get("edit_disclosure")


@pytest.mark.parametrize("route", ["main", "recovery"])
@pytest.mark.parametrize("same_value", [False, True])
def test_typed_capital_owns_application_and_conflicting_flat_value_is_disclosed(
    monkeypatch, route, same_value
):
    request = _request("Change the capital", requested_field="assumption")
    prior = request.latest_task_snapshot.pending_strategy_summary.capital_amount
    typed = prior * 0.9
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [{"op": "set", "target": "capital", "number": typed}],
        "initial_capital": typed if same_value else prior * 0.8,
    }
    if route == "main":
        outcome, card = asyncio.run(card_for_edit_plan(monkeypatch, plan))
        assert outcome == "await_approval"
        capital = card["display_facts"]["capital"]
    else:
        card = asyncio.run(_recover_and_confirm(request, plan, monkeypatch))
        capital = card["strategy"]["capital_amount"]
    assert capital == typed
    if same_value:
        assert not card.get("edit_disclosure")
    else:
        assert card["edit_disclosure"]["unapplied"] == [
            {"op": "set", "target": "capital", "reason": "conflicting_edit_carriers"}
        ]


@pytest.mark.parametrize("flat_capital", [None, 9000])
def test_refused_target_alias_has_one_authoritative_receipt(flat_capital):
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[{"op": "clear", "target": "starting_capital"}],
            initial_capital=flat_capital,
        ),
        request=_request("Clear starting capital"),
    )
    assert response.candidate_strategy_draft.extra_parameters["edit_disclosure"][
        "unapplied"
    ] == [{"op": "clear", "target": "capital", "reason": "unsupported_operation"}]


@pytest.mark.parametrize("route", ["main", "recovery"])
def test_valid_timeframe_conflict_keeps_typed_winner_in_both_routes(monkeypatch, route):
    allowed = (
        build_default_capability_contract()
        .get_optional_parameter("timeframe")
        .allowed_range.allowed_values
    )
    request = _request("Change the timeframe", requested_field="assumption")
    current = request.latest_task_snapshot.pending_strategy_summary.timeframe
    typed = next(value for value in allowed if value != current)
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [{"op": "set", "target": "timeframe", "value": typed}],
        "timeframe": current,
    }
    if route == "main":
        outcome, card = asyncio.run(card_for_edit_plan(monkeypatch, plan))
        assert outcome == "await_approval"
        # Runtime card facts retain the supported timeframe selected by ops.
        assert card["display_facts"]["timeframe"] == typed
    else:
        card = asyncio.run(_recover_and_confirm(request, plan, monkeypatch))
        assert card["strategy"]["timeframe"] == typed
    assert card["edit_disclosure"]["unapplied"] == [
        {"op": "set", "target": "timeframe", "reason": "conflicting_edit_carriers"}
    ]


@pytest.mark.parametrize("route", ["main", "recovery"])
@pytest.mark.parametrize("asset_operation", [None, "replace"])
def test_explicit_empty_asset_carrier_is_accounted_for_beside_success(
    monkeypatch, route, asset_operation
):
    request = _request("Change capital and assets", requested_field="assumption")
    capital = request.latest_task_snapshot.pending_strategy_summary.capital_amount * 0.9
    plan = {
        "outcome": "ready_to_confirm",
        "operations": [{"op": "set", "target": "capital", "number": capital}],
        "asset_universe": [],
        "asset_universe_operation": asset_operation,
    }
    if route == "main":
        outcome, card = asyncio.run(card_for_edit_plan(monkeypatch, plan))
        assert outcome == "await_approval"
    else:
        card = asyncio.run(_recover_and_confirm(request, plan, monkeypatch))
    if asset_operation is not None:
        assert card["edit_disclosure"]["unapplied"] == [
            {"op": "set", "target": "asset", "reason": "not_materialized"}
        ]
    else:
        assert not card.get("edit_disclosure")


def test_explicit_empty_asset_carrier_cannot_hide_behind_a_typed_asset_target():
    assets = _request(
        "Change assets"
    ).latest_task_snapshot.pending_strategy_summary.asset_universe
    plan = ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        operations=[{"op": "replace", "target": "asset", "symbols": assets}],
        asset_universe=[],
        asset_universe_operation="replace",
    )
    disclosure = artifact_edit_disclosure(
        plan,
        current_asset_universe=assets,
        materialized_targets={"asset"},
        has_changes=False,
        resolved=ResolvedArtifactEdit(asset_universe=assets),
    )
    assert disclosure["unapplied"] == [
        {"op": "set", "target": "asset", "reason": "conflicting_edit_carriers"}
    ]
