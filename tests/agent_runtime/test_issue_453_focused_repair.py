# ruff: noqa: F403, F405
from tests.agent_runtime._llm_interpreter_common import *


@pytest.mark.asyncio
async def test_issue_453_bare_unsupported_dca_starter_repairs_to_amount_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = "¿Y si hubiera comprado Coca-Cola cada mes durante cinco años?"
    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=True,
                user_goal_summary="Probar compras mensuales de Coca-Cola durante cinco años.",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar Coca-Cola cada mes durante cinco años.",
                asset_universe=["KO"],
                asset_class="equity",
                date_range_raw_text="durante cinco años",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=5,
                    unit="year",
                    anchor="today",
                    confidence=0.94,
                    evidence="durante cinco años",
                ),
                cadence="monthly",
                missing_required_fields=["capital_amount"],
                confidence=0.94,
                evidence_spans={
                    "strategy_type": "comprado Coca-Cola cada mes",
                    "asset_universe": "Coca-Cola",
                    "cadence": "cada mes",
                    "date_range": "durante cinco años",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(confidence=0.9)
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            user_goal_summary="La solicitud no es compatible.",
            assistant_response="No puedo ejecutar esa estrategia directamente.",
            semantic_turn_act="unsupported_request",
        ),
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "strategy_drafting"
    assert ready_response.requires_clarification is True
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    assert ready_response.missing_required_fields == ["capital_amount"]
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == ["KO"]
    assert draft.cadence == "monthly"
    assert draft.date_range is not None


def test_issue_453_active_context_without_requested_field_blocks_noncanonical_repair() -> (
    None
):
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="The user wants to invest $500 in NFLX.",
        assistant_response="That request is not supported.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="$500",
            strategy_thesis="The user wants to invest $500 in NFLX.",
        ),
        semantic_turn_act="unsupported_request",
    )
    request = InterpretationRequest(
        current_user_message="$500",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold NFLX.",
                asset_universe=["NFLX"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            )
        ),
        user=UserState(user_id="u1", language_preference="en"),
    )

    assert (
        interpreter_module._strategy_extraction_repair_is_allowed(
            response,
            request=request,
        )
        is False
    )


@pytest.mark.asyncio
async def test_issue_453_pending_capital_answer_repairs_without_acknowledgment(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            focused_context = "\n".join(
                message["content"] for message in kwargs["messages"]
            )
            assert '"strategy_type": "buy_and_hold"' in focused_context
            assert '"requested_field": "capital_amount"' in focused_context
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="El usuario eligió $500 de capital inicial para NFLX.",
                language="es-419",
                capital_amount=500,
                confidence=0.95,
                evidence_spans={"capital_amount": "$500"},
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=500,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener NFLX.",
        asset_universe=["NFLX"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
    )
    acknowledgment = "Entendido, quieres invertir $500."
    ready_response = await interpreter_module._response_ready_for_runtime(
        response=LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="continue",
            user_goal_summary="User wants to invest $500",
            assistant_response=acknowledgment,
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="$500",
                capital_amount=500,
            ),
            semantic_turn_act="unsupported_request",
        ),
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="$500",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "requested_field": "capital_amount",
            },
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.semantic_turn_act == "answer_pending_need"
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["NFLX"]
    assert draft.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert draft.capital_amount == 500
