"""An independent money audit settles facts by role and value, not slot name."""

from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.interpreter.audits import StatedRunFieldFidelityAudit
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_from_stated_run_field_fidelity_audit,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMAmbiguousField,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.domain.market_data.assets import ResolvedAsset
from argus.agent_runtime.semantic_integrity import (
    DECLARED_TOOL_INPUT_CONFLICT,
    conserve_semantic_constraints,
)

ROLE_FIELDS = {
    field.json_schema_extra["x-argus-capital-role"]: name
    for name, field in BacktestStrategyInput.model_fields.items()
    if isinstance(field.json_schema_extra, dict)
    and "x-argus-capital-role" in field.json_schema_extra
}
AUDIT_FIELDS = {
    "starting_capital": "capital_amount",
    "recurring_contribution": "recurring_contribution_amount",
}


def test_retained_role_correction_refreshes_missing_fields_before_shape_check(monkeypatch):
    replies = json.loads(
        (
            Path(__file__).parent
            / "fixtures/financial_role_missing_replies_542fcfb2.json"
        ).read_text()
    )["replies"]
    primary = LLMInterpretationResponse.model_validate(replies["LLMInterpretationResponse"])
    request = InterpretationRequest(
        current_user_message=primary.candidate_strategy_draft.raw_user_phrasing,
        user=UserState(user_id="retained-role-readiness"),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "resolve_asset",
        lambda symbol, **kwargs: ResolvedAsset(symbol, "equity", symbol, symbol),
    )
    focused = llm_interpreter._response_from_focused_strategy_extraction(
        extraction=FocusedStrategyExtraction.model_validate(replies["FocusedStrategyExtraction"]),
        request=request,
        base_response=primary,
    )
    assert focused.missing_required_fields == []
    assert focused.candidate_strategy_draft.recurring_contribution is None
    audit = StatedRunFieldFidelityAudit.model_validate(replies["StatedRunFieldFidelityAudit"])

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=focused, audit=audit, current_message=request.current_user_message
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.capital_amount == audit.capital_amount
    assert repaired.candidate_strategy_draft.total_capital == primary.candidate_strategy_draft.total_capital
    assert repaired.candidate_strategy_draft.recurring_contribution is None
    assert repaired.missing_required_fields == ["capital_amount"]
    assert repaired.requires_clarification
    assert repaired.ambiguous_fields == focused.ambiguous_fields
    assert llm_interpreter._structured_interpretation_has_required_shape(repaired, request=request)


def unresolved_response(role, value, *, strategy_type="dca_accumulation"):
    """Authored controls, separate from the retained full-turn provider bodies."""
    return LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        semantic_turn_act="new_idea",
        user_goal_summary="A controlled financial-role projection.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type=strategy_type,
            capital_amount=value,
            field_provenance={"capital_amount": role},
        ),
        requires_clarification=True,
        ambiguous_fields=[
            LLMAmbiguousField(
                field_name=ROLE_FIELDS[role],
                raw_value=str(value),
                reason_code="financial_role_evidence_unresolved",
            )
        ],
    )


@pytest.mark.parametrize("role", AUDIT_FIELDS)
@pytest.mark.parametrize("value", [0, 250.5])
def test_independent_same_role_audit_settles_alias_without_repopulating_it(role, value):
    response = unresolved_response(role, value)
    before = response.model_dump(mode="json")

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response,
        audit=StatedRunFieldFidelityAudit(**{AUDIT_FIELDS[role]: value}),
    )

    assert repaired is not None
    assert repaired.ambiguous_fields == []
    assert not repaired.requires_clarification
    assert repaired.candidate_strategy_draft.capital_amount == value
    assert repaired.candidate_strategy_draft.field_provenance["capital_amount"] == role
    assert getattr(repaired.candidate_strategy_draft, ROLE_FIELDS[role]) is None
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes
    assert response.model_dump(mode="json") == before


@pytest.mark.parametrize("value", [0, 250.5])
@pytest.mark.parametrize("prior_role", ["explicit_user", "recurring_contribution"])
def test_equal_number_audit_still_corrects_its_verified_role(value, prior_role):
    response = unresolved_response("starting_capital", value)
    response.ambiguous_fields = []
    response.requires_clarification = False
    response.candidate_strategy_draft.field_provenance["capital_amount"] = prior_role

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=StatedRunFieldFidelityAudit(capital_amount=value)
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == value
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    report = conserve_semantic_constraints(
        strategy=draft.to_runtime_strategy(), selected_thread_metadata={}
    )
    assert report.evidence.recurring_contribution is None
    assert report.evidence.total_capital == value


@pytest.mark.parametrize("role", AUDIT_FIELDS)
@pytest.mark.parametrize("value", [0, 250.5])
@pytest.mark.parametrize(
    "unsettled", ["no_audit", "different_value", "other_reason", "currency_text"]
)
def test_unverified_or_conflicting_money_ambiguity_stays_blocking(role, value, unsettled):
    response = unresolved_response(role, value)
    audit = StatedRunFieldFidelityAudit()
    if unsettled != "no_audit":
        setattr(
            audit,
            AUDIT_FIELDS[role],
            value + 1 if unsettled == "different_value" else value,
        )
    if unsettled == "other_reason":
        response.ambiguous_fields[0].reason_code = DECLARED_TOOL_INPUT_CONFLICT
    if unsettled == "currency_text":
        response.ambiguous_fields[0].raw_value = f"${value}"

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )
    result = repaired if repaired is not None else response

    assert result.ambiguous_fields == response.ambiguous_fields
    assert result.requires_clarification
    assert getattr(result.candidate_strategy_draft, ROLE_FIELDS[role]) is None


@pytest.mark.parametrize(
    ("audit_role", "pending_role"),
    [pair for pair in permutations(ROLE_FIELDS, 2) if pair[0] in AUDIT_FIELDS],
)
@pytest.mark.parametrize("value", [0, 250.5])
def test_equal_value_in_another_audited_role_cannot_settle_pending_role(
    audit_role, pending_role, value
):
    response = unresolved_response(pending_role, value)
    audit = StatedRunFieldFidelityAudit(**{AUDIT_FIELDS[audit_role]: value})

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )
    result = repaired if repaired is not None else response

    assert result.ambiguous_fields == response.ambiguous_fields
    assert result.requires_clarification
    assert getattr(result.candidate_strategy_draft, ROLE_FIELDS[pending_role]) is None


@pytest.mark.parametrize("role", AUDIT_FIELDS)
@pytest.mark.parametrize("value", [0, 250.5])
def test_audit_cannot_settle_alias_against_an_unequal_typed_fact(role, value):
    response = unresolved_response(role, value)
    setattr(response.candidate_strategy_draft, ROLE_FIELDS[role], value + 1)
    audit = StatedRunFieldFidelityAudit(**{AUDIT_FIELDS[role]: value})

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )
    result = repaired if repaired is not None else response

    assert result.ambiguous_fields == response.ambiguous_fields
    assert result.requires_clarification
    assert getattr(result.candidate_strategy_draft, ROLE_FIELDS[role]) == value + 1


@pytest.mark.parametrize("value", [0, 250.5])
@pytest.mark.parametrize("equal_roles", [True, False])
def test_independent_typed_seed_contribution_and_ceiling_survive_audit(
    value, equal_roles
):
    response = unresolved_response("starting_capital", value)
    values = {
        role: value if equal_roles else value + index
        for index, role in enumerate(ROLE_FIELDS)
    }
    draft = response.candidate_strategy_draft
    for role, field_name in ROLE_FIELDS.items():
        setattr(draft, field_name, values[role])
    response.ambiguous_fields[0].raw_value = str(values["starting_capital"])
    response.unsupported_constraints = [
        LLMUnsupportedConstraint(
            category="unsupported_dca_contribution_ceiling",
            raw_value="a known ceiling",
            explanation="The declared contribution ceiling remains unsupported.",
        )
    ]
    audit = StatedRunFieldFidelityAudit(
        capital_amount=values["starting_capital"],
        recurring_contribution_amount=values["recurring_contribution"],
    )

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )

    assert repaired is not None
    assert repaired.ambiguous_fields == []
    assert repaired.requires_clarification
    assert repaired.unsupported_constraints == response.unsupported_constraints
    assert {
        role: getattr(repaired.candidate_strategy_draft, field_name)
        for role, field_name in ROLE_FIELDS.items()
    } == values
    report = conserve_semantic_constraints(
        strategy=repaired.candidate_strategy_draft.to_runtime_strategy(),
        selected_thread_metadata={},
    )
    assert report.evidence.recurring_contribution == values["recurring_contribution"]
    assert report.evidence.total_capital == values["starting_capital"]
    assert report.evidence.contribution_ceiling == values["total_capital"]


def test_alias_settlement_preserves_unrelated_pending_need():
    response = unresolved_response("starting_capital", 0)
    response.missing_required_fields = ["date_range"]

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=StatedRunFieldFidelityAudit(capital_amount=0)
    )

    assert repaired is not None
    assert repaired.ambiguous_fields == []
    assert repaired.missing_required_fields == ["date_range"]
    assert repaired.requires_clarification
