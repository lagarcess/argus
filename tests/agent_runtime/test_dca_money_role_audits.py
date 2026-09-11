"""What the user said an amount is outranks what an audit guesses it is.

Recorded 2026-09-10: "$1,000 is starting capital, not a total contribution cap"
was typed as the seed by the primary read, and the contract audit then reported
the same $1,000 as a budget. The runtime wrote it under a ceiling key, the
semantic reader refused the plan as capped, and the user was asked about a cap
they had ruled out.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.interpreter.audits import (
    DcaContractAudit,
    StatedRunFieldFidelityAudit,
)
from argus.agent_runtime.interpreter.dca_audits import (
    _response_from_dca_contract_audit,
)
from argus.agent_runtime.interpreter.run_field_audits import (
    _response_from_stated_run_field_fidelity_audit,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.semantic_integrity import (
    UNSUPPORTED_DCA_CONTRIBUTION_CEILING,
    conserve_semantic_constraints,
)
from argus.agent_runtime.state.models import StrategySummary


def _dca_response(
    *, initial_capital: float | None, seed_provenance: str | None
) -> LLMInterpretationResponse:
    provenance = {
        "asset_universe": "explicit_user",
        "date_range": "explicit_user",
        "recurring_contribution": "explicit_user",
        "cadence": "explicit_user",
    }
    if seed_provenance is not None:
        provenance["initial_capital"] = seed_provenance
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Monthly DCA with a stated seed.",
        semantic_turn_act="new_idea",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            asset_universe=["AAPL"],
            asset_class="equity",
            cadence="monthly",
            date_range={"start": "2024-01-02", "end": "2024-12-31"},
            capital_amount=100.0,
            recurring_contribution=100.0,
            initial_capital=initial_capital,
            comparison_baseline="SPY",
            field_provenance=provenance,
        ),
    )


def _contract_audit(**budget: Any) -> DcaContractAudit:
    return DcaContractAudit(
        is_recurring_buy_request=True,
        recurring_contribution_amount=100.0,
        cadence="monthly",
        confidence=0.95,
        **budget,
    )


@pytest.mark.parametrize(
    "budget_source", ["starting_capital", "cap", "total_budget", None]
)
def test_budget_audit_cannot_re_role_money_the_user_typed_as_the_seed(
    budget_source: str | None,
) -> None:
    response = _dca_response(initial_capital=1000.0, seed_provenance="explicit_user")

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(
            total_budget_amount=1000.0, total_budget_source=budget_source
        ),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.initial_capital == 1000.0
    assert draft.total_capital is None
    assert "total_budget" not in draft.extra_parameters
    assert draft.field_provenance["initial_capital"] == "explicit_user"
    assert draft.recurring_contribution == 100.0
    assert "dca_budget_audit_outranked_by_typed_seed" in repaired.reason_codes


@pytest.mark.parametrize(
    "budget_source",
    ["starting_capital", "initial_capital", "starting_principal", "lump_sum"],
)
def test_budget_audit_with_a_seed_role_types_the_seed_not_a_ceiling(
    budget_source: str,
) -> None:
    response = _dca_response(initial_capital=None, seed_provenance=None)

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(
            total_budget_amount=1000.0, total_budget_source=budget_source
        ),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.initial_capital == 1000.0
    assert draft.field_provenance["initial_capital"] == budget_source
    assert draft.total_capital is None
    assert "total_budget" not in draft.extra_parameters
    assert "dca_budget_audit_typed_as_seed" in repaired.reason_codes


def test_a_distinct_cap_beside_a_typed_seed_is_still_a_ceiling() -> None:
    response = _dca_response(initial_capital=1000.0, seed_provenance="explicit_user")

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(total_budget_amount=5000.0, total_budget_source="cap"),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.initial_capital == 1000.0
    assert draft.total_capital == 5000.0
    assert draft.extra_parameters["total_budget"] == 5000.0
    assert draft.field_provenance["total_capital"] == "cap"


def test_fidelity_audit_corroborates_a_seed_the_primary_typed_without_provenance() -> (
    None
):
    # Live 2026-09-10, two of three runs: the primary read typed
    # initial_capital 1000 with no provenance map at all, and the projection
    # dropped it, so the card showed $0 starting capital.
    response = _dca_response(initial_capital=1000.0, seed_provenance=None)
    audit = StatedRunFieldFidelityAudit(
        capital_amount=1000.0,
        recurring_contribution_amount=100.0,
        cadence="monthly",
        comparison_baseline="SPY",
        confidence=0.8,
    )

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100.0
    assert draft.initial_capital == 1000.0
    assert draft.field_provenance["initial_capital"] == "starting_capital"
    assert "stated_run_field_seed_corroborated" in repaired.reason_codes
    projected = _strategy_from_llm(draft, "Start with $1,000 then $100 a month.")
    assert projected.extra_parameters["initial_capital"] == 1000.0
    assert projected.capital_amount == 100.0


def test_fidelity_audit_does_not_invent_a_seed_the_primary_never_typed() -> None:
    response = _dca_response(initial_capital=None, seed_provenance=None)
    audit = StatedRunFieldFidelityAudit(
        capital_amount=5000.0,
        recurring_contribution_amount=100.0,
        cadence="monthly",
        confidence=0.8,
    )

    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response, audit=audit
    )

    draft = (repaired or response).candidate_strategy_draft
    assert draft.initial_capital is None
    assert draft.capital_amount == 100.0


def _pending_dca(extra: dict[str, Any]) -> StrategySummary:
    return StrategySummary(
        strategy_type="dca_accumulation",
        asset_universe=["AAPL"],
        asset_class="equity",
        cadence="monthly",
        date_range={"start": "2024-01-02", "end": "2024-12-31"},
        capital_amount=100.0,
        comparison_baseline="SPY",
        extra_parameters=extra,
    )


def test_semantic_reader_treats_a_seed_role_under_a_ceiling_key_as_the_seed() -> None:
    strategy = _pending_dca(
        {
            "recurring_contribution": 100.0,
            "initial_capital": 1000.0,
            "total_budget": 1000.0,
            "field_provenance": {
                "recurring_contribution": "explicit_user",
                "initial_capital": "explicit_user",
                "total_capital": "starting_capital",
            },
        }
    )

    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})

    assert [c.category for c in report.unsupported_constraints] == []
    assert report.optional_parameter_values["initial_capital"] == 1000.0
    assert report.strategy.capital_amount == 100.0
    assert "semantic_dca_seed_role_read_over_ceiling_key" in report.reason_codes


def test_semantic_reader_keeps_a_ceiling_whose_role_is_a_cap() -> None:
    strategy = _pending_dca(
        {
            "recurring_contribution": 100.0,
            "total_budget": 5000.0,
            "field_provenance": {
                "recurring_contribution": "explicit_user",
                "total_capital": "cap",
            },
        }
    )

    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})

    assert [c.category for c in report.unsupported_constraints] == [
        UNSUPPORTED_DCA_CONTRIBUTION_CEILING
    ]
