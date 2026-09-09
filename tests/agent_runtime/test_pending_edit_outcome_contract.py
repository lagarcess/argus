"""Every admitted edit plan carries its outcome through the card boundary."""

from __future__ import annotations

import pytest
from argus.agent_runtime.artifact_edit_planner import ArtifactAssumptionEditPlan
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _response_from_artifact_assumption_edit_plan,
)

from tests.agent_runtime.test_compound_edit_contract import _request


@pytest.mark.parametrize("message", ["Remove the absent asset", "Quita TSLA"])
@pytest.mark.parametrize(
    "fields",
    [{}, {"initial_capital": 10000}, {"timeframe": "1D"}],
    ids=["empty", "copied-capital", "copied-timeframe"],
)
def test_no_applied_change_has_a_typed_outcome(message, fields):
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(outcome="ready_to_confirm", **fields),
        request=_request(message),
    )
    assert response.candidate_strategy_draft.extra_parameters["edit_disclosure"] == {
        "unapplied": [
            {"op": "edit", "target": "requested_change", "reason": "no_change_applied"}
        ]
    }


@pytest.mark.parametrize("outcome", ["needs_clarification", "unsupported"])
def test_non_ready_plan_keeps_disclosure_if_a_complete_card_can_reissue(outcome):
    note = "The requested change needs more detail."
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(outcome=outcome, assistant_response=note),
        request=_request("Change that assumption"),
    )
    disclosure = response.candidate_strategy_draft.extra_parameters["edit_disclosure"]
    assert disclosure["note"] == note
    assert disclosure["unapplied"][0]["reason"] == "no_change_applied"


@pytest.mark.parametrize(
    ("fields", "target"),
    [
        ({"fee_rate": 0.9}, "fees"),
        ({"slippage": 0.9}, "slippage"),
        ({"comparison_baseline": " "}, "benchmark"),
    ],
)
@pytest.mark.parametrize("with_successful_edit", [False, True])
def test_rejected_legacy_field_is_disclosed_alone_or_beside_a_success(
    fields,
    target,
    with_successful_edit,
):
    plan_fields = {
        **fields,
        **({"initial_capital": 9000} if with_successful_edit else {}),
    }
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(outcome="ready_to_confirm", **plan_fields),
        request=_request("Set the requested inputs"),
    )
    draft = response.candidate_strategy_draft
    disclosure = draft.extra_parameters["edit_disclosure"]
    assert any(entry["target"] == target for entry in disclosure["unapplied"])
    if with_successful_edit:
        assert draft.initial_capital == plan_fields["initial_capital"]


def test_changed_legacy_field_remains_a_success():
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(outcome="ready_to_confirm", initial_capital=9000),
        request=_request("Use 9000"),
    )
    assert response.candidate_strategy_draft.initial_capital == 9000
    assert "edit_disclosure" not in response.candidate_strategy_draft.extra_parameters


@pytest.mark.parametrize("timeframe", ["bad-frame", ""])
@pytest.mark.parametrize("typed", [False, True])
def test_timeframe_that_the_runtime_discards_is_not_counted_as_applied(timeframe, typed):
    from argus.agent_runtime.artifact_edit_planner import EditOperation

    fields = (
        {"operations": [EditOperation(op="set", target="timeframe", value=timeframe)]}
        if typed
        else {"timeframe": timeframe}
    )
    response = _response_from_artifact_assumption_edit_plan(
        plan=ArtifactAssumptionEditPlan(outcome="ready_to_confirm", **fields),
        request=_request("Use that timeframe"),
    )
    # An already-refused typed empty value remains in the existing clarification
    # path; all card-producing variants must carry the refused timeframe.
    disclosure = response.candidate_strategy_draft.extra_parameters["edit_disclosure"]
    assert any(entry["target"] == "timeframe" for entry in disclosure["unapplied"])
