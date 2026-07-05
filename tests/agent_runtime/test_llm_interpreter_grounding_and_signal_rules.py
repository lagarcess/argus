# ruff: noqa: F403, F405
from tests.agent_runtime._llm_interpreter_common import *


def test_candidate_text_requires_name_or_explicit_symbol_evidence() -> None:
    assert not _candidate_text_supports_resolved_asset(
        "aapl",
        ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
    )
    assert not _candidate_text_supports_resolved_asset(
        "tsla",
        ResolvedAssetStub("TSLA", "equity", name="Tesla Inc."),
    )
    assert _candidate_text_supports_resolved_asset(
        "apple",
        ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
    )
    assert _candidate_text_supports_resolved_asset(
        "AAPL",
        ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
    )
    assert _candidate_text_supports_resolved_asset(
        "$tsla",
        ResolvedAssetStub("TSLA", "equity", name="Tesla Inc."),
    )

def test_candidate_text_does_not_ground_short_lowercase_symbols_without_case_signal() -> None:
    assert not _candidate_text_supports_resolved_asset(
        "me",
        ResolvedAssetStub("ME", "equity", name="23andMe Holding Co."),
    )
    assert _candidate_text_supports_resolved_asset(
        "ME",
        ResolvedAssetStub("ME", "equity", name="23andMe Holding Co."),
    )

def test_candidate_text_keeps_lowercase_action_words_from_becoming_assets() -> None:
    assert not _candidate_text_supports_resolved_asset(
        "test",
        ResolvedAssetStub(
            "TEST",
            "equity",
            name="YieldMax TSLA Performance & Distribution Target 25 ETF",
        ),
    )
    assert not _candidate_text_supports_resolved_asset(
        "want",
        ResolvedAssetStub("WANT", "equity", name="Direxion Daily Consumer ETF"),
    )
    assert _candidate_text_supports_resolved_asset(
        "WANT",
        ResolvedAssetStub("WANT", "equity", name="Direxion Daily Consumer ETF"),
    )

def test_candidate_text_does_not_ground_single_word_from_long_fund_name() -> None:
    assert not _candidate_text_supports_resolved_asset(
        "investment",
        ResolvedAssetStub(
            "APPX",
            "equity",
            name="Investment Managers Series Trust II Tradr 2X Long APP Daily ETF",
        ),
    )
    assert _candidate_text_supports_resolved_asset(
        "apple",
        ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
    )

def test_provider_ticker_mentions_support_lowercase_exact_ticker_evidence() -> None:
    def resolve_candidate(query: str) -> AssetResolution | None:
        normalized = query.strip().upper()
        if normalized == "APPLE":
            asset = ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        elif normalized == "GOOGL":
            asset = ResolvedAssetStub("GOOGL", "equity", name="Alphabet Inc.")
        elif normalized == "QQQ":
            asset = ResolvedAssetStub("QQQ", "equity", name="Invesco QQQ Trust")
        elif normalized == "NU":
            asset = ResolvedAssetStub("NU", "equity", name="Nu Holdings Ltd.")
        else:
            return None
        return AssetResolution(
            status="resolved",
            raw_text=query,
            asset=asset,
            candidates=(asset,),
            provenance=ResolutionProvenance(
                field="asset_universe",
                raw_text=query,
                source="user_mention",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol=asset.canonical_symbol,
                asset_class=asset.asset_class,
                validated_by="provider_catalog",
                confidence="high",
            ),
        )

    mentions = provider_ticker_mentions_from_text(
        "how did apple do with qqq and nu in 2024",
        resolve_candidate=resolve_candidate,
    )

    assert [mention.raw_text for mention in mentions] == ["qqq", "nu"]
    assert [mention.asset.canonical_symbol for mention in mentions] == ["QQQ", "NU"]

    compound_mentions = provider_ticker_mentions_from_text(
        "add Google/GOOGL to the card",
        resolve_candidate=resolve_candidate,
    )

    assert [mention.raw_text for mention in compound_mentions] == ["GOOGL"]
    assert [mention.asset.canonical_symbol for mention in compound_mentions] == [
        "GOOGL"
    ]


@pytest.mark.asyncio
async def test_asset_grounding_keeps_lowercase_provider_ticker_from_messy_turn(
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

    async def fake_json_schema(**kwargs):
        calls.append(kwargs["schema_name"])
        return AssetGroundingAudit(grounded_symbols=[], confidence=0.95)

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "_request_current_turn_has_material_execution_evidence",
        lambda request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Comprar y mantener ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-10-13", "end": "2026-06-13"},
            capital_amount=100000,
        ),
        semantic_turn_act="new_idea",
    )

    audited = await interpreter_module._asset_grounding_audited_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="compra y manten eth ultimos 8 meses 100k",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == []
    assert audited.candidate_strategy_draft.asset_universe == ["ETH"]

def test_extra_provider_asset_benchmark_evidence_requires_grounded_primary_asset() -> None:
    from argus.agent_runtime.benchmark_evidence import (
        current_message_has_extra_provider_asset_for_benchmark,
    )

    def resolution(asset: ResolvedAssetStub, raw_text: str) -> AssetResolution:
        return AssetResolution(
            status="resolved",
            raw_text=raw_text,
            asset=asset,
            candidates=(asset,),
            provenance=ResolutionProvenance(
                field="asset_universe",
                raw_text=raw_text,
                source="user_mention",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol=asset.canonical_symbol,
                asset_class=asset.asset_class,
                validated_by="provider_catalog",
                confidence="high",
            ),
        )

    def resolve_candidate(query: str) -> AssetResolution | None:
        normalized = query.strip().upper()
        if normalized == "QQQ":
            asset = ResolvedAssetStub("QQQ", "equity", name="Invesco QQQ Trust")
            return resolution(asset, query)
        if normalized == "NU":
            asset = ResolvedAssetStub(
                "NU",
                "equity",
                name="Nu Holdings Ltd.",
                raw_symbol="NU",
            )
            return resolution(asset, query)
        return None

    assert current_message_has_extra_provider_asset_for_benchmark(
        LLMStrategyDraft(asset_universe=["AAPL"], asset_class="equity"),
        current_message="apple qqq from the start of 2024",
        resolved_asset_mentions=[
            ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        ],
        resolve_candidate=resolve_candidate,
    )
    assert not current_message_has_extra_provider_asset_for_benchmark(
        LLMStrategyDraft(asset_universe=["APPX"], asset_class="equity"),
        current_message=(
            "lets see what an investment of 500 in nu could have made this "
            "year so far"
        ),
        resolved_asset_mentions=[],
        resolve_candidate=resolve_candidate,
    )

@pytest.mark.asyncio
async def test_ready_run_with_missing_stated_benchmark_uses_fidelity_audit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.llm_interpreter import (
        ExecutableStrategyGroundingAudit,
        StatedRunFieldFidelityAudit,
    )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == "APPLE":
            return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        if normalized in {"AAPL", "QQQ"}:
            return ResolvedAssetStub(normalized, "equity")
        raise ValueError("unsupported_symbol")

    calls: list[str] = []

    async def invoke_stub(*, schema_name: str, **kwargs):
        del kwargs
        calls.append(schema_name)
        if schema_name == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User wants to compare Apple with QQQ.",
                candidate_strategy_draft=LLMStrategyDraft(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Apple.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range={"start": "2024-01-01", "end": "2024-12-31"},
                    comparison_baseline=None,
                ),
                semantic_turn_act="new_idea",
            )
        if schema_name == "ExecutableStrategyGroundingAudit":
            return ExecutableStrategyGroundingAudit(
                outcome="grounded",
                confidence=0.95,
            )
        if schema_name == "AssetGroundingAudit":
            return AssetGroundingAudit(
                grounded_symbols=["AAPL"],
                confidence=0.95,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return StatedRunFieldFidelityAudit(
                comparison_baseline="QQQ",
                confidence=0.95,
            )
        raise AssertionError(f"Unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", invoke_stub)

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "how did apple do against qqq from the start of 2024 through "
                "the end of 2024, simple buy and hold"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )

    assert "StatedRunFieldFidelityAudit" in calls
    assert result is not None
    assert result.candidate_strategy_draft.comparison_baseline == "QQQ"

@pytest.mark.asyncio
async def test_stated_run_field_fidelity_audit_repairs_pending_dca_contribution_role(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, model_name
        calls.append(schema_name)
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model(
                recurring_contribution_amount=200,
                cadence="weekly",
                confidence=0.95,
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User wants to adjust the DCA contribution.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple weekly.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-03-01", "end": "2024-10-31"},
            capital_amount=250,
            cadence="weekly",
            field_provenance={
                "capital_amount": "starting_capital",
                "cadence": "explicit_user",
            },
        ),
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="change contribution to 200 dollars every week",
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={
            "requested_field": "assumption",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert "StatedRunFieldFidelityAudit" in calls
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 200
    assert draft.cadence == "weekly"
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_run_field_fidelity_audit_checks_dca_assumption_replies_with_prior_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, model_name
        calls.append(schema_name)
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model(
                recurring_contribution_amount=200,
                cadence="weekly",
                confidence=0.95,
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User wants to adjust the DCA contribution.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple weekly.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-03-01", "end": "2024-10-31"},
            capital_amount=250,
            cadence="weekly",
            field_provenance={
                "capital_amount": "recurring_contribution",
                "cadence": "explicit_user",
            },
        ),
        semantic_turn_act="answer_pending_need",
        artifact_target="active_confirmation",
    )
    request = InterpretationRequest(
        current_user_message="make the contribution 200 dollars every week",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Buy Apple weekly.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2024-03-01", "end": "2024-10-31"},
                capital_amount=250,
                cadence="weekly",
                extra_parameters={
                    "field_provenance": {
                        "capital_amount": "recurring_contribution",
                        "cadence": "explicit_user",
                    }
                },
            )
        ),
        selected_thread_metadata={
            "requested_field": "assumption",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert "StatedRunFieldFidelityAudit" in calls
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 200
    assert draft.cadence == "weekly"
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes

def test_dca_executable_shape_uses_canonical_dca_contract() -> None:
    assert not _llm_strategy_draft_has_executable_shape(
        LLMStrategyDraft(strategy_type="dca_accumulation", cadence="weekly")
    )
    assert _llm_strategy_draft_has_executable_shape(
        LLMStrategyDraft(
            strategy_type="dca_accumulation",
            capital_amount=250,
            recurring_contribution=250,
            cadence="weekly",
            field_provenance={
                "capital_amount": "recurring_contribution",
                "recurring_contribution": "explicit_user",
                "cadence": "explicit_user",
            },
        )
    )
    assert not _llm_strategy_draft_has_executable_shape(
        LLMStrategyDraft(
            strategy_type="dca_accumulation",
            entry_rule={"type": "rsi_threshold", "threshold": 30},
        )
    )

def test_structured_interpretation_rejects_underfilled_dca_shape() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test recurring NVDA buys.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy NVDA weekly over the last year.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range={"start": "2025-06-13", "end": "2026-06-13"},
            missing_details=[],
        ),
        missing_required_fields=[],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    assert not interpreter_module._structured_interpretation_has_required_shape(
        response,
        request=InterpretationRequest(
            current_user_message="compraba nvidia cada semana ultimo año",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

def test_structured_interpretation_rejects_supported_partial_clarification() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        assistant_response=(
            "You mentioned the last 12 months — could you share the exact "
            "start and end dates you'd like to test?"
        ),
        user_goal_summary=current_turn,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    assert not interpreter_module._structured_interpretation_has_required_shape(
        response,
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

def test_structured_interpretation_rejects_fresh_supported_pending_need_label() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        assistant_response=(
            "You mentioned the last 12 months -- could you give me the exact "
            "start and end dates you'd like to test?"
        ),
        user_goal_summary=current_turn,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )

    assert not interpreter_module._structured_interpretation_has_required_shape(
        response,
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

def test_llm_interpreter_validates_asset_class_with_alpaca_resolver(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        calls.append(symbol)
        return ResolvedAssetStub(
            canonical_symbol=symbol.upper(),
            asset_class="crypto" if symbol.upper() == "BTC" else "equity",
        )

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Backtest Tesla and Bitcoin together.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Backtest Tesla and Bitcoin together.",
            strategy_type="buy_and_hold",
            strategy_thesis="Hold Tesla and Bitcoin together.",
            asset_universe=["tsla", "btc"],
            date_range="last 2 years",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Backtest Tesla and Bitcoin together.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["tsla", "btc"]
    assert result.candidate_strategy_draft.asset_universe == ["TSLA", "BTC"]
    assert result.candidate_strategy_draft.asset_class == "mixed"
    assert result.unsupported_constraints[0].category == "unsupported_asset_mix"
    assert "currency pairs" in result.unsupported_constraints[0].explanation

def test_llm_interpreter_prompt_names_currency_pair_runtime_truth() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt()

    assert "currency pairs" in prompt
    assert "currency pair benchmark is the tested pair itself" in prompt
    assert "Kraken" in prompt

def test_llm_interpreter_prompt_routes_why_result_questions_to_performance_focus() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "why did this result happen" in prompt
    assert "why/how the result happened" in prompt
    assert "why_underperformed" in prompt

def test_llm_interpreter_prompt_names_artifact_target_contract() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "artifact_target" in prompt
    assert "latest_result only when" in prompt
    assert "pending_refinement" in prompt
    assert "do not let a completed result capture unrelated turns" in prompt

def test_llm_interpreter_maps_latest_result_context_to_artifact_target() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    result = interpreter._to_runtime_interpretation(
        LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            user_goal_summary="User asked a standalone market-context question.",
            assistant_response="I can turn that into a testable idea.",
            uses_latest_result_context=False,
            semantic_turn_act="unsupported_request",
        ),
        request=InterpretationRequest(
            current_user_message="what are the top market movers?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_backtest_result_reference=ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="run-1",
                    metadata={"result_card": {"title": "BTC run"}},
                )
            ),
            user=UserState(user_id="u1"),
        ),
    )

    assert result.artifact_target == "none"

def test_llm_interpreter_maps_context_question_focus() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    result = interpreter._to_runtime_interpretation(
        LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="continue",
            user_goal_summary="User asked for broad inflation context.",
            assistant_response=None,
            uses_latest_result_context=False,
            semantic_turn_act="educational_question",
            context_question_focus="macro_context",
            artifact_target="none",
        ),
        request=InterpretationRequest(
            current_user_message="what's happening to inflation right now?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.context_question_focus == "macro_context"
    assert result.artifact_target == "none"
    assert result.capability_question_focus is None

def test_llm_interpreter_prompt_separates_benchmarks_from_asset_universe() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "against spy" in prompt
    assert "with spy as the benchmark" in prompt
    assert "con spy como referencia" in prompt
    assert "do not call this an unsupported direct comparison" in prompt
    assert "comparison_baseline" in prompt
    assert "do not add benchmark symbols to asset_universe" in prompt
    assert "exact start/end dates" in prompt
    assert "never replace them with past year" in prompt

def test_focused_strategy_repair_prompt_preserves_benchmark_comparisons() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    messages = interpreter_module._focused_strategy_extraction_messages(
        InterpretationRequest(
            current_user_message=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        )
    )
    prompt = messages[0].content.lower()

    assert "benchmark" in prompt
    assert "reference" in prompt
    assert "comparison_baseline" in prompt
    assert "one primary asset" in prompt
    assert "executable buy_and_hold" in prompt
    assert "not unsupported" in prompt
    assert "any language" in prompt

def test_stated_run_field_prompt_preserves_reference_benchmarks_semantically() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    request = InterpretationRequest(
        current_user_message=(
            "Compra y mantén AAPL durante los últimos 12 meses "
            "con SPY como referencia."
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=request.current_user_message,
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-14", "end": "2026-06-14"},
        ),
        semantic_turn_act="new_idea",
    )

    messages = interpreter_module._stated_run_field_fidelity_messages(
        response=response,
        request=request,
    )
    prompt = messages[0]["content"].lower()

    assert "language-agnostic" in prompt
    assert "benchmark/reference/baseline/comparison" in prompt
    assert "comparison_baseline" in prompt
    assert "asset_universe" in prompt
    assert "user-stated comparison asset" in prompt

def test_llm_interpreter_prompt_preserves_valuation_as_valid_context() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "valuation and fundamental language is valid investing intent" in prompt
    assert "p/e" in prompt
    assert "concept is financially real" in prompt
    assert "executable historical price/indicator rule" in prompt
    assert "supported proxy" in prompt

def test_llm_interpreter_prompt_understands_crossover_shorthand() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "buy when the 50 crosses the 200" in prompt
    assert "50/200 cross" in prompt
    assert "use sma as the default assumption" in prompt
    assert "do not ask what the buy trigger is" in prompt
    assert "ask only for truly missing run facts" in prompt

def test_llm_interpreter_prompt_uses_provider_date_allowances() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "equity launch history starts in 2016" in prompt
    assert "bounded recent-data window" in prompt
    assert "1h, 4h, or 1d" in prompt
    assert "preserve those requested fields" in prompt
    assert "do not silently widen the timeframe" in prompt
    assert "provider names, candle counts, and provider plumbing" in prompt

def test_llm_interpreter_prompt_contracts_language_agnostic_metadata() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "canonical internal values" in prompt
    assert "date_range_raw_text" in prompt
    assert "date_range_intent" in prompt
    assert "rolling_window" in prompt
    assert "year_to_date" in prompt
    assert "relative lookback anchored to the present" in prompt
    assert "already a complete temporal constraint" in prompt
    assert "evidence_spans" in prompt
    assert "assistant_response in the resolved product language" in prompt
    assert "detected input language is metadata" in prompt
    assert "short, messy, or grammatically imperfect" in prompt

def test_llm_strategy_draft_carries_language_and_evidence_metadata() -> None:
    draft = LLMStrategyDraft(
        raw_user_phrasing="Compra y manten ETH de enero 2024 a marzo 2024.",
        strategy_type="buy_and_hold",
        asset_universe=["ETH"],
        date_range_raw_text="enero 2024 a marzo 2024",
        language="es-419",
        evidence_spans={
            "strategy_type": "Compra y manten",
            "asset_universe": "ETH",
            "date_range": "enero 2024 a marzo 2024",
        },
    )

    strategy = _strategy_from_llm(draft)

    assert draft.language == "es-419"
    assert draft.date_range_raw_text == "enero 2024 a marzo 2024"
    assert strategy.extra_parameters["language"] == "es-419"
    assert (
        strategy.extra_parameters["date_range_raw_text"]
        == "enero 2024 a marzo 2024"
    )
    assert strategy.extra_parameters["evidence_spans"] == {
        "strategy_type": "Compra y manten",
        "asset_universe": "ETH",
        "date_range": "enero 2024 a marzo 2024",
    }

def test_llm_strategy_draft_resolves_canonical_date_range_intent() -> None:
    draft = LLMStrategyDraft(
        raw_user_phrasing="Compra y mantiene AAPL durante los últimos 12 meses.",
        language="es-419",
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        date_range_intent=LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
            evidence="durante los últimos 12 meses",
        ),
        evidence_spans={
            "strategy_type": "Compra y mantiene",
            "asset_universe": "AAPL",
            "date_range": "durante los últimos 12 meses",
        },
    )

    strategy = _strategy_from_llm(draft)

    assert strategy.date_range == {
        "start": date(date.today().year - 1, date.today().month, date.today().day).isoformat(),
        "end": date.today().isoformat(),
    }
    assert strategy.extra_parameters["date_range_intent"] == {
        "kind": "rolling_window",
            "start": None,
            "end": None,
            "day_offset": None,
            "count": 12,
        "unit": "month",
        "anchor": "today",
        "year": None,
        "endpoint": None,
        "confidence": 0.8,
        "evidence": "durante los últimos 12 meses",
    }

def test_llm_strategy_draft_recovers_rolling_intent_from_bounded_evidence() -> None:
    draft = LLMStrategyDraft(
        raw_user_phrasing=(
            "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
        ),
        language="en",
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        comparison_baseline="SPY",
        date_range={"start": "2025-06-15", "end": "2026-06-15"},
        evidence_spans={
            "asset_universe": "AAPL",
            "comparison_baseline": "SPY",
            "window": "last 12 months",
        },
    )

    strategy = _strategy_from_llm(draft)

    assert strategy.extra_parameters["date_range_intent"] == {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.65,
        "evidence": "last 12 months",
    }
    assert strategy.date_range == {
        "start": date(date.today().year - 1, date.today().month, date.today().day).isoformat(),
        "end": date.today().isoformat(),
    }

def test_current_message_run_field_contract_prefers_bounded_date_evidence_span() -> None:
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Compra y manten ETH de enero 2024 a marzo 2024.",
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            date_range={"start": "2023-01-01", "end": "2023-12-31"},
            date_range_raw_text="enero 2024 a marzo 2024",
            language="es-419",
            evidence_spans={"date_range": "enero 2024 a marzo 2024"},
        ),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=InterpretationRequest(
            current_user_message="hazlo",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": "2024-01-01",
        "end": "2024-03-31",
    }

def test_current_message_run_field_contract_uses_canonical_intent_not_phrase_scan() -> None:
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar AAPL.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Compra y mantiene AAPL durante los últimos 12 meses.",
            language="es-419",
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=12,
                unit="month",
                anchor="today",
                evidence="durante los últimos 12 meses",
            ),
            evidence_spans={"date_range": "durante los últimos 12 meses"},
        ),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=InterpretationRequest(
            current_user_message="solo hazlo",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired is not None
    assert repaired.candidate_strategy_draft.date_range == {
        "start": date(date.today().year - 1, date.today().month, date.today().day).isoformat(),
        "end": date.today().isoformat(),
    }

def test_current_message_run_field_contract_recovers_supported_current_turn_window() -> None:
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        assistant_response=(
            "To run the test, I just need the specific 12-month window."
        ),
        user_goal_summary=(
            "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
        ),
        missing_required_fields=["date_range"],
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            language="en",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL with SPY as the benchmark.",
            asset_universe=["AAPL"],
            asset_class="equity",
            comparison_baseline="SPY",
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=12,
                unit="month",
                anchor="today",
                evidence="last 12 months",
            ),
        ),
    )

    repaired = _response_from_current_message_run_field_contract(
        response=response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired is not None
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.missing_required_fields == []
    assert repaired.candidate_strategy_draft.date_range == {
        "start": date(date.today().year - 1, date.today().month, date.today().day).isoformat(),
        "end": date.today().isoformat(),
    }

@pytest.mark.asyncio
async def test_stated_run_field_fidelity_audit_preserves_bare_numeric_capital(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []
    captured_messages: list[object] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del model_name
        calls.append((task, schema_name))
        captured_messages.extend(messages)
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model(capital_amount=100000, confidence=0.95)
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y manten ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-03-31"},
            date_range_raw_text="enero de 2024 hasta marzo de 2024",
            language="es-419",
            evidence_spans={
                "strategy_type": "Compra y manten",
                "asset_universe": "ETH",
                "date_range": "enero de 2024 hasta marzo de 2024",
            },
        ),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == [("field_fidelity", "StatedRunFieldFidelityAudit")]
    assert "con 100000" in str(captured_messages)
    assert "share counts" in captured_messages[0]["content"]
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_starting_capital_recheck_repairs_broad_audit_omission(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []
    captured_messages: dict[str, list[object]] = {}

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del model_name
        calls.append((task, schema_name))
        captured_messages[schema_name] = list(messages)
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model(confidence=0.92)
        if schema_name == "StatedStartingCapitalAudit":
            return schema_model(starting_capital=100000, confidence=0.94)
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-03-31"},
            date_range_raw_text="enero de 2024 hasta marzo de 2024",
            language="es-419",
            evidence_spans={
                "strategy_type": "Compra y mantén",
                "asset_universe": "ETH",
                "date_range": "enero de 2024 hasta marzo de 2024",
            },
        ),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == [
        ("field_fidelity", "StatedRunFieldFidelityAudit"),
        ("field_fidelity", "StatedStartingCapitalAudit"),
    ]
    focused_prompt = captured_messages["StatedStartingCapitalAudit"][0]["content"]
    focused_messages = str(captured_messages["StatedStartingCapitalAudit"])
    assert "focused starting-capital verifier" in focused_prompt
    assert "language-agnostic" in focused_prompt
    assert "100k -> 100000" in focused_prompt
    assert "con 100000" in focused_messages
    assert "Do not copy default assumptions" in focused_prompt
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    assert "stated_run_field_fidelity_audit" in repaired.reason_codes
    assert "stated_starting_capital_recheck" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_starting_capital_recheck_runs_when_broad_audit_fails(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        if schema_name == "StatedRunFieldFidelityAudit":
            raise ValueError("broad audit route failed")
        if schema_name == "StatedStartingCapitalAudit":
            return schema_model(starting_capital=100000, confidence=0.94)
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-03-31"},
            date_range_raw_text="enero de 2024 hasta marzo de 2024",
            language="es-419",
            evidence_spans={
                "strategy_type": "Compra y mantén",
                "asset_universe": "ETH",
                "date_range": "enero de 2024 hasta marzo de 2024",
            },
        ),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == [
        ("field_fidelity", "StatedRunFieldFidelityAudit"),
        ("field_fidelity", "StatedStartingCapitalAudit"),
    ]
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    assert "stated_starting_capital_recheck" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_starting_capital_recheck_runs_when_broad_audit_skips(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []

    async def no_broad_change(**kwargs) -> None:
        del kwargs
        return None

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        if schema_name == "StatedStartingCapitalAudit":
            return schema_model(starting_capital=100000, confidence=0.94)
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        no_broad_change,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            strategy_type="buy_and_hold",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2024-03-31"},
            date_range_raw_text="enero de 2024 hasta marzo de 2024",
            language="es-419",
            evidence_spans={
                "strategy_type": "Compra y mantén",
                "asset_universe": "ETH",
                "date_range": "enero de 2024 hasta marzo de 2024",
            },
        ),
    )

    repaired = await interpreter_module._audit_stated_run_fields(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == [("field_fidelity", "StatedStartingCapitalAudit")]
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    assert "stated_starting_capital_recheck" in repaired.reason_codes

@pytest.mark.asyncio
async def test_stated_starting_capital_recheck_surfaces_draft_prose_evidence(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    captured_messages: list[dict[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, model_name
        assert schema_name == "StatedStartingCapitalAudit"
        captured_messages.extend(messages)
        return schema_model(starting_capital=100000, confidence=0.94)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere probar ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compra y manten eth ultimos 8 meses 100k",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Compra y mantenimiento de Ethereum (ETH) durante los "
                "últimos 8 meses con un capital inicial de 100.000."
            ),
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-10-14", "end": "2026-06-13"},
            date_range_raw_text="ultimos 8 meses",
            language="es-419",
        ),
    )

    repaired = await interpreter_module._audit_stated_starting_capital_fidelity(
        response=response,
        request=InterpretationRequest(
            current_user_message="compra y manten eth ultimos 8 meses 100k",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    prompt_blocks = [message["content"] for message in captured_messages]
    prose_index = next(
        index
        for index, content in enumerate(prompt_blocks)
        if content.startswith("Draft prose evidence JSON:")
    )
    draft_index = next(
        index
        for index, content in enumerate(prompt_blocks)
        if content.startswith("Structured draft JSON:")
    )
    assert prose_index < draft_index
    assert "capital_amount\": null" in prompt_blocks[prose_index]
    assert "capital inicial de 100.000" in prompt_blocks[prose_index]
    assert "compra y manten eth ultimos 8 meses 100k" in prompt_blocks[prose_index]
    assert repaired is not None
    draft = repaired.candidate_strategy_draft
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"

@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_assumption_edit_after_model_failure(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            raise ValueError("general interpreter returned unusable JSON")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible draft starting capital.",
            initial_capital=5000,
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Use $5,000 starting capital",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                )
            ),
            selected_thread_metadata={
                "requested_field": "assumption",
                "last_stage_outcome": "await_user_reply",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls[0] == "LLMInterpretationResponse"
    assert "ArtifactAssumptionEditPlan" in calls
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_benchmark_after_prose_only_response(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized not in {"AAPL", "MSFT", "QQQ", "TSLA"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=False,
                assistant_response=(
                    "I can update the visible confirmation card to use QQQ."
                ),
                user_goal_summary="User asked to change the benchmark.",
                candidate_strategy_draft=LLMStrategyDraft(),
                semantic_turn_act="result_followup",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            comparison_baseline="QQQ",
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-19"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "compare it to QQQ, keep the same assets and dates"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=pending,
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={"strategy": pending.model_dump(mode="json")},
                ),
            ),
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.assistant_response is None
    assert result.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "comparison_baseline": "explicit_user"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_underfilled_active_artifact_assumption_edit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User continued the visible draft.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="Use $5,000 starting capital",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                ),
                semantic_turn_act="answer_pending_need",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible draft starting capital.",
            initial_capital=5000,
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Use $5,000 starting capital",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                )
            ),
            selected_thread_metadata={
                "requested_field": "assumption",
                "last_stage_outcome": "await_user_reply",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls[0] == "LLMInterpretationResponse"
    assert "ArtifactAssumptionEditPlan" in calls
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_asset_append_after_model_failure(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            raise TimeoutError("general interpreter timed out")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User added Microsoft to the visible draft.",
            asset_universe=["MSFT"],
            asset_universe_operation="append",
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Include MSFT too, keep everything else the same.",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Apple.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range={"start": "2025-01-01", "end": "2026-06-05"},
                    capital_amount=10000,
                    timeframe="1D",
                    comparison_baseline="SPY",
                ),
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls[0] == "LLMInterpretationResponse"
    assert "ArtifactAssumptionEditPlan" in calls
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]
    assert result.candidate_strategy_draft.extra_parameters[
        "asset_universe_operation"
    ] == "append"
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "asset_universe": "explicit_user"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_routes_active_confirmation_compound_asset_edit_to_planner(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        aliases = {
            "AAPL": "AAPL",
            "GOOGL": "GOOGL",
            "MICROSOFT": "MSFT",
            "MSFT": "MSFT",
            "TSLA": "TSLA",
        }
        canonical = aliases.get(normalized)
        if canonical is None:
            raise ValueError("invalid_symbol")
        names = {
            "AAPL": "Apple Inc.",
            "GOOGL": "Alphabet Inc.",
            "MSFT": "Microsoft Corporation",
            "TSLA": "Tesla Inc.",
        }
        return ResolvedAssetStub(canonical, "equity", name=names[canonical])

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User edited the visible confirmation.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "Add GOOGL, remove Microsoft, set capital to $75,000, "
                        "date March 1, 2026 to June 5, 2026"
                    ),
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold the selected equities.",
                    asset_universe=["MSFT"],
                    asset_universe_operation="replace",
                    date_range={"start": "2026-03-01", "end": "2026-06-05"},
                    capital_amount=75000,
                    field_provenance={
                        "asset_universe": "explicit_user",
                        "date_range": "explicit_user",
                        "capital_amount": "explicit_user",
                    },
                ),
                semantic_turn_act="answer_pending_need",
            )
        if schema_model.__name__ == "StatedRunFieldFidelityAudit":
            return StatedRunFieldFidelityAudit(confidence=0.9)
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed multiple visible assumptions.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="add",
                    target="asset",
                    symbols=["GOOGL"],
                ),
                artifact_edit_planner.EditOperation(
                    op="remove",
                    target="asset",
                    symbols=["Microsoft"],
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=75000,
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range",
                        start="2026-03-01",
                        end="2026-06-05",
                        confidence=0.95,
                        evidence="March 1, 2026 to June 5, 2026",
                    ),
                ),
            ],
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    active_strategy = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-30"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "Add GOOGL, remove Microsoft, set capital to $75,000, "
                "date March 1, 2026 to June 5, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={
                        "confirmation_payload": {
                            "strategy": active_strategy.model_dump(mode="json"),
                            "launch_payload": {
                                "strategy_type": "buy_and_hold",
                                "symbols": ["AAPL", "MSFT", "TSLA"],
                                "asset_class": "equity",
                                "date_range": {
                                    "start": "2026-01-01",
                                    "end": "2026-06-30",
                                },
                                "capital_amount": 100000,
                                "benchmark_symbol": "SPY",
                            },
                        }
                    },
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls[:2] == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "TSLA",
        "GOOGL",
    ]
    assert result.candidate_strategy_draft.capital_amount == 75000
    assert result.candidate_strategy_draft.date_range == {
        "start": "2026-03-01",
        "end": "2026-06-05",
    }
    assert result.candidate_strategy_draft.extra_parameters[
        "date_range_intent"
    ] == {
        "kind": "explicit_range",
        "start": "2026-03-01",
        "end": "2026-06-05",
        "day_offset": None,
        "count": None,
        "unit": None,
        "anchor": "today",
        "year": None,
        "endpoint": None,
        "confidence": 0.95,
        "evidence": "March 1, 2026 to June 5, 2026",
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_routes_messy_scalar_asset_edit_to_planner(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        aliases = {
            "AAPL": "AAPL",
            "MICROSOFT": "MSFT",
            "TSLA": "TSLA",
            "GOOGL": "GOOGL",
        }
        canonical = aliases.get(normalized)
        if canonical is None:
            raise ValueError("invalid_symbol")
        names = {
            "AAPL": "Apple Inc.",
            "GOOGL": "Alphabet Inc.",
            "MSFT": "Microsoft Corporation",
            "TSLA": "Tesla Inc.",
        }
        return ResolvedAssetStub(canonical, "equity", name=names[canonical])

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User edited the visible confirmation.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "ok tweak the card: add Google/GOOGL, ditch Microsoft, "
                        "make cash seventy five grand, dates 3/1/26 thru june 5 2026"
                    ),
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold the selected equities.",
                    date_range={"start": "2026-03-01", "end": "2026-06-05"},
                    capital_amount=75000,
                    field_provenance={
                        "date_range": "explicit_user",
                        "capital_amount": "explicit_user",
                    },
                ),
                semantic_turn_act="answer_pending_need",
            )
        if schema_model.__name__ == "StatedRunFieldFidelityAudit":
            return StatedRunFieldFidelityAudit(confidence=0.9)
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed multiple visible assumptions.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="add",
                    target="asset",
                    symbols=["Google/GOOGL"],
                ),
                artifact_edit_planner.EditOperation(
                    op="remove",
                    target="asset",
                    symbols=["Microsoft"],
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=75000,
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range",
                        start="2026-03-01",
                        end="2026-06-05",
                        confidence=0.95,
                        evidence="3/1/26 thru june 5 2026",
                    ),
                ),
            ],
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    active_strategy = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-30"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "ok tweak the card: add Google/GOOGL, ditch Microsoft, "
                "make cash seventy five grand, dates 3/1/26 thru june 5 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={
                        "confirmation_payload": {
                            "strategy": active_strategy.model_dump(mode="json"),
                            "launch_payload": {
                                "strategy_type": "buy_and_hold",
                                "symbols": ["AAPL", "MSFT", "TSLA"],
                                "asset_class": "equity",
                                "date_range": {
                                    "start": "2026-01-01",
                                    "end": "2026-06-30",
                                },
                                "capital_amount": 100000,
                                "benchmark_symbol": "SPY",
                            },
                        }
                    },
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "TSLA",
        "GOOGL",
    ]
    assert result.candidate_strategy_draft.capital_amount == 75000
    assert result.candidate_strategy_draft.date_range == {
        "start": "2026-03-01",
        "end": "2026-06-05",
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_routes_lowercase_ticker_asset_edit_to_planner(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        aliases = {
            "AAPL": "AAPL",
            "GOOGL": "GOOGL",
            "MSFT": "MSFT",
            "TSLA": "TSLA",
        }
        canonical = aliases.get(normalized)
        if canonical is None:
            raise ValueError("invalid_symbol")
        names = {
            "AAPL": "Apple Inc.",
            "GOOGL": "Alphabet Inc.",
            "MSFT": "Microsoft Corporation",
            "TSLA": "Tesla Inc.",
        }
        return ResolvedAssetStub(canonical, "equity", name=names[canonical])

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User edited the visible confirmation.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "can you add googl, remove msft, and keep it at 75k?"
                    ),
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold the selected equities.",
                    capital_amount=75000,
                    field_provenance={"capital_amount": "explicit_user"},
                ),
                semantic_turn_act="answer_pending_need",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed multiple visible assumptions.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="add",
                    target="asset",
                    symbols=["googl"],
                ),
                artifact_edit_planner.EditOperation(
                    op="remove",
                    target="asset",
                    symbols=["msft"],
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="capital",
                    number=75000,
                ),
            ],
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    active_strategy = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-30"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "can you add googl, remove msft, and keep it at 75k?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={
                        "confirmation_payload": {
                            "strategy": active_strategy.model_dump(mode="json"),
                            "launch_payload": {
                                "strategy_type": "buy_and_hold",
                                "symbols": ["AAPL", "MSFT", "TSLA"],
                                "asset_class": "equity",
                                "date_range": {
                                    "start": "2026-01-01",
                                    "end": "2026-06-30",
                                },
                                "capital_amount": 100000,
                                "benchmark_symbol": "SPY",
                            },
                        }
                    },
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "TSLA",
        "GOOGL",
    ]
    assert result.candidate_strategy_draft.capital_amount == 75000
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_allows_rsi_threshold_edit_from_active_confirmation_payload(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="User wants to edit the RSI thresholds.",
                candidate_strategy_draft=LLMStrategyDraft(),
                assistant_response="I can change those thresholds on the card.",
                semantic_turn_act="educational_question",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed RSI thresholds on the visible card.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="indicator_entry_threshold",
                    number=20,
                ),
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="indicator_exit_threshold",
                    number=60,
                ),
            ],
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    active_strategy = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Buy TSLA when RSI is oversold and exit when overbought.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=1000,
        comparison_baseline="SPY",
        entry_logic="Buy when RSI(14) drops to 30 or below.",
        exit_logic="Sell when RSI(14) rises to 70 or above.",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 14,
                "entry_threshold": 30,
                "exit_threshold": 70,
            },
        },
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message=(
                "Change the RSI entry threshold to 20 and exit threshold to 60"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={
                        "confirmation_payload": {
                            "strategy": active_strategy.model_dump(mode="json"),
                            "launch_payload": {
                                "strategy_type": "indicator_threshold",
                                "symbols": ["TSLA"],
                                "asset_class": "equity",
                                "date_range": {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                },
                                "capital_amount": 1000,
                                "benchmark_symbol": "SPY",
                                "indicator": "rsi",
                                "indicator_period": 14,
                                "entry_threshold": 30,
                                "exit_threshold": 70,
                            },
                        }
                    },
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    parameters = result.candidate_strategy_draft.extra_parameters[
        "indicator_parameters"
    ]
    assert parameters["indicator"] == "rsi"
    assert parameters["entry_threshold"] == 20.0
    assert parameters["exit_threshold"] == 60.0
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_rejects_rsi_threshold_edit_on_buy_hold_card(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "_response_can_skip_optional_runtime_readiness_audits",
        lambda *args, **kwargs: True,
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="User wants to edit RSI thresholds.",
                candidate_strategy_draft=LLMStrategyDraft(),
                assistant_response="I can change RSI thresholds on an RSI card.",
                semantic_turn_act="educational_question",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed RSI thresholds on the visible card.",
            operations=[
                artifact_edit_planner.EditOperation(
                    op="set",
                    target="indicator_entry_threshold",
                    number=20,
                ),
            ],
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    active_strategy = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold TSLA.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=1000,
        comparison_baseline="SPY",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Change the RSI entry threshold to 20",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                    metadata={
                        "confirmation_payload": {
                            "strategy": active_strategy.model_dump(mode="json"),
                            "launch_payload": {
                                "strategy_type": "buy_and_hold",
                                "symbols": ["TSLA"],
                                "asset_class": "equity",
                                "date_range": {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                },
                                "capital_amount": 1000,
                                "benchmark_symbol": "SPY",
                            },
                        }
                    },
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent != "backtest_execution"
    assert result.requires_clarification
    assert result.candidate_strategy_draft.strategy_type != "indicator_threshold"
    assert "indicator_parameters" not in result.candidate_strategy_draft.extra_parameters


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_benchmark_edit_after_model_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="User might want a QQQ comparison.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="compare it to QQQ",
                    asset_universe=["QQQ"],
                    asset_class="equity",
                ),
                assistant_response=(
                    "Use the card controls to change the benchmark to QQQ."
                ),
                semantic_turn_act="educational_question",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            comparison_baseline="QQQ",
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="compare it to QQQ, keep the same assets and dates",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
                    asset_universe=["AAPL", "MSFT", "TSLA"],
                    asset_class="equity",
                    date_range={"start": "2023-01-01", "end": "today"},
                    capital_amount=100000,
                    timeframe="1D",
                    comparison_baseline="SPY",
                ),
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls[0] == "LLMInterpretationResponse"
    assert "ArtifactAssumptionEditPlan" in calls
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.asset_universe == []
    assert result.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "comparison_baseline": "explicit_user"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_benchmark_edit_when_model_restates_prior_setup(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User continued the visible draft.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "compare it to QQQ, keep the same assets and dates"
                    ),
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
                    asset_universe=["AAPL", "MSFT", "TSLA"],
                    asset_class="equity",
                    date_range={"start": "2023-01-01", "end": "today"},
                    capital_amount=100000,
                    timeframe="1D",
                    comparison_baseline="SPY",
                ),
                semantic_turn_act="refine_current_idea",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            comparison_baseline="QQQ",
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="compare it to QQQ, keep the same assets and dates",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
                    asset_universe=["AAPL", "MSFT", "TSLA"],
                    asset_class="equity",
                    date_range={"start": "2023-01-01", "end": "today"},
                    capital_amount=100000,
                    timeframe="1D",
                    comparison_baseline="SPY",
                ),
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.asset_universe == []
    assert result.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "comparison_baseline": "explicit_user"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_asset_operation_when_model_keeps_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="refine",
                requires_clarification=False,
                user_goal_summary="El usuario agregó dos activos.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="agrega GOOGL y NVDA",
                    strategy_type="buy_and_hold",
                    asset_universe=["GOOGL", "NVDA"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                    field_provenance={
                        "asset_universe": "explicit_user",
                        "comparison_baseline": "explicit_user",
                    },
                ),
                semantic_turn_act="refine_current_idea",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="El usuario agregó dos activos.",
            asset_universe=["GOOGL", "NVDA"],
            asset_universe_operation="append",
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="agrega GOOGL y NVDA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
                    asset_universe=["AAPL", "MSFT", "TSLA"],
                    asset_class="equity",
                    date_range={"start": "2023-01-01", "end": "2026-06-19"},
                    capital_amount=100000,
                    timeframe="1D",
                    comparison_baseline="QQQ",
                ),
                active_confirmation_reference=ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="confirmation-1",
                    artifact_status="active",
                ),
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1", language_preference="es-419"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.asset_universe == ["GOOGL", "NVDA"]
    assert result.candidate_strategy_draft.extra_parameters[
        "asset_universe_operation"
    ] == "append"
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "asset_universe": "explicit_user"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_artifact_assumption_edit_planner_supports_dca_recurring_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible recurring contribution.",
            recurring_contribution_amount=200,
            cadence="weekly",
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await artifact_edit_planner.plan_artifact_assumption_edit(
        current_user_message="make the contribution 200 dollars every week",
        prior_strategy={
            "strategy_type": "dca_accumulation",
            "asset_universe": ["AAPL"],
            "date_range": {"start": "2024-03-01", "end": "2024-10-31"},
            "capital_amount": 250,
            "cadence": "weekly",
        },
        active_confirmation=None,
        preferred_model="test-model",
    )

    assert plan is not None
    assert plan.recurring_contribution_amount == 200
    assert plan.cadence == "weekly"


@pytest.mark.asyncio
async def test_artifact_assumption_edit_planner_supports_asset_replace(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User replaced the visible traded assets.",
            asset_universe=["AMD", "INTC"],
            asset_universe_operation="replace",
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await artifact_edit_planner.plan_artifact_assumption_edit(
        current_user_message="reemplázalas con AMD e INTC",
        prior_strategy={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT"],
            "date_range": {"start": "2024-01-01", "end": "today"},
        },
        active_confirmation=None,
        preferred_model="test-model",
    )

    assert plan is not None
    assert plan.asset_universe == ["AMD", "INTC"]
    assert plan.asset_universe_operation == "replace"


@pytest.mark.asyncio
async def test_artifact_assumption_edit_planner_rejects_asset_edit_without_operation(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible traded assets.",
            asset_universe=["GOOGL", "NVDA"],
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await artifact_edit_planner.plan_artifact_assumption_edit(
        current_user_message="add GOOGL and NVDA",
        prior_strategy={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT", "TSLA"],
            "comparison_baseline": "QQQ",
            "date_range": {"start": "2023-01-01", "end": "today"},
        },
        active_confirmation=None,
        preferred_model="test-model",
    )

    assert plan is None


@pytest.mark.asyncio
async def test_artifact_assumption_edit_planner_allows_same_assets_without_operation(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            asset_universe=["TSLA", "AAPL", "MSFT"],
            comparison_baseline="QQQ",
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await artifact_edit_planner.plan_artifact_assumption_edit(
        current_user_message="compare the same setup to QQQ",
        prior_strategy={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT", "TSLA"],
            "comparison_baseline": "SPY",
            "date_range": {"start": "2023-01-01", "end": "today"},
        },
        active_confirmation=None,
        preferred_model="test-model",
    )

    assert plan is not None
    assert plan.comparison_baseline == "QQQ"


@pytest.mark.asyncio
async def test_artifact_assumption_edit_planner_supports_benchmark_edit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            comparison_baseline="QQQ",
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await artifact_edit_planner.plan_artifact_assumption_edit(
        current_user_message="compare it to QQQ",
        prior_strategy={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL", "MSFT", "TSLA"],
            "comparison_baseline": "SPY",
            "date_range": {"start": "2023-01-01", "end": "today"},
        },
        active_confirmation=None,
        preferred_model="test-model",
    )

    assert plan is not None
    assert plan.comparison_baseline == "QQQ"


def test_artifact_assumption_edit_plan_maps_dca_recurring_contribution() -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    plan = artifact_edit_planner.ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        user_goal_summary="User changed the visible recurring contribution.",
        recurring_contribution_amount=200,
        cadence="weekly",
        confidence=0.91,
    )

    response = interpreter_module._response_from_artifact_assumption_edit_plan(
        plan=plan,
        request=InterpretationRequest(
            current_user_message="make the contribution 200 dollars every week",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Buy Apple weekly.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range={"start": "2024-03-01", "end": "2024-10-31"},
                    capital_amount=250,
                    cadence="weekly",
                )
            ),
            selected_thread_metadata={
                "requested_field": "assumption",
                "last_stage_outcome": "await_user_reply",
            },
            user=UserState(user_id="u1"),
        ),
    )

    draft = response.candidate_strategy_draft
    assert draft.capital_amount == 200
    assert draft.recurring_contribution == 200
    assert draft.cadence == "weekly"
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["recurring_contribution"] == "recurring_contribution"
    assert draft.field_provenance["cadence"] == "explicit_user"
    assert draft.extra_parameters["recurring_contribution"] == 200
    assert draft.extra_parameters["recurring_cadence"] == "weekly"


def test_artifact_assumption_edit_plan_maps_asset_operation() -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    plan = artifact_edit_planner.ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        user_goal_summary="User added Microsoft to the visible draft.",
        asset_universe=["MSFT"],
        asset_universe_operation="append",
        confidence=0.91,
    )

    response = interpreter_module._response_from_artifact_assumption_edit_plan(
        plan=plan,
        request=InterpretationRequest(
            current_user_message="agrega MSFT",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range={"start": "2024-01-01", "end": "today"},
                )
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        ),
    )

    draft = response.candidate_strategy_draft
    assert draft.asset_universe == ["MSFT"]
    assert draft.extra_parameters["asset_universe_operation"] == "append"
    assert draft.field_provenance == {"asset_universe": "explicit_user"}


def test_artifact_assumption_edit_plan_maps_benchmark() -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    plan = artifact_edit_planner.ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        user_goal_summary="User changed the visible benchmark.",
        comparison_baseline="QQQ",
        confidence=0.91,
    )

    response = interpreter_module._response_from_artifact_assumption_edit_plan(
        plan=plan,
        request=InterpretationRequest(
            current_user_message="compare it to QQQ",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT", "TSLA"],
                    asset_class="equity",
                    date_range={"start": "2023-01-01", "end": "today"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        ),
    )

    draft = response.candidate_strategy_draft
    assert draft.asset_universe == []
    assert draft.comparison_baseline == "QQQ"
    assert draft.field_provenance == {"comparison_baseline": "explicit_user"}


def test_artifact_assumption_edit_plan_applies_compound_operations() -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent

    # The canonical failing case: add an asset AND change the date in one turn.
    plan = artifact_edit_planner.ArtifactAssumptionEditPlan(
        outcome="ready_to_confirm",
        user_goal_summary="User added AMZN and moved the start date.",
        operations=[
            artifact_edit_planner.EditOperation(
                op="add", target="asset", symbols=["AMZN"]
            ),
            artifact_edit_planner.EditOperation(
                op="set",
                target="date_window",
                date_window=LLMDateRangeIntent(
                    kind="rolling_window", count=12, unit="month"
                ),
            ),
        ],
        confidence=0.9,
    )

    response = interpreter_module._response_from_artifact_assumption_edit_plan(
        plan=plan,
        request=InterpretationRequest(
            current_user_message="add AMZN and use the last 12 months",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range={"start": "2024-01-01", "end": "today"},
                )
            ),
            selected_thread_metadata={},
            user=UserState(user_id="u1"),
        ),
    )

    draft = response.candidate_strategy_draft
    # asset added to the current set, not replacing it or dropping the date
    assert draft.asset_universe == ["AAPL", "AMZN"]
    assert draft.asset_universe_operation == "replace"
    assert draft.date_range is not None
    assert draft.date_range_intent is not None
    assert draft.field_provenance["asset_universe"] == "explicit_user"
    assert draft.field_provenance["date_range"] == "explicit_user"


def test_strategy_from_llm_preserves_asset_operation_in_extra_parameters() -> None:
    strategy = _strategy_from_llm(
        LLMStrategyDraft(
            asset_universe=["MSFT"],
            asset_universe_operation="append",
        )
    )

    assert strategy.asset_universe == ["MSFT"]
    assert strategy.extra_parameters["asset_universe_operation"] == "append"


def test_signal_rule_plan_promotes_macd_crossover_to_ready_rule_spec() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="Test Bitcoin with a MACD crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="ok run the macd crossover only",
            strategy_type="signal_strategy",
            strategy_thesis="Test Bitcoin when MACD turns bullish.",
            asset_universe=["BTC"],
            date_range="last 6 months",
            entry_logic="MACD crosses above its signal line",
        ),
        assistant_response="I need a more specific rule.",
    )
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                    "operator": "cross_above",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                    "operator": "cross_below",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                }
            ]
        },
    }

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="ready_to_confirm",
            user_goal_summary="Test Bitcoin with a MACD crossover.",
            entry_logic="MACD(12,26,9) crosses above signal",
            exit_logic="MACD(12,26,9) crosses below signal",
            rule_spec=rule_spec,
        ),
    )

    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert repaired.candidate_strategy_draft.entry_logic == (
        "MACD(12,26,9) crosses above signal"
    )
    assert "signal_rule_plan_repair" in repaired.reason_codes

def test_signal_rule_plan_ready_drops_unplanned_risk_rules() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_above",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_below",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
    }
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Nvidia with a 50/200 SMA crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="signal_strategy",
            strategy_thesis="Test Nvidia with a 50/200 SMA crossover.",
            asset_universe=["NVDA"],
            date_range="last 1 year",
            risk_rules=[LLMRiskRule(type="max_drawdown", value_pct=0.2)],
        ),
    )

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="ready_to_confirm",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            rule_spec=rule_spec,
        ),
    )

    assert repaired.intent == "backtest_execution"
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert repaired.candidate_strategy_draft.risk_rules == []

def test_signal_rule_plan_draft_only_routes_to_unsupported_recovery() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple when news sentiment turns positive.",
            strategy_type="signal_strategy",
            strategy_thesis="Use news sentiment as the Apple entry trigger.",
            asset_universe=["AAPL"],
            date_range="last 1 year",
            entry_logic="news sentiment turns positive",
        ),
    )

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="draft_only",
            assistant_response="Sentiment/news signals are not executable yet.",
        ),
    )

    assert repaired.intent == "unsupported_or_out_of_scope"
    assert repaired.semantic_turn_act == "unsupported_request"
    assert repaired.missing_required_fields == []
    assert repaired.candidate_strategy_draft.strategy_type is None
    assert repaired.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert "Sentiment/news" in repaired.unsupported_constraints[0].explanation
    assert "signal_rule_plan_draft_only" in repaired.reason_codes

@pytest.mark.asyncio
async def test_supported_signal_rule_recovery_rescues_underfilled_ma_crossover(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 50,
                    },
                    "operator": "cross_above",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 200,
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 50,
                    },
                    "operator": "cross_below",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 200,
                    },
                }
            ]
        },
    }

    async def plan_stub(**kwargs):
        candidate = kwargs["candidate_strategy"]
        assert candidate["strategy_type"] == "signal_strategy"
        return SignalRulePlan(
            outcome="ready_to_confirm",
            user_goal_summary="Test NVDA with a 50/200 SMA crossover.",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            rule_spec=rule_spec,
        )

    monkeypatch.setattr(interpreter_module, "repair_signal_rule_plan", plan_stub)

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Nvidia with a Golden Cross strategy.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Test Nvidia when the 50-day moving average crosses above "
                "the 200-day moving average over the last year."
            ),
            strategy_thesis="Use a Golden Cross strategy on NVDA.",
            asset_universe=["NVDA"],
            date_range="last 1 year",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="Golden Cross strategy",
                explanation="This rule is not executable yet.",
            )
        ],
    )

    repaired = await _recover_supported_signal_rule_from_draft_if_needed(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Test Nvidia when the 50-day moving average crosses above "
                "the 200-day moving average over the last year."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired is not None
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.unsupported_constraints == []
    assert repaired.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert (
        "supported_signal_rule_contract_recovery" in repaired.reason_codes
    )

def test_structured_ma_crossover_is_executable_without_text_parser() -> None:
    draft = LLMStrategyDraft(
        strategy_type="signal_strategy",
        strategy_thesis="Test Nvidia with a 50/200 moving-average crossover.",
        asset_universe=["NVDA"],
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
    )

    assert _llm_strategy_draft_has_executable_shape(draft)

@pytest.mark.asyncio
async def test_money_only_underfilled_strategy_uses_supported_rule_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        if symbol.lower() == "tesla":
            return ResolvedAssetStub("TSLA", "equity", "Tesla Inc.", "TSLA")
        raise ValueError("invalid_symbol")

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del kwargs
        assert "January 2022" in request.current_user_message
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.date_range = {
            "start": "2022-01-01",
            "end": "today",
        }
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    async def focused_extraction_stub(**kwargs):
        assert kwargs["schema_model"] is FocusedStrategyExtraction
        assert kwargs["schema_name"] == "FocusedStrategyExtraction"
        return _tsla_50_200_focused_extraction()

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        resolve_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        focused_extraction_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test a 50/200 crossover on Tesla.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_thesis=(
                "Backtest a bullish SMA 50/200 crossover on Tesla from January "
                "2022 to today with $10,000 capital."
            ),
            capital_amount=10000,
        ),
        assistant_response=(
            "That specific crossover logic is not directly executable yet."
        ),
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = repaired.candidate_strategy_draft
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert "focused_strategy_extraction_repair" in repaired.reason_codes
    assert draft.asset_universe == ["TSLA"]
    assert draft.date_range == {
        "start": "2022-01-01",
        "end": date.today().isoformat(),
    }
    assert draft.capital_amount == 10000
    assert draft.strategy_type == "signal_strategy"
    assert draft.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    assert draft.exit_logic

@pytest.mark.asyncio
async def test_plain_50_200_crossover_does_not_fall_through_to_unsupported_copy(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime import signal_rule_repair as repair_module

    async def fail_if_model_called(**kwargs):
        raise AssertionError("plain 50/200 crossover should use supported rule grammar")

    async def focused_extraction_stub(**kwargs):
        assert kwargs["schema_model"] is FocusedStrategyExtraction
        assert kwargs["schema_name"] == "FocusedStrategyExtraction"
        return _tsla_50_200_focused_extraction()

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        if symbol.lower() == "tesla":
            return ResolvedAssetStub("TSLA", "equity", "Tesla Inc.", "TSLA")
        raise ValueError("invalid_symbol")

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del kwargs
        assert "January 2022" in request.current_user_message
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.date_range = {
            "start": "2022-01-01",
            "end": "today",
        }
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    monkeypatch.setattr(
        repair_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        focused_extraction_stub,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User asked for a 50/200 crossover test on Tesla.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_thesis=(
                "The user wants to backtest a moving average crossover strategy "
                "on Tesla stock from January 2022 to today with a $10,000 capital."
            ),
            capital_amount=10000,
        ),
        assistant_response=(
            "I can't run a full 50/200 moving-average crossover yet."
        ),
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = repaired.candidate_strategy_draft
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert "focused_strategy_extraction_repair" in repaired.reason_codes
    assert draft.strategy_type == "signal_strategy"
    assert draft.asset_universe == ["TSLA"]
    assert draft.asset_class == "equity"
    assert draft.date_range == {
        "start": "2022-01-01",
        "end": date.today().isoformat(),
    }
    assert draft.capital_amount == 10000
    assert draft.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    assert draft.exit_logic

@pytest.mark.asyncio
async def test_structured_signal_draft_canonicalizes_interpreter_asset(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime import signal_rule_repair as repair_module

    async def fail_if_model_called(**kwargs):
        del kwargs
        raise AssertionError("asset canonicalization should not need a model")

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        if symbol.lower() in {"tesla", "tsla"}:
            return ResolvedAssetStub("TSLA", "equity", "Tesla Inc.", "TSLA")
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    monkeypatch.setattr(
        repair_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=(
            "Backtest a 50/200 moving-average crossover for Tesla."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="signal_strategy",
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_thesis=(
                "Backtest a moving-average crossover strategy for Tesla (TSLA) "
                "where entry occurs when the 50-day SMA crosses above the "
                "200-day SMA between January 2022 and today, starting with "
                "$10,000 capital."
            ),
            asset_universe=["TSLA"],
            date_range={"start": "2022-01-01", "end": "today"},
            capital_amount=10000,
            entry_rule={
                "type": "moving_average_crossover",
                "direction": "bullish",
                "fast_period": 50,
                "slow_period": 200,
                "fast_indicator": "sma",
                "slow_indicator": "sma",
            },
            exit_rule={
                "type": "moving_average_crossover",
                "direction": "bearish",
                "fast_period": 50,
                "slow_period": 200,
                "fast_indicator": "sma",
                "slow_indicator": "sma",
            },
        ),
        assistant_response=None,
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = repaired.candidate_strategy_draft
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.missing_required_fields == []
    assert "provider_catalog_asset_recovery" not in repaired.reason_codes
    assert draft.asset_universe == ["TSLA"]
    assert draft.asset_class == "equity"
    assert draft.entry_rule and draft.exit_rule

@pytest.mark.asyncio
async def test_structured_signal_draft_rejects_catalog_matches_not_supported_by_user_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime import signal_rule_repair as repair_module

    async def fail_if_model_called(**kwargs):
        del kwargs
        raise AssertionError("catalog-backed asset filtering should not need a model")

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        # Simulates a permissive provider catalog: any noisy phrase could resolve
        # to a real asset, but recovery must only accept assets grounded in the
        # user's actual words.
        compact = "".join(char for char in str(symbol).upper() if char.isalnum())
        if compact == "MA":
            return ResolvedAssetStub("MA", "equity", "Mastercard Incorporated", "MA")
        provider_symbol = compact[:4] or "NOPE"
        return ResolvedAssetStub(
            provider_symbol,
            "equity",
            "Unrelated Corp",
            provider_symbol,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    monkeypatch.setattr(
        repair_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Backtest a 50/200 moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="signal_strategy",
            raw_user_phrasing="buy when the 50 crosses the 200",
            strategy_thesis=(
                "Buy when the short-term trend (50-day MA) crosses above "
                "the long-term trend (200-day MA)."
            ),
            date_range={"start": "2025-01-01", "end": "2025-12-31"},
            entry_rule={
                "type": "moving_average_crossover",
                "direction": "bullish",
                "fast_period": 50,
                "slow_period": 200,
                "fast_indicator": "sma",
                "slow_indicator": "sma",
            },
            exit_rule={
                "type": "moving_average_crossover",
                "direction": "bearish",
                "fast_period": 50,
                "slow_period": 200,
                "fast_indicator": "sma",
                "slow_indicator": "sma",
            },
        ),
        missing_required_fields=["asset_universe"],
        assistant_response="Which asset should I test?",
    )

    repaired = interpreter_module._augment_strategy_assets_from_resolvable_context(
        response=response,
        request=InterpretationRequest(
            current_user_message="buy when the 50 crosses the 200",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = repaired.candidate_strategy_draft
    assert draft.asset_universe == []
    assert draft.asset_class is None
    assert "asset_universe" in repaired.missing_required_fields
    assert "provider_catalog_asset_recovery" not in repaired.reason_codes

@pytest.mark.asyncio
async def test_unsupported_supported_rule_classification_gets_signal_rule_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        if symbol.lower() in {"tesla", "tsla"}:
            return ResolvedAssetStub("TSLA", "equity", "Tesla Inc.", "TSLA")
        raise ValueError("invalid_symbol")

    async def plan_stub(**kwargs):
        del kwargs
        calls.append("signal_rule_plan")
        plan = _sma_50_200_crossover_plan(
            strategy_thesis="Test Tesla with a 50/200 moving-average crossover."
        )
        return plan.model_copy(update={"asset_universe": ["Tesla"]})

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del kwargs
        calls.append("field_fidelity_audit")
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.date_range = {
            "start": "2022-01-01",
            "end": "today",
        }
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "repair_signal_rule_plan", plan_stub)
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User asked for a 50/200 crossover test on Tesla.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_thesis="Test Tesla with a 50/200 crossover.",
            capital_amount=10000,
        ),
        assistant_response="I can't run a 50/200 crossover directly yet.",
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="50/200 crossover",
                explanation="This rule is not executable yet.",
            )
        ],
        semantic_turn_act="unsupported_request",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = repaired.candidate_strategy_draft
    assert calls == ["signal_rule_plan", "field_fidelity_audit"]
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.unsupported_constraints == []
    assert draft.strategy_type == "signal_strategy"
    assert draft.asset_universe == ["TSLA"]
    assert draft.date_range == {
        "start": "2022-01-01",
        "end": date.today().isoformat(),
    }
    assert draft.capital_amount == 10000
    assert draft.entry_logic == "50-day SMA crosses above 200-day SMA"
    assert draft.exit_logic == "50-day SMA crosses below 200-day SMA"

@pytest.mark.asyncio
async def test_supported_rule_repair_audits_dropped_user_stated_capital(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        if symbol.lower() in {"tesla", "tsla"}:
            return ResolvedAssetStub("TSLA", "equity", "Tesla Inc.", "TSLA")
        raise ValueError("invalid_symbol")

    async def plan_stub(**kwargs):
        del kwargs
        calls.append("signal_rule_plan")
        plan = _sma_50_200_crossover_plan(
            strategy_thesis=(
                "Test Tesla with a 50/200 moving-average crossover using $10,000."
            ),
        )
        return plan.model_copy(update={"asset_universe": ["Tesla"]})

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del kwargs
        calls.append("field_fidelity_audit")
        assert "10k" in request.current_user_message
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.capital_amount = 10000
        repaired.candidate_strategy_draft.field_provenance["capital_amount"] = (
            "starting_capital"
        )
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "repair_signal_rule_plan", plan_stub)
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User asked for a 50/200 crossover test on Tesla.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_thesis="Test Tesla with a 50/200 crossover.",
        ),
        assistant_response="I can't run a 50/200 crossover directly yet.",
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="50/200 crossover",
                explanation="This rule is not executable yet.",
            )
        ],
        semantic_turn_act="unsupported_request",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["signal_rule_plan", "field_fidelity_audit"]
    assert repaired.candidate_strategy_draft.capital_amount == 10000
    assert (
        repaired.candidate_strategy_draft.field_provenance["capital_amount"]
        == "starting_capital"
    )


@pytest.mark.asyncio
async def test_pending_signal_rule_answer_uses_entry_rule_metadata(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def plan_stub(**kwargs):
        calls.append(kwargs)
        assert kwargs["current_user_message"] == "usa 50 y 200 dias"
        assert kwargs["prior_strategy"]["asset_universe"] == ["TSLA"]
        return _sma_50_200_crossover_plan(
            strategy_thesis="Test TSLA with a 50/200 moving-average crossover."
        )

    monkeypatch.setattr(interpreter_module, "repair_signal_rule_plan", plan_stub)

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied the moving-average periods.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="usa 50 y 200 dias",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="usa el cruce de medias moviles compatible",
            asset_universe=["USA"],
            asset_class="equity",
            date_range={"start": "2025-12-13", "end": "2026-07-01"},
            date_range_raw_text="50 y 200 dias",
            field_provenance={"asset_universe": "explicit_user"},
            evidence_spans={
                "asset_universe": "usa",
                "entry_rule": "50 y 200 dias",
                "date_range": "50 y 200 dias",
            },
        ),
        semantic_turn_act="answer_pending_need",
    )
    request = InterpretationRequest(
        current_user_message="usa 50 y 200 dias",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="signal_strategy",
                strategy_thesis="Test TSLA with a moving-average crossover.",
                asset_universe=["TSLA"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                entry_logic="Use a moving-average crossover.",
            )
        ),
        selected_thread_metadata={
            "requested_field": "entry_rule",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    repaired = await interpreter_module._signal_rule_checked_response(
        response=response,
        preferred_model="test-model",
        request=request,
    )
    runtime = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._to_runtime_interpretation(repaired, request=request)

    assert calls
    assert repaired.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert "signal_rule_plan_repair" in repaired.reason_codes
    strategy = runtime.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.rule_spec is not None
    assert "pending_non_asset_answer_preserved_prior_asset" in runtime.reason_codes


@pytest.mark.asyncio
async def test_vague_valuation_idea_is_audited_before_buy_hold_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def grounding_audit_stub(*, response, request, **kwargs):
        del kwargs
        calls.append("strategy_grounding_audit")
        assert response.candidate_strategy_draft.strategy_type == "buy_and_hold"
        assert "looked cheap" in request.current_user_message
        repaired = response.model_copy(deep=True)
        repaired.intent = "strategy_drafting"
        repaired.requires_clarification = True
        repaired.assistant_response = (
            "Cheap can mean valuation, but I need a testable proxy before running it."
        )
        repaired.missing_required_fields = ["entry_logic", "date_range"]
        repaired.reason_codes = [
            *repaired.reason_codes,
            "executable_strategy_grounding_needs_clarification",
        ]
        repaired.candidate_strategy_draft.strategy_type = None
        return repaired

    monkeypatch.setattr(
        interpreter_module,
        "_audit_executable_strategy_grounding",
        grounding_audit_stub,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test Tesla when it looked cheap.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="what if I bought Tesla when it looked cheap?",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "User wants to test a buy-and-hold strategy for Tesla based on "
                "perceived cheapness."
            ),
            asset_universe=["TSLA"],
            asset_class="equity",
            timeframe="long-term",
            date_range={"start": "2016-01-01", "end": "today"},
        ),
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="what if I bought Tesla when it looked cheap?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["strategy_grounding_audit"]
    assert repaired.intent == "strategy_drafting"
    assert repaired.requires_clarification is True
    assert repaired.assistant_response
    assert "entry_logic" in repaired.missing_required_fields

def test_signal_grounding_audit_blocks_invented_vague_momentum_rule() -> None:
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="User wants to buy SPY when it starts rising.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test buying SPY when it starts rising.",
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="5-day SMA crosses above 20-day SMA",
            exit_logic="5-day SMA crosses below 20-day SMA",
            entry_rule={
                "type": "moving_average_crossover",
                "direction": "bullish",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
            },
            exit_rule={
                "type": "moving_average_crossover",
                "direction": "bearish",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
            },
        ),
    )
    audit = SignalRuleGroundingAudit(
        outcome="needs_clarification",
        assistant_response="I can test this, but I need the exact rising trigger first.",
        missing_required_fields=["entry_logic"],
    )

    repaired = _response_from_signal_grounding_audit(response=response, audit=audit)

    draft = repaired.candidate_strategy_draft
    assert repaired.requires_clarification is True
    assert repaired.missing_required_fields == ["entry_logic"]
    assert repaired.assistant_response == audit.assistant_response
    assert "signal_rule_grounding_needs_clarification" in repaired.reason_codes
    assert draft.entry_logic is None
    assert draft.exit_logic is None
    assert draft.entry_rule is None
    assert draft.exit_rule is None
    assert draft.rule_spec is None

def test_signal_grounding_audit_prompt_accepts_common_crossover_shorthand() -> None:
    messages = _signal_rule_grounding_messages(
        current_user_message="buy when the 50 crosses the 200",
        candidate_strategy={
            "strategy_type": "signal_strategy",
            "entry_rule": {
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
            "exit_rule": {
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bearish",
            },
        },
        prior_strategy=None,
    )

    prompt = messages[0]["content"]

    assert "buy when the 50 crosses the 200" in prompt
    assert "ground a bullish SMA 50/200 crossover" in prompt
    assert "opposite-crossover exit" in prompt
    assert "do not ask the user to restate" in prompt

def test_pending_signal_rule_planning_response_preserves_prior_artifact() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User confirmed a subset of the pending signal idea.",
        candidate_strategy_draft=LLMStrategyDraft(),
        assistant_response="Do you want to use only MACD?",
    )
    prior_strategy = {
        "strategy_type": "signal_strategy",
        "strategy_thesis": "Test Bitcoin when MACD turns bullish and volume jumps.",
        "asset_universe": ["BTC"],
        "asset_class": "crypto",
        "date_range": "last 6 months",
    }

    repaired = _pending_signal_rule_planning_response(
        response=response,
        prior_strategy=prior_strategy,
        current_user_message="ok run the macd crossover only",
    )

    draft = repaired.candidate_strategy_draft
    assert draft.strategy_type == "signal_strategy"
    assert draft.asset_universe == ["BTC"]
    assert draft.date_range == "last 6 months"
    assert draft.raw_user_phrasing == "ok run the macd crossover only"
    assert draft.strategy_thesis is None
    assert draft.entry_logic is None
    assert draft.rule_spec is None

def test_llm_interpreter_maps_indicator_threshold_fields_to_strategy_parameters(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        user_goal_summary="User supplied RSI thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use RSI: enter at 20 and exit at 60.",
            strategy_type="indicator_threshold",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            indicator="rsi",
            entry_threshold=20,
            exit_threshold=60,
            date_range="past 3 months",
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Use RSI: enter at 20 and exit at 60.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    parameters = result.candidate_strategy_draft.extra_parameters[
        "indicator_parameters"
    ]
    assert parameters["indicator"] == "rsi"
    assert parameters["entry_threshold"] == 20
    assert parameters["exit_threshold"] == 60
