"""An ordinary conversation turn spends no provider calls after the primary read.

Subtract-the-guardrails lane: the capability audit, the context audit, the
focused discovery read and the focused strategy repair are backtest checks.
A plain educational turn has nothing for them to check, so none of them may
run; the strategy-flow shapes they were built for keep them.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter as interpreter_module
from argus.agent_runtime.interpreter import discovery_focused_read as dfr
from argus.agent_runtime.interpreter.focused_extraction import (
    strategy_extraction_repair_is_allowed,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState

CONCEPT_QUESTIONS = (
    "What is compound interest?",
    "¿Qué significa inflación?",
    "What does diversification mean?",
)


def _request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )


def _educational_response(message: str, **overrides: Any) -> LLMInterpretationResponse:
    fields: dict[str, Any] = {
        "intent": "conversation_followup",
        "task_relation": "new_task",
        "requires_clarification": False,
        "user_goal_summary": "User asks what a concept means.",
        "assistant_response": "Here is what that means, in plain words.",
        "candidate_strategy_draft": LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_thesis="User wants to understand a concept.",
        ),
        "semantic_turn_act": "educational_question",
        "artifact_target": "none",
    }
    fields.update(overrides)
    return LLMInterpretationResponse(**fields)


def _forbid_provider_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def _refuse(**kwargs: Any) -> None:
        calls.append(str(kwargs.get("schema_name")))
        raise AssertionError(
            f"provider call on a plain turn: {kwargs.get('schema_name')}"
        )

    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", _refuse)
    monkeypatch.setattr(dfr, "invoke_openrouter_json_schema", _refuse)
    monkeypatch.setattr(interpreter_module, "research_rail_enabled", lambda: False)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("message", CONCEPT_QUESTIONS)
async def test_concept_question_reaches_the_runtime_with_zero_audit_calls(
    monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    calls = _forbid_provider_calls(monkeypatch)
    response = _educational_response(message)

    ready = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=_request(message),
    )

    assert calls == []
    assert ready.intent == "conversation_followup"
    assert ready.semantic_turn_act == "educational_question"
    assert ready.assistant_response == response.assistant_response
    assert ready.capability_question_focus is None
    assert ready.context_question_focus is None
    assert ready.asset_discovery is None


@pytest.mark.asyncio
async def test_concept_question_without_prose_still_runs_no_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _forbid_provider_calls(monkeypatch)
    message = "What is an ETF?"

    ready = await interpreter_module._response_ready_for_runtime(
        response=_educational_response(message, assistant_response=None),
        preferred_model="test-model",
        request=_request(message),
    )

    assert calls == []
    assert ready.semantic_turn_act == "educational_question"


class TestCapabilityAuditGate:
    def test_educational_prose_is_not_re_read(self) -> None:
        message = "What is compound interest?"
        assert not interpreter_module._response_needs_capability_side_question_audit(
            response=_educational_response(message), request=_request(message)
        )

    def test_a_pending_field_still_earns_the_read(self) -> None:
        message = "Can I use Bollinger Bands?"
        request = InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u1"),
        )
        assert interpreter_module._response_needs_capability_side_question_audit(
            response=_educational_response(message), request=request
        )


class TestContextAuditGate:
    def test_educational_turn_is_not_re_read(self) -> None:
        message = "What does inflation mean?"
        assert not interpreter_module._response_needs_context_question_audit(
            response=_educational_response(message, assistant_response=None),
            request=_request(message),
        )

    def test_unsupported_strategy_shape_still_earns_the_read(self) -> None:
        message = "what are the top market movers?"
        response = _educational_response(
            message,
            intent="strategy_drafting",
            semantic_turn_act="unsupported_request",
            requires_clarification=True,
            missing_required_fields=[],
        )
        assert interpreter_module._response_needs_context_question_audit(
            response=response, request=_request(message)
        )


class TestDiscoveryReadGate:
    def test_concept_question_never_triggers_the_read(self) -> None:
        response = _educational_response("What is an ETF?", assistant_response=None)
        assert not dfr.focused_discovery_read_applicable(response)
        assert not dfr.focused_discovery_read_applicable(
            response.model_copy(
                update={
                    "research_query": ResearchQueryExtraction(question_kind="concept")
                }
            )
        )

    def test_a_fact_question_with_no_payload_and_no_owner_triggers_it(self) -> None:
        response = _educational_response(
            "find me cryptos that are trending",
            assistant_response=None,
            candidate_strategy_draft=LLMStrategyDraft(),
            research_query=ResearchQueryExtraction(
                question_kind="find_assets", discovery_category="trending cryptos"
            ),
        )
        assert dfr.focused_discovery_read_applicable(response)


class TestRepairAdmission:
    @staticmethod
    def _allowed(response: LLMInterpretationResponse, *, evidence: bool) -> bool:
        return strategy_extraction_repair_is_allowed(
            response,
            request=_request(str(response.candidate_strategy_draft.raw_user_phrasing)),
            has_failed_action_launch_payload=lambda request: False,
            noncanonical_text_needs_repair=lambda *, response, request: False,
            has_active_strategy_context=lambda request: False,
            current_turn_has_material_execution_evidence=lambda request: evidence,
        )

    def test_educational_turn_needs_current_turn_facts(self) -> None:
        response = _educational_response("What is compound interest?")
        assert self._allowed(response, evidence=False) is False
        assert self._allowed(response, evidence=True) is True

    def test_the_evidence_predicate_sees_a_named_asset_but_not_a_concept(self) -> None:
        evidence = (
            interpreter_module._request_current_turn_has_material_execution_evidence
        )
        assert (
            evidence(_request("Test Apple when news sentiment turns positive.")) is True
        )
        for message in CONCEPT_QUESTIONS:
            assert evidence(_request(message)) is False, message


@pytest.mark.asyncio
async def test_a_well_formed_empty_extraction_ends_the_repair_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models_asked: list[str] = []

    async def _nothing_to_extract(**kwargs: Any) -> FocusedStrategyExtraction:
        models_asked.append(str(kwargs["model_name"]))
        return FocusedStrategyExtraction(
            is_testable_strategy=False, user_goal_summary="a concept question"
        )

    monkeypatch.setattr(
        interpreter_module, "invoke_openrouter_json_schema", _nothing_to_extract
    )
    monkeypatch.setattr(
        interpreter_module,
        "_unique_repair_models",
        lambda *_a, **_k: ["primary", "fallback"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "_strategy_extraction_repair_is_allowed",
        lambda *_a, **_k: True,
    )
    message = "What is compound interest?"

    repaired = await interpreter_module._repair_incomplete_strategy_extraction(
        failed_response=_educational_response(message),
        preferred_model="primary",
        request=_request(message),
    )

    assert repaired is None
    assert models_asked == ["primary"]


@pytest.mark.asyncio
async def test_a_provider_failure_still_moves_to_the_next_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models_asked: list[str] = []

    async def _first_fails(**kwargs: Any) -> FocusedStrategyExtraction:
        models_asked.append(str(kwargs["model_name"]))
        if len(models_asked) == 1:
            raise RuntimeError("provider down")
        return FocusedStrategyExtraction(
            is_testable_strategy=False, user_goal_summary="a concept question"
        )

    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", _first_fails)
    monkeypatch.setattr(
        interpreter_module,
        "_unique_repair_models",
        lambda *_a, **_k: ["primary", "fallback"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "_strategy_extraction_repair_is_allowed",
        lambda *_a, **_k: True,
    )
    message = "What is compound interest?"

    repaired = await interpreter_module._repair_incomplete_strategy_extraction(
        failed_response=_educational_response(message),
        preferred_model="primary",
        request=_request(message),
    )

    assert repaired is None
    assert models_asked == ["primary", "fallback"]
