"""A focused repair needs evidence before adding a new financial meaning."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.focused_extraction import (
    response_from_focused_strategy_extraction,
)
from argus.agent_runtime.llm_interpreter import canonical_strategy_interpretation
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.semantic_integrity import conserve_semantic_constraints
from argus.agent_runtime.stages.interpret import _stage_result_from_interpretation
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import RunState, UserState

ROLE_FIELDS = tuple(
    name
    for name, field in BacktestStrategyInput.model_fields.items()
    if isinstance(field.json_schema_extra, dict)
    and "x-argus-capital-role" in field.json_schema_extra
)
STATED_SEED = (
    "Start with $5,000 in SPY and add $200 every month, "
    "from January 2024 through December 2024."
)


@pytest.fixture
def request_context(faker: Any) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=STATED_SEED,
        user=UserState(user_id=faker.uuid4()),
    )


def _base(**values: Any) -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="calculate",
        task_relation="new_task",
        user_goal_summary=STATED_SEED,
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            cadence="monthly",
            **values,
        ),
    )


def _repair(
    request: InterpretationRequest,
    *,
    base: LLMInterpretationResponse | None = None,
    **values: Any,
) -> LLMInterpretationResponse:
    return response_from_focused_strategy_extraction(
        extraction=FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary=request.current_user_message,
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            **values,
        ),
        request=request,
        base_response=base,
        resolve_asset_candidate=lambda *_args, **_kwargs: None,
    )


@pytest.mark.asyncio
async def test_seed_only_repair_cannot_invent_an_equal_valued_ceiling(
    request_context: InterpretationRequest,
) -> None:
    # Minimal reconstruction of retained 19-candidate-r2: the focused receipt
    # added a ceiling, but the only $5,000 quote belonged to the existing seed.
    base = _base(
        capital_amount=200,
        initial_capital=5000,
        field_provenance={
            "initial_capital": "starting_capital",
            "capital_amount": "recurring_contribution",
        },
        evidence_spans={
            "initial_capital": "Start with $5,000",
            "capital_amount": "$200 every month",
        },
    )
    response = _repair(
        request_context, base=base, recurring_contribution=200, total_capital=5000
    )
    draft = response.candidate_strategy_draft
    assert draft.initial_capital == 5000
    assert draft.recurring_contribution == 200
    assert draft.total_capital is None
    assert response.requires_clarification
    assert [
        (item.field_name, float(item.raw_value)) for item in response.ambiguous_fields
    ] == [("total_capital", 5000)]

    interpretation = canonical_strategy_interpretation(response, request=request_context)
    report = conserve_semantic_constraints(
        strategy=interpretation.candidate_strategy_draft, selected_thread_metadata={}
    )
    assert report.evidence.contribution_ceiling is None
    assert report.evidence.total_capital == 5000
    assert report.evidence.recurring_contribution == 200
    assert report.unsupported_constraints == []
    decision = await _stage_result_from_interpretation(
        state=RunState(current_user_message=request_context.current_user_message),
        user=request_context.user,
        snapshot=None,
        interpretation=interpretation,
        capability_contract=build_default_capability_contract(),
        selected_thread_metadata={},
    )
    assert decision.outcome == "needs_clarification"
    assert [item["field_name"] for item in decision.patch["ambiguous_fields"]] == [
        "total_capital"
    ]


@pytest.mark.parametrize("field_name", ROLE_FIELDS)
@pytest.mark.parametrize("value", [0, 200])
@pytest.mark.parametrize("base_channel", ["typed", "extension", "semantic_capital"])
def test_existing_same_role_fact_survives_without_a_repeated_quote(
    request_context: InterpretationRequest,
    field_name: str,
    value: float,
    base_channel: str,
) -> None:
    if base_channel == "typed":
        base = _base(**{field_name: value})
    elif base_channel == "extension":
        base = _base(extra_parameters={field_name: value})
    else:
        role = BacktestStrategyInput.model_fields[field_name].json_schema_extra[
            "x-argus-capital-role"
        ]
        base = _base(capital_amount=value, field_provenance={"capital_amount": role})
    response = _repair(request_context, base=base, **{field_name: value})
    assert getattr(response.candidate_strategy_draft, field_name) == value
    assert response.ambiguous_fields == []


@pytest.mark.parametrize("field_name", ROLE_FIELDS)
@pytest.mark.parametrize("value", [0, 200])
def test_current_role_quote_can_use_its_existing_canonical_carrier(
    request_context: InterpretationRequest, field_name: str, value: float
) -> None:
    role = BacktestStrategyInput.model_fields[field_name].json_schema_extra[
        "x-argus-capital-role"
    ]
    quote = f"Use {value} for {field_name.replace('_', ' ')}"
    request = request_context.model_copy(update={"current_user_message": quote + "."})
    response = _repair(
        request,
        **{field_name: value},
        capital_amount=value,
        field_provenance={"capital_amount": role},
        evidence_spans={"capital_amount": quote},
    )
    assert getattr(response.candidate_strategy_draft, field_name) == value
    assert response.candidate_strategy_draft.field_provenance["capital_amount"] == role
    assert response.ambiguous_fields == []


@pytest.mark.parametrize("field_name", ROLE_FIELDS)
@pytest.mark.parametrize("value", [0, 200])
def test_new_role_accepts_its_bounded_current_quote(
    request_context: InterpretationRequest, field_name: str, value: float
) -> None:
    # Containment proves quote provenance, not the semantics of arbitrary text.
    quote = f"Use {value} for {field_name.replace('_', ' ')}"
    request = request_context.model_copy(update={"current_user_message": quote + "."})
    response = _repair(request, **{field_name: value}, evidence_spans={field_name: quote})
    assert getattr(response.candidate_strategy_draft, field_name) == value
    assert response.ambiguous_fields == []


@pytest.mark.parametrize("field_name", ROLE_FIELDS)
@pytest.mark.parametrize("value", [0, 200])
@pytest.mark.parametrize("quote", [None, "", "   ", "a quote from a different turn"])
def test_new_role_without_current_evidence_retains_a_blocker(
    request_context: InterpretationRequest,
    field_name: str,
    value: float,
    quote: str | None,
) -> None:
    spans = {} if quote is None else {field_name: quote}
    response = _repair(
        request_context,
        **{field_name: value},
        extra_parameters={field_name: value},
        evidence_spans=spans,
    )
    draft = response.candidate_strategy_draft
    assert getattr(draft, field_name) is None
    assert field_name not in draft.extra_parameters
    assert field_name not in draft.field_provenance
    assert response.requires_clarification
    assert [
        (item.field_name, float(item.raw_value)) for item in response.ambiguous_fields
    ] == [(field_name, value)]


@pytest.mark.parametrize("borrow_quote", [False, True])
def test_seed_evidence_cannot_be_relabelled_as_a_ceiling(
    request_context: InterpretationRequest, borrow_quote: bool
) -> None:
    quote = "Start with $5,000"
    base = _base(initial_capital=5000, evidence_spans={"initial_capital": quote})
    response = _repair(
        request_context,
        base=base,
        total_capital=5000,
        evidence_spans={"total_capital": quote} if borrow_quote else {},
    )
    assert response.candidate_strategy_draft.initial_capital == 5000
    assert response.candidate_strategy_draft.total_capital is None
    assert response.requires_clarification
    assert [item.field_name for item in response.ambiguous_fields] == ["total_capital"]


def test_equal_seed_and_ceiling_with_distinct_evidence_remain_distinct(
    request_context: InterpretationRequest,
) -> None:
    seed_quote = "Start with $5,000"
    ceiling_quote = "invest no more than $5,000 overall"
    request = request_context.model_copy(
        update={"current_user_message": f"{seed_quote} and {ceiling_quote}."}
    )
    base = _base(initial_capital=5000, evidence_spans={"initial_capital": seed_quote})
    response = _repair(
        request,
        base=base,
        total_capital=5000,
        evidence_spans={"total_capital": ceiling_quote},
    )
    assert response.candidate_strategy_draft.initial_capital == 5000
    assert response.candidate_strategy_draft.total_capital == 5000
    assert response.ambiguous_fields == []


@pytest.mark.parametrize("field_name", ROLE_FIELDS)
def test_ungrounded_replacement_keeps_base_fact_and_disputed_value(
    request_context: InterpretationRequest, field_name: str
) -> None:
    response = _repair(
        request_context, base=_base(**{field_name: 0}), **{field_name: 200}
    )
    assert getattr(response.candidate_strategy_draft, field_name) == 0
    assert response.requires_clarification
    assert [
        (item.field_name, float(item.raw_value)) for item in response.ambiguous_fields
    ] == [(field_name, 200)]
