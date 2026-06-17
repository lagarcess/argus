from dataclasses import dataclass
from datetime import date

import pytest
from argus.agent_runtime.asset_text_grounding import (
    _candidate_text_supports_resolved_asset,
    provider_ticker_mentions_from_text,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    AssetGroundingAudit,
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
    _llm_strategy_draft_has_executable_shape,
    _pending_signal_rule_planning_response,
    _recover_supported_signal_rule_from_draft_if_needed,
    _response_from_current_message_run_field_contract,
    _response_from_signal_grounding_audit,
    _response_from_signal_rule_plan,
    _strategy_from_llm,
)
from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
    _signal_rule_grounding_messages,
)
from argus.agent_runtime.stages.interpret import InterpretationRequest, interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConversationMessage,
    ResolutionProvenance,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.domain.backtesting.rules import (
    describe_rule_spec,
    rule_spec_from_moving_average_crossover_rules,
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def _sma_50_200_crossover_rule_spec() -> dict:
    rule_spec = rule_spec_from_moving_average_crossover_rules(
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
        exit_rule=None,
    )
    assert rule_spec is not None
    return rule_spec


def _sma_50_200_crossover_plan(*, strategy_thesis: str) -> SignalRulePlan:
    rule_spec = _sma_50_200_crossover_rule_spec()
    return SignalRulePlan(
        outcome="ready_to_confirm",
        user_goal_summary=strategy_thesis,
        strategy_thesis=strategy_thesis,
        entry_logic=describe_rule_spec(rule_spec, "entry"),
        exit_logic=describe_rule_spec(rule_spec, "exit"),
        rule_spec=rule_spec,
        confidence=0.86,
    )


def _tsla_50_200_focused_extraction() -> FocusedStrategyExtraction:
    return FocusedStrategyExtraction(
        is_testable_strategy=True,
        requires_clarification=False,
        user_goal_summary="User asked for a 50/200 crossover test on Tesla.",
        language="en",
        strategy_type="signal_strategy",
        strategy_thesis=(
            "Backtest a bullish SMA 50/200 crossover on Tesla from January "
            "2022 to today with $10,000 capital."
        ),
        asset_universe=["Tesla"],
        asset_class="equity",
        date_range={"start": "2022-01-01", "end": "today"},
        capital_amount=10000,
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
        evidence_spans={
            "asset_universe": "Tesla",
            "date_range": "from January 2022 to today",
            "capital_amount": "10k",
            "entry_rule": "the 50 crosses the 200",
        },
        confidence=0.91,
    )


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

    assert calls == [
        "LLMInterpretationResponse",
        "ArtifactAssumptionEditPlan",
    ]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
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

    assert calls == [
        "LLMInterpretationResponse",
        "ArtifactAssumptionEditPlan",
    ]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
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
    assert draft.date_range == {"start": "2022-01-01", "end": "today"}
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
    assert draft.date_range == {"start": "2022-01-01", "end": "today"}
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
async def test_structured_signal_draft_recovers_missing_asset_from_context(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime import signal_rule_repair as repair_module

    async def fail_if_model_called(**kwargs):
        del kwargs
        raise AssertionError("catalog-backed asset recovery should not need a model")

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
        requires_clarification=True,
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
        missing_required_fields=["asset_universe"],
        assistant_response=(
            "Just to confirm, are you testing this on TSLA stock?"
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
    assert repaired.missing_required_fields == []
    assert "provider_catalog_asset_recovery" in repaired.reason_codes
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
        return _sma_50_200_crossover_plan(
            strategy_thesis="Test Tesla with a 50/200 moving-average crossover."
        )

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
    assert draft.date_range == {"start": "2022-01-01", "end": "today"}
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
        return plan

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
            "end": date.today().isoformat(),
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


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_pending_field_side_question_to_capability(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        assert kwargs["task"] == "interpretation"
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
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User is asking a side question.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Can I use Bollinger Bands?",
            strategy_thesis="Can I use Bollinger Bands?",
        ),
        missing_required_fields=["asset_universe"],
        confidence=0.62,
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Can I use Bollinger Bands?",
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={"requested_field": "asset_universe"},
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
    assert ready_response.artifact_target == "none"
    assert ready_response.missing_required_fields == []
    assert "capability_side_question_audit" in ready_response.reason_codes
    assert "vague_strategy_start_guidance" not in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_audits_pending_asset_answer_despite_educational_copy(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "AssetAnswerCandidateAudit"
        return interpreter_module.AssetAnswerCandidateAudit(
            candidate_symbols=["GOOGL"],
            needs_clarification=False,
            confidence=0.92,
        )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == "GOOGL":
            return ResolvedAssetStub(
                "GOOGL",
                "equity",
                name="Alphabet Inc. Class A Common Stock",
            )
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the asset edit with a company name.",
        assistant_response=(
            "Did you mean GOOGL, or would you like to start fresh?"
        ),
        semantic_turn_act="educational_question",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="google",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="indicator_threshold",
                strategy_thesis="Test TSLA with an RSI threshold.",
                asset_universe=["TSLA"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                entry_logic="Buy when RSI(14) drops to 30 or below",
                exit_logic="Sell when RSI(14) rises to 55 or above",
            )
        ),
        selected_thread_metadata={"requested_field": "asset_universe"},
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=request,
    )

    assert ready_response.semantic_turn_act == "answer_pending_need"
    assert ready_response.candidate_strategy_draft.asset_universe == ["GOOGL"]
    assert ready_response.candidate_strategy_draft.asset_class == "equity"
    assert ready_response.assistant_response is None
    assert "requested_asset_answer_candidate_audit" in ready_response.reason_codes


def test_requested_asset_answer_audit_prompt_does_not_copy_rejection_prose() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the asset edit with a company name.",
        assistant_response=(
            'I ran "Google" through our supported assets and it did not match.'
        ),
        semantic_turn_act="educational_question",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="google",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Test TSLA with buy and hold.",
                asset_universe=["TSLA"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            )
        ),
        selected_thread_metadata={"requested_field": "asset_universe"},
        user=UserState(user_id="u1"),
    )

    messages = interpreter_module._requested_asset_answer_candidate_audit_messages(
        response=response,
        request=request,
    )

    joined = "\n".join(message["content"] for message in messages)
    assert "Current asset answer: google" in joined
    assert "did not match" not in joined
    assert "assistant_response" not in joined
    assert "TSLA" in joined


@pytest.mark.asyncio
async def test_pending_asset_answer_audit_tries_fallback_model_before_rejecting(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "AssetAnswerCandidateAudit"
        calls.append(kwargs["model_name"])
        if len(calls) == 1:
            return interpreter_module.AssetAnswerCandidateAudit(
                candidate_symbols=[],
                needs_clarification=False,
                confidence=0.4,
            )
        return interpreter_module.AssetAnswerCandidateAudit(
            candidate_symbols=["GBEX"],
            needs_clarification=False,
            confidence=0.91,
        )

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == "GBEX":
            return ResolvedAssetStub(
                "GBEX",
                "equity",
                name="Globex Corporation Common Stock",
            )
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["structured-primary", "structured-fallback"],
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the asset edit with a company name.",
        assistant_response="I cannot treat that as a supported ticker.",
        semantic_turn_act="educational_question",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="globex",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Test AAPL with buy and hold.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            )
        ),
        selected_thread_metadata={"requested_field": "asset_universe"},
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured-primary",
        request=request,
    )

    assert calls == ["structured-primary", "structured-fallback"]
    assert ready_response.semantic_turn_act == "answer_pending_need"
    assert ready_response.candidate_strategy_draft.asset_universe == ["GBEX"]
    assert ready_response.candidate_strategy_draft.asset_class == "equity"
    assert ready_response.assistant_response is None
    assert "requested_asset_answer_candidate_audit" in ready_response.reason_codes


def test_requested_asset_answer_audit_validates_ranked_candidates_before_clarifying(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == "GBEX":
            return ResolvedAssetStub(
                "GBEX",
                "equity",
                name="Globex Corporation Common Stock",
            )
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the asset edit with a company name.",
        assistant_response="Which listed share should I use?",
        semantic_turn_act="educational_question",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="globex",
        recent_thread_history=[],
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="buy_and_hold",
                strategy_thesis="Test ACME with buy and hold.",
                asset_universe=["ACME"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
            )
        ),
        selected_thread_metadata={"requested_field": "asset_universe"},
        user=UserState(user_id="u1"),
    )
    audit = interpreter_module.AssetAnswerCandidateAudit(
        candidate_symbols=["GBEX", "GBEY"],
        needs_clarification=True,
        confidence=0.88,
    )

    ready_response = interpreter_module._response_from_requested_asset_answer_candidate_audit(
        response=response,
        request=request,
        audit=audit,
    )

    assert ready_response is not None
    assert ready_response.semantic_turn_act == "answer_pending_need"
    assert ready_response.candidate_strategy_draft.asset_universe == ["GBEX"]
    assert ready_response.candidate_strategy_draft.asset_class == "equity"
    assert ready_response.assistant_response is None
    assert "requested_asset_answer_candidate_audit" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_audits_capability_side_question_with_rule_shape(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "CapabilitySideQuestionAudit"
        return interpreter_module.CapabilitySideQuestionAudit(
            is_capability_question=True,
            focus="supported_indicators",
            assistant_response=None,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User asks whether Bollinger Bands are supported.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Can I use Bollinger Bands?",
            strategy_thesis="User is asking whether Bollinger Bands are supported.",
            strategy_type="signal_strategy",
            entry_logic="Use Bollinger Bands as the signal concept.",
        ),
        missing_required_fields=["asset_universe"],
        confidence=0.64,
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Can I use Bollinger Bands?",
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={"requested_field": "asset_universe"},
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
    assert ready_response.candidate_strategy_draft.strategy_type is None
    assert ready_response.missing_required_fields == []
    assert "capability_side_question_audit" in ready_response.reason_codes
    assert "vague_strategy_start_guidance" not in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_standalone_movers_to_context_focus(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        if kwargs["schema_name"] == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        assert kwargs["schema_name"] == "ContextQuestionAudit"
        return interpreter_module.ContextQuestionAudit(
            is_context_question=True,
            focus="market_movers",
            confidence=0.88,
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
        user_goal_summary="User asks for top market movers.",
        assistant_response="I can't pull live market movers.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="what are the top market movers?",
            strategy_thesis="what are the top market movers?",
        ),
        missing_required_fields=[],
        confidence=0.62,
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="what are the top market movers?",
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
    assert ready_response.context_question_focus == "market_movers"
    assert ready_response.capability_question_focus is None
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert "context_question_audit" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_lets_context_override_strategy_capability_label(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        if kwargs["schema_name"] == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        assert kwargs["schema_name"] == "ContextQuestionAudit"
        return interpreter_module.ContextQuestionAudit(
            is_context_question=True,
            focus="market_movers",
            confidence=0.9,
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
        user_goal_summary="User asks for top market movers.",
        assistant_response="I cannot provide live movers, but try a threshold rule.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_strategies",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="what are the top market movers?",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.context_question_focus == "market_movers"
    assert ready_response.capability_question_focus is None
    assert ready_response.assistant_response is None
    assert "context_question_audit" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_unsupported_movers_to_context_focus(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        if kwargs["schema_name"] == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=False,
                confidence=0.8,
            )
        assert kwargs["schema_name"] == "ContextQuestionAudit"
        return interpreter_module.ContextQuestionAudit(
            is_context_question=True,
            focus="market_movers",
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    async def no_strategy_repair(**kwargs):
        del kwargs
        return None

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        no_strategy_repair,
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks for current top market movers.",
        assistant_response=None,
        semantic_turn_act="unsupported_request",
        capability_question_focus="general",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="what are the top market movers?",
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
    assert ready_response.context_question_focus == "market_movers"
    assert ready_response.capability_question_focus is None
    assert ready_response.assistant_response is None
    assert "context_question_audit" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_clears_ungrounded_lowercase_asset_extraction(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        if schema_name == "DcaContributionRoleAudit":
            return interpreter_module.DcaContributionRoleAudit(
                recurring_contribution_explicit=True,
                total_budget_not_recurring=False,
                confidence=0.9,
            )
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=False,
                confidence=0.2,
            )
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=False,
                confidence=0.8,
            )
        assert schema_name == "AssetGroundingAudit"
        return interpreter_module.AssetGroundingAudit(
            grounded_symbols=[],
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User asks to walk through DCA.",
        assistant_response="Great, let's set up a monthly DCA for ME.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Walk me through a DCA",
            strategy_type="dca_accumulation",
            strategy_thesis="Monthly DCA for ME.",
            asset_universe=["ME"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            cadence="monthly",
            capital_amount=100,
            field_provenance={
                "capital_amount": "recurring_contribution",
                "cadence": "explicit_user",
            },
        ),
        missing_required_fields=[],
        confidence=0.7,
        semantic_turn_act="answer_pending_need",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Walk me through a DCA",
        recent_thread_history=[],
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.candidate_strategy_draft.asset_universe == []
    assert ready_response.assistant_response is None
    assert "asset_grounding_audit_removed_unsubstantiated_symbols" in (
        ready_response.reason_codes
    )


@pytest.mark.asyncio
async def test_asset_grounding_audit_recovers_lowercase_ticker_from_misplaced_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = "".join(char for char in str(symbol).upper() if char.isalnum())
        if normalized == "NU":
            return ResolvedAssetStub(
                "NU",
                "equity",
                name="Nu Holdings Ltd.",
                raw_symbol="NU",
            )
        if normalized in {"APPX", "INVESTMENT"}:
            return ResolvedAssetStub(
                "APPX",
                "equity",
                name=(
                    "Investment Managers Series Trust II Tradr 2X Long APP "
                    "Daily ETF"
                ),
                raw_symbol="APPX",
            )
        raise ValueError("unsupported_symbol")

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "AssetGroundingAudit"
        prompt = "\n".join(str(message["content"]) for message in kwargs["messages"])
        assert "APPX" in prompt
        assert "NU" in prompt
        return interpreter_module.AssetGroundingAudit(
            grounded_symbols=[],
            confidence=0.92,
        )

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test a lump-sum investment in NU.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "lets see what an investment of 500 in nu could have made this "
                "year so far if invested at the begining of this year"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Test a simple lump-sum investment in NU.",
            asset_universe=["APPX"],
            asset_class="equity",
            date_range={"start": "2026-01-01", "end": "2026-06-03"},
            capital_amount=500,
            comparison_baseline="NU",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=(
            "lets see what an investment of 500 in nu could have made this "
            "year so far if invested at the begining of this year"
        ),
        recent_thread_history=[],
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._asset_grounding_audited_response(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["NU"]
    assert draft.asset_class == "equity"
    assert draft.comparison_baseline is None
    assert draft.strategy_thesis is None
    assert "asset_grounding_audit_removed_unsubstantiated_symbols" in (
        ready_response.reason_codes
    )
    assert "misplaced_benchmark_asset_recovered" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_asset_grounding_audit_recovers_exact_ticker_when_asset_is_empty(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = "".join(char for char in str(symbol).upper() if char.isalnum())
        if normalized == "NU":
            return ResolvedAssetStub(
                "NU",
                "equity",
                name="Nu Holdings Ltd.",
                raw_symbol="NU",
            )
        raise ValueError("unsupported_symbol")

    async def audit_stub(**kwargs):
        raise AssertionError("empty asset recovery should not require an LLM audit")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test a lump-sum investment.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "lets see what an investment of 500 in nu could have made this "
                "year so far if invested at the begining of this year"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Evaluate a $500 investment.",
            asset_universe=[],
            asset_class=None,
            date_range={"start": "2026-01-01", "end": "2026-06-03"},
            capital_amount=500,
            comparison_baseline="NU",
            field_provenance={
                "capital_amount": "starting_capital",
                "comparison_baseline": "stated_run_field_fidelity_audit",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=(
            "lets see what an investment of 500 in nu could have made this "
            "year so far if invested at the begining of this year"
        ),
        recent_thread_history=[],
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._asset_grounding_audited_response(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["NU"]
    assert draft.asset_class == "equity"
    assert draft.comparison_baseline is None
    assert draft.strategy_thesis is None
    assert "misplaced_benchmark_asset_recovered" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_asset_grounding_audit_does_not_recover_benchmark_when_asset_name_is_grounded(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = "".join(char for char in str(symbol).upper() if char.isalnum())
        if normalized in {"APPLE", "AAPL"}:
            return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        if normalized == "QQQ":
            return ResolvedAssetStub("QQQ", "equity", name="Invesco QQQ Trust")
        if normalized == "APPX":
            return ResolvedAssetStub(
                "APPX",
                "equity",
                name="Investment Managers Series Trust II Tradr ETF",
            )
        raise ValueError("unsupported_symbol")

    async def audit_stub(**kwargs):
        assert kwargs["schema_name"] == "AssetGroundingAudit"
        return interpreter_module.AssetGroundingAudit(
            grounded_symbols=[],
            confidence=0.92,
        )

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to compare Apple with QQQ.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="apple qqq from the start of 2024",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["APPX"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            comparison_baseline="QQQ",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="apple qqq from the start of 2024",
        recent_thread_history=[],
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._asset_grounding_audited_response(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == []
    assert draft.comparison_baseline == "QQQ"
    assert "misplaced_benchmark_asset_recovered" not in ready_response.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_side_question_after_ungrounded_asset_extraction(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        calls.append(kwargs["schema_name"])
        if kwargs["schema_name"] == "AssetGroundingAudit":
            return interpreter_module.AssetGroundingAudit(
                grounded_symbols=[],
                confidence=0.92,
            )
        if kwargs["schema_name"] == "CapabilitySideQuestionAudit":
            return interpreter_module.CapabilitySideQuestionAudit(
                is_capability_question=True,
                focus="supported_strategies",
                assistant_response=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema: {kwargs['schema_name']}")

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == "DG":
            return ResolvedAssetStub("DG", "equity", name="Dollar General Corporation")
        if normalized == "BTC":
            return ResolvedAssetStub("BTC", "crypto", name="Bitcoin")
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User asks what recurring buys mean.",
        assistant_response=(
            "I can test recurring buys for DG. How much should each recurring "
            "purchase be?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="explain what recurring buys mean",
            strategy_type="dca_accumulation",
            strategy_thesis="Test recurring buys for DG.",
            asset_universe=["DG"],
        ),
        missing_required_fields=["capital_amount", "cadence", "date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="explain what recurring buys mean",
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
            )
        ),
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["AssetGroundingAudit", "CapabilitySideQuestionAudit"]
    assert ready_response.intent == "conversation_followup"
    assert ready_response.semantic_turn_act == "educational_question"
    assert ready_response.capability_question_focus == "supported_strategies"
    assert ready_response.candidate_strategy_draft.asset_universe == []
    assert ready_response.missing_required_fields == []
    assert ready_response.assistant_response is None
    assert "asset_grounding_audit_removed_unsubstantiated_symbols" in (
        ready_response.reason_codes
    )
    assert "capability_side_question_audit" in ready_response.reason_codes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_message", "extracted_symbol", "asset_name", "strategy_thesis"),
    [
        (
            "explain what recurring buys mean",
            "DG",
            "Dollar General Corporation",
            "Test recurring buys for DG.",
        ),
        (
            "what does average entry price mean for beginners?",
            "AEP",
            "American Electric Power Company",
            "Test average entry price for AEP.",
        ),
    ],
)
async def test_llm_interpreter_keeps_side_question_conversational_when_audit_unavailable_after_ungrounded_asset(
    monkeypatch,
    current_message,
    extracted_symbol,
    asset_name,
    strategy_thesis,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        calls.append(kwargs["schema_name"])
        if kwargs["schema_name"] == "AssetGroundingAudit":
            return interpreter_module.AssetGroundingAudit(
                grounded_symbols=[],
                confidence=0.92,
            )
        if kwargs["schema_name"] == "CapabilitySideQuestionAudit":
            raise TimeoutError("audit unavailable")
        raise AssertionError(f"Unexpected schema: {kwargs['schema_name']}")

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        if normalized == extracted_symbol:
            return ResolvedAssetStub(
                extracted_symbol,
                "equity",
                name=asset_name,
            )
        if normalized == "BTC":
            return ResolvedAssetStub("BTC", "crypto", name="Bitcoin")
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User asks an investing concept side question.",
        assistant_response="I can set up a test if you tell me the missing facts.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_message,
            strategy_type="dca_accumulation",
            strategy_thesis=strategy_thesis,
            asset_universe=[extracted_symbol],
        ),
        missing_required_fields=["capital_amount", "cadence", "date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
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
            )
        ),
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["AssetGroundingAudit", "CapabilitySideQuestionAudit"]
    assert ready_response.intent == "conversation_followup"
    assert ready_response.semantic_turn_act == "educational_question"
    assert ready_response.artifact_target == "none"
    assert ready_response.candidate_strategy_draft.asset_universe == []
    assert ready_response.missing_required_fields == []
    assert ready_response.assistant_response is None
    assert "asset_grounding_audit_removed_unsubstantiated_symbols" in (
        ready_response.reason_codes
    )
    assert "capability_side_question_audit_unavailable_after_asset_grounding" in (
        ready_response.reason_codes
    )


@pytest.mark.asyncio
async def test_asset_grounding_audit_clears_lowercase_pronoun_even_with_run_context(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        calls.append(kwargs["schema_name"])
        return interpreter_module.AssetGroundingAudit(
            grounded_symbols=[],
            confidence=0.2,
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
        user_goal_summary="User wants to buy it last year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy it last year",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy IT last year.",
            asset_universe=["IT"],
            date_range="last year",
        ),
        missing_required_fields=["capital_amount"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="buy it last year",
        recent_thread_history=[],
        user=UserState(user_id="u1"),
    )

    audited = await interpreter_module._asset_grounding_audited_response(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["AssetGroundingAudit"]
    assert audited.candidate_strategy_draft.asset_universe == []
    assert "asset_grounding_audit_low_confidence_cleared_suspicious_symbols" in (
        audited.reason_codes
    )


@pytest.mark.asyncio
async def test_llm_interpreter_preserves_recent_dca_strategy_family_when_user_supplies_run_facts(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        if schema_name == "DcaContributionRoleAudit":
            return interpreter_module.DcaContributionRoleAudit(
                recurring_contribution_explicit=False,
                total_budget_not_recurring=True,
                confidence=0.9,
            )
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=True,
                total_budget_amount=200000,
                total_budget_source="total_budget",
                confidence=0.9,
            )
        assert schema_name == "StrategyFamilyContinuityAudit"
        return interpreter_module.StrategyFamilyContinuityAudit(
            should_rebind_strategy_family=True,
            strategy_type="dca_accumulation",
            total_budget_not_recurring=True,
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied LYFT, a date window, and total budget.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "I want to invest in LYFT from Feb 2020 to Feb 2025 "
                "with $200,000 total"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Invest in LYFT over the requested period.",
            asset_universe=["LYFT"],
            date_range={"start": "2020-02-01", "end": "2025-02-28"},
            date_range_intent=LLMDateRangeIntent(
                kind="explicit_range",
                start="2020-02-01",
                end="2025-02-28",
                evidence="from Feb 2020 to Feb 2025",
            ),
            capital_amount=200000,
            field_provenance={"capital_amount": "total_capital"},
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=(
            "I want to invest in LYFT from Feb 2020 to Feb 2025 with $200,000 total"
        ),
        recent_thread_history=[
            ConversationMessage(role="user", content="Walk me through a DCA"),
            ConversationMessage(
                role="assistant",
                content=(
                    "In Argus, DCA maps to recurring buys. Tell me the asset, "
                    "period, amount, and schedule when you want to set one up."
                ),
            ),
        ],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "dca_accumulation"
    assert draft.total_capital == 200000
    assert draft.capital_amount is None
    assert draft.field_provenance["total_capital"] == "total_budget"
    assert "capital_amount" in ready_response.missing_required_fields
    assert ready_response.requires_clarification is True
    assert "strategy_family_continuity_rebound" in ready_response.reason_codes


def test_provider_catalog_recovery_ignores_lowercase_symbol_only_verbs(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        compact = "".join(char for char in str(symbol).upper() if char.isalnum())
        if compact == "TEST":
            return ResolvedAssetStub(
                "TEST",
                "equity",
                "YieldMax TSLA Performance & Distribution Target 25 ETF",
                "TEST",
            )
        if compact in {"ME", "MEUSD"}:
            return ResolvedAssetStub("ME", "crypto", "ME/USD", "ME/USD")
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    assets = interpreter_module._resolved_asset_mentions_from_message(
        "test ME/USD buy and hold"
    )

    assert [asset.canonical_symbol for asset in assets] == ["ME"]


@pytest.mark.asyncio
async def test_llm_interpreter_repairs_silently_reshaped_launch_fields(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    calls: list[str] = []

    async def repair_stub(*, failed_response, request, **kwargs):
        del kwargs
        calls.append("focused_strategy_extraction")
        return interpreter_module._response_from_focused_strategy_extraction(
            extraction=interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Test BTC on hourly candles from 2020 to today.",
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold BTC over the requested hourly window.",
                asset_universe=["BTC"],
                asset_class="crypto",
                timeframe="1h",
                date_range={"start": "2020-01-01", "end": "today"},
                capital_amount=1000,
            ),
            request=request,
            base_response=failed_response,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del request, kwargs
        calls.append("field_fidelity_audit")
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.timeframe = "1h"
        repaired.candidate_strategy_draft.date_range = {
            "start": "2020-01-01",
            "end": "today",
        }
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test BTC buy and hold.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="test BTC on 1 hour candles from 2020 to today with $1k",
            strategy_type="buy_and_hold",
            strategy_thesis="Test BTC buy and hold.",
            asset_universe=["BTC"],
            asset_class="crypto",
            timeframe="1D",
            date_range={"start": "2020-01-01", "end": "2025-06-18"},
            capital_amount=1000,
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message="test BTC on 1 hour candles from 2020 to today with $1k",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["field_fidelity_audit"]
    strategy = ready_response.candidate_strategy_draft
    assert strategy.timeframe == "1h"
    assert strategy.date_range == {"start": "2020-01-01", "end": "today"}
    assert strategy.capital_amount == 1000


@pytest.mark.asyncio
async def test_llm_interpreter_audits_timeframe_sensitive_launch_fields_when_dropped(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    calls: list[str] = []

    async def repair_stub(*, failed_response, request, **kwargs):
        del kwargs
        calls.append("focused_strategy_extraction")
        return interpreter_module._response_from_focused_strategy_extraction(
            extraction=interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Test BTC on hourly candles from 2016 to today.",
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold BTC over the requested hourly window.",
                asset_universe=["BTC"],
                asset_class="crypto",
                timeframe="1h",
                date_range={"start": "2016-01-01", "end": "today"},
            ),
            request=request,
            base_response=failed_response,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_repair_incomplete_strategy_extraction",
        repair_stub,
    )

    async def field_fidelity_audit_stub(*, response, request, **kwargs):
        del request, kwargs
        calls.append("field_fidelity_audit")
        repaired = response.model_copy(deep=True)
        repaired.candidate_strategy_draft.timeframe = "1h"
        repaired.reason_codes = [
            *repaired.reason_codes,
            "stated_run_field_fidelity_audit",
        ]
        return repaired

    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test BTC buy and hold.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="test BTC 1h from 2016 to today",
            strategy_type="buy_and_hold",
            strategy_thesis="Test BTC buy and hold.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range={"start": "2016-01-01", "end": "today"},
        ),
        semantic_turn_act="new_idea",
    )
    request = InterpretationRequest(
        current_user_message="test BTC 1h from 2016 to today",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["field_fidelity_audit"]
    strategy = ready_response.candidate_strategy_draft
    assert strategy.timeframe == "1h"
    assert strategy.date_range == {
        "start": "2016-01-01",
        "end": date.today().isoformat(),
    }


@pytest.mark.asyncio
async def test_llm_interpreter_audits_user_stated_capital_on_ready_launch(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

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

    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_field_fidelity",
        field_fidelity_audit_stub,
        raising=False,
    )

    async def executable_grounding_audit_noop(*, response, **kwargs):
        del kwargs
        return None

    monkeypatch.setattr(
        interpreter_module,
        "_audit_executable_strategy_grounding",
        executable_grounding_audit_noop,
        raising=False,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Buy and hold BTC from 2024 with $10,000.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="what if I bought Bitcoin at the start of 2024 with 10k?",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Evaluate Bitcoin from the start of 2024 with an initial capital "
                "of $10,000."
            ),
            asset_universe=["BTC"],
            asset_class="crypto",
            timeframe="daily",
            date_range={"start": "2024-01-01", "end": "today"},
        ),
        semantic_turn_act="new_idea",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "what if I bought Bitcoin at the start of 2024 with 10k?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["field_fidelity_audit"]
    assert ready_response.candidate_strategy_draft.capital_amount == 10000
    assert (
        ready_response.candidate_strategy_draft.field_provenance["capital_amount"]
        == "starting_capital"
    )


def test_llm_interpreter_keeps_pending_artifact_assumptions_as_followup() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="results_explanation",
        task_relation="continue",
        user_goal_summary="User asks what assumptions the visible draft uses.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["NVDA"],
            date_range="past 6 months",
        ),
        assistant_response="The assumptions include a starting capital of $10,000.",
        semantic_turn_act="result_followup",
        result_followup_focus="assumptions",
    )

    normalized = interpreter_module._normalize_response_for_runtime_context(
        response,
        request=InterpretationRequest(
            current_user_message="What assumptions are you using?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range="past 6 months",
                )
            ),
            user=UserState(user_id="u1"),
        ),
    )

    assert normalized.intent == "conversation_followup"
    assert normalized.semantic_turn_act == "result_followup"
    assert normalized.result_followup_focus == "assumptions"
    assert normalized.assistant_response is None
    assert "routed_pending_artifact_assumptions_followup" in normalized.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_preserves_result_followup_during_pending_refinement(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if len(calls) == 1:
            return LLMInterpretationResponse(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User asks what the latest completed run tested.",
                semantic_turn_act="result_followup",
                result_followup_focus="what_tested",
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="Incorrectly replays the prior MSFT run as a new draft.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold MSFT.",
                asset_universe=["MSFT"],
                date_range={"start": "2025-01-01", "end": "2025-12-31"},
                capital_amount=100000,
            ),
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Before changing anything, what exactly did you test?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold MSFT.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range={"start": "2025-01-01", "end": "2025-12-31"},
                ),
                latest_backtest_result_reference=ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="run-msft-2025",
                    artifact_status="completed",
                    metadata={
                        "symbols": ["MSFT"],
                        "benchmark_symbol": "SPY",
                        "metrics": {
                            "aggregate": {
                                "performance": {
                                    "total_return_pct": 15.6,
                                    "benchmark_return_pct": 16.6,
                                    "delta_vs_benchmark_pct": -1.1,
                                }
                            }
                        },
                        "config_snapshot": {
                            "template": "buy_and_hold",
                            "symbols": ["MSFT"],
                            "date_range": {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                            },
                            "starting_capital": 1000,
                        },
                    },
                ),
            ),
            selected_thread_metadata={
                "requested_field": "refinement",
                "source_result_run_id": "run-msft-2025",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "LatestResultRoutingAudit"]
    assert result is not None
    assert result.intent == "results_explanation"
    assert result.semantic_turn_act == "result_followup"
    assert result.result_followup_focus == "what_tested"


def test_focused_strategy_extraction_uses_indicator_threshold_registry() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary="Buy when SMA is below a chosen level.",
        indicator="sma",
        timeframe="1h",
        entry_threshold=450,
        exit_threshold=500,
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Buy SPY when SMA is under 450.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.candidate_strategy_draft.strategy_type == "indicator_threshold"
    assert response.candidate_strategy_draft.indicator == "sma"
    assert response.candidate_strategy_draft.timeframe == "1h"


def test_focused_strategy_extraction_does_not_force_unknown_strategy_contracts() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary="Buy Apple when news sentiment turns positive.",
        strategy_type="sentiment_strategy",
        strategy_thesis="Use sentiment as the entry signal for Apple.",
        asset_universe=["AAPL"],
        date_range="past year",
        entry_logic="news sentiment turns positive",
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.intent == "unsupported_or_out_of_scope"
    assert response.semantic_turn_act == "unsupported_request"
    assert response.requires_clarification is True
    assert response.candidate_strategy_draft.strategy_type is None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert (
        "focused_strategy_extraction_unrecognized_contract" in response.reason_codes
    )


def test_focused_strategy_extraction_prompt_preserves_draft_only_strategy_fields() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    messages = interpreter_module._focused_strategy_extraction_messages(
        InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )
    prompt = messages[0].content

    assert "it does not mean Argus can execute every part" in prompt
    assert "preserve the asset, period, unsupported rule" in prompt
    assert "Valuation/P/E language is financially valid context" in prompt
    assert "route toward the closest supported proxy" in prompt
    assert "Shorthand like 'the 50 crosses the 200'" in prompt


def test_focused_strategy_extraction_prompt_requires_relative_window_intent() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    messages = interpreter_module._focused_strategy_extraction_messages(
        InterpretationRequest(
            current_user_message=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )
    prompt = messages[0].content

    assert "Relative windows such as 'last 8 months'" in prompt
    assert "must become date_range_intent" in prompt
    assert "Do not ask for exact endpoint dates" in prompt
    assert "one-time historical acquisition or purchase plus holding" in prompt
    assert "not unsupported manual trade replay" in prompt


def test_focused_strategy_extraction_preserves_non_executable_idea_as_recovery() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=False,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        strategy_thesis="Use sentiment as the entry signal for Apple.",
        asset_universe=["AAPL"],
        date_range="past year",
        entry_logic="news sentiment turns positive",
        assistant_response="Sentiment/news signals are not executable yet.",
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.intent == "unsupported_or_out_of_scope"
    assert response.semantic_turn_act == "unsupported_request"
    assert response.requires_clarification is True
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.candidate_strategy_draft.date_range == "past year"
    assert "Sentiment/news signals" in response.unsupported_constraints[0].explanation


@pytest.mark.asyncio
async def test_underfilled_unsupported_strategy_draft_gets_structured_recovery(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def invoke_stub(**kwargs):
        calls.append(kwargs["schema_name"])
        return interpreter_module.FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary="Trade Tesla using Reddit sentiment.",
            strategy_type="sentiment_strategy",
            strategy_thesis="Use Reddit sentiment as the entry signal for Tesla.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
            entry_logic="Reddit sentiment turns positive",
            assistant_response=(
                "Sentiment is useful context, but it is not an executable rule yet."
            ),
        )

    async def passthrough_signal_check(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_signal_rule_checked_response",
        passthrough_signal_check,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Trade Tesla using Reddit sentiment.",
        assistant_response=(
            "I can help you test a social media signal proxy using supported indicators."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="trade Tesla based on Reddit sentiment for the last year",
            strategy_thesis="Trade Tesla using Reddit sentiment as a signal.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
        ),
        missing_required_fields=["entry_logic", "exit_logic"],
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message=(
                "trade Tesla based on Reddit sentiment for the last year"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert repaired.intent == "unsupported_or_out_of_scope"
    assert repaired.semantic_turn_act == "unsupported_request"
    assert repaired.unsupported_constraints
    assert repaired.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert "social media signal proxy" not in str(
        repaired.unsupported_constraints[0].explanation
    ).lower()


@pytest.mark.asyncio
async def test_vague_valuation_prompt_with_short_copy_gets_structured_recovery(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def invoke_stub(**kwargs):
        schema = kwargs["schema_model"]
        return schema(
            is_testable_strategy=True,
            user_goal_summary="Explore whether buying Tesla when it looked cheap worked.",
            strategy_type="valuation_strategy",
            strategy_thesis="Use perceived undervaluation as the entry idea for Tesla.",
            asset_universe=["TSLA"],
            asset_class="equity",
            entry_logic="Perceived undervaluation or valuation looked cheap",
            assistant_response=(
                "Valuation is useful context, but Argus needs a supported historical "
                "proxy before it can run the test."
            ),
        )

    async def passthrough_signal_check(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_signal_rule_checked_response",
        passthrough_signal_check,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Buy Tesla when it looked cheap.",
        assistant_response="Totally —",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="what if I bought Tesla when it looked cheap?",
            strategy_thesis=(
                "Buy Tesla when perceived as undervalued and hold over a "
                "specified period."
            ),
            asset_universe=["TSLA"],
            asset_class="equity",
            entry_logic="Perceived undervaluation",
        ),
        missing_required_fields=["entry_logic", "date_range", "exit_logic"],
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="what if I bought Tesla when it looked cheap?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.semantic_turn_act == "unsupported_request"
    assert repaired.unsupported_constraints
    assert repaired.assistant_response != "Totally —"


def test_unsupported_free_text_strategy_response_needs_context_repair() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        assistant_response=(
            "This strategy requires sentiment analysis, which is not supported."
        ),
    )

    assert interpreter_module._response_needs_artifact_context_repair(response) is True


def test_conversation_followup_with_unstructured_strategy_text_needs_repair() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="Test Apple when news sentiment turns positive.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple when news sentiment turns positive.",
            strategy_thesis="Test Apple when news sentiment turns positive.",
        ),
        assistant_response=(
            "This strategy requires sentiment analysis, which is not supported."
        ),
        semantic_turn_act="educational_question",
    )

    assert interpreter_module._response_needs_artifact_context_repair(response) is True


def test_llm_interpreter_promotes_typed_indicator_values_from_extra_parameters(
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
            raw_user_phrasing="Use RSI entry 20 exit 60.",
            strategy_type="indicator_threshold",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            date_range="past 3 months",
            indicator="rsi",
            extra_parameters={
                "entry_threshold": 20,
                "exit_threshold": 60,
                "field_provenance": {
                    "entry_threshold": "user",
                    "exit_threshold": "user",
                },
                "indicator_parameters": {
                    "indicator": "rsi",
                    "entry_threshold": 30,
                    "exit_threshold": 55,
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Use RSI entry 20 exit 60.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    parameters = strategy.extra_parameters["indicator_parameters"]
    assert parameters["entry_threshold"] == 20.0
    assert parameters["exit_threshold"] == 60.0
    assert strategy.entry_logic == "Buy when RSI(14) drops to 20 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 60 or above"


def test_llm_interpreter_preserves_user_supplied_rsi_period(monkeypatch) -> None:
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
        user_goal_summary="User supplied an RSI period and thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use a 7-period RSI, buy below 25 and sell above 60.",
            strategy_type="indicator_threshold",
            strategy_thesis="Use a shorter RSI threshold rule for TSLA.",
            asset_universe=["TSLA"],
            date_range="past 3 months",
            indicator="rsi",
            indicator_period=7,
            entry_threshold=25,
            exit_threshold=60,
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Use a 7-period RSI, buy below 25 and sell above 60."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    parameters = strategy.extra_parameters["indicator_parameters"]
    assert parameters["indicator_period"] == 7
    assert parameters["entry_threshold"] == 25.0
    assert parameters["exit_threshold"] == 60.0
    assert strategy.entry_logic == "Buy when RSI(7) drops to 25 or below"
    assert strategy.exit_logic == "Sell when RSI(7) rises to 60 or above"


def test_llm_signal_rule_defaults_describe_indicator_parameters(monkeypatch) -> None:
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
        user_goal_summary="User supplied RSI signal thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use RSI: enter at 20 and exit at 60.",
            strategy_type="signal_strategy",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            date_range="past 3 months",
            entry_logic="RSI is 20 or lower",
            exit_logic="RSI is 60 or higher",
            rule_spec={
                "entry": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "lte",
                            "right": 20,
                        }
                    ]
                },
                "exit": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "gte",
                            "right": 60,
                        }
                    ]
                },
            },
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

    strategy = result.candidate_strategy_draft
    assert strategy.entry_logic == "RSI(14) is 20 or lower"
    assert strategy.exit_logic == "RSI(14) is 60 or higher"


def test_llm_interpreter_merges_refinement_with_pending_strategy(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="since 2021",
            cadence="monthly",
            capital_amount=500,
            sizing_mode="capital_amount",
        ),
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="refine",
        user_goal_summary="Make the pending DCA strategy weekly.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Actually make that weekly instead.",
            strategy_type="dca_accumulation",
            cadence="weekly",
            evidence_spans={"cadence": "weekly"},
        ),
    )

    interpretation = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Actually make that weekly instead.",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Actually make that weekly instead.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        structured_interpreter=lambda request: interpretation,
    )

    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["BTC"]
    assert strategy.capital_amount == 500
    assert strategy.date_range == "since 2021"
    assert strategy.cadence == "weekly"


def test_llm_interpreter_preserves_semantic_turn_act_from_response() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User approved the pending strategy.",
        semantic_turn_act="approval",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="yes run it",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.semantic_turn_act == "approval"


def test_llm_system_prompt_forbids_scaffolding_and_internal_field_names() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "requested_field" in prompt
    assert "not specified" in prompt
    assert "do not expose" in prompt or "never expose" in prompt


def test_llm_system_prompt_owns_phase_one_routing_and_quality_rules() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "semantic_turn_act" in prompt
    assert "approval" in prompt
    assert "refine_current_idea" in prompt
    assert "conversation_followup" in prompt
    assert "educational" in prompt
    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "missing_required_fields" in prompt
    assert "not specified" in prompt
    assert "what to try next" in prompt
    assert "next_experiment" in prompt


def test_llm_system_prompt_owns_phase_three_extraction_rules() -> None:
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()

    assert "Extract symbols, company names, crypto assets, and currency pairs" in prompt
    assert "Do not rely on backend text-pattern extraction" in prompt
    assert "date_range" in prompt
    assert "cadence" in prompt
    assert "semantic_turn_act is the routing source of truth" in prompt
    assert "response_profile_overrides" in prompt
    assert "social" in prompt.lower()
    assert "educational" in prompt.lower()
    assert "what if I bought/held/owned" in prompt
    assert "not a capability or education question" in prompt


def test_llm_interpreter_treats_moving_average_crossover_as_executable_signal(
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia on a 50/200 moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            entry_logic="50-day moving average crosses above the 200-day moving average",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.entry_logic == (
        "50-day SMA crosses above 200-day SMA"
    )
    assert result.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert result.candidate_strategy_draft.exit_logic == (
        "50-day SMA crosses below 200-day SMA"
    )
    assert result.unsupported_constraints == []


def test_llm_interpreter_humanizes_unsupported_simplification_labels(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia when MACD crosses above its signal line.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Nvidia when MACD crosses above its signal line.",
            asset_universe=["NVDA"],
            entry_logic="MACD crosses above its signal line",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="MACD signal-line crossover",
                explanation="MACD signal-line crossovers are not directly executable.",
                simplification_labels=["rsi_preset", "buy_and_hold", "dca_accumulation"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when MACD crosses above its signal line."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    labels = [
        option.label
        for option in result.unsupported_constraints[0].simplification_options
    ]
    assert labels == [
        "Use the supported RSI rule",
        "Compare with buy and hold",
        "Try recurring buys",
    ]
    explanation = result.unsupported_constraints[0].explanation
    assert "MACD" in explanation
    assert "directly executable" in explanation


def test_llm_interpreter_drops_stale_unsupported_copy_for_executable_rsi_threshold(
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
        intent="backtest_execution",
        task_relation="refine",
        user_goal_summary="Use RSI 40 for the Apple dip rule.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy every time rsi drops below 40",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple when RSI drops below 40.",
            asset_universe=["AAPL"],
            date_range="last two years",
            entry_logic="RSI drops below 40",
            indicator="rsi",
            entry_threshold=40,
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="RSI below 40",
                explanation="The only executable RSI preset is buy below 30.",
                simplification_labels=["rsi_preset"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="buy every time rsi drops below 40",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="strategy_drafting",
                completed=False,
                pending_strategy_summary=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple after big drops.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last two years",
                ),
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert result.unsupported_constraints == []
    assert strategy.entry_logic == "Buy when RSI(14) drops to 40 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 55 or above"


@pytest.mark.asyncio
async def test_supported_strategy_capability_conflict_audit_clears_simple_buy_and_hold(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        return schema_model(
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.94,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere comprar y mantener ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
            ),
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range="enero de 2024 hasta marzo de 2024",
            capital_amount=100000,
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
                ),
                explanation="This idea depends on strategy logic that is not executable yet.",
                simplification_labels=[
                    "Use a supported RSI threshold rule",
                    "Compare with buy and hold",
                    "Use a supported moving-average crossover",
                ],
            )
        ],
    )

    request = InterpretationRequest(
        current_user_message=(
            "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )
    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == [("capability_conflict", "SupportedStrategyCapabilityConflictAudit")]
    assert audited is not None
    result = interpreter._to_runtime_interpretation(audited, request=request)
    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["ETH"]
    assert strategy.capital_amount == 100000
    assert result.unsupported_constraints == []
    assert "supported_strategy_capability_conflict_audit" in result.reason_codes


@pytest.mark.asyncio
async def test_supported_strategy_capability_conflict_audit_falls_back_to_structured_shape(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def unavailable_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, schema_name, model_name
        raise TimeoutError("audit unavailable")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        unavailable_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary=(
            "Buy and hold AAPL over the last 12 months with SPY as benchmark."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Hold AAPL over the last 12 months.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range_raw_text="last 12 months",
            date_range_intent=interpreter_module.LLMDateRangeIntent(
                kind="rolling_window",
                count=12,
                unit="month",
                anchor="today",
                confidence=0.92,
                evidence="last 12 months",
            ),
            capital_amount=100000,
            comparison_baseline="SPY",
            evidence_spans={
                "asset_universe": "AAPL",
                "date_range": "last 12 months",
                "strategy_type": "Buy and hold",
                "comparison_baseline": "SPY",
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="raw buy-and-hold comparison",
                explanation=(
                    "The primary interpretation incorrectly treated a supported "
                    "buy-and-hold comparison as unsupported custom logic."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
    )

    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
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

    assert audited is not None
    assert audited.unsupported_constraints == []
    assert audited.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert audited.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert audited.candidate_strategy_draft.comparison_baseline == "SPY"
    assert (
        "supported_strategy_capability_structured_fallback"
        in audited.reason_codes
    )


@pytest.mark.asyncio
async def test_supported_strategy_capability_audit_canonicalizes_raw_multilingual_buy_and_hold(
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
        return schema_model(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.94,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="El usuario quiere comprar y mantener ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compra y manten eth ultimos 8 meses 100k",
            language="es-419",
            strategy_type="compra y manten",
            strategy_thesis="compra y manten eth ultimos 8 meses 100k",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=8,
                unit="month",
                anchor="today",
                evidence="ultimos 8 meses",
            ),
            capital_amount=100000,
            evidence_spans={
                "strategy_type": "compra y manten",
                "asset_universe": "eth",
                "date_range": "ultimos 8 meses",
                "capital_amount": "100k",
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="compra y manten",
                explanation=(
                    "No podemos ejecutar 'compra y manten' directamente."
                ),
                simplification_labels=[
                    "Compare with buy and hold",
                    "Use a supported RSI threshold rule",
                ],
            )
        ],
        semantic_turn_act="unsupported_request",
    )

    request = InterpretationRequest(
        current_user_message="compra y manten eth ultimos 8 meses 100k",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )
    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == [("capability_conflict", "SupportedStrategyCapabilityConflictAudit")]
    assert captured_messages
    assert "Use semantic meaning, not keyword or phrase matching" in captured_messages[0]["content"]
    assert "plain performance, return, or benchmark comparison" in captured_messages[0]["content"]
    assert audited is not None
    result = interpreter._to_runtime_interpretation(audited, request=request)
    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["ETH"]
    assert strategy.capital_amount == 100000
    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
            evidence="ultimos 8 meses",
        )
    )
    assert expected_range is not None
    assert strategy.date_range == expected_range.payload
    assert result.unsupported_constraints == []
    assert result.requires_clarification is False
    assert result.semantic_turn_act == "new_idea"
    assert "supported_strategy_capability_conflict_audit" in result.reason_codes


@pytest.mark.asyncio
async def test_supported_strategy_capability_audit_arbitrates_entry_exit_misread(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        return schema_model(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.94,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
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
        user_goal_summary=(
            "Comprar y mantener AAPL durante los últimos 12 meses con SPY "
            "como referencia."
        ),
        assistant_response=(
            "La estrategia de solo 'compra y mantén' no es ejecutable "
            "directamente."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Comprar y mantener AAPL durante los últimos 12 meses con SPY "
                "como referencia."
            ),
            strategy_thesis=(
                "Comprar y mantener AAPL durante los últimos 12 meses con SPY "
                "como referencia."
            ),
            asset_universe=["AAPL"],
            asset_class="equity",
            entry_logic="buy",
            exit_logic="hold",
            evidence_spans={
                "asset_universe": "AAPL",
                "comparison_baseline": "SPY",
                "entry_logic": "Comprar",
                "exit_logic": "mantener",
                "date_range_raw_text": "últimos 12 meses",
                "date_range_intent": "rolling_window",
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="buy",
                explanation=(
                    "The model projected supported buy-and-hold language into "
                    "low-level unsupported rule fields."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "date_range"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Comprar y mantener AAPL durante los últimos 12 meses con SPY "
                "como referencia."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls == [("capability_conflict", "SupportedStrategyCapabilityConflictAudit")]
    assert audited is not None
    draft = audited.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.entry_logic is None
    assert draft.exit_logic is None
    assert audited.unsupported_constraints == []
    assert "entry_logic" not in audited.missing_required_fields
    assert "supported_strategy_capability_conflict_audit" in audited.reason_codes


@pytest.mark.asyncio
async def test_supported_strategy_capability_audit_rechecks_dca_money_role(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        calls.append(schema_name)
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="dca_accumulation",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.94,
            )
        if schema_name == "DcaContributionRoleAudit":
            return interpreter_module.DcaContributionRoleAudit(
                recurring_contribution_explicit=True,
                total_budget_not_recurring=False,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    message = (
        "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=message,
        assistant_response="Las compras recurrentes no están disponibles.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_thesis=message,
            asset_universe=["NVDA"],
            asset_class="equity",
            capital_amount=250,
            cadence="weekly",
            date_range={"start": "2025-06-14", "end": "2026-06-14"},
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=message,
                explanation="The model over-routed a supported DCA request.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "exit_logic"],
        semantic_turn_act="unsupported_request",
    )

    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert audited is not None
    assert calls == [
        "SupportedStrategyCapabilityConflictAudit",
        "DcaContributionRoleAudit",
    ]
    draft = audited.candidate_strategy_draft
    assert draft.strategy_type == "dca_accumulation"
    assert draft.capital_amount == 250
    assert draft.recurring_contribution == 250
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["recurring_contribution"] == "explicit_user"
    assert audited.unsupported_constraints == []
    assert audited.requires_clarification is False


@pytest.mark.asyncio
async def test_supported_capability_recovery_rechecks_dropped_trailing_capital(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []
    captured_starting_capital_messages: list[dict[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, model_name
        calls.append(schema_name)
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=False,
                confidence=0.92,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.94,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(confidence=0.88)
        if schema_name == "StatedStartingCapitalAudit":
            captured_starting_capital_messages.extend(messages)
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=100000,
                confidence=0.93,
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="El usuario quiere comprar y mantener ETH.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compra y manten eth ultimos 8 meses 100k",
            language="es-419",
            strategy_type="compra y manten",
            strategy_thesis=(
                "Estrategia de compra y mantenimiento de ETH por los ultimos "
                "8 meses con capital inicial de 100.000 USD."
            ),
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=8,
                unit="month",
                anchor="today",
                evidence="ultimos 8 meses",
            ),
            evidence_spans={
                "strategy_type": "compra y manten",
                "asset_universe": "eth",
                "date_range": "ultimos 8 meses",
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="compra y manten",
                explanation="No podemos ejecutar compra y manten directamente.",
            )
        ],
        semantic_turn_act="unsupported_request",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="compra y manten eth ultimos 8 meses 100k",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "SupportedStrategyCapabilityConflictAudit" in calls
    assert "StatedRunFieldFidelityAudit" in calls
    assert "StatedStartingCapitalAudit" in calls
    assert calls.index("SupportedStrategyCapabilityConflictAudit") < calls.index(
        "StatedRunFieldFidelityAudit"
    )
    assert calls.index("StatedRunFieldFidelityAudit") < calls.index(
        "StatedStartingCapitalAudit"
    )
    assert captured_starting_capital_messages
    capital_prompt = captured_starting_capital_messages[0]["content"]
    assert "standalone numeric magnitude" in capital_prompt
    assert "structured draft prose" in capital_prompt
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["ETH"]
    assert draft.capital_amount == 100000
    assert draft.field_provenance["capital_amount"] == "starting_capital"
    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=8,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_supported_capability_shape_beats_primary_capability_focus(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[tuple[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        if schema_name == "DcaContractAudit":
            return schema_model(
                is_recurring_buy_request=False,
                confidence=0.92,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return schema_model(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.93,
            )
        raise AssertionError(f"unexpected repair schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="The user bought ETH once and held it.",
        assistant_response=(
            "That one-time purchase is not directly supported. Choose RSI, "
            "a moving-average crossover, or buy and hold."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="bought ETH and held it for 8 months with 100k",
            language="en",
            strategy_type="one_time_purchase_hold",
            strategy_thesis="Bought ETH once and held it for 8 months.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-10-13", "end": "2026-06-13"},
            capital_amount=100000,
            evidence_spans={
                "strategy_type": "bought ETH and held it",
                "asset_universe": "ETH",
                "date_range": "8 months",
                "capital_amount": "100k",
            },
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="one_time_purchase_hold",
                explanation="The model treated the supported hold shape as custom logic.",
                simplification_labels=[
                    "Compare with buy and hold",
                    "Use a supported RSI threshold rule",
                ],
            )
        ],
        semantic_turn_act="unsupported_request",
        capability_question_focus="supported_strategies",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="bought ETH and held it for 8 months with 100k",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="en"),
        ),
    )

    assert (
        "capability_conflict",
        "SupportedStrategyCapabilityConflictAudit",
    ) in calls
    assert all(schema_name != "FocusedStrategyExtraction" for _, schema_name in calls)
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.capability_question_focus is None
    assert ready_response.candidate_strategy_draft.strategy_type == "buy_and_hold"
    assert ready_response.candidate_strategy_draft.asset_universe == ["ETH"]
    assert ready_response.candidate_strategy_draft.capital_amount == 100000
    assert ready_response.unsupported_constraints == []


@pytest.mark.asyncio
async def test_supported_shape_inside_unsupported_recovery_gets_focused_repair(
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
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.91,
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
                date_range_raw_text="the last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.94,
                    evidence="the last 8 months",
                ),
                capital_amount=100000,
                confidence=0.92,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "the last 8 months",
                    "strategy_type": "bought eth and held it",
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="The user bought ETH and held it.",
        assistant_response=(
            "You can't backtest a manual buy-and-hold like that directly here."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
            language="en",
            strategy_thesis=(
                "i bought eth and held it for the last 8 months with 100k"
            ),
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="i bought eth and held it for the last 8 months with 100k",
                explanation="The model over-routed a supported hold shape.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        semantic_turn_act="unsupported_request",
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

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["ETH"]
    assert draft.asset_class == "crypto"
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
async def test_unsupported_recovery_allows_focused_spanish_strategy_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

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
                user_goal_summary="Probar comprar y mantener ETH durante 8 meses.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener ETH durante los ultimos 8 meses.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="los ultimos 8 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.94,
                    evidence="los ultimos 8 meses",
                ),
                capital_amount=100000,
                confidence=0.92,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "los ultimos 8 meses",
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="El usuario compró ETH y lo mantuvo.",
        assistant_response=(
            "No puedo ejecutar directamente una compra manual pasada."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compre eth y lo mantuve los ultimos 8 meses con 100k",
            language="es-419",
            strategy_thesis="compre eth y lo mantuve los ultimos 8 meses con 100k",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="compre eth y lo mantuve los ultimos 8 meses con 100k",
                explanation=(
                    "The model over-routed a supported hold shape as manual execution."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        semantic_turn_act="unsupported_request",
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

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["ETH"]
    assert draft.asset_class == "crypto"
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
async def test_empty_unsupported_benchmark_comparison_gets_focused_repair(
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
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar AAPL contra SPY durante 12 meses.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener AAPL con SPY como referencia.",
                asset_universe=["AAPL"],
                asset_class="equity",
                comparison_baseline="SPY",
                date_range_raw_text="los últimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.94,
                    evidence="los últimos 12 meses",
                ),
                confidence=0.92,
                evidence_spans={
                    "asset_universe": "AAPL",
                    "comparison_baseline": "SPY",
                    "date_range": "los últimos 12 meses",
                    "strategy_type": "Compra y mantén",
                },
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
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
        ),
        assistant_response=(
            "Esa idea no se puede ejecutar directamente así, pero podemos acercarnos."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            language="es-419",
            strategy_thesis=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "Compra y mantén AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                explanation=(
                    "The model over-routed a supported benchmark comparison."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=[
            "entry_logic",
            "asset_universe",
            "exit_logic",
            "date_range",
        ],
        semantic_turn_act="unsupported_request",
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
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=12,
            unit="month",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_underfilled_focused_repair_uses_capability_and_date_audits(
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
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Compra y mantén AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                strategy_type=None,
                asset_universe=["AAPL"],
                comparison_baseline="SPY",
                confidence=0.98,
                evidence_spans={
                    "strategy": "Compra y mantén",
                    "asset": "AAPL",
                    "window": "últimos 12 meses",
                    "benchmark": "SPY como referencia",
                },
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.94,
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
        ),
        assistant_response=(
            "Puedo comparar el rendimiento de AAPL contra SPY como referencia. "
            "¿Prefieres eso?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            strategy_thesis=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "Compra y mantén AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                explanation=(
                    "The model over-routed a supported benchmark comparison."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=[
            "entry_logic",
            "asset_universe",
            "exit_logic",
            "date_range",
        ],
        semantic_turn_act="unsupported_request",
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
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[:3] == [
        "FocusedStrategyExtraction",
        "SupportedStrategyCapabilityConflictAudit",
        "FocusedDateWindowExtraction",
    ]
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
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_supported_focused_repair_missing_date_uses_required_field_contract(
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
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Compra y mantén AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                strategy_type="buy_and_hold",
                asset_universe=["AAPL"],
                comparison_baseline="SPY",
                confidence=0.98,
                evidence_spans={
                    "asset": "AAPL",
                    "action": "Compra y mantén",
                    "window": "los últimos 12 meses",
                    "benchmark": "SPY como referencia.",
                },
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
        ),
        assistant_response=(
            "Puedo comparar el rendimiento de AAPL contra SPY como referencia. "
            "¿Prefieres eso?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            strategy_thesis=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "Compra y mantén AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                explanation=(
                    "The model over-routed a supported benchmark comparison."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        semantic_turn_act="unsupported_request",
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
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[:2] == [
        "FocusedStrategyExtraction",
        "FocusedDateWindowExtraction",
    ]
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
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_supported_partial_spanish_draft_gets_focused_schema_repair(
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
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar ETH comprado y mantenido 8 meses.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Mantener ETH durante el periodo indicado.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="ultimos 8 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.94,
                    evidence="ultimos 8 meses",
                ),
                capital_amount=100000,
                confidence=0.92,
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
        "_resolved_asset_mentions_from_message",
        lambda message: [],
    )
    monkeypatch.setattr(
        interpreter_module,
        "_request_has_provider_exact_execution_asset",
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
        user_goal_summary="El usuario quiere mantener ETH por 8 meses.",
        assistant_response=(
            "Entendido: comprar ETH y mantenerlo 8 meses con 100k. "
            "Para simularlo, dime el periodo exacto."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compre eth y lo mantuve los ultimos 8 meses con 100k",
            language="es-419",
            strategy_type="buy_and_hold",
            asset_class="crypto",
            capital_amount=100000,
            strategy_thesis="comprar ETH y mantenerlo 8 meses con 100k",
        ),
        missing_required_fields=["asset_universe", "date_range"],
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

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["ETH"]
    assert draft.asset_class == "crypto"
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
    assert draft.date_range_raw_text == "ultimos 8 meses"


@pytest.mark.asyncio
async def test_supported_partial_draft_gets_schema_repair_after_date_audit_failure(
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
            raise RuntimeError("date specialist unavailable")
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="en",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold ETH through the stated period.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.93,
                    evidence="last 8 months",
                ),
                capital_amount=100000,
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "last 8 months",
                    "strategy_type": "bought eth and held it",
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
    assert "FocusedStrategyExtraction" in calls
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
async def test_supported_partial_clarification_without_missing_list_repairs(
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
                has_date_window=False,
                confidence=0.3,
                evidence="",
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Backtest holding ETH over the last 8 months.",
                language="en",
                strategy_type="buy_and_hold",
                strategy_thesis="Hold ETH through the stated period.",
                asset_universe=["ETH"],
                asset_class="crypto",
                date_range_raw_text="last 8 months",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=8,
                    unit="month",
                    anchor="today",
                    confidence=0.93,
                    evidence="last 8 months",
                ),
                capital_amount=100000,
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "eth",
                    "capital_amount": "100k",
                    "date_range": "last 8 months",
                    "strategy_type": "bought eth and held it",
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
async def test_spanish_supported_pending_need_without_missing_list_gets_date_audit(
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
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
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
            "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
        ),
        assistant_response=(
            "Entendido, probaremos comprar y mantener AAPL por 12 meses con "
            "SPY como referencia. ¿Cuál es la fecha de inicio para los 12 meses?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener AAPL con SPY como referencia.",
            asset_universe=["AAPL"],
            asset_class="equity",
            comparison_baseline="SPY",
        ),
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
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
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
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_spanish_supported_date_clarification_with_minimal_draft_gets_audits(
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
        user_goal_summary=(
            "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
        ),
        assistant_response=(
            "¿Qué período exacto de 12 meses quieres probar?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Comprar y mantener AAPL durante los últimos 12 meses para "
                "evaluar su desempeño relativo frente al mercado (SPY)."
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
                "Compra y mantén AAPL durante los últimos 12 meses "
                "con SPY como referencia."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
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
    draft = ready_response.candidate_strategy_draft
    assert draft.asset_universe == ["AAPL"]
    assert draft.comparison_baseline == "SPY"
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_partial_prose_date_payload_gets_focused_date_audit(
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
        lambda _request: False,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Comprar y mantener AAPL durante los últimos 12 meses con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=current_turn,
        assistant_response=(
            "Solo necesito confirmar el período exacto. ¿Quieres probar la "
            "simulación desde hace exactamente 12 meses hasta hoy?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"end": "últimos 12 meses"},
            comparison_baseline="SPY",
        ),
        missing_required_fields=["date_range"],
        semantic_turn_act="new_idea",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
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
    assert draft.date_range == expected_range.payload
    assert draft.date_range_raw_text == "últimos 12 meses"


def test_focused_strategy_repair_prompt_omits_legacy_contract_examples() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
    )
    request = InterpretationRequest(
        current_user_message=current_turn,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )
    wire_messages = interpreter_module._openrouter_wire_messages(
        interpreter_module._focused_strategy_extraction_messages(request)
    )

    prompt_text = "\n".join(message["content"] for message in wire_messages)
    assert "rsi_mean_reversion" not in prompt_text
    assert "candidate_strategy_draft" not in prompt_text
    assert "date_range='last 3 months'" not in prompt_text


def test_focused_date_window_prompt_treats_prose_endpoints_as_evidence() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    current_turn = (
        "Comprar y mantener AAPL durante los últimos 12 meses con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=current_turn,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            date_range={"end": "últimos 12 meses"},
        ),
    )
    request = InterpretationRequest(
        current_user_message=current_turn,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    prompt_text = "\n".join(
        message["content"]
        for message in interpreter_module._focused_date_window_extraction_messages(
            response=response,
            request=request,
        )
    )

    assert "partial date_range" in prompt_text
    assert "non-executable evidence" in prompt_text
    assert "relative lookback anchored to the present" in prompt_text
    assert "already a complete temporal constraint" in prompt_text
    assert "Never put prose or shorthand relative windows inside date_range" in prompt_text


@pytest.mark.asyncio
async def test_supported_date_gap_escalates_before_unrelated_audits(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized == "AAPL":
            return ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
        if normalized == "SPY":
            return ResolvedAssetStub(
                "SPY",
                "equity",
                name="SPDR S&P 500 ETF Trust",
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedDateWindowExtraction":
            return kwargs["schema_model"](
                has_date_window=False,
                confidence=0.2,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Comprar y mantener AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis=(
                    "Comprar y mantener AAPL durante los últimos 12 meses "
                    "con SPY como referencia."
                ),
                asset_universe=["AAPL"],
                asset_class="equity",
                comparison_baseline="SPY",
                date_range_raw_text="últimos 12 meses",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=12,
                    unit="month",
                    anchor="today",
                    confidence=0.9,
                    evidence="últimos 12 meses",
                ),
                confidence=0.9,
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
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="buy_and_hold",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.9,
            )
        if schema_name == "ExecutableStrategyGroundingAudit":
            return interpreter_module.ExecutableStrategyGroundingAudit(
                outcome="grounded",
                confidence=0.9,
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
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    current_turn = (
        "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia."
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=current_turn,
        assistant_response=(
            "Entendido: comprar y mantener AAPL por 12 meses, comparando contra "
            "SPY. ¿En qué fecha quieres que terminen esos 12 meses?"
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=current_turn,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=current_turn,
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
            current_user_message=current_turn,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    focused_strategy_index = calls.index("FocusedStrategyExtraction")
    last_date_window_index = len(calls) - 1 - calls[::-1].index(
        "FocusedDateWindowExtraction"
    )
    assert focused_strategy_index == last_date_window_index + 1
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
    draft = ready_response.candidate_strategy_draft
    assert draft.date_range == expected_range.payload
    assert draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
async def test_pending_date_answer_overrides_macro_context_interpretation(
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
                date_range_raw_text="calendario 2024",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="calendar_year",
                    year=2024,
                    confidence=0.91,
                    evidence="calendario 2024",
                ),
                confidence=0.91,
                evidence="calendario 2024",
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(confidence=0.9)
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-15", "end": "2026-06-12"},
        capital_amount=100000,
        comparison_baseline="SPY",
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="El usuario pregunta por el contexto macro de 2024.",
        assistant_response=(
            "Para entender cómo se comportaron los mercados en 2024, el "
            "contexto macro fue clave."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="calendario 2024",
        ),
        semantic_turn_act="educational_question",
        context_question_focus="macro_context",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="calendario 2024",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "requested_field": "date_range",
            },
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert calls[0] == "FocusedDateWindowExtraction"
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(kind="calendar_year", year=2024)
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.task_relation == "continue"
    assert ready_response.semantic_turn_act == "answer_pending_need"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    assert ready_response.context_question_focus is None
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_executable_supported_fields_clear_stale_clarification_prose(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def passthrough_signal_check(**kwargs):
        return kwargs["response"]

    async def no_grounding_repair(**kwargs):
        return None

    async def passthrough_asset_grounding(**kwargs):
        return kwargs["response"]

    async def no_field_audit(**kwargs):
        return None

    monkeypatch.setattr(
        interpreter_module,
        "_signal_rule_checked_response",
        passthrough_signal_check,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_executable_strategy_grounding",
        no_grounding_repair,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_asset_grounding_audited_response",
        passthrough_asset_grounding,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_stated_run_fields",
        no_field_audit,
    )

    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Comprar y mantener ETH durante los ultimos 8 meses.",
        assistant_response=(
            "El backtest directo no está disponible; elige otra regla."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="compra y manten eth ultimos 8 meses 100k",
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-10-13", "end": "2026-06-13"},
            capital_amount=100000,
            evidence_spans={
                "strategy_type": "compra y manten",
                "asset_universe": "eth",
                "date_range": "ultimos 8 meses",
                "capital_amount": "100k",
            },
        ),
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="compra y manten eth ultimos 8 meses 100k",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.intent == "backtest_execution"
    assert repaired.semantic_turn_act == "new_idea"
    assert (
        "executable_fields_overrode_clarification_prose" in repaired.reason_codes
    )


@pytest.mark.asyncio
async def test_supported_strategy_capability_conflict_audit_keeps_extra_rule_block(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model(
            drop_unsupported_strategy_logic=False,
            keep_unsupported_strategy_logic=True,
            confidence=0.92,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="El usuario quiere condicionar una compra de ETH a noticias.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Compra y mantén ETH cuando las noticias sean positivas durante 2024"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Compra y mantén ETH cuando las noticias sean positivas durante 2024"
            ),
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range="2024",
            capital_amount=100000,
            entry_logic="Comprar cuando las noticias sean positivas",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="cuando las noticias sean positivas",
                explanation=(
                    "The request depends on news sentiment, which is not executable."
                ),
                simplification_labels=["Compare with buy and hold"],
            )
        ],
    )

    audited = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Compra y mantén ETH cuando las noticias sean positivas durante 2024"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert audited is None


def test_llm_interpreter_does_not_merge_prior_dca_into_fresh_strategy(
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
        task_relation="new_task",
        user_goal_summary="User wants to define Apple dip buying.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Apple after big drops?",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple after big drops.",
            asset_universe=["AAPL"],
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Apple after big drops?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="strategy_drafting",
                completed=False,
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Buy a fixed amount every month.",
                    cadence="monthly",
                    capital_amount=500,
                ),
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.cadence is None
    assert strategy.capital_amount is None


def test_llm_interpreter_removes_stale_indicator_limit_when_user_only_said_drops(
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
        task_relation="new_task",
        user_goal_summary="User wants to test Apple after big drops.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Apple after big drops?",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple after big drops.",
            asset_universe=["AAPL"],
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="moving-average crossover",
                explanation=(
                    "Argus cannot execute that exact moving-average or "
                    "compound indicator logic yet."
                ),
                simplification_labels=["Compare NVDA with buy and hold"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Apple after big drops?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.strategy_type == "indicator_threshold"
    assert result.candidate_strategy_draft.cadence is None
    assert result.candidate_strategy_draft.capital_amount is None
    assert result.unsupported_constraints == []


def test_llm_interpreter_accepts_structured_date_ranges(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from last year to date.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Bitcoin from January 1 last year to date.",
            asset_universe=["BTC"],
            date_range={"start": "2025-01-01", "end": "today"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
    assert resolve_date_range(strategy.date_range, today=date(2026, 5, 3)).payload == {
        "start": "2025-01-01",
        "end": "2026-05-03",
    }


def test_llm_interpreter_keeps_relative_date_contract_when_model_invents_dates(
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Backtest TSLA with RSI thresholds over the last 5 years.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "test tsla rsi below 20 and sell above 60 over the last 5 years"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Test TSLA with RSI thresholds.",
            asset_universe=["TSLA"],
            indicator="rsi",
            entry_threshold=20,
            exit_threshold=60,
            date_range={"start": "2019-07-29", "end": "2024-07-29"},
            date_range_intent=LLMDateRangeIntent(
                kind="rolling_window",
                count=5,
                unit="year",
                anchor="today",
                evidence="last 5 years",
            ),
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "test tsla rsi below 20 and sell above 60 over the last 5 years"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(
            kind="rolling_window",
            count=5,
            unit="year",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert strategy.date_range == expected_range.payload


def test_llm_interpreter_preserves_user_since_year_when_model_defaults_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Invest $500 in Bitcoin every month since 2021.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="since 2021",
            date_range_intent=LLMDateRangeIntent(
                kind="since",
                year=2021,
                evidence="since 2021",
            ),
            cadence="monthly",
            capital_amount=500,
            evidence_spans={"cadence": "every month"},
            field_provenance={
                "capital_amount": "recurring_contribution",
                "cadence": "explicit_user",
            },
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Invest $500 in Bitcoin every month since 2021.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    expected_range = interpreter_module.resolve_date_range_intent(
        LLMDateRangeIntent(kind="since", year=2021)
    )
    assert expected_range is not None
    assert strategy.date_range == expected_range.payload
    assert strategy.capital_amount == 500
    assert strategy.cadence == "monthly"


def test_llm_interpreter_rejects_invented_dca_cadence(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User supplied LYFT, dates, and total budget.",
        requires_clarification=True,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
                "$200,000 of capital"
            ),
            strategy_type="dca_accumulation",
            strategy_thesis="DCA into LYFT.",
            asset_universe=["LYFT"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2025-02-28"},
            cadence="monthly",
            assumptions=[
                "Invest equal dollar amounts at regular intervals (monthly) over the period."
            ],
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
                "$200,000 of capital"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="DCA setup.",
                )
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.cadence is None
    assert strategy.assumptions == []
    assert result.missing_required_fields == ["capital_amount", "cadence"]


def test_llm_interpreter_rejects_invented_dca_contribution_amount(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Tesla every month.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Tesla every month?",
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Tesla every month.",
            asset_universe=["TSLA"],
            asset_class="equity",
            cadence="monthly",
            capital_amount=10000,
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Tesla every month?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.capital_amount is None


@pytest.mark.asyncio
async def test_dca_contribution_role_audit_demotes_total_budget(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        assert schema_name == "DcaContributionRoleAudit"
        return interpreter_module.DcaContributionRoleAudit(
            recurring_contribution_explicit=False,
            total_budget_not_recurring=True,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User supplied total capital for a DCA setup.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
                "$200,000 of capital"
            ),
            strategy_type="dca_accumulation",
            strategy_thesis="Recurring buys for LYFT.",
            asset_universe=["LYFT"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2025-02-28"},
            capital_amount=200000,
            field_provenance={"capital_amount": "recurring_contribution"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    audited = await interpreter_module._dca_contribution_role_audited_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "I would like to invest in LYFT over 5 years feb 2020-feb 2025, "
                "$200,000 of capital"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = audited.candidate_strategy_draft
    assert audited.requires_clarification is True
    assert draft.capital_amount is None
    assert draft.total_capital == 200000
    assert "capital_amount" in audited.missing_required_fields
    assert "dca_total_budget_role_audited" in audited.reason_codes


@pytest.mark.asyncio
async def test_dca_contribution_role_audit_preserves_recurring_amount_with_cap(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        assert schema_name == "DcaContributionRoleAudit"
        return interpreter_module.DcaContributionRoleAudit(
            recurring_contribution_explicit=True,
            total_budget_not_recurring=True,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="User supplied recurring buys with a contribution cap.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "what if I bought $125 of BTC every two weeks from 2022 "
                "through 2023 with a $3000 cap?"
            ),
            strategy_type="dca_accumulation",
            strategy_thesis="Recurring buys for BTC.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range={"start": "2022-01-01", "end": "2023-12-31"},
            capital_amount=125,
            recurring_contribution=125,
            cadence="biweekly",
            total_capital=3000,
            sizing_mode="capital_amount",
            field_provenance={
                "capital_amount": "recurring_contribution",
                "recurring_contribution": "recurring_contribution",
                "total_capital": "cap",
                "cadence": "explicit_user",
            },
            extra_parameters={
                "recurring_contribution": 125,
                "recurring_cadence": "biweekly",
                "total_budget": 3000,
            },
        ),
        semantic_turn_act="new_idea",
    )

    audited = await interpreter_module._dca_contribution_role_audited_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "what if I bought $125 of BTC every two weeks from 2022 "
                "through 2023 with a $3000 cap?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = audited.candidate_strategy_draft
    assert audited.requires_clarification is False
    assert audited.intent == "backtest_execution"
    assert draft.capital_amount == 125
    assert draft.recurring_contribution == 125
    assert draft.cadence == "biweekly"
    assert draft.total_capital == 3000
    assert draft.sizing_mode == "capital_amount"
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["total_capital"] == "cap"
    assert "capital_amount" not in audited.missing_required_fields
    assert "dca_recurring_contribution_grounded_in_current_message" in (
        audited.reason_codes
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "symbol", "amount", "cadence", "budget"),
    [
        (
            "run the recurring buys only",
            "MSFT",
            750,
            "quarterly",
            9000,
        ),
        (
            "just use the scheduled deposits without that budget ceiling",
            "BTC",
            125,
            "biweekly",
            3000,
        ),
    ],
)
async def test_pending_response_option_selection_applies_structured_payload(
    monkeypatch,
    message: str,
    symbol: str,
    amount: float,
    cadence: str,
    budget: float,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        assert schema_name == "PendingResponseOptionSelectionAudit"
        return interpreter_module.PendingResponseOptionSelectionAudit(
            is_selection=True,
            selected_option_index=0,
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User selected a supported simplification.",
        assistant_response="Which simplification would you like to use?",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="dca_accumulation",
            strategy_thesis=f"Recurring buys for {symbol}.",
            asset_universe=[symbol],
            asset_class="crypto" if symbol == "BTC" else "equity",
            date_range={"start": "2021-01-01", "end": "2023-12-31"},
            capital_amount=amount,
            recurring_contribution=amount,
            cadence=cadence,
            total_capital=budget,
            field_provenance={
                "capital_amount": "recurring_contribution",
                "recurring_contribution": "recurring_contribution",
                "total_capital": "cap",
                "cadence": "explicit_user",
            },
            extra_parameters={"total_budget": budget},
        ),
        semantic_turn_act="unsupported_request",
    )

    audited = await interpreter_module._pending_response_option_selected_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis=f"Recurring buys for {symbol}.",
                    asset_universe=[symbol],
                    asset_class="crypto" if symbol == "BTC" else "equity",
                    date_range={"start": "2021-01-01", "end": "2023-12-31"},
                    capital_amount=amount,
                    cadence=cadence,
                    extra_parameters={
                        "recurring_contribution": amount,
                        "total_budget": budget,
                        "field_provenance": {
                            "capital_amount": "recurring_contribution",
                            "total_capital": "cap",
                            "cadence": "explicit_user",
                        },
                    },
                )
            ),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "response_intent": {
                    "kind": "unsupported_recovery",
                    "semantic_needs": ["simplification_choice"],
                    "options": [
                        {
                            "label": "Run recurring buys only",
                            "replacement_values": {
                                "ignore_initial_capital": True
                            },
                        }
                    ],
                },
            },
            user=UserState(user_id="u1"),
        ),
    )

    draft = audited.candidate_strategy_draft
    assert audited.intent == "backtest_execution"
    assert audited.requires_clarification is False
    assert audited.assistant_response is None
    assert audited.unsupported_constraints == []
    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == [symbol]
    assert draft.capital_amount == amount
    assert draft.recurring_contribution == amount
    assert draft.cadence == cadence
    assert draft.total_capital is None
    assert draft.initial_capital is None
    assert "total_budget" not in draft.extra_parameters
    assert draft.field_provenance.get("capital_amount") == "recurring_contribution"
    assert "total_capital" not in draft.field_provenance
    assert "pending_response_option_selected" in audited.reason_codes


@pytest.mark.asyncio
async def test_pending_response_option_selection_wins_over_generic_asset_parse(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        if schema_name == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary="User answered a pending recovery choice.",
                assistant_response="Ready to go?",
                candidate_strategy_draft=LLMStrategyDraft(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring buys.",
                    asset_universe=["JUST"],
                    asset_class="equity",
                    date_range={"start": "2021-01-01", "end": "2023-12-31"},
                ),
                semantic_turn_act="answer_pending_need",
            )
        assert schema_name == "PendingResponseOptionSelectionAudit"
        return interpreter_module.PendingResponseOptionSelectionAudit(
            is_selection=True,
            selected_option_index=0,
            confidence=0.92,
        )

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="just run the scheduled deposits without the budget ceiling",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring buys for MSFT.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range={"start": "2021-01-01", "end": "2023-12-31"},
                    capital_amount=750,
                    cadence="quarterly",
                    extra_parameters={
                        "recurring_contribution": 750,
                        "total_budget": 9000,
                        "field_provenance": {
                            "capital_amount": "recurring_contribution",
                            "total_capital": "cap",
                            "cadence": "explicit_user",
                        },
                    },
                )
            ),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "response_intent": {
                    "kind": "unsupported_recovery",
                    "semantic_needs": ["simplification_choice"],
                    "options": [
                        {
                            "label": "Run recurring buys only",
                            "replacement_values": {
                                "ignore_initial_capital": True
                            },
                        }
                    ],
                },
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.requires_clarification is False
    assert result.assistant_response is None
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]
    assert result.candidate_strategy_draft.capital_amount == 750
    assert result.candidate_strategy_draft.cadence == "quarterly"
    assert result.candidate_strategy_draft.extra_parameters.get(
        "recurring_contribution"
    ) == 750
    assert "total_budget" not in result.candidate_strategy_draft.extra_parameters
    assert "pending_response_option_selected" in result.reason_codes


@pytest.mark.asyncio
async def test_pending_response_option_selection_handles_approval_like_answer(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        if schema_name == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User approved the pending choice.",
                assistant_response=None,
                candidate_strategy_draft=LLMStrategyDraft(),
                semantic_turn_act="approval",
            )
        assert schema_name == "PendingResponseOptionSelectionAudit"
        return interpreter_module.PendingResponseOptionSelectionAudit(
            is_selection=True,
            selected_option_index=0,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    result = await OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    ).ainvoke(
        InterpretationRequest(
            current_user_message="yes, run the recurring buys",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Recurring buys for MSFT.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range={"start": "2021-01-01", "end": "2023-12-31"},
                    capital_amount=750,
                    cadence="quarterly",
                    extra_parameters={
                        "recurring_contribution": 750,
                        "total_budget": 9000,
                        "field_provenance": {
                            "capital_amount": "recurring_contribution",
                            "total_capital": "cap",
                            "cadence": "explicit_user",
                        },
                    },
                )
            ),
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "response_intent": {
                    "kind": "unsupported_recovery",
                    "semantic_needs": ["simplification_choice"],
                    "options": [
                        {
                            "label": "Run recurring buys only",
                            "replacement_values": {
                                "ignore_initial_capital": True
                            },
                        }
                    ],
                },
            },
            user=UserState(user_id="u1"),
        )
    )

    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.requires_clarification is False
    assert result.candidate_strategy_draft.asset_universe == ["MSFT"]
    assert "total_budget" not in result.candidate_strategy_draft.extra_parameters
    assert "pending_response_option_selected" in result.reason_codes


@pytest.mark.asyncio
async def test_dca_contribution_role_audit_preserves_current_recurring_amount(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_model, model_name
        assert schema_name == "DcaContributionRoleAudit"
        calls.append(schema_name)
        return interpreter_module.DcaContributionRoleAudit(
            recurring_contribution_explicit=True,
            total_budget_not_recurring=False,
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy NVDA every week in 2024.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought $250 of NVDA every week in 2024?",
            strategy_type="dca_accumulation",
            strategy_thesis="Buy NVDA weekly.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range={"end": "2024-12-31"},
            capital_amount=250,
            cadence="weekly",
            field_provenance={"capital_amount": "starting_capital"},
        ),
        requires_clarification=True,
        missing_required_fields=["capital_amount", "cadence", "date_range"],
        semantic_turn_act="new_idea",
    )

    audited = await interpreter_module._dca_contribution_role_audited_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message="What if I bought $250 of NVDA every week in 2024?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    draft = audited.candidate_strategy_draft
    assert draft.capital_amount == 250
    assert draft.recurring_contribution == 250
    assert draft.cadence == "weekly"
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["cadence"] == "explicit_user"
    assert "capital_amount" not in audited.missing_required_fields
    assert "cadence" not in audited.missing_required_fields
    assert "date_range" in audited.missing_required_fields
    assert "dca_recurring_contribution_grounded_in_current_message" in (
        audited.reason_codes
    )
    assert calls == ["DcaContributionRoleAudit"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "message",
        "draft_symbol",
        "draft_date_range",
        "draft_capital_amount",
        "recurring_amount",
        "cadence",
        "total_budget",
        "budget_source",
    ),
    [
        (
            "try buying $750 of MSFT quarterly from 2021 through 2023 with a $9,000 cap",
            "MSFT",
            {"start": "2021-01-01", "end": "2023-12-31"},
            9000,
            750,
            "quarterly",
            9000,
            "cap",
        ),
        (
            "what if I bought $125 of BTC every two weeks from 2022 through 2023 with a $3,000 budget cap",
            "BTC",
            {"start": "2022-01-01", "end": "2023-12-31"},
            3000,
            125,
            "biweekly",
            3000,
            "max_budget",
        ),
    ],
)
async def test_dca_contract_audit_recovers_recurring_buy_shape_before_capability_fallback(
    monkeypatch,
    message,
    draft_symbol,
    draft_date_range,
    draft_capital_amount,
    recurring_amount,
    cadence,
    total_budget,
    budget_source,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, model_name
        calls.append(schema_name)
        if schema_name == "DcaContractAudit":
            return schema_model(
                is_recurring_buy_request=True,
                recurring_contribution_amount=recurring_amount,
                cadence=cadence,
                total_budget_amount=total_budget,
                total_budget_source=budget_source,
                confidence=0.92,
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants recurring buys with a contribution cap.",
        assistant_response=(
            "Recurring buys are not available yet. Try buy and hold instead."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_type=None,
            strategy_thesis=message,
            asset_universe=[draft_symbol],
            date_range=draft_date_range,
            capital_amount=draft_capital_amount,
            field_provenance={"capital_amount": budget_source},
        ),
        missing_required_fields=["entry_logic", "exit_logic"],
        semantic_turn_act="unsupported_request",
        capability_question_focus="supported_strategies",
        artifact_target="none",
        reason_codes=["capability_side_question_audit"],
    )
    request = InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = repaired.candidate_strategy_draft
    assert "DcaContractAudit" in calls
    assert repaired.intent == "backtest_execution"
    assert repaired.semantic_turn_act == "new_idea"
    assert repaired.capability_question_focus is None
    assert repaired.assistant_response is None
    assert draft.strategy_type == "dca_accumulation"
    assert draft.capital_amount == recurring_amount
    assert draft.cadence == cadence
    assert draft.total_capital == total_budget
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["total_capital"] == budget_source
    assert "capital_amount" not in repaired.missing_required_fields
    assert "cadence" not in repaired.missing_required_fields
    assert "dca_contract_audit" in repaired.reason_codes


@pytest.mark.asyncio
async def test_dca_contract_audit_preserves_optional_cap_on_ready_dca_shape(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, model_name
        calls.append(schema_name)
        if schema_name == "DcaContractAudit":
            return schema_model(
                is_recurring_buy_request=True,
                recurring_contribution_amount=125,
                cadence="biweekly",
                total_budget_amount=3000,
                total_budget_source="cap",
                confidence=0.92,
            )
        if schema_name == "DcaContributionRoleAudit":
            return interpreter_module.DcaContributionRoleAudit(
                recurring_contribution_explicit=True,
                total_budget_not_recurring=True,
                confidence=0.9,
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants recurring buys with a contribution cap.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "what if I bought $125 of BTC every two weeks from 2022 "
                "through 2023 with a $3000 cap?"
            ),
            strategy_type="dca_accumulation",
            strategy_thesis="Recurring buys for BTC.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range={"start": "2022-01-01", "end": "2023-12-31"},
            capital_amount=125,
            cadence="biweekly",
            field_provenance={
                "capital_amount": "recurring_contribution",
                "cadence": "explicit_user",
            },
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message=(
            "what if I bought $125 of BTC every two weeks from 2022 "
            "through 2023 with a $3000 cap?"
        ),
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1"),
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    draft = repaired.candidate_strategy_draft
    assert "DcaContractAudit" in calls
    assert repaired.requires_clarification is False
    assert draft.strategy_type == "dca_accumulation"
    assert draft.capital_amount == 125
    assert draft.recurring_contribution == 125
    assert draft.cadence == "biweekly"
    assert draft.total_capital == 3000
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["total_capital"] == "cap"
    assert draft.extra_parameters["total_budget"] == 3000
    assert "dca_contract_audit" in repaired.reason_codes


def test_llm_interpreter_rejects_invented_initial_capital(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test Apple with RSI.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Simplify it to RSI.",
            strategy_type="indicator_threshold",
            strategy_thesis="Test Apple with RSI.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="last year",
            indicator="rsi",
            initial_capital=100000,
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Simplify it to RSI.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert "initial_capital" not in result.candidate_strategy_draft.extra_parameters


def test_llm_interpreter_drops_unstated_buy_hold_execution_defaults(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="Test TSLA over the past year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="test the past year",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla.",
            asset_universe=["TSLA"],
            date_range="past 1 year",
            sizing_mode="fixed",
            capital_amount=10000,
            position_size=1.0,
            risk_rules=[LLMRiskRule(type="max_position_size", value_pct=100.0)],
            field_provenance={"capital_amount": "default_assumption"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="test the past year",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.capital_amount is None
    assert strategy.position_size is None
    assert strategy.sizing_mode is None
    assert strategy.risk_rules == []
    assert "field_provenance" not in strategy.extra_parameters


def test_llm_interpreter_preserves_grounded_initial_capital(monkeypatch) -> None:
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test Apple with RSI using $10,000.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple with RSI using $10,000.",
            strategy_type="indicator_threshold",
            strategy_thesis="Test Apple with RSI.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="last year",
            indicator="rsi",
            initial_capital=10000,
            field_provenance={"initial_capital": "explicit_user"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Test Apple with RSI using $10,000.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.extra_parameters["initial_capital"] == 10000
    assert result.candidate_strategy_draft.capital_amount == 10000


def test_llm_interpreter_maps_grounded_total_capital_to_non_dca_starting_capital(
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
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test Tesla with a 50/200 crossover using $10,000.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "buy when the 50 crosses the 200 for Tesla from January 2022 "
                "to today with 10k"
            ),
            strategy_type="signal_strategy",
            strategy_thesis="Test Tesla with a 50/200 moving-average crossover.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range={"start": "2022-01-01", "end": "today"},
            total_capital=10000,
            field_provenance={"total_capital": "total_capital"},
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
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

    strategy = result.candidate_strategy_draft
    assert strategy.capital_amount == 10000
    assert strategy.extra_parameters["total_capital"] == 10000
    assert strategy.extra_parameters["field_provenance"]["capital_amount"] == (
        "starting_capital"
    )


@pytest.mark.asyncio
async def test_latest_result_routing_audit_repairs_capability_misroute(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def fake_json_schema(**kwargs):
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            focus="next_experiment",
            confidence=0.92,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": -32.6,
                            "benchmark_return_pct": 54.9,
                            "delta_vs_benchmark_pct": -87.5,
                        }
                    }
                },
                "config_snapshot": {"template": "signal_strategy"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what to try next.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_strategies",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="what should I try next?",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls
    assert calls[0]["schema_model"] is interpreter_module.LatestResultRoutingAudit
    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.result_followup_focus == "next_experiment"
    assert repaired.capability_question_focus is None
    assert "latest_result_routing_audit" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_routing_audit_refines_general_followup_focus(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def fake_json_schema(**kwargs):
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            focus="next_experiment",
            confidence=0.91,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": -32.6,
                            "benchmark_return_pct": 54.9,
                            "delta_vs_benchmark_pct": -87.5,
                        }
                    }
                },
                "config_snapshot": {"template": "signal_strategy"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what to try next.",
        assistant_response=(
            "Try MACD or a Bollinger Band filter next."
        ),
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="what should I try next?",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls
    assert calls[0]["schema_model"] is interpreter_module.LatestResultRoutingAudit
    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.result_followup_focus == "next_experiment"
    assert repaired.assistant_response is None
    assert "latest_result_routing_audit" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_routing_audit_marks_save_request(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(**kwargs):
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            save_requested=True,
            focus="general",
            confidence=0.92,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 35.0,
                            "benchmark_return_pct": 24.0,
                            "delta_vs_benchmark_pct": 11.0,
                        }
                    }
                },
                "config_snapshot": {"template": "buy_and_hold"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to save the latest result.",
        assistant_response="I can explain the latest result.",
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="save this",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.artifact_target == "latest_result"
    assert repaired.assistant_response is None
    assert "latest_result_routing_audit" in repaired.reason_codes
    assert "latest_result_save_requested" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_save_audit_can_mark_general_routing(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[type] = []

    async def fake_json_schema(**kwargs):
        schema = kwargs["schema_model"]
        calls.append(schema)
        if schema is interpreter_module.LatestResultRoutingAudit:
            return schema(
                targets_latest_result=True,
                save_requested=False,
                focus="general",
                confidence=0.92,
            )
        return schema(save_requested=True, confidence=0.94)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 35.0,
                            "benchmark_return_pct": 24.0,
                            "delta_vs_benchmark_pct": 11.0,
                        }
                    }
                },
                "config_snapshot": {"template": "buy_and_hold"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to save the latest result.",
        assistant_response="I can explain the latest result.",
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="save this",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == [
        interpreter_module.LatestResultRoutingAudit,
        interpreter_module.LatestResultSaveAudit,
    ]
    assert "latest_result_save_requested" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_save_audit_runs_after_non_general_result_focus(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[type] = []

    async def fake_json_schema(**kwargs):
        schema = kwargs["schema_model"]
        calls.append(schema)
        if schema is interpreter_module.LatestResultRoutingAudit:
            return schema(
                targets_latest_result=True,
                save_requested=False,
                focus="why_underperformed",
                confidence=0.9,
            )
        return schema(save_requested=True, confidence=0.94)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-save-focus",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 103.0,
                            "benchmark_return_pct": 47.0,
                            "delta_vs_benchmark_pct": 56.0,
                        }
                    }
                },
                "config_snapshot": {"template": "buy_and_hold"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to save the latest result.",
        assistant_response="I can explain what happened.",
        semantic_turn_act="result_followup",
        result_followup_focus="why_underperformed",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="save this",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == [
        interpreter_module.LatestResultRoutingAudit,
        interpreter_module.LatestResultSaveAudit,
    ]
    assert repaired.result_followup_focus == "why_underperformed"
    assert "latest_result_save_requested" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_routing_audit_repairs_copied_underfilled_strategy(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def fake_json_schema(**kwargs):
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            focus="why_underperformed",
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": -32.6,
                            "benchmark_return_pct": 54.9,
                            "delta_vs_benchmark_pct": -87.5,
                        }
                    }
                },
                "config_snapshot": {"template": "signal_strategy"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        missing_required_fields=["entry_logic"],
        user_goal_summary="User asks why the latest result happened.",
        assistant_response=(
            "The strategy likely missed the rally because the signal lagged."
        ),
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="why did that happen?",
            strategy_type="signal_strategy",
            strategy_thesis="why did that happen?",
            asset_universe=["TSLA"],
            date_range="2022-01-01 to 2026-05-20",
            timeframe="1D",
        ),
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="why did that happen?",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls
    assert calls[0]["schema_model"] is interpreter_module.LatestResultRoutingAudit
    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.result_followup_focus == "why_underperformed"
    assert repaired.assistant_response is None
    assert repaired.missing_required_fields == []
    assert "latest_result_routing_audit" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_routing_audit_refines_what_tested_when_user_asks_benchmark_why(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def fake_json_schema(**kwargs):
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            focus="why_underperformed",
            confidence=0.88,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["BTC"],
                "benchmark_symbol": "BTC",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 75.5,
                            "benchmark_return_pct": 75.5,
                            "delta_vs_benchmark_pct": 0.0,
                        }
                    }
                },
                "config_snapshot": {"template": "buy_and_hold"},
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the result matched the benchmark.",
        assistant_response="I tested BTC buy and hold against BTC.",
        semantic_turn_act="result_followup",
        result_followup_focus="what_tested",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="so why did it match BTC exactly?",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls
    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.result_followup_focus == "why_underperformed"
    assert repaired.assistant_response is None
    assert "latest_result_routing_audit" in repaired.reason_codes


@pytest.mark.asyncio
async def test_latest_result_routing_audit_checks_copied_executable_result_shape(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[dict[str, object]] = []

    async def fake_json_schema(**kwargs):
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            targets_latest_result=True,
            focus="why_underperformed",
            confidence=0.9,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["BTC"],
                "benchmark_symbol": "BTC",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 75.1,
                            "benchmark_return_pct": 75.1,
                            "delta_vs_benchmark_pct": 0.0,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "resolved_strategy": {
                        "strategy_type": "buy_and_hold",
                        "asset_universe": ["BTC"],
                    },
                },
            },
        )
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the latest BTC run matched BTC.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="why did it match BTC exactly?",
            strategy_type="buy_and_hold",
            strategy_thesis="Explain why the BTC run matched BTC.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range={"start": "2024-01-01", "end": "2026-05-20"},
            timeframe="1D",
        ),
        semantic_turn_act="new_idea",
    )

    repaired = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="structured/primary",
        request=InterpretationRequest(
            current_user_message="why did it match BTC exactly?",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls
    assert calls[0]["schema_model"] is interpreter_module.LatestResultRoutingAudit
    assert repaired.semantic_turn_act == "result_followup"
    assert repaired.result_followup_focus == "why_underperformed"
    assert repaired.assistant_response is None
    assert "latest_result_routing_audit" in repaired.reason_codes


def test_llm_interpreter_honors_explicit_buy_and_hold_over_entry_like_phrase(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from January 1 last year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Bitcoin from January 1 last year.",
            asset_universe=["BTC"],
            date_range={"start": "2024-01-01", "end": "today"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert result.requires_clarification is False


def test_llm_interpreter_preserves_actual_user_phrasing_when_model_rewrites_it(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    user_message = (
        "let's try a basic buy and hold on BTC from jan first last year to date"
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Buy and hold BTC.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy and hold on BTC from jan first last 1 year to date",
            strategy_type="buy_and_hold",
            asset_universe=["BTC"],
            date_range={"start": "2025-01-01", "end": "today"},
            capital_amount=10000,
            comparison_baseline="BTC",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=user_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.raw_user_phrasing == user_message
    assert strategy.strategy_thesis == user_message
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}


def test_focused_strategy_repair_prompt_covers_starter_capability_shapes() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    messages = interpreter_module._focused_strategy_extraction_messages(
        InterpretationRequest(
            current_user_message="What if I bought Bitcoin this year so far?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )
    prompt = messages[0].content

    assert "year_to_date" in prompt
    assert "recurring_contribution" in prompt
    assert "dca_accumulation" in prompt
    assert "supported buy_and_hold simulation" in prompt
    assert "recurring fixed-amount purchase" in prompt


def test_dca_required_fields_accept_resolved_date_range_intent() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    draft = LLMStrategyDraft(
        strategy_type="dca_accumulation",
        asset_universe=["NVDA"],
        asset_class="equity",
        capital_amount=250,
        recurring_contribution=250,
        cadence="weekly",
        date_range_intent=interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=1,
            unit="year",
            anchor="today",
        ),
    )

    missing = interpreter_module._capability_required_missing_fields_for_canonical_strategy(
        ["date_range"],
        draft=draft,
    )
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=1,
            unit="year",
            anchor="today",
        )
    )

    assert expected_range is not None
    assert missing == []
    assert draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_complete_absolute_run_skips_optional_runtime_readiness_audits(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "MSFT"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity", name=normalized)

    async def fail_optional_audit(**_kwargs):
        raise AssertionError("optional readiness audit should not run")

    async def fail_schema_audit(**_kwargs):
        raise AssertionError("structured audit should not run")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fail_schema_audit,
    )
    for name in (
        "_pending_response_option_selected_response",
        "_requested_asset_answer_candidate_audited_response",
        "_latest_result_routing_audited_response",
        "_asset_grounding_audited_response",
        "_capability_side_question_audited_response",
        "_context_question_audited_response",
        "_dca_contract_audited_response",
        "_strategy_family_continuity_audited_response",
        "_dca_contribution_role_audited_response",
        "_audit_supported_strategy_capability_conflict",
        "_focused_date_window_audited_response",
        "_supported_date_gap_schema_repaired_response",
        "_repair_incomplete_strategy_extraction",
        "_audit_stated_run_fields",
        "_audit_executable_strategy_grounding",
    ):
        monkeypatch.setattr(interpreter_module, name, fail_optional_audit)

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
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener AAPL y MSFT con pesos iguales.",
            asset_universe=["AAPL", "MSFT"],
            asset_class="equity",
            date_range={"start": "2025-01-01", "end": "2026-06-05"},
            capital_amount=10000,
            comparison_baseline="SPY",
            field_provenance={"capital_amount": "starting_capital"},
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

    assert interpreter_module._response_can_skip_optional_runtime_readiness_audits(
        response=response,
        request=request,
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2026-06-05",
    }
    assert ready_response.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "MSFT",
    ]
    assert ready_response.candidate_strategy_draft.comparison_baseline == "SPY"
    assert ready_response.candidate_strategy_draft.capital_amount == 10000


@pytest.mark.asyncio
async def test_missing_starting_capital_rechecks_before_optional_runtime_audits(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "MSFT"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity", name=normalized)

    async def fail_optional_audit(**_kwargs):
        raise AssertionError("optional readiness audit should not run")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=10000,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    for name in (
        "_pending_response_option_selected_response",
        "_requested_asset_answer_candidate_audited_response",
        "_latest_result_routing_audited_response",
        "_asset_grounding_audited_response",
        "_capability_side_question_audited_response",
        "_context_question_audited_response",
        "_dca_contract_audited_response",
        "_strategy_family_continuity_audited_response",
        "_dca_contribution_role_audited_response",
        "_audit_supported_strategy_capability_conflict",
        "_focused_date_window_audited_response",
        "_supported_date_gap_schema_repaired_response",
        "_repair_incomplete_strategy_extraction",
        "_audit_stated_run_fields",
        "_audit_executable_strategy_grounding",
    ):
        monkeypatch.setattr(interpreter_module, name, fail_optional_audit)

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
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener AAPL y MSFT con pesos iguales.",
            asset_universe=["AAPL", "MSFT"],
            asset_class="equity",
            date_range={"start": "2025-01-01", "end": "2026-06-05"},
            comparison_baseline="SPY",
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

    assert (
        interpreter_module._optional_runtime_readiness_audit_blocker(
            response=response,
            request=request,
        )
        == "stated_starting_capital_recheck"
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert calls == ["StatedStartingCapitalAudit"]
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2026-06-05",
    }
    assert ready_response.candidate_strategy_draft.asset_universe == [
        "AAPL",
        "MSFT",
    ]
    assert ready_response.candidate_strategy_draft.comparison_baseline == "SPY"
    assert ready_response.candidate_strategy_draft.capital_amount == 10000
    assert ready_response.candidate_strategy_draft.field_provenance[
        "capital_amount"
    ] == "starting_capital"
    assert "stated_starting_capital_recheck" in ready_response.reason_codes
    assert "stated_run_field_fidelity_audit" in ready_response.reason_codes


@pytest.mark.asyncio
async def test_missing_turn_act_underfilled_strategy_repairs_before_baseline_audits(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL", "MSFT"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity", name=normalized)

    async def fail_baseline_audit(**_kwargs):
        raise AssertionError("baseline audit should not run before focused repair")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
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
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=False,
                confidence=0.1,
            )
        if schema_name == "StatedRunFieldFidelityAudit":
            return interpreter_module.StatedRunFieldFidelityAudit(confidence=0.9)
        if schema_name == "StatedStartingCapitalAudit":
            return interpreter_module.StatedStartingCapitalAudit(
                starting_capital=None,
                confidence=0.9,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type=None,
                confidence=0.2,
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )
    for name in (
        "_capability_side_question_audited_response",
        "_context_question_audited_response",
        "_dca_contract_audited_response",
        "_strategy_family_continuity_audited_response",
        "_dca_contribution_role_audited_response",
    ):
        monkeypatch.setattr(interpreter_module, name, fail_baseline_audit)

    message = (
        "Prueba una estrategia de comprar y mantener AAPL y MSFT con pesos "
        "iguales desde el 1 de enero de 2025 hasta el 5 de junio de 2026 "
        "con 10000 dolares"
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener AAPL y MSFT con pesos iguales.",
            asset_universe=["AAPL", "MSFT"],
            asset_class="equity",
            comparison_baseline="SPY",
        ),
        semantic_turn_act=None,
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
    assert ready_response.semantic_turn_act == "new_idea"
    assert "coerced_missing_turn_act_to_new_idea" in ready_response.reason_codes
    assert ready_response.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2026-06-05",
    }
    assert ready_response.candidate_strategy_draft.capital_amount == 10000


def test_unprovenanced_non_default_benchmark_blocks_runtime_fast_path(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized not in {"AAPL"}:
            raise ValueError("invalid_symbol")
        return ResolvedAssetStub(normalized, "equity", name=normalized)

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)

    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test AAPL from January 1, 2025 to June 5, 2026.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-01-01", "end": "2026-06-05"},
            capital_amount=10000,
            comparison_baseline="QQQ",
        ),
        semantic_turn_act="new_idea",
        artifact_target="none",
    )
    request = InterpretationRequest(
        current_user_message="Test AAPL from January 1, 2025 to June 5, 2026.",
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u1", language_preference="en"),
    )

    assert (
        interpreter_module._optional_runtime_readiness_audit_blocker(
            response=response,
            request=request,
        )
        == "unprovenanced_benchmark"
    )
    assert not interpreter_module._response_can_skip_optional_runtime_readiness_audits(
        response=response,
        request=request,
    )


def test_relative_window_evidence_blocks_optional_readiness_fast_path() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = (
        "Compra y mantén AAPL durante los últimos 2 años con 10000 dolares."
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            language="es-419",
            strategy_type="buy_and_hold",
            strategy_thesis=message,
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2026-01-01"},
            capital_amount=10000,
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

    assert interpreter_module._current_turn_has_relative_window_evidence(request)
    assert interpreter_module._response_needs_temporal_runtime_repair(
        response=response,
        request=request,
    )
    assert not interpreter_module._response_can_skip_optional_runtime_readiness_audits(
        response=response,
        request=request,
    )


@pytest.mark.asyncio
async def test_dca_repair_uses_focused_date_audit_from_bounded_evidence_span(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar compras recurrentes de Nvidia.",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar $250 de Nvidia cada semana.",
                asset_universe=["NVDA"],
                asset_class="equity",
                capital_amount=250,
                recurring_contribution=250,
                cadence="weekly",
                confidence=0.91,
                evidence_spans={"date_range_intent": "durante el último año"},
            )
        if schema_name == "FocusedDateWindowExtraction":
            return interpreter_module.FocusedDateWindowExtraction(
                has_date_window=True,
                date_range_raw_text="durante el último año",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=1,
                    unit="year",
                    anchor="today",
                    confidence=0.92,
                    evidence="durante el último año",
                ),
                confidence=0.92,
                evidence="durante el último año",
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    async def no_conflict_audit(**_kwargs):
        return None

    async def passthrough_response(**kwargs):
        return kwargs["response"]

    monkeypatch.setattr(
        interpreter_module,
        "_asset_grounding_audited_response",
        passthrough_response,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_capability_side_question_audited_response",
        passthrough_response,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_context_question_audited_response",
        passthrough_response,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_audit_supported_strategy_capability_conflict",
        no_conflict_audit,
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    message = (
        "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
    )
    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=message,
        assistant_response="Las compras recurrentes no están disponibles.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_thesis=message,
            asset_universe=["NVDA"],
            asset_class="equity",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=message,
                explanation="The model over-routed a supported DCA request.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "exit_logic", "date_range"],
        semantic_turn_act="unsupported_request",
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
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=1,
            unit="year",
            anchor="today",
        )
    )

    assert "FocusedStrategyExtraction" in calls
    assert "FocusedDateWindowExtraction" in calls
    assert calls.index("FocusedStrategyExtraction") < calls.index(
        "FocusedDateWindowExtraction"
    )
    assert expected_range is not None
    assert ready_response.intent == "backtest_execution"
    assert ready_response.unsupported_constraints == []
    assert ready_response.missing_required_fields == []
    assert ready_response.candidate_strategy_draft.date_range == expected_range.payload


@pytest.mark.asyncio
async def test_counterfactual_bitcoin_ytd_starter_gets_focused_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized in {"BITCOIN", "BTC"}:
            return ResolvedAssetStub(
                "BTC",
                "crypto",
                name="Bitcoin",
                raw_symbol=query,
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar Bitcoin en lo que va del año.",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar Bitcoin en lo que va del año.",
                asset_universe=["Bitcoin"],
                asset_class="crypto",
                date_range_raw_text="en lo que va del año",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="year_to_date",
                    confidence=0.93,
                    evidence="en lo que va del año",
                ),
                confidence=0.91,
                evidence_spans={
                    "strategy_type": "compraba Bitcoin",
                    "asset_universe": "Bitcoin",
                    "date_range": "en lo que va del año",
                },
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="¿Qué habría pasado si compraba Bitcoin en lo que va del año?",
        assistant_response="Esa idea necesita una regla de entrada y salida.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "¿Qué habría pasado si compraba Bitcoin en lo que va del año?"
            ),
            strategy_thesis=(
                "¿Qué habría pasado si compraba Bitcoin en lo que va del año?"
            ),
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="¿Qué habría pasado si compraba Bitcoin en lo que va del año?",
                explanation="The model over-routed a supported counterfactual purchase.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "asset_universe", "exit_logic"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    request = InterpretationRequest(
        current_user_message=(
            "¿Qué habría pasado si compraba Bitcoin en lo que va del año?"
        ),
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
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(kind="year_to_date")
    )
    assert expected_range is not None
    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["BTC"]
    assert draft.asset_class == "crypto"
    assert draft.date_range == expected_range.payload

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = interpreter._to_runtime_interpretation(ready_response, request=request)
    assert result.candidate_strategy_draft.asset_universe == ["BTC"]


@pytest.mark.asyncio
async def test_weekly_nvidia_dca_starter_gets_focused_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized in {"NVIDIA", "NVDA"}:
            return ResolvedAssetStub(
                "NVDA",
                "equity",
                name="NVIDIA Corporation",
                raw_symbol=query,
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar compras recurrentes de Nvidia.",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar $250 de Nvidia cada semana.",
                asset_universe=["NVDA"],
                asset_class="equity",
                capital_amount=250,
                recurring_contribution=250,
                cadence="weekly",
                date_range_raw_text="durante el último año",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=1,
                    unit="year",
                    anchor="today",
                    confidence=0.92,
                    evidence="durante el último año",
                ),
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "Nvidia",
                    "recurring_contribution": "$250",
                    "cadence": "cada semana",
                    "date_range": "durante el último año",
                },
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
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
        ),
        assistant_response="Las compras recurrentes no están disponibles.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            strategy_thesis=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range={"start": "2025-06-13", "end": "2026-06-13"},
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
                ),
                explanation="The model over-routed a supported DCA request.",
                simplification_labels=["Compare with buy and hold"],
            )
        ],
        missing_required_fields=["entry_logic", "asset_universe", "exit_logic"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.unsupported_constraints == []
    draft = ready_response.candidate_strategy_draft
    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=1,
            unit="year",
            anchor="today",
        )
    )
    assert expected_range is not None
    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == ["NVDA"]
    assert draft.asset_class == "equity"
    assert draft.recurring_contribution == 250
    assert draft.capital_amount == 250
    assert draft.cadence == "weekly"
    assert draft.date_range == expected_range.payload
    assert draft.field_provenance["capital_amount"] == "recurring_contribution"
    assert draft.field_provenance["recurring_contribution"] == "explicit_user"
    assert draft.field_provenance["cadence"] == "explicit_user"


@pytest.mark.asyncio
async def test_dca_capability_conflict_repair_does_not_stop_underfilled(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized in {"NVIDIA", "NVDA"}:
            return ResolvedAssetStub(
                "NVDA",
                "equity",
                name="NVIDIA Corporation",
                raw_symbol=query,
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=False,
                confidence=0.92,
            )
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            return interpreter_module.SupportedStrategyCapabilityConflictAudit(
                selected_strategy_type="dca_accumulation",
                drop_unsupported_strategy_logic=True,
                keep_unsupported_strategy_logic=False,
                confidence=0.92,
            )
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar compras recurrentes de Nvidia.",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar $250 de Nvidia cada semana.",
                asset_universe=["NVDA"],
                asset_class="equity",
                capital_amount=250,
                recurring_contribution=250,
                cadence="weekly",
                date_range_raw_text="durante el último año",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=1,
                    unit="year",
                    anchor="today",
                    confidence=0.92,
                    evidence="durante el último año",
                ),
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "Nvidia",
                    "recurring_contribution": "$250",
                    "cadence": "cada semana",
                    "date_range": "durante el último año",
                },
            )
        raise AssertionError(f"Unexpected schema {schema_name}")

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_asset)
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        audit_stub,
    )

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
        ),
        assistant_response="Las compras recurrentes no están disponibles.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            strategy_thesis=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range={"start": "2025-06-13", "end": "2026-06-13"},
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=(
                    "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
                ),
                explanation="The model over-routed a supported DCA request.",
                simplification_labels=["dca_accumulation"],
            )
        ],
        missing_required_fields=["entry_logic", "asset_universe", "exit_logic"],
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    ready_response = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "SupportedStrategyCapabilityConflictAudit" in calls
    assert "FocusedStrategyExtraction" in calls
    assert calls.index("SupportedStrategyCapabilityConflictAudit") < calls.index(
        "FocusedStrategyExtraction"
    )
    assert ready_response.intent == "backtest_execution"
    assert ready_response.requires_clarification is False
    assert ready_response.assistant_response is None
    assert ready_response.missing_required_fields == []
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == ["NVDA"]
    assert draft.recurring_contribution == 250
    assert draft.capital_amount == 250
    assert draft.cadence == "weekly"


@pytest.mark.asyncio
async def test_vague_guidance_does_not_preempt_focused_strategy_extraction(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    def resolve_asset(query: str) -> ResolvedAssetStub:
        normalized = query.strip().upper()
        if normalized in {"NVIDIA", "NVDA"}:
            return ResolvedAssetStub(
                "NVDA",
                "equity",
                name="NVIDIA Corporation",
                raw_symbol=query,
            )
        raise ValueError("invalid_symbol")

    calls: list[str] = []

    async def audit_stub(**kwargs):
        schema_name = kwargs["schema_name"]
        calls.append(schema_name)
        if schema_name == "FocusedStrategyExtraction":
            return interpreter_module.FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="Probar compras recurrentes de Nvidia.",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar $250 de Nvidia cada semana.",
                asset_universe=["NVDA"],
                asset_class="equity",
                capital_amount=250,
                recurring_contribution=250,
                cadence="weekly",
                date_range_raw_text="durante el último año",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=1,
                    unit="year",
                    anchor="today",
                    confidence=0.92,
                    evidence="durante el último año",
                ),
                confidence=0.91,
                evidence_spans={
                    "asset_universe": "Nvidia",
                    "recurring_contribution": "$250",
                    "cadence": "cada semana",
                    "date_range": "durante el último año",
                },
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
        requires_clarification=False,
        user_goal_summary="El usuario quiere probar una idea de inversión.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            strategy_thesis=(
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
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
                "¿Qué habría pasado si compraba $250 de Nvidia cada semana durante el último año?"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1", language_preference="es-419"),
        ),
    )

    assert "FocusedStrategyExtraction" in calls
    assert "vague_strategy_start_guidance" not in ready_response.reason_codes
    assert ready_response.intent == "backtest_execution"
    draft = ready_response.candidate_strategy_draft
    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == ["NVDA"]
    assert draft.recurring_contribution == 250
    assert draft.cadence == "weekly"
