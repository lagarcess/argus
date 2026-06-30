# ruff: noqa: F403, F405
from tests.agent_runtime._llm_interpreter_common import *


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_default_rsi_exit_when_current_turn_supplies_threshold(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    calls: list[str] = []

    async def repair_stub(*, failed_response, request, **kwargs):
        del kwargs
        calls.append("focused_strategy_extraction")
        return interpreter_module._response_from_focused_strategy_extraction(
            extraction=interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="User supplied RSI entry and exit thresholds.",
                strategy_type="indicator_threshold",
                strategy_thesis="Buy TSLA on RSI dips and exit when RSI rebounds.",
                indicator="rsi",
                indicator_period=14,
                entry_threshold=30,
                exit_threshold=70,
            ),
            request=request,
            base_response=failed_response,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User supplied an RSI dip strategy.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy when RSI 14 drops below 30, sell when it gets above 70."
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Buy TSLA on RSI dips.",
            asset_universe=["TSLA"],
            date_range="past year",
            capital_amount=1000,
            indicator="rsi",
            indicator_period=14,
            entry_threshold=30,
            exit_threshold=55,
        ),
        semantic_turn_act="answer_pending_need",
    )
    request = InterpretationRequest(
        current_user_message=(
            "Let's use the RSI dip version: buy when RSI 14 drops below 30, "
            "sell when it gets above 70."
        ),
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Test TSLA when it looks cheap.",
                asset_universe=["TSLA"],
                asset_class="equity",
                date_range="past year",
                capital_amount=1000,
            )
        ),
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )
    result = interpreter._to_runtime_interpretation(ready_response, request=request)

    parameters = result.candidate_strategy_draft.extra_parameters[
        "indicator_parameters"
    ]
    assert calls == ["focused_strategy_extraction"]
    assert parameters["entry_threshold"] == 30.0
    assert parameters["exit_threshold"] == 70.0
    assert result.candidate_strategy_draft.exit_logic == (
        "Sell when RSI(14) rises to 70 or above"
    )

@pytest.mark.asyncio
async def test_retry_word_inside_new_prompt_uses_focused_strategy_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def repair_stub(*, failed_response, request, **kwargs):
        del kwargs
        calls.append(request.current_user_message)
        return interpreter_module._response_from_focused_strategy_extraction(
            extraction=interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="User wants an Apple buy-and-hold comparison.",
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold Apple against QQQ over 2026.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2026-01-01", "end": "2026-12-31"},
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="year_to_date",
                    year=2026,
                    end="2026-06-01",
                    evidence="2026 so far",
                ),
                comparison_baseline="QQQ",
            ),
            request=request,
            base_response=failed_response,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to retry the failed action.",
        candidate_strategy_draft=LLMStrategyDraft(),
        semantic_turn_act="retry_failed_action",
    )
    request = InterpretationRequest(
        current_user_message=(
            "one more messy retry check: how did apple perform against qqq "
            "from the start of 2026 through the end of 2026, simple buy and hold"
        ),
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            latest_failed_action_reference=ArtifactReference(
                artifact_kind="failed_action",
                artifact_id="stale-failed-action",
                artifact_status="failed",
                metadata={"action_type": "run_backtest", "retryable": True},
            )
        ),
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == [request.current_user_message]
    assert ready_response.semantic_turn_act == "new_idea"
    assert ready_response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert ready_response.candidate_strategy_draft.comparison_baseline == "QQQ"

@pytest.mark.asyncio
async def test_current_year_so_far_repairs_llm_year_end_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.nlp import natural_time as natural_time_module

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 6, 30)

    monkeypatch.setattr(natural_time_module, "date", FrozenDate)

    async def repair_stub(*, failed_response, request, **kwargs):
        del kwargs
        return interpreter_module._response_from_focused_strategy_extraction(
            extraction=interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="User wants an Apple buy-and-hold comparison.",
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold Apple against QQQ in 2026 so far.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2026-01-01", "end": "2026-12-31"},
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="year_to_date",
                    year=2026,
                    confidence=0.9,
                    evidence="2026 so far",
                ),
                comparison_baseline="QQQ",
            ),
            request=request,
            base_response=failed_response,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks a fresh comparison.",
        candidate_strategy_draft=LLMStrategyDraft(),
    )
    request = InterpretationRequest(
        current_user_message=(
            "how did apple perform against QQQ in 2026 so far, simple buy and hold"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.semantic_turn_act == "new_idea"
    assert ready_response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert ready_response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2026-01-01",
        "end": "2026-06-30",
    }
    shifted_resolution = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="year_to_date",
            year=2026,
            confidence=0.9,
            evidence="2026 so far",
        ),
        today=date(2027, 1, 15),
    )
    assert shifted_resolution is not None
    assert shifted_resolution.payload == {
        "start": "2026-01-01",
        "end": "2026-12-31",
    }

@pytest.mark.asyncio
async def test_stated_run_field_contract_repairs_compact_month_year_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fail_if_audit_model_is_needed(**kwargs):
        raise AssertionError(f"unexpected audit call: {kwargs.get('schema_name')}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fail_if_audit_model_is_needed,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants a monthly DCA strategy.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy AAPL and GOOG monthly.",
            asset_universe=["AAPL", "GOOG"],
            asset_class="equity",
            date_range={"start": "2021-01-01", "end": "2024-01-01"},
            date_range_raw_text="Jan 2021-Jan 2024",
            capital_amount=200,
            cadence="monthly",
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "Can you set a strategy where I buy AAPL GOOG at $200 every month "
            "for Jan 2021-Jan 2024?"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": "2021-01-01",
        "end": "2024-01-31",
    }
    assert "current_message_run_field_contract_repair" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_run_field_contract_repairs_spanish_month_year_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fail_if_audit_model_is_needed(**kwargs):
        raise AssertionError(f"unexpected audit call: {kwargs.get('schema_name')}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fail_if_audit_model_is_needed,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="El usuario quiere probar comprar y mantener Tesla.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener Tesla.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range={"start": "2021-01-01", "end": "2024-01-01"},
            date_range_raw_text="enero de 2021 hasta diciembre de 2024",
            date_range_intent=LLMDateRangeIntent(
                kind="explicit_range",
                start="2021-01-01",
                end="2024-12-31",
                evidence="enero de 2021 hasta diciembre de 2024",
            ),
            capital_amount=100000,
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message=(
            "Compra y manten Tesla desde enero de 2021 hasta diciembre de 2024"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": "2021-01-01",
        "end": "2024-12-31",
    }
    assert "current_message_run_field_contract_repair" in repaired.reason_codes

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_message",
    [
        "explain what dollar cost averaging means",
        "what does average entry price mean for beginners?",
    ],
)
async def test_candidate_failure_repair_skips_active_confirmation_side_question_without_execution_evidence(
    monkeypatch,
    current_message,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    repair_calls: list[str] = []

    async def failed_interpreter_stub(**kwargs):
        assert kwargs["schema_name"] == "LLMInterpretationResponse"
        raise TimeoutError("structured interpreter unavailable")

    async def repair_stub(*, request, **kwargs):
        del kwargs
        repair_calls.append(request.current_user_message)
        raise AssertionError("side questions should not enter focused strategy repair")

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        failed_interpreter_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=current_message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring buys for BTC.",
                    asset_universe=["BTC"],
                    asset_class="crypto",
                    date_range={"start": "2022-01-01", "end": "2023-12-31"},
                    capital_amount=125,
                    cadence="biweekly",
                ),
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    metadata={
                        "strategy": "Recurring Buys",
                        "assets": ["BTC"],
                    },
                ),
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert result is None
    assert repair_calls == []

@pytest.mark.asyncio
async def test_llm_interpreter_does_not_repair_vague_strategy_start(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def post_guidance_llm_stub(**kwargs):
        del kwargs
        raise AssertionError(
            "vague strategy starters should not enter executable repair or audit"
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_signal_rule_checked_response",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_executable_strategy_grounding",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_plan_pending_artifact_assumption_edit",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_plan_focused_artifact_edit",
        post_guidance_llm_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to create a strategy but gave no details yet.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="I want to create a new strategy.",
            strategy_thesis="Create a new strategy.",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="I want to create a new strategy.",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.intent == "beginner_guidance"
    assert ready_response.semantic_turn_act == "new_idea"
    assert ready_response.artifact_target == "none"
    assert "vague_strategy_start_guidance" in ready_response.reason_codes

@pytest.mark.asyncio
async def test_llm_interpreter_treats_empty_strategy_shell_as_guidance(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def post_guidance_llm_stub(**kwargs):
        del kwargs
        raise AssertionError(
            "empty strategy shells should not enter executable repair or audit"
        )

    monkeypatch.setattr(
        interpreter_module,
        "_signal_rule_checked_response",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_executable_strategy_grounding",
        post_guidance_llm_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        post_guidance_llm_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Create a new strategy",
        missing_required_fields=["entry_condition", "custom_rule_shape"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="I want to create a new strategy.",
            strategy_thesis="I want to create a new strategy.",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="I want to create a new strategy.",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.intent == "beginner_guidance"
    assert ready_response.requires_clarification is True
    assert ready_response.missing_required_fields == []
    assert "vague_strategy_start_guidance" in ready_response.reason_codes

@pytest.mark.asyncio
async def test_llm_interpreter_does_not_convert_capability_question_to_guidance() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks whether Bollinger Bands are supported.",
        assistant_response="Yes, Bollinger Bands are supported for runnable rules.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_indicators",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Can I use Bollinger Bands?",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.intent == "strategy_drafting"
    assert ready_response.capability_question_focus == "supported_indicators"
    assert "vague_strategy_start_guidance" not in ready_response.reason_codes

@pytest.mark.asyncio
async def test_llm_interpreter_repairs_unfocused_capability_answer(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "CapabilitySideQuestionAudit"
        return interpreter_module.CapabilitySideQuestionAudit(
            is_capability_question=True,
            focus="supported_indicators",
            assistant_response=None,
            confidence=0.88,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks whether Bollinger Bands are supported.",
        assistant_response="Bollinger Bands are not supported yet.",
        semantic_turn_act="educational_question",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Can I use Bollinger Bands?",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.intent == "conversation_followup"
    assert ready_response.semantic_turn_act == "educational_question"
    assert ready_response.capability_question_focus == "supported_indicators"
    assert ready_response.assistant_response is None
    assert "capability_side_question_audit" in ready_response.reason_codes

@pytest.mark.asyncio
async def test_material_execution_evidence_routes_to_structured_repair_before_capability(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=True,
                focus="supported_strategies",
                assistant_response="Which supported strategy do you want?",
                confidence=0.95,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="pt",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold ETH through the period.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range={
                    "start": "2025-10-13",
                    "end": "2026-06-13",
                },
                date_range_raw_text="ultimos 8 meses",
                capital_amount=100000,
                confidence=0.9,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "ultimos 8 meses",
                    "strategy_type": "compra e mantem",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range={
                    "start": "2025-10-13",
                    "end": "2026-06-13",
                },
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=100000,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="compra e mantem eth ultimos 8 meses 100k",
        assistant_response=(
            "Which supported strategy should I use: RSI, buy and hold, or a "
            "moving-average crossover?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compra e mantem eth ultimos 8 meses 100k",
            strategy_thesis="compra e mantem eth ultimos 8 meses 100k",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="compra e mantem eth ultimos 8 meses 100k",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert "FocusedStrategyExtraction" in calls
    assert "CapabilitySideQuestionAudit" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.capability_question_focus is None
    assert ready_response.assistant_response is None
    assert ready_response.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert ready_response.candidate_strategy_draft.asset_universe == ["ETH"]
    assert ready_response.candidate_strategy_draft.capital_amount == 100000

@pytest.mark.asyncio
async def test_underfilled_nonclarifying_execution_repairs_before_capability(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "MSFT"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity", name=normalized)

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            raise AssertionError("capability audit should not run first")
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Comprar y mantener AAPL y MSFT.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener AAPL y MSFT con pesos iguales.",
                asset_universe=["AAPL", "MSFT"],
                asset_class="equity",
                date_range={"start": "2025-01-01", "end": "2026-06-05"},
                capital_amount=10000,
                confidence=0.92,
                evidence_spans={
                    "asset_universe": "AAPL y MSFT",
                    "capital_amount": "10000 dolares",
                    "date_range": "1 de enero de 2025 hasta el 5 de junio de 2026",
                    "strategy_type": "comprar y mantener",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=10000,
                date_range={"start": "2025-01-01", "end": "2026-06-05"},
                confidence=0.91,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=10000,
                confidence=0.91,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    message = (
        "Prueba una estrategia de comprar y mantener AAPL y MSFT con pesos "
        "iguales desde el 1 de enero de 2025 hasta el 5 de junio de 2026 "
        "con 10000 dolares"
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_thesis=message,
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls[0] == "FocusedStrategyExtraction"
    assert "CapabilitySideQuestionAudit" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "MSFT",
    ]
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2026-06-05",
    }

@pytest.mark.asyncio
async def test_noncanonical_strategy_text_with_material_evidence_gets_repaired(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "AAPL":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=False,
                confidence=0.92,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Comprar y mantener AAPL con SPY como referencia.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener AAPL.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={
                    "start": "2025-06-14",
                    "end": "2026-06-14",
                },
                date_range_raw_text="los últimos 12 meses",
                comparison_baseline="SPY",
                confidence=0.9,
                evidence_spans={
                    "asset_universe": "AAPL",
                    "comparison_baseline": "SPY como referencia",
                    "date_range": "los últimos 12 meses",
                    "strategy_type": "Compra y mantén",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                date_range={
                    "start": "2025-06-14",
                    "end": "2026-06-14",
                },
                comparison_baseline="SPY",
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda request: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_message = (
        "Compra y mantén AAPL durante los últimos 12 meses "
        "con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=current_message,
        assistant_response=(
            "El concepto de compra inicial aún no es ejecutable directamente. "
            "¿Quieres comparar con compra y mantención, usar RSI o un cruce?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_message,
            strategy_type="compra y mantención",
            strategy_thesis=current_message,
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-14", "end": "2026-06-14"},
            comparison_baseline="SPY",
            language="es-419",
        ),
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=current_message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_anchored_supported_draft_without_date_evidence_gets_schema_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="en",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold ETH through the period.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                capital_amount=100000,
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "last 8 months",
                    "strategy_type": "bought eth and just held it",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response=(
            "To run the simulation, what 8-month window do you have in mind?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and just held it last 8 months with 100k",
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="Hold ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
            evidence_spans={
                "asset_universe": "eth",
                "capital_amount": "100k",
                "strategy_type": "bought eth and just held it",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and just held it last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "FocusedStrategyExtraction" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert ready_response.candidate_strategy_draft.asset_universe == ["ETH"]
    assert ready_response.candidate_strategy_draft.capital_amount == 100000
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert (
        ready_response.candidate_strategy_draft.date_range
        == expected_range.payload
    )

@pytest.mark.asyncio
async def test_llm_evidence_span_triggers_date_intent_repair_without_text_gate(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response=(
            "What are the start and end dates for your 8-month ETH hold?"
        ),
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and held it for the last 8 months with 100k",
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="User bought ETH and held it for the last 8 months.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
            extra_parameters={
                "evidence_spans": {
                    "asset": "ETH",
                    "capital": "$100k",
                    "date_range": "last 8 months",
                }
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
    assert "FocusedStrategyExtraction" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.candidate_strategy_draft.date_range_intent is not None
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_canonical_supported_fields_trigger_date_intent_repair_without_text_gate(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response=(
            "What date did you buy, and what date are you selling?"
        ),
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and held it for the last 8 months with 100k",
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Ethereum over the last 8 months.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
    assert "FocusedStrategyExtraction" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_raw_canonical_strategy_metadata_triggers_date_intent_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response="What date range should I use?",
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and held it for the last 8 months with 100k",
            language="en",
            strategy_type=None,
            strategy_thesis="Buy and hold Ethereum over the last 8 months.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
            extra_parameters={"raw_strategy_type": "buy_and_hold"},
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
    assert "FocusedStrategyExtraction" not in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_supported_shape_recovers_date_intent_without_capital_gate(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                confidence=0.94,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=False,
                requires_clarification=True,
                user_goal_summary="Missing date window.",
                confidence=0.2,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with shorthand capital.",
        assistant_response="Which 8-month window should I use?",
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and held it for the last 8 months with 100k",
            language="en",
            strategy_type=None,
            strategy_thesis="Buy and hold ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            extra_parameters={"raw_strategy_type": "buy_and_hold"},
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "StatedRunFieldFidelityAudit" in calls
    assert "FocusedDateWindowExtraction" in calls
    assert calls.index("FocusedDateWindowExtraction") < calls.index(
        "StatedRunFieldFidelityAudit"
    )
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    draft = ready_response.candidate_strategy_draft
    assert draft.capital_amount == 100000
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_focused_date_intent_repair_replaces_low_provenance_base_window(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Mantener ETH durante los ultimos 8 meses.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="ultimos 8 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    evidence="ultimos 8 meses",
                ),
                capital_amount=100000,
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "ultimos 8 meses",
                    "strategy_type": "compre eth y lo mantuve",
                },
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="ETH buy-and-hold with $100K.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compre eth y lo mantuve los ultimos 8 meses con 100k",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Mantener ETH durante los ultimos 8 meses.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-06-13", "end": "2026-06-12"},
            capital_amount=100000,
            evidence_spans={
                "asset_universe": "eth",
                "capital_amount": "100k",
                "strategy_type": "compre eth y lo mantuve",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "compre eth y lo mantuve los ultimos 8 meses con 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload
    assert ready_response.candidate_strategy_draft.date_range != {
        "start": "2025-06-13",
        "end": "2026-06-12",
    }

@pytest.mark.asyncio
async def test_relative_window_semantic_drift_uses_focused_date_window_intent(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Mantener ETH durante los ultimos 8 meses.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range={"start": "2025-06-13", "end": "2026-06-12"},
                capital_amount=100000,
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "ETH",
                    "capital_amount": "100k",
                    "time_window": "los ultimos 8 meses",
                    "strategy_type": "compre eth y lo mantuve",
                },
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="los ultimos 8 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.93,
                    evidence="los ultimos 8 meses",
                ),
                confidence=0.93,
                evidence="los ultimos 8 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="ETH buy-and-hold with $100K.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compre eth y lo mantuve los ultimos 8 meses con 100k",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Mantener ETH durante los ultimos 8 meses.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-06-13", "end": "2026-06-12"},
            capital_amount=100000,
            evidence_spans={
                "asset_universe": "ETH",
                "capital_amount": "100k",
                "time_window": "los ultimos 8 meses",
                "strategy_type": "compre eth y lo mantuve",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "compre eth y lo mantuve los ultimos 8 meses con 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload
    assert ready_response.candidate_strategy_draft.date_range_intent is not None
    assert ready_response.candidate_strategy_draft.date_range_raw_text == (
        "los ultimos 8 meses"
    )

@pytest.mark.asyncio
async def test_unprovenanced_stale_date_range_uses_focused_date_window_intent(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "AAPL":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="los últimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.94,
                    evidence="los últimos 12 meses",
                ),
                confidence=0.94,
                evidence="los últimos 12 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_message = (
        "Compra y mantén AAPL durante los últimos 12 meses "
        "con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=current_message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_message,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=current_message,
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-06-14", "end": "2025-06-14"},
            comparison_baseline="SPY",
            evidence_spans={
                "asset_universe": "AAPL",
                "comparison_baseline": "SPY como referencia",
                "strategy_type": "Compra y mantén",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload
    assert ready_response.candidate_strategy_draft.date_range_intent is not None
    assert ready_response.candidate_strategy_draft.date_range_raw_text == (
        "los últimos 12 meses"
    )


@pytest.mark.asyncio
async def test_unprovenanced_calendar_year_intent_uses_focused_date_window_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="from 2023 to date",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="explicit_range",
                    start="2023-01-01",
                    end="today",
                    anchor="today",
                    confidence=0.95,
                    evidence="from 2023 to date",
                ),
                confidence=0.95,
                evidence="from 2023 to date",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_message = (
        "ok let's test holding AAPL, MSFT and TSLA from 2023 to date with 100k"
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=current_message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_message,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_message,
            asset_universe=["AAPL", "MSFT", "TSLA"],
            asset_class="equity",
            date_range={"start": "2023-01-01", "end": "2023-12-31"},
            date_range_intent=interpreter_module.LLMDateRangeIntent(
                kind="calendar_year",
                year=2023,
            ),
            capital_amount=100000,
            evidence_spans={
                "asset_universe": "AAPL, MSFT and TSLA",
                "capital_amount": "100k",
                "strategy_type": "holding",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2023-01-01",
        "end": date.today().isoformat(),
    }
    assert ready_response.candidate_strategy_draft.date_range_raw_text == (
        "from 2023 to date"
    )


@pytest.mark.asyncio
async def test_raw_date_evidence_does_not_trust_mismatched_calendar_year_intent(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="from 2023 to date",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="explicit_range",
                    start="2023-01-01",
                    end="today",
                    anchor="today",
                    confidence=0.95,
                    evidence="from 2023 to date",
                ),
                confidence=0.95,
                evidence="from 2023 to date",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda _request: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_message = (
        "messy P1 canary: let's hold AAPL MSFT and TSLA from 2023 to date "
        "with 100k, compare defaults are fine"
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=current_message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_message,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_message,
            asset_universe=["AAPL", "MSFT", "TSLA"],
            asset_class="equity",
            date_range={"start": "2023-01-01", "end": "2023-12-31"},
            date_range_raw_text="from 2023 to date",
            date_range_intent=interpreter_module.LLMDateRangeIntent(
                kind="calendar_year",
                year=2023,
                confidence=0.88,
                evidence="from 2023 to date",
            ),
            capital_amount=100000,
            evidence_spans={
                "asset_universe": "AAPL MSFT and TSLA",
                "capital_amount": "100k",
                "date_range": "from 2023 to date",
                "strategy_type": "hold",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2023-01-01",
        "end": date.today().isoformat(),
    }
    assert ready_response.candidate_strategy_draft.date_range_raw_text == (
        "from 2023 to date"
    )


@pytest.mark.asyncio
async def test_missing_date_clarification_uses_focused_date_window_intent(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=True,
                user_goal_summary="Backtest holding ETH.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Mantener ETH.",
                asset_universe=["ETH"],
                asset_class="crypto",
                capital_amount=100000,
                missing_required_fields=["date_range"],
                assistant_response="¿En qué fecha exacta comenzaste?",
                confidence=0.84,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="los ultimos 8 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="los ultimos 8 meses",
                ),
                confidence=0.92,
                evidence="los ultimos 8 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response="¿En qué fecha exacta comenzaste?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compre eth y lo mantuve los ultimos 8 meses con 100k",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Mantener ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "compre eth y lo mantuve los ultimos 8 meses con 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_supported_compare_shape_without_capital_gets_date_window_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "AssetGroundingAudit":
            return interpreter_module.AssetGroundingAudit(
                grounded_symbols=["AAPL"],
                confidence=0.92,
            )
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="los ultimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="los ultimos 12 meses",
                ),
                confidence=0.92,
                evidence="los ultimos 12 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Comparar Apple contra SPY.",
        assistant_response=(
            "¿Qué fecha de finalización prefieres para los últimos 12 meses?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compara apple con spy durante los ultimos 12 meses",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comparar Apple contra SPY.",
            asset_universe=["AAPL"],
            asset_class="equity",
            evidence_spans={"comparison_baseline_evidence": "SPY"},
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "compara apple con spy durante los ultimos 12 meses"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_pending_supported_chip_shape_gets_focused_date_and_benchmark_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="los últimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="los últimos 12 meses",
                ),
                confidence=0.92,
                evidence="los últimos 12 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="AAPL buy-and-hold.",
        assistant_response="Entendido. ¿Qué período quieres usar para AAPL?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
            extra_parameters={
                "language": "es-419",
                "raw_strategy_type": "buy_and_hold",
            },
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            selected_thread_metadata={"requested_field": "date_range"},
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_fresh_supported_chip_shape_repairs_dotted_date_field_path(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                confidence=0.92,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="AAPL buy-and-hold against SPY.",
        assistant_response=(
            "Got it — buy and hold AAPL over the last 12 months with SPY as "
            "the benchmark. What end date should I use for the 12-month window?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
            comparison_baseline="SPY",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
        missing_required_fields=["date_range.end"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_fresh_supported_chip_shape_audits_current_turn_for_omitted_date(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                confidence=0.92,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="AAPL buy-and-hold against SPY.",
        assistant_response=(
            "Got it — buy-and-hold AAPL versus SPY over the past year. "
            "Which 12-month window would you like?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
            comparison_baseline="SPY",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
        missing_required_fields=[],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_live_chip_shape_recovers_omitted_window_and_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                confidence=0.92,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Buy-and-hold AAPL for the last 12 months, benchmarked against SPY."
        ),
        assistant_response=(
            "Got it — buy-and-hold AAPL for the last 12 months, "
            "benchmarked against SPY. To run the test, I just need the "
            "specific end date. What date should mark the end of that "
            "12-month window?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Long-only buy-and-hold investment in AAPL over the last "
                "12 months, benchmarked against SPY."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_supported_clarification_gets_strategy_repair_after_empty_date_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=False,
                confidence=0.72,
                evidence="",
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Buy and hold AAPL over the last 12 months with SPY as "
                    "the benchmark."
                ),
                strategy_type="buy_and_hold",
                strategy_thesis=(
                    "Buy and hold AAPL over the last 12 months with SPY as "
                    "the benchmark."
                ),
                asset_universe=["AAPL"],
                asset_class="equity",
                comparison_baseline="SPY",
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                evidence_spans={
                    "date_range": "last 12 months",
                    "comparison_baseline": "SPY",
                },
                confidence=0.92,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                capital_amount=None,
                capital_role=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Buy-and-hold AAPL for the past 12 months with SPY as the benchmark."
        ),
        assistant_response=(
            "Got it — buy-and-hold AAPL for the past 12 months with SPY as the "
            "benchmark. To run the simulation, what 12-month window would you "
            "like to use?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    ).payload

@pytest.mark.asyncio
async def test_supported_pending_need_label_allows_strategy_repair_after_date_timeout(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            raise TimeoutError("date audit timed out")
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Buy and hold AAPL over the last 12 months with SPY as "
                    "the benchmark."
                ),
                strategy_type="buy_and_hold",
                strategy_thesis=(
                    "Buy and hold AAPL over the last 12 months with SPY as "
                    "the benchmark."
                ),
                asset_universe=["AAPL"],
                asset_class="equity",
                comparison_baseline="SPY",
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                evidence_spans={
                    "date_range": "last 12 months",
                    "comparison_baseline": "SPY",
                },
                confidence=0.92,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                capital_amount=None,
                capital_role=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Buy-and-hold AAPL for the past 12 months with SPY as the benchmark."
        ),
        assistant_response=(
            "You mentioned the last 12 months -- could you give me the exact "
            "start and end dates you'd like to test?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    ).payload

@pytest.mark.asyncio
async def test_live_evidence_spans_window_and_benchmark_repair_to_canonical_fields(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 12 months",
                ),
                confidence=0.92,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Buy-and-hold AAPL vs SPY for the last 12 months.",
        assistant_response=(
            "Got it — buy-and-hold AAPL vs SPY for the last 12 months. "
            "To set the exact window, do you mean the trailing 12 months "
            "from today, or a specific 12-month period?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            extra_parameters={
                "evidence_spans": {
                    "asset": "AAPL",
                    "benchmark": "SPY",
                    "window": "last 12 months",
                    "strategy": "Buy and hold",
                },
                "raw_strategy_type": "buy_and_hold",
            },
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
            evidence="last 12 months",
        )
    )
    assert expected_range is not None
    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_extra_evidence_spans_window_resolve_after_empty_date_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=False,
                confidence=0.1,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Buy-and-hold AAPL vs SPY for the last 12 months.",
        assistant_response="What exact date window should I use?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            extra_parameters={
                "evidence_spans": {
                    "asset": "AAPL",
                    "benchmark": "SPY",
                    "window": "last 12 months",
                    "strategy": "Buy and hold",
                },
                "raw_strategy_type": "buy_and_hold",
            },
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_text("last 12 months")
    assert expected_range is not None
    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_fresh_supported_pending_need_uses_natural_time_after_empty_date_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub(
                "AAPL",
                "equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            )
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
                raw_symbol="SPY",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    evidence="last 12 months",
                ),
                confidence=0.9,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=current_turn,
        assistant_response=(
            "Got it - buy-and-hold AAPL with SPY as the benchmark. "
            "To run the test, I just need the specific 12-month window."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            comparison_baseline="SPY",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
            evidence="last 12 months",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_supported_compare_recovery_normalizes_to_buy_and_hold_contract(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "AssetGroundingAudit":
            return interpreter_module.AssetGroundingAudit(
                grounded_symbols=["AAPL"],
                confidence=0.92,
            )
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.92,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="últimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="últimos 12 meses",
                ),
                confidence=0.92,
                evidence="últimos 12 meses",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
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

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Comparar Apple contra SPY.",
        assistant_response=(
            "¿Qué tipo de comparación te gustaría hacer? Puedo comparar con "
            "comprar y mantener."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compara apple con spy durante los ultimos 12 meses",
            language="es-419",
            strategy_type=None,
            strategy_thesis=(
                "Comparar el rendimiento de Apple (AAPL) frente al S&P 500 (SPY) "
                "durante los últimos 12 meses."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
            extra_parameters={
                "language": "es",
                "evidence_spans": {
                    "date_range_raw_text": "últimos 12 meses",
                    "asset_universe_evidence": "Apple (AAPL)",
                    "comparison_baseline_evidence": "SPY (S&P 500)",
                },
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="Comparar el rendimiento de Apple contra SPY.",
                explanation="Primary interpretation treated a supported comparison as custom logic.",
                simplification_labels=[
                    "Use a supported RSI threshold rule",
                    "Compare with buy and hold",
                    "Use a supported moving-average crossover",
                ],
            )
        ],
        missing_required_fields=["entry_logic", "exit_logic", "date_range"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "compara apple con spy durante los ultimos 12 meses"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "SupportedStrategyCapabilityConflictAudit" in calls
    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"

@pytest.mark.asyncio
async def test_supported_compare_recovery_uses_structured_fallback_when_audit_unavailable(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "AssetGroundingAudit":
            return interpreter_module.AssetGroundingAudit(
                grounded_symbols=["AAPL"],
                confidence=0.92,
            )
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            raise TimeoutError("capability audit unavailable")
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
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

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Buy and hold AAPL with SPY as benchmark.",
        assistant_response=(
            "I can't run raw buy-and-hold directly, but I can compare with "
            "buy and hold."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="Hold AAPL over the last 12 months.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            date_range_raw_text="last 12 months",
            capital_amount=1000,
            comparison_baseline="SPY",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="raw buy-and-hold comparison",
                explanation="Primary interpretation treated supported logic as custom.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "exit_logic"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "SupportedStrategyCapabilityConflictAudit" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    assert ready_response.missing_required_fields == []
    assert (
        "supported_strategy_capability_structured_fallback"
        in ready_response.reason_codes
    )

@pytest.mark.asyncio
async def test_fresh_answer_pending_need_with_missing_date_gets_date_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.92,
                    evidence="last 8 months",
                ),
                confidence=0.92,
                evidence="last 8 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100k.",
        assistant_response=(
            "To run the backtest, I just need the exact start and end dates."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="i bought eth and held it for the last 8 months with 100k",
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="Backtest ETH buy-and-hold over the last 8 months.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
            extra_parameters={
                "language": "en",
                "raw_strategy_type": "buy_and_hold",
            },
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert "FocusedDateWindowExtraction" in calls
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload

@pytest.mark.asyncio
async def test_fresh_supported_pending_need_uses_current_turn_window_and_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        symbol = query.strip().upper()
        if symbol == "AAPL" or query.strip().lower() == "apple":
            return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        if symbol == "SPY":
            return ResolvedAssetStub("SPY", "equity", name="SPDR S&P 500 ETF Trust")
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        if schema_name == "ContextQuestionAudit":
            return interpreter_module.ContextQuestionAudit(
                is_context_question=False,
                confidence=0.8,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 12 months",
                date_range_intent=LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    evidence="last 12 months",
                ),
                confidence=0.9,
                evidence="last 12 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                comparison_baseline="SPY",
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="AAPL buy-and-hold with SPY benchmark.",
        assistant_response=(
            "Got it. What end date should the 12-month window use?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            extra_parameters={
                "raw_strategy_type": "buy_and_hold",
            },
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
            evidence="last 12 months",
        )
    )
    assert expected_range is not None
    assert "FocusedDateWindowExtraction" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.date_range == expected_range.payload
    assert draft.date_range_raw_text == "last 12 months"
    assert draft.comparison_baseline == "SPY"

def test_current_message_run_field_repair_uses_user_language_for_bounded_date_evidence() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "Compra y mantén AAPL de enero de 2024 hasta marzo de 2024 "
        "con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="AAPL buy-and-hold with SPY benchmark.",
        assistant_response="¿Qué fecha de cierre prefieres?",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range_raw_text="enero de 2024 hasta marzo de 2024",
            comparison_baseline="SPY",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    repaired = interpreter_module._response_from_current_message_run_field_contract(
        response=response,
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_text(
        "enero de 2024 hasta marzo de 2024",
        languages=("es",),
    )
    assert expected_range is not None
    assert repaired is not None
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.missing_required_fields == []
    assert repaired.candidate_strategy_draft.date_range == expected_range.payload


def test_current_message_run_field_repair_prefers_explicit_bounded_range_over_mismatched_intent() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "probemos algo medio simple: comprar y mantener AAPL, MSFT y TSLA, "
        "pesos iguales, desde enero 1 2025 hasta junio 5 2026, con 10000 "
        "dolares, comparalo con SPY, sin fees ni deslizamiento"
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=current_turn,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL", "MSFT", "TSLA"],
            asset_class="equity",
            date_range={"start": "2025-01-01", "end": "2025-12-31"},
            date_range_raw_text="desde enero 1 2025 hasta junio 5 2026",
            date_range_intent=LLMDateRangeIntent(
                kind="calendar_year",
                year=2025,
                confidence=0.9,
                evidence="desde enero 1 2025 hasta junio 5 2026",
            ),
            capital_amount=10000,
            comparison_baseline="SPY",
            evidence_spans={
                "date_range": "desde enero 1 2025 hasta junio 5 2026",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    repaired = interpreter_module._response_from_current_message_run_field_contract(
        response=response,
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2026-06-05",
    }
    assert "current_message_run_field_contract_repair" in repaired.reason_codes


@pytest.mark.asyncio
async def test_supported_partial_date_clarification_gets_direct_date_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        if query.strip().upper() != "ETH":
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(
            "ETH",
            "crypto",
            name="Ethereum",
            raw_symbol="ETH/USD",
        )

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=True,
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.93,
                    evidence="last 8 months",
                ),
                confidence=0.93,
                evidence="last 8 months",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(
                capital_amount=100000,
                date_range=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="ETH buy-and-hold with $100K.",
        assistant_response=(
            "Got it — ETH buy-and-hold with $100K. "
            "What date range should I use?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="ETH buy-and-hold with $100K.",
            asset_universe=["ETH"],
            asset_class="crypto",
            capital_amount=100000,
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload
    assert ready_response.candidate_strategy_draft.date_range_raw_text == (
        "last 8 months"
    )
