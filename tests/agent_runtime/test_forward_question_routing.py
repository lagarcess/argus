"""Decision 10 (2026-09-10): a question about the future is answered.

Forward-looking and valuation questions used to be classified as unsupported
by the interpreter prompt and refused by admission; a typed future horizon
forced every read onto the strategy route so no forecast could escape. Now the
horizon means the opposite for a question read: a strategy claim over a period
that has not happened yet is not a runnable test, so it cannot outrank the
question, and research answers with cited scenarios. The one refusal that
survives is a test asked over a future window, and its copy says why.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime import research_answer
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.clarification_contract import intent_clarification_fallback
from argus.agent_runtime.interpreter.research_routing import (
    FUTURE_HORIZON_QUESTION_REASON_CODE,
    primary_research_query,
    research_turn_has_conflicting_owner,
    strategy_claim_waived_by_future_horizon,
)
from argus.agent_runtime.interpreter.unsupported_admission import (
    FUTURE_PERFORMANCE_ADMISSION_BLOCKED,
    FUTURE_PERFORMANCE_CATEGORY,
    future_test_window_capability_clause,
)
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.research_grounded import _research_prompt
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import (
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UnsupportedConstraint,
    UserState,
)
from argus.domain.research.config import (
    RETRIEVAL_INSTRUCTIONS,
    SCENARIO_RETRIEVAL_INSTRUCTIONS,
    retrieval_spec,
)

NVDA_FUTURE_QUESTION = (
    "If I invest $10,000 in NVDA using a golden cross strategy, how much will "
    "it be worth in ten years?"
)
GOLDEN_CROSS = {
    "type": "moving_average_crossover",
    "fast_indicator": "sma",
    "fast_period": 50,
    "slow_indicator": "sma",
    "slow_period": 200,
    "direction": "bullish",
}


def _future_intent(evidence: str = "in ten years") -> dict[str, Any]:
    return {
        "kind": "future_window",
        "count": 10,
        "unit": "year",
        "anchor": "today",
        "confidence": 0.9,
        "evidence": evidence,
    }


def _strategy_claim_draft(*, future: bool) -> StrategySummary:
    """What the model still extracts from the question: the named strategy,
    the amount, and (when asked to) the horizon."""
    return StrategySummary(
        strategy_type="signal_strategy",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=10000,
        entry_rule=dict(GOLDEN_CROSS),
        extra_parameters={"date_range_intent": _future_intent()} if future else {},
    )


def _question_read(**overrides: Any) -> StructuredInterpretation:
    return StructuredInterpretation.model_validate(
        {
            "intent": "conversation_followup",
            "task_relation": "new_task",
            "requires_clarification": False,
            "user_goal_summary": "What a golden-cross NVDA investment becomes.",
            "semantic_turn_act": "educational_question",
            "research_query": {"question_kind": "company_lookup", "symbols": ["NVDA"]},
            "candidate_strategy_draft": _strategy_claim_draft(future=True),
            **overrides,
        }
    )


def test_a_strategy_claim_over_a_future_horizon_does_not_own_a_question() -> None:
    read = _question_read()
    assert strategy_claim_waived_by_future_horizon(read)
    assert not research_turn_has_conflicting_owner(read)
    assert primary_research_query(read) is not None
    # The waiver records that it fired, on the interpretation itself.
    assert FUTURE_HORIZON_QUESTION_REASON_CODE in read.reason_codes


def test_an_explicit_strategy_intent_over_a_future_horizon_is_still_a_question() -> None:
    read = _question_read(intent="strategy_drafting", semantic_turn_act="new_idea")
    assert primary_research_query(read) is not None


def test_the_same_claim_without_a_horizon_keeps_builder_ownership() -> None:
    read = _question_read(candidate_strategy_draft=_strategy_claim_draft(future=False))
    assert not strategy_claim_waived_by_future_horizon(read)
    assert research_turn_has_conflicting_owner(read)
    assert primary_research_query(read) is None
    assert FUTURE_HORIZON_QUESTION_REASON_CODE not in read.reason_codes


def test_a_typed_refusal_still_owns_its_route_over_a_future_horizon() -> None:
    read = _question_read(
        unsupported_constraints=[
            UnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="options straddle",
                explanation="not executable",
            )
        ]
    )
    assert research_turn_has_conflicting_owner(read)
    assert primary_research_query(read) is None


@dataclass(frozen=True)
class _ResolvedAsset:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class _Interpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    async def ainvoke(self, request):
        return self.response


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    response: StructuredInterpretation,
    *,
    message: str,
) -> tuple[StageResult, list[Any]]:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol, **_: _ResolvedAsset(symbol.upper(), "equity"),
    )
    dispatched: list[Any] = []

    async def dispatch(query, **kwargs):
        dispatched.append(query)
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={"assistant_response": "scenario answer"},
        )

    monkeypatch.setattr(research_answer, "_dispatch", dispatch)
    result = asyncio.run(
        interpret_stage_async(
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=UserState(user_id="u1", language_preference="en"),
            latest_task_snapshot=None,
            selected_thread_metadata={},
            structured_interpreter=_Interpreter(response),
        )
    )
    return result, dispatched


def test_the_forward_question_reaches_research_through_the_whole_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, dispatched = _run_turn(
        monkeypatch, _question_read(), message=NVDA_FUTURE_QUESTION
    )
    assert result.outcome == "ready_to_respond"
    assert result.patch.get("assistant_response") == "scenario answer"
    assert [query.question_kind for query in dispatched] == ["company_lookup"]
    assert result.patch.get("confirmation_payload") is None


def test_a_test_asked_over_a_future_window_still_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one boundary that survives: no data exists for the window."""
    run_request = _question_read(
        intent="backtest_execution",
        semantic_turn_act="new_idea",
        research_query={"question_kind": "none"},
    )
    result, dispatched = _run_turn(
        monkeypatch,
        run_request,
        message="Backtest a golden cross on NVDA over the next ten years.",
    )
    assert dispatched == []
    assert result.outcome == "needs_clarification"
    decision = result.decision
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED in decision.reason_codes
    constraint = next(
        item
        for item in decision.unsupported_constraints
        if item.category == FUTURE_PERFORMANCE_CATEGORY
    )
    assert "has not happened yet" in constraint.explanation
    assert "predict" not in constraint.explanation
    assert result.patch.get("confirmation_payload") is None


def test_the_surviving_fallback_copy_names_the_missing_data_and_offers_both() -> None:
    contract = build_default_capability_contract()
    copy = intent_clarification_fallback(
        response_intent={
            "kind": "unsupported_recovery",
            "facts": {
                "unsupported_constraints": [
                    {
                        "category": FUTURE_PERFORMANCE_CATEGORY,
                        "raw_value": "in ten years",
                        "explanation": "no data",
                    }
                ]
            },
            "options": [
                {
                    "label": option.label,
                    "replacement_values": dict(option.replacement_values),
                }
                for option in contract.get_simplification_options(
                    FUTURE_PERFORMANCE_CATEGORY
                )
            ],
        },
        strategy=StrategySummary(asset_universe=["NVDA"]),
    )
    assert copy is not None
    assert "no market data for a period that has not happened yet" in copy
    assert "historical period" in copy
    assert "analysts" in copy
    assert "predict" not in copy


def test_the_interpreter_prompt_sends_forward_questions_to_research() -> None:
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()
    clause = future_test_window_capability_clause()
    assert clause in prompt
    assert "Forward-looking and valuation questions are research questions" in clause
    assert "research_query.scenario_question=true" in clause
    assert "arithmetic, not a prediction" in clause
    assert "backtest over a future period" in clause
    assert "cannot predict future performance" not in prompt
    assert "classify the request as unsupported_or_out_of_scope" not in prompt


def _prompt(*, scenario: bool) -> str:
    return _research_prompt(
        message=NVDA_FUTURE_QUESTION,
        subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
        period="in ten years",
        language="en",
        question_kind="company_lookup",
        publisher_sources_required=True,
        scenario=scenario,
    )


def test_a_scenario_question_carries_the_scenario_contract() -> None:
    """The typed signal selects the provider contract that lets computed
    figures through; every other question keeps the retrieval contract the
    recordings froze, byte for byte."""
    prompt = _prompt(scenario=True)
    assert "scenarios you compute" in prompt
    assert "never estimate a live number. No investment advice." in prompt
    assert "scenarios" not in _prompt(scenario=False)

    scenario_spec = retrieval_spec(
        "balanced", question_kind="company_lookup", language_tag="en", scenario=True
    )
    plain_spec = retrieval_spec(
        "balanced", question_kind="company_lookup", language_tag="en"
    )
    assert scenario_spec.instructions == SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert plain_spec.instructions == RETRIEVAL_INSTRUCTIONS
    assert SCENARIO_RETRIEVAL_INSTRUCTIONS.startswith(RETRIEVAL_INSTRUCTIONS)
    assert "labeled scenario ranges" in SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert "never say what the reader should do" in SCENARIO_RETRIEVAL_INSTRUCTIONS
    assert "never rowed" in SCENARIO_RETRIEVAL_INSTRUCTIONS


def test_the_research_query_types_the_scenario_signal() -> None:
    field = ResearchQueryExtraction.model_fields["scenario_question"]
    assert field.default is False
    assert "will be worth" in str(field.description)
    assert "grow into" in str(field.description)


def test_a_scenario_question_always_requires_publisher_sources() -> None:
    """Whatever kind the question was typed as, a computed scenario is
    grounded on published inputs, so the missing-publisher retry and the
    withhold both apply to it."""
    from argus.agent_runtime.research_grounded import requires_publisher_sources

    scenario = ResearchQueryExtraction(
        question_kind="cross_company", symbols=["NVDA", "AMD"], scenario_question=True
    )
    plain = ResearchQueryExtraction(
        question_kind="cross_company", symbols=["NVDA", "AMD"]
    )
    assert requires_publisher_sources(scenario)
    assert not requires_publisher_sources(plain)


def test_a_future_horizon_without_a_research_query_never_voices_a_forecast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one read research cannot claim: a typed horizon and no question
    shape. The model's forecast prose stays out; the recovery offers the
    historical test and the analyst research."""
    result, dispatched = _run_turn(
        monkeypatch,
        _question_read(
            research_query={"question_kind": "none"},
            assistant_response="Your $10,000 could be worth about $150,000 in ten years.",
        ),
        message=NVDA_FUTURE_QUESTION,
    )
    assert dispatched == []
    assert result.outcome == "needs_clarification"
    assert FUTURE_PERFORMANCE_ADMISSION_BLOCKED in result.decision.reason_codes
    assert result.patch.get("assistant_response") is None


def test_the_scenario_contract_applies_on_either_typed_fact() -> None:
    """A missing scenario bit never quietly selects the ordinary contract when
    the interpreter typed the horizon: either typed fact is enough, and a read
    with neither is an ordinary lookup."""
    from argus.agent_runtime.research_grounded import scenario_contract_applies

    query_only = ResearchQueryExtraction(
        question_kind="company_lookup", symbols=["NVDA"], scenario_question=True
    )
    plain_query = ResearchQueryExtraction(
        question_kind="company_lookup", symbols=["NVDA"]
    )
    with_horizon = _question_read(research_query=plain_query.model_dump(mode="json"))
    without = _question_read(
        research_query=plain_query.model_dump(mode="json"),
        candidate_strategy_draft=StrategySummary(),
    )
    from argus.agent_runtime.research_grounded import SCENARIO_FROM_HORIZON_REASON_CODE

    assert scenario_contract_applies(query_only, without)
    assert SCENARIO_FROM_HORIZON_REASON_CODE not in without.reason_codes
    assert scenario_contract_applies(plain_query, with_horizon)
    # The horizon compensated for the primary read; that is recorded, once.
    assert with_horizon.reason_codes.count(SCENARIO_FROM_HORIZON_REASON_CODE) == 1
    assert scenario_contract_applies(plain_query, with_horizon)
    assert with_horizon.reason_codes.count(SCENARIO_FROM_HORIZON_REASON_CODE) == 1
    assert not scenario_contract_applies(plain_query, without)
    assert SCENARIO_FROM_HORIZON_REASON_CODE not in without.reason_codes
