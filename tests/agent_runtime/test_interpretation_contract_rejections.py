"""Regression locks for the interpreter ValueError dead end.

Covers the three post-response rejection sites: the one that fired on
legitimate input, the two that correctly reject an unusable response, the
bounded in-tier self-correction, and the banner those failures render.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.contract_recovery import (
    incomplete_response_error,
)
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
    _response_ready_for_runtime,
)
from argus.agent_runtime.llm_interpreter_types import InterpretationContractError
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    interpret_stage_async,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)

USER = UserState(user_id="contract-user", language_preference="es")


def _prior() -> StrategySummary:
    return StrategySummary(
        raw_user_phrasing="Quiero probar cruce de medias en AAPL",
        requested_strategy_template="moving_average_crossover",
        strategy_type="moving_average_crossover",
        asset_universe=["AAPL"],
        asset_class="equity",
        entry_logic="SMA 50 cruza arriba de SMA 200",
        exit_logic="SMA 50 cruza abajo de SMA 200",
    )


def _card_request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="strategy_drafting",
            completed=False,
            pending_strategy_summary=_prior(),
            pending_needs=["period"],
            active_confirmation_reference=ArtifactReference(
                artifact_kind="confirmation",
                artifact_id="c1",
                artifact_status="pending",
            ),
            last_unresolved_follow_up="¿Qué periodo quieres usar?",
        ),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        user=USER,
    )


def _bare_request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={},
        user=USER,
    )


def _response(**overrides: Any) -> LLMInterpretationResponse:
    payload: dict[str, Any] = {
        "intent": "strategy_drafting",
        "user_goal_summary": "contract",
        "task_relation": "new_task",
        "requires_clarification": False,
        "assistant_response": "",
        "candidate_strategy_draft": LLMStrategyDraft(),
    }
    payload.update(overrides)
    return LLMInterpretationResponse(**payload)


@pytest.fixture
def no_repairs(monkeypatch) -> None:
    """Pin the "repair could not rescue it" case that production hits."""
    from argus.agent_runtime import llm_interpreter

    async def _none(*_args: Any, **_kwargs: Any) -> None:
        return None

    for name in (
        "_plan_artifact_edit_response",
        "_repair_incomplete_strategy_extraction",
        "_plan_pending_artifact_assumption_edit",
        "_unsupported_context_question_audited_response",
        "_audit_stated_run_fields",
        "_audit_supported_strategy_capability_conflict",
        "_audit_executable_strategy_grounding",
        "_focused_date_window_audited_response",
        "_ready_active_artifact_edit_planned_response",
        "_early_starting_capital_rechecked_response",
        "_early_focused_strategy_repaired_response",
    ):
        monkeypatch.setattr(llm_interpreter, name, _none, raising=False)

    async def _passthrough(*, response: Any, **_kwargs: Any) -> Any:
        return response

    monkeypatch.setattr(
        llm_interpreter, "_stated_run_field_audited_response", _passthrough
    )


def test_knowledge_answer_survives_when_strategy_upgrade_fails(no_repairs) -> None:
    # Site 1 fired only when the response already carried an answer, so the
    # turn that had something to show was the one being thrown away.
    response = _response(
        intent="unsupported_or_out_of_scope",
        semantic_turn_act="unsupported_request",
        requires_clarification=True,
        assistant_response="Puedo analizar el S&P 500 mediante SPY.",
    )

    ready = asyncio.run(
        _response_ready_for_runtime(
            response=response,
            preferred_model="primary/model",
            request=_bare_request("Ayúdame con estadísticas sobre el S&P 500"),
        )
    )

    assert ready.assistant_response == "Puedo analizar el S&P 500 mediante SPY."


def test_replay_without_material_update_is_still_rejected(no_repairs) -> None:
    response = _response(
        task_relation="refine",
        semantic_turn_act="refine_current_idea",
    )

    with pytest.raises(InterpretationContractError) as excinfo:
        asyncio.run(
            _response_ready_for_runtime(
                response=response,
                preferred_model="primary/model",
                request=_card_request("del ultimo año para aca"),
            )
        )

    assert "replayed the active artifact" in str(excinfo.value)
    assert excinfo.value.corrective_hint


def test_response_with_nothing_to_show_is_still_rejected(no_repairs) -> None:
    response = _response(
        intent="unsupported_or_out_of_scope",
        semantic_turn_act="unsupported_request",
        requires_clarification=True,
        assistant_response="",
    )

    with pytest.raises(InterpretationContractError) as excinfo:
        asyncio.run(
            _response_ready_for_runtime(
                response=response,
                preferred_model="primary/model",
                request=_bare_request("Ayúdame con estadísticas sobre el S&P 500"),
            )
        )

    assert excinfo.value.corrective_hint


def test_incomplete_reason_names_the_actual_gap() -> None:
    knowledge = _response(
        intent="unsupported_or_out_of_scope",
        semantic_turn_act="unsupported_request",
    )
    reason = str(
        incomplete_response_error(
            response=knowledge,
            request=_bare_request("Ayúdame con estadísticas sobre el S&P 500"),
        )
    )

    # A knowledge turn has no strategy draft, so it must not be blamed for one.
    assert "strategy draft" not in reason
    assert "unsupported_or_out_of_scope" in reason


def test_self_correction_reasks_the_same_tier_once(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter

    calls: list[tuple[str, bool]] = []

    async def fake_invoke(**kwargs: Any) -> LLMInterpretationResponse:
        messages = kwargs["messages"]
        corrective = any(
            "rejected by runtime validation" in message["content"]
            for message in messages
        )
        calls.append((str(kwargs["model_name"]), corrective))
        return _response()

    async def gated_ready(
        *, response: Any, preferred_model: str, request: Any, **_kwargs: Any
    ) -> Any:
        if len(calls) == 1:
            raise InterpretationContractError(
                "OpenRouter interpretation replayed the active artifact without "
                "a material current-turn update",
                corrective_hint="Apply the current message to the draft.",
            )
        return response

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", fake_invoke)
    monkeypatch.setattr(
        llm_interpreter, "_response_ready_for_runtime", gated_ready
    )
    monkeypatch.setattr(
        llm_interpreter,
        "openrouter_structured_model_candidates",
        lambda *_a, **_k: ["primary/model", "fallback/model"],
    )

    async def _no_context(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(
        llm_interpreter,
        "provider_asset_resolution_context_for_request",
        _no_context,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter(_card_request("del ultimo año para aca"))

    assert result is not None
    # Corrected in place on the first tier, so the fallback tier is never used.
    assert calls == [("primary/model", False), ("primary/model", True)]


class _UnavailableInterpreter:
    def __init__(self, failure_kind: str | None) -> None:
        self.last_failure_kind = failure_kind
        self.last_status = "failed"

    def __call__(self, request: InterpretationRequest) -> None:
        return None

    async def ainvoke(self, request: InterpretationRequest) -> None:
        return None


def _interpreter_unavailable_patch(failure_kind: str | None) -> dict[str, Any]:
    result = asyncio.run(
        interpret_stage_async(
            state=RunState.new(
                current_user_message="Ayúdame con estadísticas sobre el S&P 500",
                recent_thread_history=[],
            ),
            user=USER,
            latest_task_snapshot=None,
            structured_interpreter=_UnavailableInterpreter(failure_kind),
        )
    )
    return result.stage_patch


def test_contract_rejection_banner_is_not_retryable() -> None:
    patch = _interpreter_unavailable_patch("contract_rejected")

    # A distinct code, so the surface does not tell the user to retry when
    # there is nothing to retry with.
    assert patch["recovery"]["code"] == "interpreter_unavailable_not_retryable"
    assert patch["recovery"]["retryable"] is False
    # Nothing for the surface to render a replay action from.
    assert "retry_last_turn" not in patch
    assert "retry" not in str(patch["assistant_response"]).lower()


def test_both_interpreter_unavailable_codes_are_localized() -> None:
    import json
    from pathlib import Path

    for locale in ("en", "es-419"):
        catalog = json.loads(
            Path(f"web/public/locales/{locale}/common.json").read_text()
        )["chat"]["recovery"]
        assert catalog["interpreter_unavailable_not_retryable"]
        assert catalog["interpreter_unavailable"]


def test_transient_unavailability_still_offers_retry() -> None:
    patch = _interpreter_unavailable_patch(None)

    assert patch["recovery"]["retryable"] is True
    assert patch["retry_last_turn"]["message"]


def test_transient_failure_after_contract_rejection_restores_retry() -> None:
    from argus.agent_runtime.interpreter import contract_recovery

    class _Interp:
        last_failure_kind = None
        correction_attempted = False

    interp = _Interp()

    async def _noop_invoke(**_kwargs: Any) -> None:
        return None

    async def _noop_ready(**_kwargs: Any) -> None:
        return None

    def _handle(exc: Exception) -> None:
        asyncio.run(
            contract_recovery.handle_candidate_failure(
                interpreter=interp,
                exc=exc,
                candidate_model="primary/model",
                is_primary=True,
                wire_messages=[],
                invoke_schema=_noop_invoke,
                ready_for_runtime=_noop_ready,
                request=_bare_request("del ultimo año para aca"),
                asset_resolution_context=None,
            )
        )

    _handle(
        InterpretationContractError("rejected", corrective_hint="fix it")
    )
    assert interp.last_failure_kind == "contract_rejected"
    # A later transient failure must win the classification: retry can help.
    _handle(TimeoutError())
    assert interp.last_failure_kind is None


def test_correction_is_skipped_without_corridor_headroom() -> None:
    from argus.agent_runtime import turn_execution
    from argus.agent_runtime.interpreter import contract_recovery
    from argus.agent_runtime.state.models import RunState

    class _Interp:
        last_failure_kind = None
        correction_attempted = False

    interp = _Interp()
    attempts: list[str] = []

    async def _counting_invoke(**_kwargs: Any) -> None:
        attempts.append("correction_call")
        return None

    async def _noop_ready(**_kwargs: Any) -> None:
        return None

    with turn_execution.turn_execution_scope(
        entry_state=RunState.new(
            current_user_message="del ultimo año para aca",
            recent_thread_history=[],
        )
    ) as execution:
        execution.calls_reserved = execution.call_allowance - 2
        asyncio.run(
            contract_recovery.handle_candidate_failure(
                interpreter=interp,
                exc=InterpretationContractError(
                    "rejected", corrective_hint="fix it"
                ),
                candidate_model="primary/model",
                is_primary=True,
                wire_messages=[],
                invoke_schema=_counting_invoke,
                ready_for_runtime=_noop_ready,
                request=_bare_request("del ultimo año para aca"),
                asset_resolution_context=None,
            )
        )

    # No headroom left for repair + clarification, so no corrective call.
    assert attempts == []
    assert interp.correction_attempted is False
