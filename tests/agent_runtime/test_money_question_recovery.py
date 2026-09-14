"""Scripted acceptance regressions: an outage/pending test cannot own money math."""

from typing import Any

import httpx
import pytest
from argus.agent_runtime import calculated_answer as ca
from argus.agent_runtime import llm_interpreter as li
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.domain.calculations.answer_request import AnswerCalculation
from faker import Faker

fake = Faker()
BOND_QUESTION = "¿DOP$1 millón en un bono del Banco Popular?"
INFLATION_REPLY = (
    "Cambia solo el saldo inicial de tu ejemplo de DOP 100 a DOP 1,000. "
    "Mantén 0% de rendimiento y 5.13% de inflación durante el mismo período. "
    "¿Cuál sería el valor real final? Sin otra búsqueda."
)


@pytest.fixture
def user() -> UserState:
    return UserState(user_id=fake.uuid4(), language_preference="es-419", currency="DOP")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message", [BOND_QUESTION, INFLATION_REPLY, "What is AAPL worth?"]
)
async def test_failed_candidates_never_seed_a_test_without_a_typed_test_request(
    monkeypatch: pytest.MonkeyPatch, user: UserState, message: str
) -> None:
    seeds: list[li.LLMInterpretationResponse] = []
    failures = iter(
        [httpx.ReadTimeout("primary timed out"), httpx.ConnectError("fallback failed")]
    )

    async def invoke(**kwargs: Any) -> None:
        assert kwargs["schema_name"] == "LLMInterpretationResponse"
        raise next(failures)

    async def no_asset_context(**kwargs: Any) -> None:
        return None

    async def repair(**kwargs: Any) -> None:
        seeds.append(kwargs["failed_response"])
        return None

    monkeypatch.setattr(
        li, "provider_asset_resolution_context_for_request", no_asset_context
    )
    monkeypatch.setattr(
        li, "openrouter_structured_model_candidates", lambda: ["primary", "fallback"]
    )
    monkeypatch.setattr(li, "invoke_openrouter_json_schema", invoke)
    monkeypatch.setattr(li, "_repair_incomplete_strategy_extraction", repair)
    interpreter = li.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpret_stage_async(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=user,
        latest_task_snapshot=None,
        structured_interpreter=interpreter,
    )
    assert seeds == [], "An unread money question was seeded as strategy_drafting"
    assert result.outcome == "ready_to_respond"
    assert result.decision.intent == "conversation_followup"
    assert result.decision.candidate_strategy_draft == StrategySummary()
    assert result.stage_patch["recovery"]["code"] == "interpreter_unavailable"
    assert result.stage_patch["retry_last_turn"]["message"] == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "act", ["new_idea", "retry_failed_action", "educational_question"]
)
async def test_last_resort_repair_preserves_only_a_typed_test_read(
    monkeypatch: pytest.MonkeyPatch, user: UserState, act: str
) -> None:
    raw = li.LLMInterpretationResponse(
        intent="backtest_execution"
        if act == "retry_failed_action"
        else "strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Test SPY monthly buys",
        semantic_turn_act=act,
        candidate_strategy_draft=li.LLMStrategyDraft(
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            recurring_contribution=100,
            cadence="monthly",
        ),
    )
    original = raw.model_dump()
    seen = []
    request = InterpretationRequest(current_user_message=raw.user_goal_summary, user=user)
    if act == "retry_failed_action":
        request.latest_task_snapshot = TaskSnapshot(
            latest_failed_action_reference=ArtifactReference(
                artifact_kind="failed_action",
                artifact_id=fake.uuid4(),
                artifact_status="failed",
                metadata={"action_type": "run_backtest", "retryable": True},
            )
        )
        # A historical failure without its launch payload cannot be replayed;
        # the existing extraction predicate explicitly permits its repair.
        assert not li._structured_interpretation_has_required_shape(raw, request=request)
        assert li._strategy_extraction_repair_is_allowed(raw, request=request)

    async def repair(**kwargs: Any):
        seen.append(kwargs["failed_response"])
        return kwargs["failed_response"]

    monkeypatch.setattr(li, "_repair_incomplete_strategy_extraction", repair)
    repaired = await li._focused_strategy_repair_after_candidate_failures(
        request=request,
        preferred_model="stub",
        failed_response=raw,
    )
    if act in {"new_idea", "retry_failed_action"}:
        assert repaired is not None
        assert repaired.candidate_strategy_draft == raw.candidate_strategy_draft
        assert repaired.semantic_turn_act == act
        assert "structured_interpretation_candidates_failed" in repaired.reason_codes
        assert len(seen) == 1
    else:
        assert repaired is None and seen == []
    assert raw.model_dump() == original


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_type", ["buy_and_hold", "dca_accumulation"])
async def test_arithmetic_followup_passes_a_pending_test_and_computes(
    monkeypatch: pytest.MonkeyPatch, user: UserState, strategy_type: str
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    monkeypatch.setattr(ca, "resolve_openrouter_api_key", lambda: "stub")
    monkeypatch.setattr(ca, "openrouter_structured_model_candidates", lambda: ["stub"])
    values = {
        "start_value": 1000,
        "annual_rate_pct": 0,
        "periods": 12,
        "inflation_rate_pct": 5.13,
    }

    def voice(**kwargs: Any) -> ca.CalculatedVoicedAnswer:
        assert kwargs["schema_model"] is ca.CalculatedVoicedAnswer
        return ca.CalculatedVoicedAnswer(
            lead="El valor real final es {{real_end_value}}.",
            calculations=[
                AnswerCalculation.model_validate(
                    {
                        "kind": "growth_projection",
                        "solve_for": "end_value",
                        "inputs": [
                            {"name": name, "value": value, "source": "user"}
                            for name, value in values.items()
                        ],
                    }
                )
            ],
        )

    monkeypatch.setattr(ca, "invoke_openrouter_json_schema_sync", voice)
    pending = StrategySummary(
        strategy_type=strategy_type, asset_universe=["SPY"], asset_class="equity"
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending, pending_needs=["period"])
    before = snapshot.model_dump()

    def interpret(request: InterpretationRequest) -> StructuredInterpretation:
        assert request.latest_task_snapshot == snapshot
        return StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            user_goal_summary=INFLATION_REPLY,
            semantic_turn_act="educational_question",
            research_query=ResearchQueryExtraction(
                question_kind="none", scenario_question=True
            ),
        )

    result = await interpret_stage_async(
        state=RunState.new(
            current_user_message=INFLATION_REPLY,
            recent_thread_history=[
                {
                    "role": "assistant",
                    "content": "En un año, con 0% de rendimiento y 5.13% de inflación.",
                },
            ],
        ),
        user=user,
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
        structured_interpreter=interpret,
    )
    assert result.outcome == "ready_to_respond"
    assert ca.CALCULATED_ANSWER_REASON_CODE in result.decision.reason_codes
    card = result.stage_patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "growth_projection"
    assert card["outcome"]["status"] == "succeeded"
    assert card["outcome"]["result"]["real_end_value"] == pytest.approx(
        values["start_value"] / (1 + values["inflation_rate_pct"] / 100)
    )
    assert "{{" not in result.stage_patch["assistant_response"]
    assert snapshot.model_dump() == before
    assert "requested_field" not in result.stage_patch


@pytest.mark.asyncio
async def test_knowledge_followup_passes_pending_test_after_interpretation(
    monkeypatch: pytest.MonkeyPatch, user: UserState
) -> None:
    from argus.agent_runtime import research_answer

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    message = "¿Qué significa inflación?"
    answer = "La inflación reduce lo que puedes comprar con la misma cantidad."

    async def research(**kwargs: Any):
        from argus.agent_runtime.research_grounded import research_decision
        from argus.agent_runtime.stages.interpret_types import StageResult

        return StageResult(
            outcome="ready_to_respond",
            decision=research_decision(
                kwargs["interpretation"], user, "scripted_concept_answer"
            ),
            stage_patch={"assistant_response": answer},
        )

    monkeypatch.setattr(research_answer, "research_answer_stage_result", research)
    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary=message,
        semantic_turn_act="educational_question",
        research_query=ResearchQueryExtraction(question_kind="concept"),
    )
    result = await interpret_stage_async(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=user,
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold", asset_universe=["SPY"]
            )
        ),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "date_range",
        },
        structured_interpreter=lambda request: interpretation,
    )
    assert result.outcome == "ready_to_respond"
    assert result.stage_patch["assistant_response"] == answer
