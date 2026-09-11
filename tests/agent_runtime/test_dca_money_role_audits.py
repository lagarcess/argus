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


# --- Codex round 1 on PR #591 -------------------------------------------------


def test_budget_audit_never_replaces_an_occupied_seed_with_a_different_amount() -> None:
    # A $1,000 seed the user typed plus a $5,000 cap the audit mislabels as
    # starting capital: the seed stays, the distinct amount becomes the
    # ceiling it can only be, and the plan is refused by name downstream.
    response = _dca_response(initial_capital=1000.0, seed_provenance="explicit_user")

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(
            total_budget_amount=5000.0, total_budget_source="starting_capital"
        ),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.initial_capital == 1000.0
    assert draft.field_provenance["initial_capital"] == "explicit_user"
    assert draft.total_capital == 5000.0
    assert draft.extra_parameters["total_budget"] == 5000.0
    assert draft.field_provenance["total_capital"] == "total_budget"
    assert "dca_budget_audit_seed_role_occupied_read_as_ceiling" in repaired.reason_codes


def test_budget_audit_never_replaces_a_seed_typed_without_provenance() -> None:
    response = _dca_response(initial_capital=1000.0, seed_provenance=None)

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(
            total_budget_amount=5000.0, total_budget_source="initial_capital"
        ),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.initial_capital == 1000.0
    assert draft.total_capital == 5000.0


def test_semantic_reader_keeps_a_distinct_ceiling_whose_provenance_says_seed() -> None:
    strategy = _pending_dca(
        {
            "recurring_contribution": 100.0,
            "initial_capital": 1000.0,
            "total_budget": 5000.0,
            "field_provenance": {
                "recurring_contribution": "explicit_user",
                "initial_capital": "explicit_user",
                "total_capital": "starting_capital",
            },
        }
    )

    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})

    assert [c.category for c in report.unsupported_constraints] == [
        UNSUPPORTED_DCA_CONTRIBUTION_CEILING
    ]
    assert report.optional_parameter_values["initial_capital"] == 1000.0
    assert report.evidence.contribution_ceiling == 5000.0
    assert "semantic_dca_seed_role_read_over_ceiling_key" not in report.reason_codes


def test_semantic_reader_reads_a_lone_seed_role_under_a_ceiling_key_as_the_seed() -> None:
    strategy = _pending_dca(
        {
            "recurring_contribution": 100.0,
            "total_budget": 1000.0,
            "field_provenance": {
                "recurring_contribution": "explicit_user",
                "total_capital": "starting_principal",
            },
        }
    )

    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})

    assert report.unsupported_constraints == []
    assert report.optional_parameter_values["initial_capital"] == 1000.0
    assert "semantic_dca_seed_role_read_over_ceiling_key" in report.reason_codes


def test_seed_and_ceiling_role_names_have_one_owner() -> None:
    from argus.agent_runtime import semantic_integrity
    from argus.agent_runtime.interpreter import dca_audits
    from argus.agent_runtime.interpreter import shared as interpreter_shared
    from argus.domain.dca_capital import DCA_CEILING_ROLES, DCA_SEED_ROLES

    assert set(DCA_SEED_ROLES).isdisjoint(DCA_CEILING_ROLES)
    assert semantic_integrity._DCA_SEED_KEYS == DCA_SEED_ROLES
    assert semantic_integrity._DCA_CEILING_KEYS == DCA_CEILING_ROLES
    assert dca_audits._DCA_SEED_ROLE_SOURCES == frozenset(DCA_SEED_ROLES)
    assert set(DCA_SEED_ROLES) <= interpreter_shared._TOTAL_CAPITAL_SOURCES
    assert set(DCA_CEILING_ROLES) <= interpreter_shared._TOTAL_CAPITAL_SOURCES


@pytest.mark.parametrize(
    "role",
    sorted(
        __import__("argus.domain.dca_capital", fromlist=["DCA_SEED_ROLES"]).DCA_SEED_ROLES
    ),
)
def test_every_seed_role_is_written_and_read_as_the_seed(role: str) -> None:
    # The audit writer and the semantic reader agree on every role name: a
    # budget the audit types with a seed role executes as starting capital.
    from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm

    response = _dca_response(initial_capital=None, seed_provenance=None)
    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(total_budget_amount=1000.0, total_budget_source=role),
    )
    assert repaired is not None
    projected = _strategy_from_llm(
        repaired.candidate_strategy_draft, "Start with $1,000 then $100 a month."
    )
    report = conserve_semantic_constraints(
        strategy=projected, selected_thread_metadata={}
    )
    assert report.unsupported_constraints == []
    assert report.optional_parameter_values["initial_capital"] == 1000.0


# --- Codex round 3 on PR #591 -------------------------------------------------


def test_a_cap_slotted_as_the_seed_with_a_ceiling_role_is_not_a_typed_seed() -> None:
    # The primary read put the cap under initial_capital but kept its role as
    # total_budget. That is a ceiling in the wrong slot, not a seed the user
    # typed, so the audit's matching cap is applied, not outranked.
    response = _dca_response(initial_capital=5000.0, seed_provenance="total_budget")

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(total_budget_amount=5000.0, total_budget_source="cap"),
    )

    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.total_capital == 5000.0
    assert draft.extra_parameters["total_budget"] == 5000.0
    assert "dca_budget_audit_outranked_by_typed_seed" not in repaired.reason_codes
    projected = _strategy_from_llm(draft, "$200 a month, no more than $5,000 total.")
    report = conserve_semantic_constraints(
        strategy=projected, selected_thread_metadata={}
    )
    assert [c.category for c in report.unsupported_constraints] == [
        UNSUPPORTED_DCA_CONTRIBUTION_CEILING
    ]
    assert report.optional_parameter_values.get("initial_capital") in (None, 5000.0)
    assert report.evidence.contribution_ceiling == 5000.0


def test_semantic_reader_treats_a_seed_key_with_a_ceiling_role_as_the_ceiling() -> None:
    # The mirror of the seed-role-under-ceiling-key rule: the role wins.
    strategy = _pending_dca(
        {
            "recurring_contribution": 200.0,
            "initial_capital": 5000.0,
            "field_provenance": {
                "recurring_contribution": "explicit_user",
                "initial_capital": "total_budget",
            },
        }
    )

    report = conserve_semantic_constraints(strategy=strategy, selected_thread_metadata={})

    assert [c.category for c in report.unsupported_constraints] == [
        UNSUPPORTED_DCA_CONTRIBUTION_CEILING
    ]
    assert report.evidence.contribution_ceiling == 5000.0
    assert "semantic_dca_ceiling_role_read_over_seed_key" in report.reason_codes


@pytest.mark.parametrize(
    "seed_source", ["user", "explicit_user", "prior", "starting_capital"]
)
def test_a_seed_typed_under_a_seed_or_user_role_still_outranks_the_audit(
    seed_source: str,
) -> None:
    response = _dca_response(initial_capital=1000.0, seed_provenance=seed_source)

    repaired = _response_from_dca_contract_audit(
        response=response,
        audit=_contract_audit(total_budget_amount=1000.0, total_budget_source="cap"),
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.total_capital is None
    assert "dca_budget_audit_outranked_by_typed_seed" in repaired.reason_codes
