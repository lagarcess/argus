"""Controlled model outputs through the production planner-to-card path."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime import artifact_edit_planner as planner
from argus.agent_runtime import llm_interpreter as interpreter
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.state.models import RunState
from argus.api.chat.confirmation import runtime_confirmation_card

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub
from tests.agent_runtime.test_compound_edit_contract import _request


async def card_for_edit_plan(
    monkeypatch: Any,
    plan_data: dict[str, Any],
    *,
    language: str = "en",
    recurring: bool = False,
) -> tuple[str, dict[str, Any] | None]:
    request = _request("Apply these edits", requested_field="assumption")
    request.user.language_preference = language
    if recurring:
        strategy = request.latest_task_snapshot.pending_strategy_summary
        strategy.strategy_type = "dca_accumulation"
        strategy.cadence = "monthly"
        strategy.capital_amount = 500
        strategy.extra_parameters.update(
            initial_capital=10000, recurring_contribution=500
        )

    async def invoke(*, schema_model: Any, **kwargs: Any) -> Any:
        assert schema_model is planner.ArtifactAssumptionEditPlan
        return schema_model(**plan_data)

    def resolve_asset(symbol: str, **kwargs: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(planner, "invoke_openrouter_json_schema", invoke)
    monkeypatch.setattr(
        planner, "openrouter_structured_model_candidates", lambda: ["fixture"]
    )
    monkeypatch.setattr(interpreter, "resolve_asset", resolve_asset)
    response = await interpreter._plan_pending_artifact_assumption_edit(
        request=request,
        preferred_model="fixture",
        primary_draft=None,
    )
    if response is None:
        return "planner_declined", None
    contract = build_default_capability_contract()
    converted = interpreter.OpenRouterStructuredInterpreter(
        contract=contract
    )._to_runtime_interpretation(
        response,
        request=request,
    )
    state = RunState.new(
        current_user_message=request.current_user_message, recent_thread_history=[]
    )
    interpreted = await interpret_stage_async(
        state=state,
        user=request.user,
        latest_task_snapshot=request.latest_task_snapshot,
        selected_thread_metadata=request.selected_thread_metadata,
        structured_interpreter=lambda _: converted,
    )
    if interpreted.outcome != "ready_for_confirmation":
        return interpreted.outcome, None
    state = state.model_copy(update=interpreted.stage_patch)
    state.candidate_strategy_draft = interpreted.decision.candidate_strategy_draft
    confirmed = confirm_stage(state=state, contract=contract, language=language)
    if confirmed.outcome != "await_approval":
        return confirmed.outcome, None
    payload = confirmed.stage_patch["confirmation_payload"]
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id="edit-contract-card",
        conversation_id="edit-contract-conversation",
        language=language,
    )
    return confirmed.outcome, card
