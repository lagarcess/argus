"""Every execution field protects builder ownership without positive default
provenance. There is no tolerated field-name set. The cases span the shared
evidence tuple, including both draft models, so adding a field extends the
invariant rather than creating a new bypass.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import knowledge_answer as ka
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.interpreter.draft_shape import (
    _EXECUTION_EVIDENCE_FIELDS,
    strategy_has_execution_evidence,
)
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState

# The tuple spans two unrelated draft models, and the entry point below only
# accepts one of them. Partitioning here rather than skipping keeps every
# field accounted for: a field on neither model fails the partition test.
SUMMARY_FIELDS = tuple(
    field for field in _EXECUTION_EVIDENCE_FIELDS if field in StrategySummary.model_fields
)
DRAFT_ONLY_FIELDS = tuple(
    field
    for field in _EXECUTION_EVIDENCE_FIELDS
    if field not in StrategySummary.model_fields
)

# One populated example per field, so "carries evidence" means the same thing
# for a string, a number, a mapping and a list. Keys are asserted to cover the
# tuple exactly, which is what makes every test below total.
POPULATED_EXAMPLES: dict[str, Any] = {
    "strategy_type": "buy_and_hold",
    "requested_strategy_template": "buy_and_hold",
    "entry_logic": "buy when it closes above the 200 day average",
    "exit_logic": "sell when it closes below the 200 day average",
    "entry_rule": {"kind": "price_above", "value": 200},
    "exit_rule": {"kind": "price_below", "value": 100},
    "rule_spec": {"entry": {"kind": "price_above"}},
    "cadence": "monthly",
    "sizing_mode": "fixed_amount",
    "capital_amount": 1000.0,
    "total_capital": 5000.0,
    "initial_capital": 1000.0,
    "position_size": 250.0,
    "recurring_contribution": 100.0,
    "risk_rules": [{"kind": "stop_loss", "value": 0.1}],
}


class _Draft:
    """Duck-typed twin of the drafts the interpreter emits.

    The evidence check reads these fields off two unrelated models by getattr,
    and three of them exist on only one of the two. A stub carrying the whole
    tuple is what lets one invariant cover every field the same way.
    """

    def __init__(self, **populated: Any) -> None:
        for name in _EXECUTION_EVIDENCE_FIELDS:
            setattr(self, name, None)
        for name, value in populated.items():
            setattr(self, name, value)


def _state(message: str) -> RunState:
    state = RunState.new(current_user_message=message, recent_thread_history=[])
    return state


def test_every_execution_evidence_field_is_classified() -> None:
    """The guard that makes the rest total: a new field must be classified
    before it can ship, because an unclassified field is one nobody decided
    the rail's behaviour for."""
    assert set(POPULATED_EXAMPLES) == set(_EXECUTION_EVIDENCE_FIELDS)


@pytest.mark.parametrize("field", _EXECUTION_EVIDENCE_FIELDS)
def test_a_populated_field_is_execution_evidence(field: str) -> None:
    """Whatever the rail decides to do with it, every field in the tuple has
    to register as evidence at all; a field that reads as empty when set is a
    field that silently stopped protecting the builder route."""
    assert strategy_has_execution_evidence(_Draft(**{field: POPULATED_EXAMPLES[field]}))


@pytest.mark.parametrize(
    "field",
    _EXECUTION_EVIDENCE_FIELDS,
)
def test_real_execution_intent_keeps_the_turn_out_of_the_rail(field: str) -> None:
    """One populated field the interpreter does not inject is a user who asked
    to run something. The rail must leave it to the builder."""
    assert strategy_has_execution_evidence(
        _Draft(**{field: POPULATED_EXAMPLES[field]}),
        include_defaults=False,
    )


@pytest.mark.parametrize("field", _EXECUTION_EVIDENCE_FIELDS)
def test_only_positive_default_provenance_may_discard_execution_evidence(
    field: str,
) -> None:
    assert not strategy_has_execution_evidence(
        _Draft(**{field: POPULATED_EXAMPLES[field]}, field_provenance={field: "default"}),
        include_defaults=False,
    )


def test_an_empty_draft_reads_as_a_question() -> None:
    assert not strategy_has_execution_evidence(_Draft(), include_defaults=False)


def test_every_field_belongs_to_a_draft_model() -> None:
    """No field may be evidence in name only. The ones the interpretation
    cannot carry must at least exist on the draft the interpreter fills, or
    the tuple is guarding a field nothing can ever populate."""
    assert set(SUMMARY_FIELDS) | set(DRAFT_ONLY_FIELDS) == set(_EXECUTION_EVIDENCE_FIELDS)
    for field in DRAFT_ONLY_FIELDS:
        assert field in LLMStrategyDraft.model_fields, field


@pytest.mark.parametrize(
    "field",
    SUMMARY_FIELDS,
)
def test_the_rail_declines_a_real_build_request_end_to_end(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same invariant through the real entry point rather than its helper:
    a clarification carrying genuine execution intent falls through to the
    builder untouched, for every field, with no classifier call spent."""

    async def explode(**_kwargs: Any) -> None:
        raise AssertionError(f"no classifier may run for a build request ({field})")

    monkeypatch.setattr(ra, "research_answer_stage_result", explode)
    monkeypatch.setattr(ka, "_classify_question", explode)
    result = asyncio.run(
        ka.knowledge_answer_stage_result(
            interpretation=ka.StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                user_goal_summary="question",
                semantic_turn_act="new_idea",
                requires_clarification=True,
                missing_required_fields=["date_range"],
                candidate_strategy_draft=StrategySummary(
                    **{field: POPULATED_EXAMPLES[field]}
                ),
            ),
            state=_state("Compare PLTR to LMT"),
            user=UserState(user_id="invariant", language_preference="en"),
            snapshot=None,
            selected_thread_metadata={},
        )
    )
    assert result is None
