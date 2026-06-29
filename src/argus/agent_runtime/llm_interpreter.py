from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from argus.agent_runtime.artifact_edit_planner import (
    plan_artifact_assumption_edit,
)
from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_universe_operation,
)
from argus.agent_runtime.asset_text_grounding import (
    grounded_asset_mention_has_name_support,
    grounded_asset_mentions_from_text,
)
from argus.agent_runtime.benchmark_evidence import (
    current_message_has_extra_provider_asset_for_benchmark,
    provider_ticker_assets_from_text,
)
from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.interpreter.artifact_assumption_edit import (  # noqa: F401
    _apply_legacy_flat_edit_fields,
    _apply_resolved_edit_to_draft,
    _current_artifact_asset_universe,
    _normalized_ticker_symbol,
    _request_targets_pending_artifact_assumption_edit,
    _response_from_artifact_assumption_edit_plan,
)
from argus.agent_runtime.interpreter.asset_grounding import (  # noqa: F401
    _artifact_target_from_response,
    _comparison_baseline_has_trusted_provenance,
    _context_inheritable_asset_symbols,
    _normalized_extracted_symbol,
    _normalized_extracted_symbols,
    _prior_strategy_symbols,
    _provider_exact_ticker_supports_extracted_symbol,
    _requested_asset_answer_candidate_audit_messages,
)
from argus.agent_runtime.interpreter.audits import (  # noqa: F401
    AssetAnswerCandidateAudit,
    AssetGroundingAudit,
    CapabilitySideQuestionAudit,
    ContextQuestionAudit,
    DcaContractAudit,
    DcaContributionRoleAudit,
    ExecutableStrategyGroundingAudit,
    LatestResultRoutingAudit,
    LatestResultSaveAudit,
    PendingResponseOptionSelectionAudit,
    StatedRunFieldFidelityAudit,
    StatedStartingCapitalAudit,
    StrategyFamilyContinuityAudit,
    SupportedStrategyCapabilityConflictAudit,
)
from argus.agent_runtime.interpreter.dca_audits import (  # noqa: F401
    _capability_required_missing_fields_for_canonical_strategy,
    _dca_contract_audit_messages,
    _dca_contract_missing_fields,
    _dca_contribution_role_audit_messages,
    _dca_draft_has_recurring_amount,
    _dca_total_budget_source,
    _move_dca_total_budget_out_of_recurring_amount,
    _response_from_dca_contract_audit,
    _response_needs_dca_contribution_role_audit,
    _response_needs_strategy_family_continuity_audit,
    _strategy_family_continuity_audit_messages,
)
from argus.agent_runtime.interpreter.draft_shape import (  # noqa: F401
    _elapsed_ms,
    _llm_signal_strategy_is_underfilled,
    _llm_strategy_draft_has_executable_shape,
    _llm_strategy_draft_has_structural_execution_fields,
    _llm_strategy_draft_has_structured_rule_or_indicator_fields,
    _llm_strategy_draft_has_supported_artifact_assumption_edit,
    _llm_strategy_draft_has_unstructured_strategy_text,
    _material_strategy_updates_from_draft,
    _normalized_material_date_range_payload,
    _normalized_material_strategy_value,
    _request_has_active_strategy_context,
    _request_has_failed_action_launch_payload,
    _request_has_latest_result,
    _response_replays_prior_strategy_without_current_turn_update,
    _response_underfills_active_artifact_assumption_edit,
    _response_underfills_active_artifact_rule_edit,
    _response_underfills_pending_result_refinement,
    _structured_strategy_missing_fields_can_clarify,
)
from argus.agent_runtime.interpreter.executable_grounding import (  # noqa: F401
    _draft_has_non_executable_timeframe_label,
    _draft_uses_launch_default_window,
    _executable_strategy_grounding_messages,
    _response_from_executable_strategy_grounding_audit,
    _response_needs_executable_strategy_grounding_audit,
    _response_needs_launch_field_fidelity_repair,
)
from argus.agent_runtime.interpreter.focused_extraction import (  # noqa: F401
    _base_response_was_unsupported,
    _comparison_baseline_provenance,
    _focused_artifact_edit_messages,
    _focused_extraction_field_provenance,
    _focused_strategy_extraction_messages,
    _merge_focused_repair_with_base,
    _openrouter_wire_messages,
)
from argus.agent_runtime.interpreter.run_field_audits import (  # noqa: F401
    _clear_rule_or_indicator_fields,
    _date_endpoint_is_runtime_current,
    _date_evidence_tokens_from_text,
    _dca_response_needs_semantic_field_audit,
    _draft_capital_needs_stated_run_field_audit,
    _draft_contains_structured_capital_context,
    _draft_date_evidence_tokens,
    _draft_date_range_has_unstated_current_endpoint,
    _draft_date_range_needs_stated_run_field_audit,
    _draft_has_non_money_execution_anchor,
    _draft_has_timeframe_evidence_for_audit,
    _draft_has_unprovenanced_benchmark,
    _draft_non_capital_numeric_evidence_tokens,
    _explicit_benchmark_ticker_queries,
    _focused_repair_capital_needs_stated_run_field_audit,
    _latest_result_fact_bank_for_routing,
    _latest_result_routing_audit_messages,
    _pending_dca_assumption_reply_needs_stated_run_field_audit,
    _resolved_runtime_date_range_from_draft,
    _response_from_current_message_run_field_contract,
    _response_from_stated_run_field_fidelity_audit,
    _response_has_pending_base_field,
    _response_needs_current_message_date_repair,
    _response_needs_latest_result_routing_audit,
    _response_needs_missing_benchmark_fidelity_audit,
    _response_needs_supported_strategy_capability_conflict_audit,
    _response_targets_latest_result_followup,
    _response_with_executable_fields_preferred_over_clarification_prose,
    _response_with_resolved_runtime_date_range,
    _response_with_supported_strategy_capability_conflict_removed,
    _stated_run_field_audit_omitted_expected_fields,
    _stated_run_field_fidelity_messages,
    _structured_draft_context_text,
    _structured_supported_strategy_capability_conflict_fallback,
    _supported_strategy_capability_conflict_messages,
    _text_contains_capital_audit_signal,
)
from argus.agent_runtime.interpreter.shared import (  # noqa: F401
    _COMPARISON_BASELINE_EVIDENCE_KEYS,
    _DATE_EVIDENCE_SPAN_KEYS,
    _EXECUTABLE_TIMEFRAMES,
    _RECURRING_CAPITAL_SOURCES,
    _TOTAL_CAPITAL_SOURCES,
    _bounded_date_evidence_candidates,
    _capital_source,
    _date_range_audit_has_partial_endpoint,
    _date_range_from_bounded_evidence,
    _date_range_from_intent_or_bounded_evidence,
    _date_range_with_fidelity_audit,
    _date_value_is_less_specific,
    _draft_has_comparison_baseline_evidence,
    _draft_has_semantic_date_window_evidence,
    _draft_semantic_evidence_spans,
    _field_path_base,
    _has_complete_date_range_payload,
    _llm_strategy_draft_has_concrete_execution_target,
    _llm_strategy_draft_has_extractable_fields,
    _llm_strategy_draft_has_rule_or_indicator_fields,
    _llm_value_is_empty,
    _natural_time_language_candidates_from_hints,
    _normalized_stated_field,
    _selected_requested_field_base,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.interpreter.signal_rule import (  # noqa: F401
    _asset_recovery_query_is_explicit_ticker,
    _audit_signal_rule_grounding_if_needed,
    _llm_draft_executable_indicator_spec,
    _llm_strategy_draft_has_non_asset_strategy_anchor,
    _pending_signal_rule_planning_response,
    _prior_strategy_payload,
    _request_targets_pending_signal_rule,
    _response_from_signal_grounding_audit,
    _response_from_signal_rule_plan,
    _response_has_signal_rule_shape,
    _response_needs_indicator_default_grounding_repair,
    _response_needs_indicator_parameter_repair,
    _response_needs_signal_rule_grounding_audit,
    _response_needs_signal_rule_plan,
    _response_needs_supported_signal_rule_recovery,
    _signal_rule_plan_raw_value,
    _signal_rule_planning_context_from_prior,
    _supported_signal_rule_planning_response,
)
from argus.agent_runtime.interpreter.strategy_builder import (  # noqa: F401
    _apply_executable_indicator_defaults,
    _apply_signal_strategy_defaults,
    _clean_date_range_intent_payload,
    _clean_evidence_spans,
    _clean_optional_text,
    _compact_asset_evidence_token,
    _date_range_intent_from_bounded_evidence,
    _dca_amount_has_user_provenance,
    _dca_cadence_has_user_provenance,
    _dedupe_resolution_provenance,
    _ensure_dca_missing_execution_fields,
    _evidence_backed_field_provenance,
    _field_owned_indicator_asset_candidate,
    _ground_strategy_in_current_turn,
    _grounded_initial_capital,
    _grounded_recurring_contribution,
    _grounded_total_capital,
    _humanize_simplification_label,
    _indicator_key_from_strategy,
    _indicator_parameters_from_strategy,
    _merge_prior_strategy,
    _message_has_cashtag_for_asset,
    _non_dca_starting_capital_from_total_fields,
    _normalize_llm_domain_slots,
    _remove_stale_indicator_constraints,
    _remove_unstated_model_defaults,
    _risk_rule_is_unstated_full_position_default,
    _strategy_from_llm,
    _strategy_has_executable_rule_semantics,
    _strategy_has_explicit_asset_evidence,
    _strategy_has_indicator_parameters,
    _strategy_has_rule_semantics,
    _strategy_uses_rule_or_indicator_context,
    _unsupported_from_llm,
    _validate_indicator_rule_support,
)
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    FocusedStrategyExtraction,
    LLMAmbiguousField,
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.presentation_i18n import (
    asset_universe_operation_clarification_message,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
)
from argus.agent_runtime.run_field_contract import (
    current_message_execution_context_tokens,
)
from argus.agent_runtime.signal_rule_repair import (
    repair_signal_rule_plan,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ResolutionProvenance,
    ResolutionSource,
    StrategySummary,
)
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    executable_strategy_type,
    executable_strategy_type_from_extracted_fields,
    has_partial_explicit_date_range,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.agent_runtime.turn_execution_evidence import (
    current_turn_has_material_execution_evidence,
)
from argus.domain.market_data import is_ticker_like_query, resolve_asset
from argus.llm.openrouter import (
    OpenRouterTask,
    build_openrouter_model,
    invoke_openrouter_json_schema,
    log_openrouter_failure,
    openrouter_structured_model_candidates,
    openrouter_task_timeout_seconds,
    record_openrouter_route_receipt,
)
from argus.nlp.natural_time import (
    resolve_date_range_intent,
    resolve_date_range_text,
    resolve_rolling_window_intent_text,
)

_DEFAULT_RESOLVE_ASSET = resolve_asset
_INTERPRETATION_REPAIR_TASK: OpenRouterTask = "interpretation_repair"


def _selected_thread_metadata_context(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "none"
    context_keys = (
        "last_stage_outcome",
        "requested_field",
        "requested_fields",
        "artifact_target",
        "chat_action",
        "source_result_run_id",
        "failed_action",
        "response_intent",
    )
    context = {key: metadata[key] for key in context_keys if key in metadata}
    if not context:
        return "none"
    return json.dumps(context, sort_keys=True, default=str)


class OpenRouterStructuredInterpreter:
    def __init__(
        self,
        *,
        contract: CapabilityContract,
        model_name: str | None = None,
    ) -> None:
        self.contract = contract
        self.model_name = model_name
        self.last_status: str | None = None

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation | None:
        return asyncio.run(self.ainvoke(request))

    async def ainvoke(
        self, request: InterpretationRequest
    ) -> StructuredInterpretation | None:
        """
        Executes the interpretation turn.
        """
        messages = self._messages(request)
        if self.model_name is None:
            candidate_models = openrouter_structured_model_candidates()
            for index, candidate_model in enumerate(candidate_models):
                try:
                    response = await invoke_openrouter_json_schema(
                        task="interpretation",
                        messages=_openrouter_wire_messages(messages),
                        schema_model=LLMInterpretationResponse,
                        schema_name="LLMInterpretationResponse",
                        model_name=candidate_model,
                    )
                    if not isinstance(response, LLMInterpretationResponse):
                        continue
                    response = await _response_ready_for_runtime(
                        response=response,
                        preferred_model=candidate_model,
                        request=request,
                    )
                    self.last_status = "used" if index == 0 else "fallback_used"
                    return self._to_runtime_interpretation(response, request=request)
                except Exception as exc:
                    log_openrouter_failure(
                        task="interpretation",
                        model_name=candidate_model,
                        exc=exc,
                        message=(
                            "Direct LLM interpretation candidate failed; "
                            "trying next configured model"
                        ),
                    )
            repaired_response = await _plan_pending_artifact_assumption_edit(
                request=request,
                preferred_model=candidate_models[0] if candidate_models else "",
                require_failure_edit_evidence=True,
            )
            if repaired_response is not None:
                self.last_status = "fallback_used"
                return self._to_runtime_interpretation(
                    repaired_response,
                    request=request,
                )
            repaired_response = await _focused_strategy_repair_after_candidate_failures(
                request=request,
                preferred_model=candidate_models[0] if candidate_models else "",
            )
            if repaired_response is not None:
                self.last_status = "fallback_used"
                repaired_response = await _stated_run_field_audited_response(
                    response=repaired_response,
                    preferred_model=candidate_models[0] if candidate_models else "",
                    request=request,
                )
                return self._to_runtime_interpretation(
                    repaired_response,
                    request=request,
                )
            self.last_status = "failed"
            return None

        # 1. Try Primary Model
        model = build_openrouter_model("interpretation", model_name=self.model_name)
        if model:
            started_at = time.perf_counter()
            try:
                structured = model.with_structured_output(LLMInterpretationResponse)
                response = await asyncio.wait_for(
                    structured.ainvoke(messages),
                    timeout=openrouter_task_timeout_seconds("interpretation"),
                )
                if isinstance(response, LLMInterpretationResponse):
                    record_openrouter_route_receipt(
                        task="interpretation",
                        model_name=self.model_name,
                        mode="chat_model",
                        schema_name="LLMInterpretationResponse",
                        latency_ms=_elapsed_ms(started_at),
                        outcome="succeeded",
                    )
                    response = await _response_ready_for_runtime(
                        response=response,
                        preferred_model=self.model_name,
                        request=request,
                    )
                    self.last_status = "used"
                    return self._to_runtime_interpretation(response, request=request)
            except Exception as exc:
                record_openrouter_route_receipt(
                    task="interpretation",
                    model_name=self.model_name,
                    mode="chat_model",
                    schema_name="LLMInterpretationResponse",
                    latency_ms=_elapsed_ms(started_at),
                    outcome="failed",
                    failure_mode=type(exc).__name__,
                )
                log_openrouter_failure(
                    task="interpretation",
                    model_name=self.model_name,
                    exc=exc,
                    message="Primary LLM interpretation failed; attempting fallback",
                )

        # 2. Try Fallback Model (if primary failed or was unavailable)
        from argus.llm.openrouter import resolve_openrouter_model

        fallback_model_name = resolve_openrouter_model(
            fallback=True,
            task="interpretation",
        )

        # Don't retry with the same model name if resolve returned the same thing
        primary_model_name = resolve_openrouter_model(
            self.model_name,
            task="interpretation",
        )
        if not fallback_model_name or fallback_model_name == primary_model_name:
            self.last_status = "failed"
            return None

        fallback_model = build_openrouter_model(
            "interpretation", model_name=fallback_model_name
        )
        if fallback_model:
            started_at = time.perf_counter()
            try:
                structured = fallback_model.with_structured_output(
                    LLMInterpretationResponse
                )
                response = await asyncio.wait_for(
                    structured.ainvoke(messages),
                    timeout=openrouter_task_timeout_seconds("interpretation"),
                )
                if isinstance(response, LLMInterpretationResponse):
                    record_openrouter_route_receipt(
                        task="interpretation",
                        model_name=fallback_model_name,
                        mode="chat_model",
                        schema_name="LLMInterpretationResponse",
                        latency_ms=_elapsed_ms(started_at),
                        outcome="succeeded",
                    )
                    response = await _response_ready_for_runtime(
                        response=response,
                        preferred_model=fallback_model_name,
                        request=request,
                    )
                    self.last_status = "fallback_used"
                    return self._to_runtime_interpretation(response, request=request)
            except Exception as exc:
                self.last_status = "failed"
                record_openrouter_route_receipt(
                    task="interpretation",
                    model_name=fallback_model_name,
                    mode="chat_model",
                    schema_name="LLMInterpretationResponse",
                    latency_ms=_elapsed_ms(started_at),
                    outcome="failed",
                    failure_mode=type(exc).__name__,
                )
                log_openrouter_failure(
                    task="interpretation",
                    model_name=fallback_model_name,
                    exc=exc,
                    message="Fallback LLM interpretation failed",
                )

        repaired_response = await _plan_pending_artifact_assumption_edit(
            request=request,
            preferred_model=fallback_model_name or primary_model_name,
            require_failure_edit_evidence=True,
        )
        if repaired_response is not None:
            self.last_status = "fallback_used"
            return self._to_runtime_interpretation(repaired_response, request=request)
        repaired_response = await _focused_strategy_repair_after_candidate_failures(
            request=request,
            preferred_model=fallback_model_name or primary_model_name,
        )
        if repaired_response is not None:
            self.last_status = "fallback_used"
            repaired_response = await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=fallback_model_name or primary_model_name,
                request=request,
            )
            return self._to_runtime_interpretation(
                repaired_response,
                request=request,
            )
        return None

    def _messages(self, request: InterpretationRequest) -> list[BaseMessage]:
        prior_strategy = None
        active_confirmation = None
        latest_result = None
        latest_failed_action = None
        if request.latest_task_snapshot is not None:
            prior_strategy = (
                request.latest_task_snapshot.pending_strategy_summary
                or request.latest_task_snapshot.confirmed_strategy_summary
            )
            if request.latest_task_snapshot.active_confirmation_reference is not None:
                active_confirmation = (
                    request.latest_task_snapshot.active_confirmation_reference.model_dump(
                        mode="json"
                    )
                )
            if request.latest_task_snapshot.latest_backtest_result_reference is not None:
                latest_result = (
                    request.latest_task_snapshot.latest_backtest_result_reference.metadata
                )
            if request.latest_task_snapshot.latest_failed_action_reference is not None:
                latest_failed_action = request.latest_task_snapshot.latest_failed_action_reference.model_dump(
                    mode="json"
                )
        has_artifact_context = any(
            item is not None
            for item in (
                prior_strategy,
                active_confirmation,
                latest_result,
                latest_failed_action,
            )
        )
        history: list[BaseMessage] = []
        if not has_artifact_context:
            for item in request.recent_thread_history[-6:]:
                if not hasattr(item, "role") or not hasattr(item, "content"):
                    continue
                content = str(item.content)
                if item.role == "assistant":
                    history.append(AIMessage(content=content))
                elif item.role == "user":
                    history.append(HumanMessage(content=content))
        return [
            SystemMessage(content=self._system_prompt()),
            SystemMessage(
                content=(
                    f"User language preference: {request.user.language_preference}.\n"
                    f"Prior strategy JSON, if any: "
                    f"{prior_strategy.model_dump(mode='json') if prior_strategy else 'none'}\n"
                    f"Active confirmation reference JSON, if any: "
                    f"{active_confirmation if active_confirmation else 'none'}\n"
                    f"Latest result fact bank JSON, if any: "
                    f"{latest_result if latest_result else 'none'}\n"
                    f"Latest failed action JSON, if any: "
                    f"{latest_failed_action if latest_failed_action else 'none'}\n"
                    f"Selected thread metadata JSON, if any: "
                    f"{_selected_thread_metadata_context(request.selected_thread_metadata)}"
                )
            ),
            *history,
            HumanMessage(content=request.current_user_message),
        ]

    def _system_prompt(self) -> str:
        return (
            "You are Argus's conversational interpretation layer for an AI-first "
            "investing idea validation product. Interpret the user's natural language "
            "and return structured JSON only through the schema. Do not execute. "
            "Do not invent support. Preserve the user's raw phrasing and normalized "
            "meaning. Use prior strategy state for corrections like 'weekly instead', "
            "'use Nvidia instead', 'keep everything else', and 'sell all'.\n\n"
            "Language-agnostic contract: users may speak English, Spanish, or another "
            "language. Always return canonical internal values for executable fields "
            "such as strategy_type, asset_class, cadence, timeframe, indicator, "
            "semantic_turn_act, artifact_target, and result_followup_focus; do not "
            "translate those machine fields. Put the detected user language in "
            "candidate_strategy_draft.language. Put the exact bounded date/window "
            "phrase in candidate_strategy_draft.date_range_raw_text. For relative "
            "or semantic time windows, also fill candidate_strategy_draft."
            "date_range_intent with canonical fields: kind=rolling_window with "
            "count/unit, kind=year_to_date with optional year, kind=calendar_year "
            "with year, kind=since with start/year, kind=explicit_range with "
            "ISO start/end, or kind=endpoint_patch with endpoint plus ISO date or "
            "anchor=today and day_offset for relative day edits. Do not translate "
            "these machine fields. A user-stated relative lookback anchored to the "
            "present is already a complete temporal constraint; do not ask for "
            "calendar endpoints only because the user used natural language instead "
            "of ISO dates. Also record "
            "short evidence_spans for extracted fields such as strategy_type, "
            "asset_universe, date_range, capital_amount, cadence, and "
            "comparison_baseline. Use date_range for canonical dates only when you "
            "are confident; deterministic date parsing, intent date math, and validation run after this "
            "schema. Write assistant_response in the resolved product language "
            "from the user language preference unless the user explicitly asks "
            "to switch languages. Detected input language is metadata for "
            "interpretation, not the rendering contract. Treat short, "
            "messy, or grammatically imperfect follow-ups as normal user input, not "
            "malformed requests; extract supported strategy intent, asset evidence, "
            "date/window intent, and language when those facts are visible.\n\n"
            "Supported execution truth for Alpha: long-only backtests; buy_and_hold, "
            "dca_accumulation, registry-backed indicator threshold rules, and "
            "schema-backed signal strategies are executable. RSI is executable with "
            "user-specified thresholds from 0 to 100, a default period of 14, a "
            "default entry threshold of 30, and a default exit threshold of 55 when "
            "the user leaves one side unspecified. SMA and EMA crossovers, MACD "
            "crossing signal, price versus SMA/EMA/Bollinger Bands, and simple "
            "volume-above-volume-SMA confirmations are executable when you provide a "
            "complete rule_spec. Incomplete indicator ideas and indicators without an "
            "executable registry spec can be understood and drafted, but are not "
            "runnable until the missing entry and exit semantics are supplied. "
            "Same asset class only; max 5 symbols; "
            "equity benchmark is SPY; crypto benchmark is BTC; currency pairs "
            "are supported through Kraken; currency pair benchmark is the tested "
            "pair itself. No brokerage trading, shorting, mixed asset-class runs, "
            "custom scripting, or real slippage/fee realism.\n\n"
            "Benchmark language matters in any user language: when a symbol is "
            "framed as a benchmark, reference, comparison target, or market "
            "baseline, put it in comparison_baseline instead of asset_universe. "
            "A one-asset buy/hold request with a separate benchmark is executable "
            "as the primary asset plus comparison_baseline; do not call this an "
            "unsupported direct comparison. Do not add benchmark symbols to "
            "asset_universe unless the user explicitly says to buy, hold, or test "
            "both as traded assets. Examples: AAPL against SPY, AAPL with SPY "
            "as the benchmark, and AAPL con SPY como referencia all mean "
            "asset_universe=['AAPL'] and comparison_baseline='SPY'. "
            "Set field_provenance.comparison_baseline="
            "'explicit_user' only when the current user message explicitly names "
            "the comparison or benchmark. When the user gives exact start/end dates, "
            "preserve them as date_range {'start':'YYYY-MM-DD','end':'YYYY-MM-DD'}; "
            "never replace them with past year, last year, or another default period. "
            f"The current runtime date is {date.today().isoformat()}; if the user "
            "says today, now, or current, preserve that endpoint as 'today' or the "
            "current runtime date, not a stale model date.\n\n"
            "When the user says something like 'buy Nvidia when the 50-day moving average "
            "crosses above the 200-day', classify it as signal_strategy, preserve "
            "the crossover as entry_logic, and default the exit to the same fast "
            "average crossing back below the slow average when the user leaves the "
            "exit unspecified. Do not ask what the buy trigger is.\n\n"
            "Common trader shorthand such as 'buy when the 50 crosses the 200', "
            "'50/200 cross', or 'golden cross' also means a moving-average crossover. "
            "If the user omits SMA/EMA, use SMA as the default assumption and expose "
            "that assumption later in the confirmation card instead of asking them "
            "to restate the trigger. Ask only for truly missing run facts such as "
            "the asset or date window.\n\n"
            "Do not turn vague momentum language such as 'starts rising', 'big drops', "
            "'breaks out', or 'looks strong' into a moving-average crossover or any "
            "other executable signal by yourself. If the user does not name the "
            "indicator, threshold, crossover, or price rule, mark the entry rule as "
            "missing or ask for the executable definition.\n\n"
            "Valuation and fundamental language is valid investing intent, not user "
            "error. If the user says a stock looked cheap, undervalued, expensive, "
            "or references P/E, earnings, revenue, margins, or fundamentals, preserve "
            "that meaning. The current engine cannot execute valuation or fundamental "
            "data as entry/exit rules, so do not pretend those rules are runnable. "
            "Ask for a supported proxy when needed, such as buy-and-hold over the "
            "period they care about, DCA, a supported RSI threshold, or a supported "
            "moving-average/signal rule. Explain the boundary in product language: "
            "the concept is financially real, but Argus needs an executable historical "
            "price/indicator rule to simulate it today.\n\n"
            "Use data-availability allowances as deterministic capability truth. "
            "Equity launch history starts in 2016 for the current launch path, so "
            "do not invent a shorter 3-year limit for equities. Currency-pair "
            "intraday history has a bounded recent-data window, and this launch path "
            "supports 1h, 4h, or 1D for currency-pair tests. Let deterministic "
            "validation decide the exact runnable window. If the user asks for an "
            "hourly/intraday timeframe or a long historical window, preserve those "
            "requested fields in the structured draft; do not silently widen the "
            "timeframe, shorten the dates, or reshape the request to make it runnable. "
            "Validation and recovery will ask for an available window when needed. "
            "Keep provider names, "
            "candle counts, and provider plumbing out of user-facing language; "
            "translate those facts into product capability wording.\n\n"
            "NLU ownership: you are the only intent and extraction layer. "
            "Extract symbols, company names, crypto assets, and currency pairs, date ranges, "
            "DCA cadence, recurring contribution amount, entry logic, exit logic, and "
            "refinement targets from the user message and thread context. Do not rely on "
            "backend text-pattern extraction. If the user writes a company name like Tesla or "
            "Bitcoin, put that text or the ticker in asset_universe; the deterministic "
            "validator will canonicalize it with the market data resolver. "
            "For any strategy_drafting or backtest_execution request, always include "
            "candidate_strategy_draft and fill the extractable fields you can see: "
            "strategy_type, strategy_thesis, asset_universe, date_range, entry_logic, "
            "exit_logic, and structured indicator or rule fields when present. "
            "Do not return an empty candidate_strategy_draft for a testable investing "
            "idea. Normal curiosity such as 'what if I bought/held/owned a company, "
            "ticker, crypto asset, or currency pair' is a testable investing idea, "
            "not a capability or education question; classify it as new_idea and "
            "extract the asset and strategy draft before asking only for truly missing "
            "run facts. "
            "For indicator threshold rules, put the indicator key in indicator, "
            "the lookback in indicator_period when supplied, and numeric threshold "
            "overrides in entry_threshold and exit_threshold. Also preserve readable "
            "entry_logic and exit_logic, but do not rely on prose alone for executable "
            "indicator parameters. If the user says 'RSI entry at 20 and exit at 60', "
            "set indicator='rsi', entry_threshold=20, exit_threshold=60, and leave "
            "indicator_period null unless the user gave a period. "
            "For executable signal strategies, populate rule_spec when the user gives "
            "a complete generic condition group. A rule_spec has entry and exit groups, "
            "each with conditions using left/operator/right operands. Use it for MACD "
            "crossing signal, Bollinger Band touches, price versus indicator, and "
            "volume confirmation. For moving-average crossovers you may also populate "
            "entry_rule and exit_rule as typed JSON. Moving-average crossovers must use "
            "{'type':'moving_average_crossover','fast_indicator':'sma'|'ema',"
            "'fast_period':number,'slow_indicator':'sma'|'ema','slow_period':number,"
            "'direction':'bullish'|'bearish'}. If the user leaves exit unspecified, "
            "you may omit exit_rule and deterministic validation will derive the "
            "opposite crossover from entry_rule. "
            "For non-recurring buy-and-hold or backtest requests, any explicit "
            "cash amount that the user says to use, test, invest, allocate, or "
            "start with belongs in capital_amount as the starting capital, "
            "normalized as a number, with field_provenance.capital_amount="
            "'starting_capital'. This is language-agnostic: phrases equivalent "
            "to 'with 10000 dollars' or 'con 10000 dolares' are complete capital "
            "evidence for a buy_and_hold request. Do not leave capital_amount "
            "null or put this amount only in total_capital/initial_capital for "
            "non-DCA runs. "
            "For natural periods, return date_range as a normalized string when exact dates "
            "are not available, or as {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'} when the "
            "user provides exact dates. For recurring buys, extract cadence as daily, weekly, "
            "biweekly, monthly, or quarterly and never invent capital_amount. For DCA, "
            "capital_amount means "
            "the recurring contribution. If the user gives both a starting principal or total "
            "budget and a recurring contribution, put the recurring amount in capital_amount "
            "and put the starting principal in initial_capital or total_capital. If the user "
            "gives only a total budget, leave capital_amount null and set initial_capital or "
            "total_capital. When you set a recurring capital_amount, set "
            "field_provenance.capital_amount='recurring_contribution' only if the user "
            "explicitly stated that recurring contribution in the message; use "
            "'total_capital' when the number is merely a total budget, available cash, or "
            "starting principal. When you set cadence, set "
            "field_provenance.cadence='explicit_user' only when the user explicitly "
            "stated the purchase schedule in the current message or visible active "
            "draft context. Never infer monthly from a multi-year date range.\n\n"
            "If the user explicitly asks, in their language, for a simple buy-and-hold "
            "investment test, classify it as buy_and_hold even when the sentence also "
            "contains a start date. "
            "A start date is the backtest period, not entry logic. If you set "
            "strategy_type to buy_and_hold or dca_accumulation, do not also add "
            "unsupported_strategy_logic unless the user asked for an additional "
            "entry rule, exit rule, fundamental rule, sentiment/news/event rule, "
            "custom script, brokerage action, shorting, or another unsupported "
            "condition beyond that supported strategy. Preserve those extra rules "
            "in entry_logic, exit_logic, or strategy_thesis when they exist so a "
            "later audit can distinguish supported strategy intent from unsupported "
            "custom logic.\n\n"
            "Clarify only when required meaning is missing, genuinely ambiguous, "
            "or unsupported in a way that requires the user to choose a simplification. "
            "Starting capital, timeframe, benchmark, fees, and slippage have safe defaults; "
            "do not ask for them before confirmation unless the user explicitly wants to change them. "
            "Safe defaults are only for missing fields. If the user states a timeframe, "
            "date window, capital amount, benchmark, fee, slippage, cadence, or indicator "
            "threshold, preserve that user-stated field even when it will need deterministic "
            "validation or recovery before it can run. "
            "For DCA or recurring-buy plans, the recurring contribution amount is not a "
            "safe default. Do not invent it; if the user does not provide the amount and "
            "there is no prior strategy amount to preserve, leave capital_amount null and "
            "mark the amount as missing. "
            "For product questions or education, set assistant_response and do not "
            "force a backtest. Keep prose concise, no emoji, no decorative markdown, "
            "and no generic chatbot openers. For unsupported requests, acknowledge the understood "
            "intent, explain the limitation, and offer executable simplifications.\n\n"
            "semantic_turn_act is the routing source of truth. Use approval when the "
            "user clearly approves a pending confirmation; in that case set intent to "
            "backtest_execution, task_relation to continue, requires_clarification to "
            "false, and preserve the prior strategy. Use refine_current_idea when the "
            "user asks to change dates, assets, assumptions, timeframe, capital, or "
            "strategy details, and ask only for the changed missing detail. Use new_idea "
            "for a fresh testable idea, answer_pending_need when the user answers the "
            "latest missing fact, educational_question for product or investing concept "
            "questions, result_followup for questions about the latest completed run, "
            "retry_failed_action when the user asks to try again, retry, rerun the same "
            "one, or otherwise repeat the latest failed run without changing the idea, "
            "and unsupported_request when the user asks for unsupported capabilities. "
            "When semantic_turn_act is result_followup, set result_followup_focus to "
            "the closest value: why_underperformed, max_drawdown, what_tested, "
            "next_experiment, assumptions, or general. Result follow-ups must be "
            "answered from the latest result facts supplied to the runtime; do not "
            "invent metrics. Use why_underperformed for any why/how the result happened "
            "or other performance "
            "question, including phrases like 'why did this result happen', even "
            "when the run actually outperformed; the answer layer will correct false "
            "underperformance premises from the facts. Use next_experiment when "
            "the user asks what to try next, what else to test, next steps, what "
            "to change, or how to refine the latest result. Assumption questions "
            "about a visible confirmation should set semantic_turn_act="
            "result_followup and result_followup_focus=assumptions even when no "
            "completed run exists; use the active confirmation/card context instead of "
            "regenerating a new card. If the user asks to save, keep, bookmark, "
            "or promote the latest completed result, set semantic_turn_act="
            "result_followup, result_followup_focus=general, artifact_target="
            "latest_result, and include reason_codes=['latest_result_save_requested']. "
            "Set artifact_target to latest_result only when the current user message "
            "is actually about the latest completed run. Set artifact_target to "
            "pending_refinement when the user is answering a Refine strategy prompt. "
            "Set artifact_target to active_confirmation for visible confirmation/card "
            "questions. Set artifact_target to none for new ideas, standalone market "
            "questions, product help, or education. Do not let a completed result "
            "capture unrelated turns merely because it exists. "
            "When semantic_turn_act is educational_question and the user asks what "
            "Argus can do, what indicators it supports, what strategies it can run, "
            "what assets are available, or what the limits are, set "
            "capability_question_focus to supported_indicators, supported_strategies, "
            "assets, limits, or general. The runtime will answer from the executable "
            "capability registry; do not make unsupported execution claims in prose. "
            "Do not set capability_question_focus when the user is asking for plain "
            "education about an investing concept or a strategy family, such as what "
            "dollar cost averaging means; answer those with natural prose and connect "
            "the concept to the closest runnable Argus experiment when useful. "
            "For standalone macro, market-event, or market-context curiosity that is "
            "not asking for live feed output and is not tied to the latest result, set "
            "context_question_focus instead of capability_question_focus. Use "
            "macro_context for inflation, rates, Fed, recession, risk-on/off, or broad "
            "macro backdrop; corporate_events for splits, dividends, corporate actions, "
            "or earnings/event context; and market_movers for broad movers, most-active, "
            "or unusual-move curiosity. Keep artifact_target=none unless the user "
            "clearly targets a visible result or current confirmation. "
            "Retry turns should preserve the failed action payload; do "
            "not reinterpret the original investing idea from scratch. "
            "Social turns are conversation_followup with assistant_response and no "
            "strategy draft unless they also contain a real investing idea. "
            "When the user explicitly asks for response style, verbosity, or expertise "
            "for this turn, set response_profile_overrides; do not rely on backend "
            "regex for those preferences.\n\n"
            "Selected thread metadata may include the pending requested_field from "
            "the visible artifact. Use it as context for short answers, not as "
            "user-facing copy. If requested_field is asset_universe and the current "
            "message is a company, ticker, crypto asset, or currency-pair answer, "
            "fill only the replacement asset field in candidate_strategy_draft and "
            "keep unrelated prior strategy fields unchanged. Use normal market-symbol "
            "knowledge for the candidate strategy when the company or asset is common; "
            "deterministic provider validation will accept, clarify, or reject it "
            "after you return. If the user gives a fresh complete idea instead of a "
            "field answer, classify that as a new idea and extract the full draft.\n\n"
            "assistant_response must be natural user-facing prose. Never expose "
            "internal field names such as asset_universe, capital_amount, "
            "requested_field, or missing_required_fields. Never output raw JSON, "
            "'not specified', template placeholders, scaffolding labels, or backend "
            "schema language. Avoid responses under 10 words except deliberate short "
            "confirmations.\n\n"
            "Treat prior result state as optional context, not the active topic by default. "
            "Set uses_latest_result_context=true only when the latest user message is semantically "
            "about the latest run/result, such as metrics, return, benchmark, drawdown, assumptions "
            "in the backtest, underperformance, or what exactly was tested. If the user asks for "
            "beginner onboarding, product help, a concept explanation, or a new idea, set it false "
            "and do not classify as results_explanation just because a completed run exists."
        )

    def _to_runtime_interpretation(
        self,
        response: LLMInterpretationResponse,
        *,
        request: InterpretationRequest,
    ) -> StructuredInterpretation:
        strategy = _strategy_from_llm(response.candidate_strategy_draft)
        _merge_prior_strategy(strategy=strategy, request=request, response=response)
        _ground_strategy_in_current_turn(strategy=strategy, request=request)
        _validate_capability_boundaries(
            strategy=strategy,
            response=response,
            request=request,
        )
        unsupported = [
            _unsupported_from_llm(item) for item in response.unsupported_constraints
        ]
        ambiguous = [
            AmbiguousField.model_validate(item.model_dump(mode="python"))
            for item in response.ambiguous_fields
        ]
        return StructuredInterpretation(
            intent=response.intent,
            task_relation=response.task_relation,
            requires_clarification=response.requires_clarification,
            user_goal_summary=response.user_goal_summary,
            candidate_strategy_draft=strategy,
            missing_required_fields=list(response.missing_required_fields),
            assistant_response=response.assistant_response,
            confidence=response.confidence,
            reason_codes=list(response.reason_codes),
            ambiguous_fields=ambiguous,
            unsupported_constraints=unsupported,
            response_profile_overrides=response.response_profile_overrides,
            semantic_turn_act=response.semantic_turn_act,
            result_followup_focus=response.result_followup_focus,
            capability_question_focus=response.capability_question_focus,
            context_question_focus=response.context_question_focus,
            artifact_target=_artifact_target_from_response(response),
        )


async def _asset_grounding_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    suspicious_symbols = _suspicious_extracted_asset_symbols(
        response=response,
        request=request,
    )
    if not suspicious_symbols:
        return _response_with_misplaced_benchmark_asset_recovered(
            response=response,
            request=request,
        )
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_asset_grounding_audit_messages(
                response=response,
                request=request,
                suspicious_symbols=suspicious_symbols,
            ),
            schema_model=AssetGroundingAudit,
            schema_name="AssetGroundingAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="Asset grounding audit failed; clearing suspicious extracted assets",
        )
        return _response_without_ungrounded_symbols(
            response=response,
            grounded_symbols=[],
            reason_code="asset_grounding_audit_unavailable_cleared_suspicious_symbols",
        )
    if not isinstance(audit, AssetGroundingAudit) or audit.confidence < 0.6:
        return _response_without_ungrounded_symbols(
            response=response,
            grounded_symbols=[],
            reason_code="asset_grounding_audit_low_confidence_cleared_suspicious_symbols",
        )
    audited_response = _response_without_ungrounded_symbols(
        response=response,
        grounded_symbols=audit.grounded_symbols,
        reason_code="asset_grounding_audit_removed_unsubstantiated_symbols",
    )
    return _response_with_misplaced_benchmark_asset_recovered(
        response=audited_response,
        request=request,
        ignored_name_supported_symbols=_normalized_extracted_symbols(
            response.candidate_strategy_draft.asset_universe
        ),
    )


def _suspicious_extracted_asset_symbols(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[str]:
    if _selected_requested_field_base(request) == "asset_universe":
        return []
    symbols = [
        str(symbol).strip().upper()
        for symbol in response.candidate_strategy_draft.asset_universe
        if str(symbol).strip()
    ]
    if not symbols:
        return []
    raw_tokens = set(request.current_user_message.translate(_ASSET_TOKEN_MAP).split())
    lower_tokens = {token.casefold() for token in raw_tokens}
    cashtag_tokens = {
        token.lstrip("$").casefold()
        for token in raw_tokens
        if token.startswith("$")
    }
    grounded_symbols = {
        str(asset.canonical_symbol).strip().upper()
        for asset in _resolved_asset_mentions_from_message(request.current_user_message)
        if str(getattr(asset, "canonical_symbol", "")).strip()
    }
    provider_ticker_symbol_map = _current_message_provider_ticker_asset_map(request)
    context_symbols = _context_inheritable_asset_symbols(
        response=response,
        request=request,
        current_grounded_symbols=grounded_symbols,
    )
    suspicious: list[str] = []
    for symbol in symbols:
        folded = symbol.casefold()
        if symbol in raw_tokens or f"${symbol}" in raw_tokens or folded in cashtag_tokens:
            continue
        if symbol in grounded_symbols or symbol in context_symbols:
            continue
        if _provider_exact_ticker_supports_extracted_symbol(
            symbol,
            provider_ticker_symbol_map=provider_ticker_symbol_map,
        ):
            continue
        if folded in lower_tokens:
            suspicious.append(symbol)
            continue
        suspicious.append(symbol)
    return suspicious


def _current_message_provider_ticker_asset_map(
    request: InterpretationRequest,
) -> dict[str, Any]:
    assets = provider_ticker_assets_from_text(
        request.current_user_message,
        resolve_candidate=_resolve_benchmark_candidate_from_message,
        limit=10,
    )
    symbol_map: dict[str, Any] = {}
    for asset in assets:
        symbol = str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        if symbol and symbol not in symbol_map:
            symbol_map[symbol] = asset
    return symbol_map


def _request_has_provider_exact_execution_asset(
    request: InterpretationRequest,
) -> bool:
    provider_ticker_symbol_map = _current_message_provider_ticker_asset_map(request)
    return any(
        _provider_exact_ticker_supports_extracted_symbol(
            symbol,
            provider_ticker_symbol_map=provider_ticker_symbol_map,
        )
        for symbol in provider_ticker_symbol_map
    )


def _misplaced_benchmark_asset_candidate(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    provider_ticker_symbol_map: dict[str, Any] | None = None,
    ignored_name_supported_symbols: set[str] | None = None,
) -> Any | None:
    draft = response.candidate_strategy_draft
    benchmark_symbol = _normalized_extracted_symbol(draft.comparison_baseline)
    if benchmark_symbol is None:
        return None
    if _current_message_has_other_name_supported_asset(
        response=response,
        request=request,
        excluding_symbol=benchmark_symbol,
        ignored_symbols=ignored_name_supported_symbols or set(),
    ):
        return None
    symbol_map = provider_ticker_symbol_map
    if symbol_map is None:
        symbol_map = _current_message_provider_ticker_asset_map(request)
    return symbol_map.get(benchmark_symbol)


def _current_message_has_other_name_supported_asset(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    excluding_symbol: str,
    ignored_symbols: set[str],
) -> bool:
    def _resolve_candidate(query: str) -> AssetResolution | None:
        try:
            return _resolve_asset_candidate(
                query,
                field="asset_universe[0]",
                source="user_mention",
            )
        except ValueError:
            return None

    mentions = grounded_asset_mentions_from_text(
        request.current_user_message,
        resolve_candidate=_resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            request.current_user_message,
            strategy_type=response.candidate_strategy_draft.strategy_type,
        ),
        limit=5,
    )
    for mention in mentions:
        symbol = (
            str(getattr(mention.asset, "canonical_symbol", "") or "")
            .strip()
            .upper()
        )
        if (
            symbol != excluding_symbol
            and symbol not in ignored_symbols
            and grounded_asset_mention_has_name_support(mention)
        ):
            return True
    return False


def _comparison_baseline_has_provider_ticker_support(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    benchmark = _normalized_extracted_symbol(draft.comparison_baseline)
    if benchmark is None:
        return False
    symbol_map = {
        str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        for asset in provider_ticker_assets_from_text(
            current_message,
            resolve_candidate=_resolve_benchmark_candidate_from_message,
            limit=10,
        )
    }
    return benchmark in symbol_map


def _response_with_misplaced_benchmark_asset_recovered(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    ignored_name_supported_symbols: set[str] | None = None,
) -> LLMInterpretationResponse:
    draft = response.candidate_strategy_draft
    if draft.asset_universe:
        return response
    candidate = _misplaced_benchmark_asset_candidate(
        response=response,
        request=request,
        ignored_name_supported_symbols=ignored_name_supported_symbols,
    )
    if candidate is None:
        return response
    symbol = str(getattr(candidate, "canonical_symbol", "") or "").strip().upper()
    if not symbol:
        return response

    repaired = response.model_copy(deep=True)
    repaired_draft = repaired.candidate_strategy_draft
    repaired_draft.asset_universe = [symbol]
    asset_class = str(getattr(candidate, "asset_class", "") or "").strip()
    if asset_class:
        repaired_draft.asset_class = asset_class
    repaired_draft.strategy_thesis = None
    repaired_draft.comparison_baseline = None
    field_provenance = dict(repaired_draft.field_provenance or {})
    field_provenance.pop("comparison_baseline", None)
    repaired_draft.field_provenance = field_provenance
    extra_parameters = dict(repaired_draft.extra_parameters or {})
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    repaired_draft.extra_parameters = extra_parameters
    return repaired.model_copy(
        update={
            "candidate_strategy_draft": repaired_draft,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *repaired.reason_codes,
                        "misplaced_benchmark_asset_recovered",
                    ]
                )
            ),
        }
    )


def _response_without_ungrounded_symbols(
    *,
    response: LLMInterpretationResponse,
    grounded_symbols: list[str],
    reason_code: str,
) -> LLMInterpretationResponse:
    grounded = {symbol.strip().upper() for symbol in grounded_symbols if symbol.strip()}
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    original_symbols = [str(symbol).strip().upper() for symbol in draft.asset_universe]
    mixed_asset_response = _response_with_mixed_asset_guardrail_from_symbols(
        response=response,
        symbols=original_symbols,
    )
    if mixed_asset_response is not None:
        return mixed_asset_response
    draft.asset_universe = [symbol for symbol in original_symbols if symbol in grounded]
    if len(draft.asset_universe) == len(original_symbols):
        return response
    missing_required_fields = list(response.missing_required_fields)
    requires_clarification = response.requires_clarification
    if not draft.asset_universe:
        draft.asset_class = None
        if canonical_strategy_type(draft.strategy_type):
            missing_required_fields = list(
                dict.fromkeys([*missing_required_fields, "asset_universe"])
            )
            requires_clarification = True
    return response.model_copy(
        update={
            "candidate_strategy_draft": draft,
            "assistant_response": None,
            "requires_clarification": requires_clarification,
            "missing_required_fields": missing_required_fields,
            "reason_codes": list(
                dict.fromkeys([*response.reason_codes, reason_code])
            ),
        }
    )


def _response_with_mixed_asset_guardrail_from_symbols(
    *,
    response: LLMInterpretationResponse,
    symbols: list[str],
) -> LLMInterpretationResponse | None:
    resolved_symbols: list[str] = []
    asset_classes: set[str] = set()
    for index, symbol in enumerate(symbols):
        try:
            resolution = _resolve_asset_candidate(
                symbol,
                field=f"asset_universe[{index}]",
                source="llm_extraction",
            )
        except ValueError:
            continue
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        canonical_symbol = str(resolution.asset.canonical_symbol or "").strip().upper()
        asset_class = str(resolution.asset.asset_class or "").strip().lower()
        if canonical_symbol:
            resolved_symbols.append(canonical_symbol)
        if asset_class:
            asset_classes.add(asset_class)
    if len(asset_classes) <= 1:
        return None
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft.asset_universe = list(dict.fromkeys(resolved_symbols))
    draft.asset_class = "mixed"
    unsupported_constraints = list(response.unsupported_constraints)
    if not any(
        item.category == "unsupported_asset_mix" for item in unsupported_constraints
    ):
        unsupported_constraints.append(
            LLMUnsupportedConstraint(
                category="unsupported_asset_mix",
                raw_value=", ".join(draft.asset_universe),
                explanation=(
                    "Argus Alpha cannot run equity, crypto, and currency pairs "
                    "together in one simulation yet."
                ),
                simplification_labels=[
                    "Run one asset class at a time",
                    "Run the equity symbols only",
                    "Run the crypto or currency pair symbols only",
                ],
            )
        )
    missing_required_fields = [
        field
        for field in response.missing_required_fields
        if _field_path_base(field) != "asset_universe"
    ]
    return response.model_copy(
        update={
            "candidate_strategy_draft": draft,
            "assistant_response": None,
            "requires_clarification": True,
            "missing_required_fields": missing_required_fields,
            "unsupported_constraints": unsupported_constraints,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "mixed_asset_guardrail_preserved_grounding_symbols",
                    ]
                )
            ),
        }
    )


async def _requested_asset_answer_candidate_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_requested_asset_answer_candidate_audit(
        response=response,
        request=request,
    ):
        return response
    messages = _requested_asset_answer_candidate_audit_messages(
        response=response,
        request=request,
    )
    for model_name in _unique_repair_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=AssetAnswerCandidateAudit,
                schema_name="AssetAnswerCandidateAudit",
                model_name=model_name,
            )
        except Exception as exc:
            log_openrouter_failure(
                task="interpretation",
                model_name=model_name,
                exc=exc,
                message=(
                    "Requested asset-answer candidate audit failed; trying next "
                    "candidate model"
                ),
            )
            continue
        repaired = _response_from_requested_asset_answer_candidate_audit(
            response=response,
            request=request,
            audit=audit,
        )
        if repaired is not None:
            return repaired
    return response


def _response_from_requested_asset_answer_candidate_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    audit: Any,
) -> LLMInterpretationResponse | None:
    if not isinstance(audit, AssetAnswerCandidateAudit) or audit.confidence < 0.6:
        return None
    candidate_symbols = [
        str(symbol or "").strip()
        for symbol in audit.candidate_symbols[:3]
        if str(symbol or "").strip()
    ]
    if audit.needs_clarification and not candidate_symbols:
        return None
    prior_symbols = _prior_strategy_symbols(request)
    for index, candidate in enumerate(candidate_symbols):
        resolution = _resolve_asset_candidate(
            candidate,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        if resolution.asset.canonical_symbol in prior_symbols:
            continue
        draft = response.candidate_strategy_draft.model_copy(deep=True)
        draft.asset_universe = [resolution.asset.canonical_symbol]
        draft.asset_class = resolution.asset.asset_class
        draft.raw_user_phrasing = draft.raw_user_phrasing or request.current_user_message
        missing = [
            field
            for field in response.missing_required_fields
            if _field_path_base(field) != "asset_universe"
        ]
        return response.model_copy(
            update={
                "intent": "backtest_execution",
                "task_relation": "continue",
                "requires_clarification": bool(missing),
                "candidate_strategy_draft": draft,
                "missing_required_fields": missing,
                "assistant_response": None,
                "semantic_turn_act": "answer_pending_need",
                "reason_codes": list(
                    dict.fromkeys(
                        [
                            *response.reason_codes,
                            "requested_asset_answer_candidate_audit",
                        ]
                    )
                ),
            }
        )
    return None


def _response_needs_requested_asset_answer_candidate_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if _selected_requested_field_base(request) != "asset_universe":
        return False
    if not request.current_user_message.strip():
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if _draft_has_valid_requested_asset_update(response.candidate_strategy_draft, request):
        return False
    return bool(_prior_strategy_symbols(request))


def _response_is_audited_requested_asset_answer_patch(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if _selected_requested_field_base(request) != "asset_universe":
        return False
    if "requested_asset_answer_candidate_audit" not in response.reason_codes:
        return False
    if response.semantic_turn_act != "answer_pending_need":
        return False
    if response.intent != "backtest_execution":
        return False
    if response.assistant_response:
        return False
    if response.candidate_strategy_draft is None:
        return False
    return _draft_has_valid_requested_asset_update(
        response.candidate_strategy_draft,
        request,
    )


def _draft_has_valid_requested_asset_update(
    draft: LLMStrategyDraft,
    request: InterpretationRequest,
) -> bool:
    prior_symbols = _prior_strategy_symbols(request)
    for index, symbol in enumerate(draft.asset_universe):
        candidate = str(symbol or "").strip()
        if not candidate:
            continue
        resolution = _resolve_asset_candidate(
            candidate,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        if resolution.asset.canonical_symbol not in prior_symbols:
            return True
    return False


_ASSET_TOKEN_MAP = str.maketrans(
    {char: " " for char in ".,;:!?()[]{}<>\"'`"}
)


def _asset_grounding_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    suspicious_symbols: list[str],
) -> list[dict[str, str]]:
    provider_ticker_symbol_map = _current_message_provider_ticker_asset_map(request)
    misplaced_candidate = _misplaced_benchmark_asset_candidate(
        response=response,
        request=request,
        provider_ticker_symbol_map=provider_ticker_symbol_map,
        ignored_name_supported_symbols=set(suspicious_symbols),
    )
    misplaced_symbol = (
        str(getattr(misplaced_candidate, "canonical_symbol", "") or "").strip().upper()
        if misplaced_candidate is not None
        else None
    )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's asset-grounding audit. The interpreter extracted "
                "asset symbols that may not be grounded in the current user message "
                "or safely inherited artifact context. Return only the extracted "
                "symbols that the user clearly intended as assets or tickers. Do "
                "not treat pronouns, helper words, verbs, or generic conversation "
                "words as assets. Keep a symbol when the user clearly named the "
                "company, asset, ticker, or cashtag. Do not invent new symbols."
            ),
        },
        {
            "role": "system",
            "content": f"Extracted symbols to audit: {suspicious_symbols}",
        },
        {
            "role": "system",
            "content": (
                "Provider-backed exact ticker candidates in the current message: "
                f"{sorted(provider_ticker_symbol_map)}"
            ),
        },
        {
            "role": "system",
            "content": f"Possible misplaced benchmark asset: {misplaced_symbol}",
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


async def _capability_side_question_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_capability_side_question_audit(
        response=response,
        request=request,
    ):
        return response
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_capability_side_question_audit_messages(
                response=response,
                request=request,
            ),
            schema_model=CapabilitySideQuestionAudit,
            schema_name="CapabilitySideQuestionAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="Capability side-question audit failed; preserving primary interpretation",
        )
        fallback_response = _capability_audit_unavailable_response_if_safe(
            response=response,
            request=request,
        )
        if fallback_response is not None:
            return fallback_response
        return response
    if (
        not isinstance(audit, CapabilitySideQuestionAudit)
        or not audit.is_capability_question
        or audit.focus is None
        or audit.confidence < 0.6
    ):
        return response
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": False,
            "candidate_strategy_draft": LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message
            ),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "assistant_response": audit.assistant_response,
            "semantic_turn_act": "educational_question",
            "capability_question_focus": audit.focus,
            "artifact_target": "none",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "capability_side_question_audit",
                    ]
                )
            ),
        }
    )


def _response_needs_capability_side_question_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.capability_question_focus is not None:
        return False
    if response.context_question_focus is not None:
        return False
    if response.semantic_turn_act in {
        "approval",
        "retry_failed_action",
        "result_followup",
    }:
        return False
    if _llm_strategy_draft_has_concrete_execution_target(
        response.candidate_strategy_draft
    ):
        return False
    if _response_needs_material_evidence_strategy_repair(
        response=response,
        request=request,
    ):
        return False
    if _response_had_unsubstantiated_asset_removed(response):
        return True
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    if _field_path_base(pending_field) == "refinement":
        return False
    if pending_field:
        return True
    if (
        response.intent == "conversation_followup"
        and response.semantic_turn_act == "educational_question"
        and bool(response.assistant_response)
    ):
        return True
    return _is_vague_strategy_start(response)


def _response_had_unsubstantiated_asset_removed(
    response: LLMInterpretationResponse,
) -> bool:
    return any(
        reason_code.startswith("asset_grounding_audit_")
        and (
            "removed_unsubstantiated" in reason_code
            or "cleared_suspicious" in reason_code
        )
        for reason_code in response.reason_codes
    )


def _capability_audit_unavailable_response_if_safe(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_had_unsubstantiated_asset_removed(response):
        return None
    if _request_current_turn_has_material_execution_evidence(request):
        return None
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": False,
            "candidate_strategy_draft": LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message
            ),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "assistant_response": None,
            "semantic_turn_act": "educational_question",
            "capability_question_focus": None,
            "artifact_target": "none",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "capability_side_question_audit",
                        "capability_side_question_audit_unavailable_after_asset_grounding",
                    ]
                )
            ),
        }
    )


def _capability_side_question_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's runtime arbitration audit. Decide whether the "
                "current user message is a capability or education side-question, "
                "even if the previous turn asked for a missing field. Use semantic "
                "meaning, not keywords. A capability side-question asks what Argus "
                "supports, what it can run, what supported concepts mean, what assets "
                "or indicators are available, or what limits apply. Return false for "
                "messages that supply assets, dates, sizing, cadence, rule details, "
                "approvals, result follow-ups, market-news/feed requests, or provider "
                "data requests. Choose one focus value only when true: "
                "supported_indicators, supported_strategies, limits, assets, or general."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {
            "role": "system",
            "content": f"Pending requested field, if any: {pending_field or 'none'}",
        },
        {"role": "user", "content": request.current_user_message},
    ]


async def _context_question_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
    force: bool = False,
) -> LLMInterpretationResponse:
    if not force and not _response_needs_context_question_audit(
        response=response, request=request
    ):
        return response
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_context_question_audit_messages(
                response=response,
                request=request,
            ),
            schema_model=ContextQuestionAudit,
            schema_name="ContextQuestionAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="Context-question audit failed; preserving primary interpretation",
        )
        return response
    if (
        not isinstance(audit, ContextQuestionAudit)
        or not audit.is_context_question
        or audit.focus is None
        or audit.confidence < 0.6
    ):
        return response
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": False,
            "candidate_strategy_draft": LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message
            ),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "assistant_response": None,
            "semantic_turn_act": "educational_question",
            "capability_question_focus": None,
            "context_question_focus": audit.focus,
            "artifact_target": "none",
            "uses_latest_result_context": False,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "context_question_audit",
                    ]
                )
            ),
        }
    )


def _response_needs_context_question_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.context_question_focus is not None:
        return False
    if response.capability_question_focus not in {
        None,
        "general",
        "limits",
        "supported_strategies",
    }:
        return False
    if response.semantic_turn_act in {
        "approval",
        "retry_failed_action",
        "result_followup",
    }:
        return False
    if _llm_strategy_draft_has_concrete_execution_target(
        response.candidate_strategy_draft
    ):
        return False
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    if _field_path_base(pending_field) == "refinement":
        return False
    if _response_targets_latest_result_followup(response=response, request=request):
        return False
    if (
        response.intent == "strategy_drafting"
        and response.semantic_turn_act == "unsupported_request"
        and response.requires_clarification
        and not response.missing_required_fields
    ):
        return True
    return (
        response.intent == "conversation_followup"
        and response.semantic_turn_act == "educational_question"
    )


async def _unsupported_context_question_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if (
        response.intent != "unsupported_or_out_of_scope"
        or response.semantic_turn_act != "unsupported_request"
        or response.missing_required_fields
        or response.context_question_focus is not None
    ):
        return None
    repaired = await _context_question_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
        force=True,
    )
    return repaired if repaired is not response else None


def _context_question_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's runtime arbitration audit. Decide whether the "
                "current user message is standalone market or macro context "
                "curiosity that should be answered as bounded context and connected "
                "to a historical experiment. Use semantic meaning, not keywords. "
                "Return true for macro backdrop, inflation/rates/Fed/recession, "
                "corporate events such as splits/dividends/earnings context, or "
                "movers/most-active/unusual-move curiosity. Return false when the "
                "user supplies executable strategy details, answers a pending field, "
                "asks what Argus supports, approves a run, or targets a visible "
                "result. Choose one focus only when true: macro_context, "
                "corporate_events, or market_movers."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {
            "role": "system",
            "content": f"Pending requested field, if any: {pending_field or 'none'}",
        },
        {"role": "user", "content": request.current_user_message},
    ]


async def _strategy_family_continuity_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_strategy_family_continuity_audit(
        response=response,
        request=request,
    ):
        return response
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_strategy_family_continuity_audit_messages(
                response=response,
                request=request,
            ),
            schema_model=StrategyFamilyContinuityAudit,
            schema_name="StrategyFamilyContinuityAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="Strategy family continuity audit failed; preserving primary interpretation",
        )
        return response
    if (
        not isinstance(audit, StrategyFamilyContinuityAudit)
        or not audit.should_rebind_strategy_family
        or audit.confidence < 0.7
    ):
        return response
    strategy_type = canonical_strategy_type(audit.strategy_type)
    if strategy_type not in {
        "buy_and_hold",
        "dca_accumulation",
        "indicator_threshold",
        "signal_strategy",
    }:
        return response
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft.strategy_type = strategy_type
    missing_required_fields = list(response.missing_required_fields)
    requires_clarification = response.requires_clarification
    if strategy_type == "dca_accumulation" and audit.total_budget_not_recurring:
        _move_dca_total_budget_out_of_recurring_amount(draft)
        if draft.capital_amount is None:
            missing_required_fields = list(
                dict.fromkeys([*missing_required_fields, "capital_amount"])
            )
            requires_clarification = True
        if _llm_value_is_empty(draft.cadence):
            missing_required_fields = list(
                dict.fromkeys([*missing_required_fields, "cadence"])
            )
            requires_clarification = True
    return response.model_copy(
        update={
            "intent": "strategy_drafting" if requires_clarification else response.intent,
            "task_relation": "continue",
            "requires_clarification": requires_clarification,
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing_required_fields,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "artifact_target": "none",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "strategy_family_continuity_rebound",
                    ]
                )
            ),
        }
    )


async def _dca_contract_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_dca_contract_audit(response=response, request=request):
        return response
    messages = _dca_contract_audit_messages(response=response, request=request)
    for model_name in _unique_repair_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=DcaContractAudit,
                schema_name="DcaContractAudit",
                model_name=model_name,
            )
        except Exception as exc:
            log_openrouter_failure(
                task="interpretation",
                model_name=model_name,
                exc=exc,
                message="DCA contract audit failed; trying next candidate model",
            )
            continue
        repaired = _response_from_dca_contract_audit(response=response, audit=audit)
        if repaired is not None:
            return repaired
    return response


def _response_needs_dca_contract_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.artifact_target == "latest_result":
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if response.intent not in {
        "strategy_drafting",
        "backtest_execution",
        "unsupported_or_out_of_scope",
    }:
        return False
    if not request.current_user_message.strip():
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return _dca_response_needs_semantic_field_audit(
            response
        ) or _current_message_has_dca_contract_shape(
            response=response,
            request=request,
        )
    if not _current_message_has_dca_contract_shape(
        response=response,
        request=request,
    ):
        return False
    if response.capability_question_focus is not None:
        return _llm_strategy_draft_has_extractable_fields(draft) or bool(
            draft.raw_user_phrasing or draft.strategy_thesis
        )
    if response.semantic_turn_act == "unsupported_request":
        return _llm_strategy_draft_has_extractable_fields(draft) or bool(
            draft.raw_user_phrasing or draft.strategy_thesis
        )
    return (
        response.requires_clarification
        and not canonical_strategy_type(draft.strategy_type)
        and _llm_strategy_draft_has_extractable_fields(draft)
    )


def _current_message_has_dca_contract_shape(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    if _supported_dca_cadence_value(draft.cadence) is not None:
        return _draft_contains_structured_capital_context(draft)
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return _llm_strategy_draft_has_extractable_fields(draft)
    if response.capability_question_focus is not None:
        return _llm_strategy_draft_has_extractable_fields(draft)
    return (
        response.semantic_turn_act == "unsupported_request"
        and _llm_strategy_draft_has_extractable_fields(draft)
    )


async def _dca_contribution_role_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_dca_contribution_role_audit(response):
        return response
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_dca_contribution_role_audit_messages(
                response=response,
                request=request,
            ),
            schema_model=DcaContributionRoleAudit,
            schema_name="DcaContributionRoleAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="DCA contribution role audit failed; preserving primary interpretation",
        )
        return response
    if not isinstance(audit, DcaContributionRoleAudit) or audit.confidence < 0.65:
        return response
    if audit.recurring_contribution_explicit:
        draft = response.candidate_strategy_draft.model_copy(deep=True)
        draft.recurring_contribution = draft.capital_amount
        if draft.field_provenance.get("capital_amount") != "recurring_contribution":
            draft.field_provenance["capital_amount"] = "recurring_contribution"
        draft.field_provenance["recurring_contribution"] = "explicit_user"
        cadence = _supported_dca_cadence_value(draft.cadence)
        missing_required_fields = list(response.missing_required_fields)
        if cadence is not None:
            draft.cadence = cadence
            draft.field_provenance["cadence"] = "explicit_user"
            missing_required_fields = [
                field
                for field in missing_required_fields
                if _field_path_base(field) != "cadence"
            ]
        missing_required_fields = [
            field
            for field in missing_required_fields
            if _field_path_base(field) != "capital_amount"
        ]
        return response.model_copy(
            update={
                "candidate_strategy_draft": draft,
                "missing_required_fields": missing_required_fields,
                "requires_clarification": bool(missing_required_fields),
                "assistant_response": None,
                "reason_codes": list(
                    dict.fromkeys(
                        [
                            *response.reason_codes,
                            "dca_recurring_contribution_grounded_in_current_message",
                        ]
                        + (
                            ["dca_total_budget_preserved_as_context"]
                            if audit.total_budget_not_recurring
                            else []
                        )
                    )
                ),
            }
        )
    if not audit.total_budget_not_recurring:
        return response
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    _move_dca_total_budget_out_of_recurring_amount(draft)
    missing_required_fields = list(
        dict.fromkeys([*response.missing_required_fields, "capital_amount"])
    )
    return response.model_copy(
        update={
            "intent": "strategy_drafting",
            "requires_clarification": True,
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing_required_fields,
            "assistant_response": None,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "dca_total_budget_role_audited",
                    ]
                )
            ),
        }
    )


async def _pending_response_option_selected_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_pending_response_option_selection_audit(
        response=response,
        request=request,
    ):
        return response
    options = _pending_response_intent_options(request)
    messages = _pending_response_option_selection_audit_messages(
        response=response,
        request=request,
        options=options,
    )
    for model_name in _unique_repair_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=PendingResponseOptionSelectionAudit,
                schema_name="PendingResponseOptionSelectionAudit",
                model_name=model_name,
            )
        except Exception as exc:
            log_openrouter_failure(
                task="interpretation",
                model_name=model_name,
                exc=exc,
                message=(
                    "Pending response option selection audit failed; trying next "
                    "candidate model"
                ),
            )
            continue
        repaired = _response_from_pending_response_option_selection_audit(
            response=response,
            request=request,
            audit=audit,
            options=options,
        )
        if repaired is not None:
            return repaired
    return response


def _response_needs_pending_response_option_selection_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not request.current_user_message.strip():
        return False
    response_intent = request.selected_thread_metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return False
    if response_intent.get("kind") != "unsupported_recovery":
        return False
    semantic_needs = response_intent.get("semantic_needs")
    if not isinstance(semantic_needs, list) or "simplification_choice" not in {
        str(need) for need in semantic_needs
    }:
        return False
    if not _pending_response_intent_options(request):
        return False
    if response.artifact_target == "latest_result":
        return False
    if response.semantic_turn_act in {
        "result_followup",
        "retry_failed_action",
    }:
        return False
    snapshot = request.latest_task_snapshot
    return bool(snapshot and snapshot.pending_strategy_summary is not None)


def _pending_response_intent_options(
    request: InterpretationRequest,
) -> list[dict[str, Any]]:
    response_intent = request.selected_thread_metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return []
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    options: list[dict[str, Any]] = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            continue
        replacement_values = raw_option.get("replacement_values")
        if not isinstance(replacement_values, dict):
            continue
        options.append(
            {
                "label": str(raw_option.get("label") or "").strip(),
                "replacement_values": dict(replacement_values),
            }
        )
    return options


def _pending_response_option_selection_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    options: list[dict[str, Any]],
) -> list[dict[str, str]]:
    pending_strategy = None
    if (
        request.latest_task_snapshot
        and request.latest_task_snapshot.pending_strategy_summary
    ):
        pending_strategy = (
            request.latest_task_snapshot.pending_strategy_summary.model_dump(
                mode="json"
            )
        )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's pending response option selection audit. The "
                "previous assistant turn asked the user to choose among structured "
                "recovery options. Decide whether the current user message "
                "semantically selects one of those options. Use meaning, not "
                "keywords. Return only the zero-based option index when the user "
                "selects an option. Return no selection when the user provides a "
                "fresh investing idea, changes fields outside the offered options, "
                "or asks an unrelated question. Do not invent a new option."
            ),
        },
        {
            "role": "system",
            "content": f"Pending strategy JSON: {pending_strategy or 'none'}",
        },
        {
            "role": "system",
            "content": (
                "Pending options JSON: "
                f"{json.dumps(options, sort_keys=True, default=str)}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Primary structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_pending_response_option_selection_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    audit: Any,
    options: list[dict[str, Any]],
) -> LLMInterpretationResponse | None:
    if (
        not isinstance(audit, PendingResponseOptionSelectionAudit)
        or not audit.is_selection
        or audit.confidence < 0.7
        or audit.selected_option_index is None
    ):
        return None
    option_index = audit.selected_option_index
    if option_index < 0 or option_index >= len(options):
        return None
    draft = _pending_strategy_draft_from_request_or_response(
        response=response,
        request=request,
    )
    if draft is None:
        return None
    replacement_values = options[option_index].get("replacement_values")
    if not isinstance(replacement_values, dict):
        return None
    replacement_result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values=replacement_values,
        current_missing=response.missing_required_fields,
    )
    missing_fields = replacement_result["missing_fields"]
    return response.model_copy(
        update={
            "intent": "strategy_drafting"
            if missing_fields
            else "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": bool(missing_fields),
            "candidate_strategy_draft": replacement_result["draft"],
            "missing_required_fields": missing_fields,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "capability_question_focus": None,
            "context_question_focus": None,
            "artifact_target": "none",
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "pending_response_option_selected",
                    ]
                )
            ),
        }
    )


def _pending_strategy_draft_from_request_or_response(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMStrategyDraft | None:
    snapshot = request.latest_task_snapshot
    if snapshot and snapshot.pending_strategy_summary is not None:
        return _llm_draft_from_strategy_summary(snapshot.pending_strategy_summary)
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_extractable_fields(draft):
        return draft.model_copy(deep=True)
    return None


def _llm_draft_from_strategy_summary(strategy: StrategySummary) -> LLMStrategyDraft:
    extra_parameters = dict(strategy.extra_parameters or {})
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    indicator_parameters = extra_parameters.get("indicator_parameters")
    if not isinstance(indicator_parameters, dict):
        indicator_parameters = {}
    date_range_intent = extra_parameters.get("date_range_intent")
    return LLMStrategyDraft(
        raw_user_phrasing=strategy.raw_user_phrasing,
        strategy_type=strategy.strategy_type,
        strategy_thesis=strategy.strategy_thesis,
        asset_universe=list(strategy.asset_universe),
        asset_class=strategy.asset_class,
        timeframe=strategy.timeframe,
        cadence=strategy.cadence,
        entry_logic=strategy.entry_logic,
        exit_logic=strategy.exit_logic,
        entry_rule=strategy.entry_rule,
        exit_rule=strategy.exit_rule,
        rule_spec=strategy.rule_spec,
        indicator=indicator_parameters.get("indicator"),
        indicator_period=indicator_parameters.get("indicator_period"),
        entry_threshold=indicator_parameters.get("entry_threshold"),
        exit_threshold=indicator_parameters.get("exit_threshold"),
        date_range=strategy.date_range,
        date_range_intent=(
            LLMDateRangeIntent.model_validate(date_range_intent)
            if isinstance(date_range_intent, dict)
            else None
        ),
        sizing_mode=strategy.sizing_mode,
        capital_amount=strategy.capital_amount,
        recurring_contribution=extra_parameters.get("recurring_contribution"),
        initial_capital=extra_parameters.get("initial_capital"),
        total_capital=extra_parameters.get("total_capital")
        or extra_parameters.get("total_budget"),
        position_size=strategy.position_size,
        risk_rules=[LLMRiskRule.model_validate(rule) for rule in strategy.risk_rules],
        assumptions=list(strategy.assumptions),
        comparison_baseline=strategy.comparison_baseline,
        refinement_of=strategy.refinement_of,
        field_provenance={
            str(key): str(value) for key, value in field_provenance.items()
        },
        extra_parameters=extra_parameters,
    )


def _apply_pending_response_option_replacement(
    *,
    draft: LLMStrategyDraft,
    replacement_values: dict[str, Any],
    current_missing: list[str],
) -> dict[str, Any]:
    repaired = draft.model_copy(deep=True)
    requested_field = replacement_values.get("requested_field")
    if replacement_values.get("ignore_initial_capital") is True:
        _clear_dca_total_budget_fields(repaired)
    if "strategy_type" in replacement_values:
        repaired.strategy_type = str(replacement_values["strategy_type"])
    if "initial_capital" in replacement_values:
        value = replacement_values.get("initial_capital")
        if value is not None:
            repaired.initial_capital = float(value)
            repaired.capital_amount = float(value)
            field_provenance = dict(repaired.field_provenance or {})
            field_provenance["capital_amount"] = "starting_capital"
            field_provenance["initial_capital"] = "starting_capital"
            repaired.field_provenance = field_provenance
    if "capital_amount" in replacement_values:
        value = replacement_values.get("capital_amount")
        if value is not None:
            repaired.capital_amount = float(value)
    if "date_range" in replacement_values:
        repaired.date_range = replacement_values["date_range"]
    if "cadence" in replacement_values:
        repaired.cadence = _supported_dca_cadence_value(
            replacement_values.get("cadence")
        )
    if "timeframe" in replacement_values:
        repaired.timeframe = str(replacement_values["timeframe"])
    if "comparison_baseline" in replacement_values:
        repaired.comparison_baseline = str(
            replacement_values["comparison_baseline"]
        ).strip()
    if canonical_strategy_type(repaired.strategy_type) != "dca_accumulation":
        _clear_dca_recurring_fields(repaired)

    missing_fields = _missing_fields_after_pending_option(
        repaired,
        requested_field=requested_field,
        current_missing=current_missing,
    )
    return {"draft": repaired, "missing_fields": missing_fields}


def _clear_dca_total_budget_fields(draft: LLMStrategyDraft) -> None:
    draft.initial_capital = None
    draft.total_capital = None
    field_provenance = dict(draft.field_provenance or {})
    for key in ("initial_capital", "total_capital"):
        field_provenance.pop(key, None)
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    for key in (
        "initial_capital",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
        "cap",
    ):
        extra_parameters.pop(key, None)
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    draft.extra_parameters = extra_parameters


def _clear_dca_recurring_fields(draft: LLMStrategyDraft) -> None:
    draft.cadence = None
    draft.recurring_contribution = None
    field_provenance = dict(draft.field_provenance or {})
    for key in ("cadence", "recurring_contribution"):
        field_provenance.pop(key, None)
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    for key in ("recurring_contribution", "recurring_cadence"):
        extra_parameters.pop(key, None)
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    draft.extra_parameters = extra_parameters


def _missing_fields_after_pending_option(
    draft: LLMStrategyDraft,
    *,
    requested_field: Any,
    current_missing: list[str],
) -> list[str]:
    missing = list(current_missing)
    if isinstance(requested_field, str) and requested_field.strip():
        missing = list(dict.fromkeys([*missing, requested_field.strip()]))
    return _dca_contract_missing_fields(missing, draft=draft)


async def _response_ready_for_runtime(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    response = _normalize_response_for_runtime_context(response, request=request)
    _log_runtime_readiness_step("started", response=response)
    planned_artifact_edit = await _ready_active_artifact_edit_planned_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if planned_artifact_edit is not None:
        return planned_artifact_edit
    if _response_can_skip_optional_runtime_readiness_audits(
        response=response,
        request=request,
    ):
        _log_runtime_readiness_step(
            "ready_after_initial_interpretation",
            response=response,
        )
        return response
    capital_response = await _early_starting_capital_rechecked_response(
        response=response,
        request=request,
    )
    if capital_response is not None:
        response = capital_response
        if _response_can_skip_optional_runtime_readiness_audits(
            response=response,
            request=request,
        ):
            _log_runtime_readiness_step(
                "ready_after_starting_capital_recheck",
                response=response,
            )
            return response
    focused_response = await _early_focused_strategy_repaired_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if focused_response is not None:
        response = focused_response
        if _response_can_skip_optional_runtime_readiness_audits(
            response=response,
            request=request,
        ):
            _log_runtime_readiness_step(
                "ready_after_early_focused_strategy_repair",
                response=response,
            )
            return response
    response = await _pending_response_option_selected_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = await _requested_asset_answer_candidate_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if _response_is_audited_requested_asset_answer_patch(
        response=response,
        request=request,
    ):
        return response
    response = await _latest_result_routing_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if _response_targets_latest_result_followup(response=response, request=request):
        return response
    response = await _asset_grounding_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if _response_needs_material_evidence_strategy_repair(
        response=response,
        request=request,
    ):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
    if _response_needs_pre_guidance_focused_strategy_extraction(
        response=response,
        request=request,
    ):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
    response = await _capability_side_question_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if (
        response.artifact_target == "none"
        and "capability_side_question_audit" in response.reason_codes
        and _response_had_unsubstantiated_asset_removed(response)
    ):
        return response
    response = await _context_question_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = await _dca_contract_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = await _strategy_family_continuity_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = await _dca_contribution_role_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    _log_runtime_readiness_step("baseline_audits_completed", response=response)
    if _response_can_skip_optional_runtime_readiness_audits(
        response=response,
        request=request,
    ):
        _log_runtime_readiness_step("ready_after_baseline_audits", response=response)
        return response
    if (
        _optional_runtime_readiness_audit_blocker(
            response=response,
            request=request,
        )
        == "launch_field_fidelity"
    ):
        _log_runtime_readiness_step(
            "launch_field_fidelity_audit_started",
            response=response,
        )
        audited_response = await _audit_stated_run_fields(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if audited_response is not None:
            response = audited_response
            if _response_can_skip_optional_runtime_readiness_audits(
                response=response,
                request=request,
            ):
                _log_runtime_readiness_step(
                    "ready_after_launch_field_fidelity_audit",
                    response=response,
                )
                return response
    _log_runtime_readiness_step(
        "capability_conflict_audit_started",
        response=response,
    )
    conflict_response = await _audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if conflict_response is not None:
        conflict_response = await _underfilled_strategy_repaired_response(
            response=conflict_response,
            preferred_model=preferred_model,
            request=request,
        )
        return await _stated_run_field_audited_response(
            response=conflict_response,
            preferred_model=preferred_model,
            request=request,
        )
    _log_runtime_readiness_step(
        "focused_date_window_audit_started",
        response=response,
    )
    date_window_response = await _focused_date_window_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if date_window_response is not None:
        return await _stated_run_field_audited_response(
            response=date_window_response,
            preferred_model=preferred_model,
            request=request,
        )
    _log_runtime_readiness_step(
        "supported_date_gap_repair_started",
        response=response,
    )
    supported_date_gap_response = await _supported_date_gap_schema_repaired_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if supported_date_gap_response is not None:
        return await _stated_run_field_audited_response(
            response=supported_date_gap_response,
            preferred_model=preferred_model,
            request=request,
        )
    if response.capability_question_focus is not None and (
        response.artifact_target == "none" or not _request_has_latest_result(request)
    ):
        if "capability_side_question_audit" in response.reason_codes:
            return response
        if _response_needs_testable_idea_repair(response=response, request=request):
            repaired_response = await _repair_incomplete_strategy_extraction(
                failed_response=response,
                preferred_model=preferred_model,
                request=request,
            )
            if repaired_response is not None:
                return await _stated_run_field_audited_response(
                    response=repaired_response,
                    preferred_model=preferred_model,
                    request=request,
                )
            context_response = await _unsupported_context_question_audited_response(
                response=response,
                preferred_model=preferred_model,
                request=request,
            )
            if context_response is not None:
                return context_response
        return response
    response = _vague_strategy_start_as_guidance(response)
    if _is_vague_strategy_start_guidance(response):
        return response
    response = _augment_strategy_assets_from_resolvable_context(
        response=response,
        request=request,
    )
    response = _clear_auto_simplified_strategy_when_rule_is_ambiguous(response)
    if _response_needs_signal_rule_plan(response):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
    response = await _signal_rule_checked_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    grounded_response = await _audit_executable_strategy_grounding(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if grounded_response is not None:
        response = grounded_response
        if response.requires_clarification:
            return response
    if _response_needs_indicator_default_grounding_repair(
        response=response,
        request=request,
    ):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            response = repaired_response
    if _response_needs_indicator_parameter_repair(response):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            response = repaired_response
    if _response_needs_launch_field_fidelity_repair(response=response):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            response = repaired_response
    if _response_needs_artifact_context_repair(response):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
        raise ValueError(
            "OpenRouter unsupported clarification omitted recoverable artifact context"
        )
    if _response_needs_structured_strategy_repair(response=response):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
    if _response_needs_testable_idea_repair(response=response, request=request):
        repaired_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if repaired_response is not None:
            return await _stated_run_field_audited_response(
                response=repaired_response,
                preferred_model=preferred_model,
                request=request,
            )
        context_response = await _unsupported_context_question_audited_response(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if context_response is not None:
            return context_response
    if _response_replays_prior_strategy_without_current_turn_update(
        response=response,
        request=request,
    ):
        if _pending_dca_assumption_reply_needs_stated_run_field_audit(
            response=response,
            request=request,
        ):
            audited_response = await _audit_stated_run_fields(
                response=response,
                preferred_model=preferred_model,
                request=request,
            )
            if audited_response is not None:
                return audited_response
        planned_response = await _plan_artifact_edit_response(
            preferred_model=preferred_model,
            request=request,
        )
        if planned_response is not None:
            return planned_response
        raise ValueError(
            "OpenRouter interpretation replayed the active artifact without a "
            "material current-turn update"
        )
    audited_response = await _audit_stated_run_fields(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if audited_response is not None:
        response = audited_response
        date_window_response = await _focused_date_window_audited_response(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if date_window_response is not None:
            response = date_window_response
    conflict_response = await _audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if conflict_response is not None:
        response = await _underfilled_strategy_repaired_response(
            response=conflict_response,
            preferred_model=preferred_model,
            request=request,
        )
    grounded_response = await _audit_executable_strategy_grounding(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if grounded_response is not None:
        response = grounded_response
    response = _response_with_executable_fields_preferred_over_clarification_prose(
        response
    )
    if _structured_interpretation_has_required_shape(response, request=request):
        return response

    planned_response = await _plan_artifact_edit_response(
        preferred_model=preferred_model,
        request=request,
    )
    if planned_response is not None:
        return planned_response
    repaired_response = await _repair_incomplete_strategy_extraction(
        failed_response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if repaired_response is not None:
        return await _stated_run_field_audited_response(
            response=repaired_response,
            preferred_model=preferred_model,
            request=request,
        )
    raise ValueError("OpenRouter interpretation returned an incomplete strategy draft")


async def _ready_active_artifact_edit_planned_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _request_targets_pending_artifact_assumption_edit(request):
        return None
    if response.semantic_turn_act in {
        "approval",
        "retry_failed_action",
    }:
        return None
    if (
        response.semantic_turn_act == "result_followup"
        and not _request_has_planner_edit_candidate_after_model_failure(request)
    ):
        return None
    if _active_artifact_asset_universe_operation_needs_planner(
        response=response,
        request=request,
    ):
        planned = await _plan_pending_artifact_assumption_edit(
            request=request,
            preferred_model=preferred_model,
        )
        if planned is not None:
            return planned
        return _asset_universe_operation_clarification_response(
            response=response,
            request=request,
        )
    if _llm_strategy_draft_has_supported_artifact_assumption_edit(
        response.candidate_strategy_draft
    ):
        return None
    planned = await _plan_pending_artifact_assumption_edit(
        request=request,
        preferred_model=preferred_model,
    )
    if planned is None or planned.requires_clarification:
        return None
    return planned


def _active_artifact_asset_universe_operation_needs_planner(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    if not draft.asset_universe:
        return False
    if normalized_asset_universe_operation(draft.asset_universe_operation) is not None:
        return False
    snapshot = request.latest_task_snapshot
    prior = (
        snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
        if snapshot is not None
        else None
    )
    if prior is None:
        return False
    candidate_symbols = {
        symbol
        for value in draft.asset_universe
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    prior_symbols = {
        symbol
        for value in prior.asset_universe
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    return bool(candidate_symbols and candidate_symbols != prior_symbols)


def _asset_universe_operation_clarification_response(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": True,
            "assistant_response": asset_universe_operation_clarification_message(
                language=request.user.language_preference
            ),
            "candidate_strategy_draft": LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message
            ),
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "asset_universe_operation_needs_clarification",
                    ]
                )
            ),
            "semantic_turn_act": "answer_pending_need",
        }
    )


def _log_runtime_readiness_step(
    step: str,
    *,
    response: LLMInterpretationResponse,
) -> None:
    draft = response.candidate_strategy_draft
    logger.debug(
        "Structured interpreter runtime readiness step={} intent={} "
        "semantic_turn_act={} strategy_type={} requires_clarification={} "
        "has_date_range={} has_date_range_intent={} has_date_range_raw_text={} "
        "missing_required_fields={} ambiguous_field_count={} "
        "unsupported_constraint_count={} reason_codes={}",
        step,
        response.intent,
        response.semantic_turn_act,
        canonical_strategy_type(draft.strategy_type),
        response.requires_clarification,
        not _llm_value_is_empty(draft.date_range),
        draft.date_range_intent is not None,
        not _llm_value_is_empty(draft.date_range_raw_text),
        list(response.missing_required_fields),
        len(response.ambiguous_fields),
        len(response.unsupported_constraints),
        list(response.reason_codes),
        step=step,
        intent=response.intent,
        task_relation=response.task_relation,
        semantic_turn_act=response.semantic_turn_act,
        requires_clarification=response.requires_clarification,
        strategy_type=canonical_strategy_type(draft.strategy_type),
        has_date_range=not _llm_value_is_empty(draft.date_range),
        has_date_range_intent=draft.date_range_intent is not None,
        has_date_range_raw_text=not _llm_value_is_empty(draft.date_range_raw_text),
        missing_required_fields=list(response.missing_required_fields),
        ambiguous_field_count=len(response.ambiguous_fields),
        unsupported_constraint_count=len(response.unsupported_constraints),
        reason_codes=list(response.reason_codes),
    )


def _response_can_skip_optional_runtime_readiness_audits(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    blocker = _optional_runtime_readiness_audit_blocker(
        response=response,
        request=request,
    )
    if blocker is None:
        return True
    logger.debug(
        "Structured interpreter runtime readiness skip blocked reason={} "
        "intent={} semantic_turn_act={} strategy_type={}",
        blocker,
        response.intent,
        response.semantic_turn_act,
        canonical_strategy_type(response.candidate_strategy_draft.strategy_type),
        blocker=blocker,
        intent=response.intent,
        semantic_turn_act=response.semantic_turn_act,
        strategy_type=canonical_strategy_type(
            response.candidate_strategy_draft.strategy_type
        ),
    )
    return False


def _optional_runtime_readiness_audit_blocker(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> str | None:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return "unsupported_intent"
    if response.semantic_turn_act != "new_idea":
        return "not_new_idea"
    if (
        response.requires_clarification
        or response.missing_required_fields
        or response.ambiguous_fields
        or response.unsupported_constraints
        or response.capability_question_focus is not None
        or response.context_question_focus is not None
    ):
        return "pending_clarification_or_constraint"
    draft = response.candidate_strategy_draft
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return "unsupported_strategy_type"
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return "rule_or_indicator_fields"
    if _capability_required_missing_fields_for_canonical_strategy([], draft=draft):
        return "missing_required_execution_fields"
    if not _structured_interpretation_has_required_shape(response, request=request):
        return "required_shape_missing"
    if _response_replays_prior_strategy_without_current_turn_update(
        response=response,
        request=request,
    ):
        return "prior_strategy_replay"
    if _response_needs_launch_field_fidelity_repair(response=response):
        return "launch_field_fidelity"
    if _response_needs_executable_strategy_grounding_audit(response=response):
        return "executable_strategy_grounding"
    if _response_needs_supported_strategy_capability_conflict_audit(response):
        return "capability_conflict"
    if _response_needs_temporal_runtime_repair(response=response, request=request):
        return "temporal_runtime_repair"
    if not _draft_asset_universe_has_exact_provider_symbols(draft):
        return "asset_universe_not_exact_provider_symbols"
    if _response_needs_missing_benchmark_fidelity_audit(response):
        return "missing_benchmark_fidelity"
    if (
        "stated_run_field_fidelity_audit" not in response.reason_codes
        and _draft_missing_exact_ticker_benchmark_needs_fidelity_audit(
            draft,
            current_message=request.current_user_message,
        )
    ):
        return "missing_benchmark_fidelity"
    if _draft_has_unprovenanced_benchmark(
        draft
    ) and not _draft_has_supported_default_benchmark(draft):
        return "unprovenanced_benchmark"
    if _response_has_current_message_date_range_reconciliation(
        response=response,
        request=request,
    ):
        return "date_range_reconciliation"
    if (
        canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
        and _dca_response_needs_semantic_field_audit(response)
    ):
        return "dca_semantic_field_audit"
    if _response_needs_stated_starting_capital_recheck(
        response=response,
        request=request,
    ):
        return "stated_starting_capital_recheck"
    return None


def _draft_asset_universe_has_exact_provider_symbols(
    draft: LLMStrategyDraft,
) -> bool:
    symbols = [
        str(symbol or "").strip()
        for symbol in draft.asset_universe
        if str(symbol or "").strip()
    ]
    if not symbols:
        return False
    for symbol in symbols:
        if not is_ticker_like_query(symbol):
            return False
        try:
            resolution = _resolve_asset_candidate(
                symbol,
                field="asset_universe",
                source="llm_extraction",
            )
        except ValueError:
            return False
        if resolution.status != "resolved" or resolution.asset is None:
            return False
        if resolution.asset.canonical_symbol.upper() != symbol.upper():
            return False
    return True


def _draft_has_supported_default_benchmark(draft: LLMStrategyDraft) -> bool:
    benchmark = _normalized_extracted_symbol(draft.comparison_baseline)
    if benchmark is None:
        return False
    asset_class = _single_provider_asset_class_for_draft(draft)
    if asset_class == "equity":
        return benchmark == "SPY"
    if asset_class == "crypto":
        return benchmark == "BTC"
    return False


def _single_provider_asset_class_for_draft(draft: LLMStrategyDraft) -> str | None:
    symbols = [
        str(symbol or "").strip()
        for symbol in draft.asset_universe
        if str(symbol or "").strip()
    ]
    asset_classes: set[str] = set()
    for symbol in symbols:
        try:
            resolution = _resolve_asset_candidate(
                symbol,
                field="asset_universe",
                source="llm_extraction",
            )
        except ValueError:
            return None
        if resolution.status != "resolved" or resolution.asset is None:
            return None
        asset_class = str(resolution.asset.asset_class or "").strip().lower()
        if asset_class:
            asset_classes.add(asset_class)
    if len(asset_classes) == 1:
        return next(iter(asset_classes))
    if asset_classes:
        return None
    explicit_asset_class = str(draft.asset_class or "").strip().lower()
    if explicit_asset_class in {"equity", "crypto"}:
        return explicit_asset_class
    return None


def _response_needs_temporal_runtime_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if _request_has_pending_date_answer_context(request):
        return True
    if _response_has_repairable_current_turn_date_gap(
        response=response,
        request=request,
    ):
        return True
    draft = response.candidate_strategy_draft
    if has_partial_explicit_date_range(draft.date_range):
        return True
    resolved_from_draft = _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if _llm_value_is_empty(draft.date_range):
        return resolved_from_draft is not None
    current_message_range = _date_range_from_current_turn_message(request)
    if (
        current_message_range is not None
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(current_message_range)
        and (
            "runtime_date_range_normalization" not in response.reason_codes
            or _current_turn_has_relative_window_evidence(request)
        )
    ):
        return True
    if _current_turn_has_relative_window_evidence(request):
        return True
    if (
        resolved_from_draft is not None
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(resolved_from_draft)
    ):
        return True
    return False


def _date_range_from_current_turn_message(
    request: InterpretationRequest,
) -> dict[str, str] | None:
    current_message = request.current_user_message.strip()
    if not current_message:
        return None
    for languages in _natural_time_language_candidates_from_hints(
        request.user.language_preference
    ):
        resolved = resolve_date_range_text(current_message, languages=languages)
        if resolved is not None:
            return resolved.payload
    return None


def _current_turn_has_relative_window_evidence(
    request: InterpretationRequest,
) -> bool:
    current_message = request.current_user_message.strip()
    if not current_message:
        return False
    for languages in _natural_time_language_candidates_from_hints(
        request.user.language_preference
    ):
        if (
            resolve_rolling_window_intent_text(current_message, languages=languages)
            is not None
        ):
            return True
    return False


async def _supported_date_gap_schema_repaired_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_has_repairable_current_turn_date_gap(
        response=response,
        request=request,
    ):
        return None
    return await _repair_incomplete_strategy_extraction(
        failed_response=response,
        preferred_model=preferred_model,
        request=request,
    )


async def _plan_artifact_edit_response(
    *,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    planned_response = await _plan_pending_artifact_assumption_edit(
        request=request,
        preferred_model=preferred_model,
    )
    if planned_response is None:
        planned_response = await _plan_focused_artifact_edit(
            model_name=preferred_model,
            request=request,
        )
    if planned_response is None:
        return None
    return await _stated_run_field_audited_response(
        response=planned_response,
        preferred_model=preferred_model,
        request=request,
    )


async def _stated_run_field_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    grounded_response = await _audit_executable_strategy_grounding(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if grounded_response is not None:
        response = grounded_response
        if response.requires_clarification:
            return response
    date_window_response = await _focused_date_window_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if date_window_response is not None:
        response = date_window_response
    audited_response = await _audit_stated_run_fields(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if audited_response is not None:
        response = audited_response
        date_window_response = await _focused_date_window_audited_response(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
        if date_window_response is not None:
            response = date_window_response
    conflict_response = await _audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if conflict_response is not None:
        response = await _underfilled_strategy_repaired_response(
            response=conflict_response,
            preferred_model=preferred_model,
            request=request,
        )
    if (
        _response_needs_supported_signal_rule_recovery(
            response,
            current_user_message=request.current_user_message,
        )
        or _llm_signal_strategy_is_underfilled(response.candidate_strategy_draft)
    ):
        response = await _signal_rule_checked_response(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
    return _response_with_executable_fields_preferred_over_clarification_prose(
        response
    )


async def _underfilled_strategy_repaired_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if _structured_interpretation_has_required_shape(response, request=request):
        return response
    repaired_response = await _repair_incomplete_strategy_extraction(
        failed_response=response,
        preferred_model=preferred_model,
        request=request,
    )
    return repaired_response or response


async def _audit_stated_run_fields(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    audited_response = await _audit_stated_run_field_fidelity(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if audited_response is not None:
        return _response_with_resolved_runtime_date_range(
            response=audited_response,
            request=request,
        )
    capital_response = await _audit_stated_starting_capital_fidelity(
        response=response,
        request=request,
    )
    if capital_response is not None:
        return _response_with_resolved_runtime_date_range(
            response=capital_response,
            request=request,
        )
    return None


def _clear_auto_simplified_strategy_when_rule_is_ambiguous(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    if not _response_has_ambiguous_rule_fields(response):
        return response
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return response
    repaired = response.model_copy(deep=True)
    repaired.requires_clarification = True
    repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *response.reason_codes,
                "blocked_auto_simplification_for_ambiguous_rule",
            ]
        )
    )
    repaired.candidate_strategy_draft.strategy_type = None
    return repaired


def _response_has_ambiguous_rule_fields(response: LLMInterpretationResponse) -> bool:
    return any(
        field.field_name in {"entry_logic", "exit_logic"}
        for field in response.ambiguous_fields
    )


async def _plan_focused_artifact_edit(
    *,
    model_name: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    messages = _focused_artifact_edit_messages(request)
    if messages is None:
        return None
    try:
        response = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_openrouter_wire_messages(messages),
            schema_model=LLMInterpretationResponse,
            schema_name="LLMInterpretationResponse",
            model_name=model_name,
        )
    except Exception:
        return None
    if not isinstance(response, LLMInterpretationResponse):
        return None
    response = _normalize_response_for_runtime_context(response, request=request)
    response = await _signal_rule_checked_response(
        response=response,
        preferred_model=model_name,
        request=request,
    )
    if not _structured_interpretation_has_required_shape(response, request=request):
        return None
    return response


async def _repair_incomplete_strategy_extraction(
    *,
    failed_response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _strategy_extraction_repair_is_allowed(failed_response, request=request):
        return None
    messages = _focused_strategy_extraction_messages(request)
    for model_name in _unique_repair_models(
        preferred_model,
        task=_INTERPRETATION_REPAIR_TASK,
    ):
        try:
            extraction = await invoke_openrouter_json_schema(
                task=_INTERPRETATION_REPAIR_TASK,
                messages=_openrouter_wire_messages(messages),
                schema_model=FocusedStrategyExtraction,
                schema_name="FocusedStrategyExtraction",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(extraction, FocusedStrategyExtraction):
            continue
        if not _focused_strategy_extraction_has_material_fields(extraction):
            continue
        response = _response_from_focused_strategy_extraction(
            extraction=extraction,
            request=request,
            base_response=failed_response,
        )
        response = _normalize_response_for_runtime_context(response, request=request)
        response = _augment_strategy_assets_from_resolvable_context(
            response=response,
            request=request,
        )
        if _response_can_skip_optional_runtime_readiness_audits(
            response=response,
            request=request,
        ):
            _log_runtime_readiness_step(
                "ready_after_focused_strategy_repair",
                response=response,
            )
            return response
        response = await _signal_rule_checked_response(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        conflict_response = await _audit_supported_strategy_capability_conflict(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        if conflict_response is not None:
            response = conflict_response
        date_window_response = await _focused_date_window_audited_response(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        if date_window_response is not None:
            response = date_window_response
        audited_response = await _audit_stated_run_fields(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        if audited_response is not None:
            response = audited_response
        if _structured_interpretation_has_required_shape(response, request=request):
            return response
    return None


async def _focused_date_window_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_focused_date_window_intent_repair(
        response=response,
        request=request,
    ):
        return None
    messages = _focused_date_window_extraction_messages(
        response=response,
        request=request,
    )
    for model_name in _unique_repair_models(
        preferred_model,
        task=_INTERPRETATION_REPAIR_TASK,
    ):
        try:
            extraction = await invoke_openrouter_json_schema(
                task=_INTERPRETATION_REPAIR_TASK,
                messages=messages,
                schema_model=FocusedDateWindowExtraction,
                schema_name="FocusedDateWindowExtraction",
                model_name=model_name,
            )
        except Exception as exc:
            log_openrouter_failure(
                task=_INTERPRETATION_REPAIR_TASK,
                model_name=model_name,
                exc=exc,
                message="Focused date-window extraction failed; preserving draft dates",
            )
            continue
        if not isinstance(extraction, FocusedDateWindowExtraction):
            continue
        repaired = _response_from_focused_date_window_extraction(
            response=response,
            extraction=extraction,
            request=request,
        )
        if repaired is not None:
            return repaired
    return None


def _response_needs_focused_date_window_intent_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    pending_date_answer = _request_has_pending_date_answer_context(request)
    if (
        response.intent not in {"strategy_drafting", "backtest_execution"}
        and not pending_date_answer
    ):
        return False
    pending_supported_date_answer = (
        _pending_supported_execution_date_answer_can_use_focused_audit(
            response=response,
            request=request,
        )
    )
    if "focused_date_window_intent_repair" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    has_repairable_current_turn_date_gap = (
        _response_has_repairable_current_turn_date_gap(
            response=response,
            request=request,
        )
    )
    if response.task_relation != "new_task" and not (
        pending_date_answer
        or pending_supported_date_answer
        or has_repairable_current_turn_date_gap
    ):
        return False
    has_material_evidence = (
        _request_current_turn_has_material_execution_evidence(request)
        or _draft_has_supported_capability_shape_for_date_repair(draft)
        or pending_date_answer
    )
    has_semantic_date_evidence = _draft_has_semantic_date_window_evidence(draft)
    if response.semantic_turn_act == "answer_pending_need" and not (
        (
            has_material_evidence
            and _response_has_pending_base_field(response, "date_range")
        )
        or pending_supported_date_answer
        or has_repairable_current_turn_date_gap
    ):
        return False
    if response.semantic_turn_act in {
        "approval",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.semantic_turn_act == "educational_question" and not pending_date_answer:
        return False
    if (
        not pending_date_answer
        and not has_material_evidence
        and not _supported_partial_draft_has_repairable_shape(draft)
    ):
        return False
    if (
        resolve_date_range_intent(draft.date_range_intent) is not None
        and has_semantic_date_evidence
    ):
        return True
    has_complete_date_range = _has_complete_date_range_payload(
        normalize_date_range_candidate(draft.date_range)
    )
    has_pending_date_range = _response_has_pending_base_field(response, "date_range")
    if (
        has_complete_date_range
        and response.requires_clarification
        and not has_pending_date_range
    ):
        return False
    if has_pending_date_range:
        return (
            has_material_evidence
            or has_semantic_date_evidence
            or _supported_partial_draft_has_repairable_shape(draft)
        )
    if _llm_value_is_empty(draft.date_range):
        return (
            pending_date_answer
            or has_semantic_date_evidence
            or has_repairable_current_turn_date_gap
        )
    if has_partial_explicit_date_range(draft.date_range):
        return True
    if has_semantic_date_evidence:
        return True
    if _complete_date_range_needs_current_turn_date_audit(
        response=response,
        request=request,
        has_complete_date_range=has_complete_date_range,
    ):
        return True
    if not _llm_value_is_empty(draft.date_range_raw_text):
        return True
    return has_repairable_current_turn_date_gap


def _request_has_pending_date_answer_context(
    request: InterpretationRequest,
) -> bool:
    if request.selected_thread_metadata.get("last_stage_outcome") != (
        "await_user_reply"
    ):
        return False
    requested_field = _field_path_base(
        str(request.selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field != "date_range":
        return False
    if not request.current_user_message.strip():
        return False
    return _request_has_active_strategy_context(request)


def _complete_date_range_needs_current_turn_date_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    has_complete_date_range: bool,
) -> bool:
    if not has_complete_date_range:
        return False
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    has_semantic_date_evidence = _draft_has_semantic_date_window_evidence(draft)
    if has_semantic_date_evidence:
        return False
    if resolve_date_range_intent(draft.date_range_intent) is not None:
        return True
    return True


def _response_has_repairable_current_turn_date_gap(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not response.requires_clarification:
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return bool(
        request.current_user_message.strip()
        or draft.raw_user_phrasing
        or draft.strategy_thesis
    )


def _pending_supported_execution_date_answer_can_use_focused_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.semantic_turn_act != "answer_pending_need":
        return False
    if not _response_has_pending_base_field(response, "date_range"):
        return False
    if response.unsupported_constraints or response.ambiguous_fields:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return bool(
        request.current_user_message.strip()
        or draft.raw_user_phrasing
        or draft.strategy_thesis
    )


def _draft_has_supported_capability_shape_for_date_repair(
    draft: LLMStrategyDraft,
) -> bool:
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not (draft.asset_universe or draft.asset_class):
        return False
    return any(
        [
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            draft.recurring_contribution is not None,
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.comparison_baseline),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
            bool(draft.field_provenance),
            bool(_draft_semantic_evidence_spans(draft)),
        ]
    )


def _focused_date_window_extraction_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You extract only the temporal constraint for an Argus backtest. "
                "The current user message may be in any language, shorthand, or "
                "messy prose. Return canonical machine fields, not user-facing "
                "copy. Do not decide strategy, asset, capital, support status, or "
                "whether to run. Do not infer a default window when the current "
                "message does not state one. Do not copy endpoint dates from the "
                "structured draft unless they are directly supported by the current "
                "user message. If the structured draft has a partial date_range "
                "whose start or end contains natural-language prose instead of an "
                "ISO date or today/current_date sentinel, treat that value only as "
                "non-executable evidence and re-extract the temporal intent from "
                "the current user message.\n\n"
                "For relative or semantic windows, do not calculate endpoint dates. "
                "A relative lookback anchored to the present is already a complete "
                "temporal constraint, even when the user does not provide calendar "
                "endpoint dates. If the current message states a lookback duration "
                "with a count and time unit in any language, set has_date_window=true "
                "and return date_range_intent kind=rolling_window with anchor=today. "
                "Do not ask for start/end dates just because the current message uses "
                "natural language. "
                "Return date_range_intent with kind=rolling_window, count, unit, "
                "anchor=today, confidence, and evidence. For year-to-date, return "
                "kind=year_to_date. For a calendar year, return kind=calendar_year "
                "and year. For since-style windows, return kind=since and start. "
                "For explicit calendar start/end endpoints, return date_range with "
                "ISO dates or the canonical sentinel today/current_date. Never put "
                "prose or shorthand relative windows inside date_range start/end. "
                "If no temporal window is present, has_date_window=false."
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON that may contain drifted dates: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_focused_date_window_extraction(
    *,
    response: LLMInterpretationResponse,
    extraction: FocusedDateWindowExtraction,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not extraction.has_date_window or extraction.confidence < 0.65:
        return None
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    raw_text = (
        str(extraction.date_range_raw_text or "").strip()
        or str(extraction.evidence or "").strip()
    )
    changed = False
    if extraction.date_range_intent is not None:
        intent_resolution = resolve_date_range_intent(extraction.date_range_intent)
        if intent_resolution is None:
            return None
        draft.date_range_intent = extraction.date_range_intent
        draft.date_range = intent_resolution.payload
        changed = True
    elif extraction.date_range is not None:
        normalized_date_range = normalize_date_range_candidate(extraction.date_range)
        if not _has_complete_date_range_payload(normalized_date_range):
            return None
        try:
            explicit_resolution = resolve_date_range(normalized_date_range)
        except Exception:
            return None
        if explicit_resolution.used_default:
            return None
        draft.date_range = explicit_resolution.payload
        changed = True
    if not changed:
        return None
    pending_date_answer = _request_has_pending_date_answer_context(request)
    if raw_text:
        draft.date_range_raw_text = raw_text
        draft.evidence_spans = {
            **dict(draft.evidence_spans or {}),
            "date_range": raw_text,
        }
    if not has_partial_explicit_date_range(draft.date_range):
        repaired.missing_required_fields = [
            field
            for field in repaired.missing_required_fields
            if _field_path_base(field) != "date_range"
        ]
        repaired.ambiguous_fields = [
            field
            for field in repaired.ambiguous_fields
            if _field_path_base(field.field_name) != "date_range"
        ]
    if (
        pending_date_answer
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.intent = "backtest_execution"
        repaired.task_relation = "continue"
        repaired.semantic_turn_act = "answer_pending_need"
        repaired.result_followup_focus = None
        repaired.capability_question_focus = None
        repaired.context_question_focus = None
        repaired.artifact_target = "active_confirmation"
    elif (
        repaired.requires_clarification
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.intent = "backtest_execution"
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "focused_date_window_intent_repair",
                *(
                    ["pending_date_answer_focused_window_repair"]
                    if pending_date_answer
                    else []
                ),
            ]
        )
    )
    return repaired


async def _plan_pending_artifact_assumption_edit(
    *,
    request: InterpretationRequest,
    preferred_model: str,
    require_failure_edit_evidence: bool = False,
) -> LLMInterpretationResponse | None:
    if not _request_targets_pending_artifact_assumption_edit(request):
        return None
    if (
        require_failure_edit_evidence
        and not _request_has_planner_edit_candidate_after_model_failure(request)
    ):
        return None
    snapshot = request.latest_task_snapshot
    prior_strategy = _prior_strategy_payload(request)
    active_confirmation = (
        snapshot.active_confirmation_reference.model_dump(mode="json")
        if snapshot is not None and snapshot.active_confirmation_reference is not None
        else None
    )
    plan = await plan_artifact_assumption_edit(
        current_user_message=request.current_user_message,
        prior_strategy=prior_strategy,
        active_confirmation=active_confirmation,
        preferred_model=preferred_model,
        language=request.user.language_preference,
    )
    if plan is None:
        return None
    return _response_from_artifact_assumption_edit_plan(plan=plan, request=request)


def _request_has_planner_edit_candidate_after_model_failure(
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field in {"assumption", "asset_universe", "comparison_baseline"}:
        return True

    snapshot = request.latest_task_snapshot
    prior = (
        snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
        if snapshot is not None
        else None
    )
    if prior is None:
        return False

    def _resolve_candidate(query: str) -> AssetResolution | None:
        try:
            return _resolve_asset_candidate(
                query,
                field="asset_universe[0]",
                source="user_mention",
            )
        except ValueError:
            return None

    current_symbols = {
        symbol
        for asset in provider_ticker_assets_from_text(
            request.current_user_message,
            resolve_candidate=_resolve_candidate,
            limit=10,
        )
        if (
            symbol := _normalized_ticker_symbol(
                getattr(asset, "canonical_symbol", None)
            )
        )
        is not None
    }
    if not current_symbols:
        return False
    prior_symbols = {
        symbol
        for value in prior.asset_universe
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    prior_benchmark = _normalized_ticker_symbol(prior.comparison_baseline)
    if prior_benchmark is not None:
        prior_symbols.add(prior_benchmark)
    return not current_symbols <= prior_symbols


async def _signal_rule_checked_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    pending_rule_answer = await _repair_pending_signal_rule_answer_if_needed(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = pending_rule_answer or response
    recovered_signal_rule = await _recover_supported_signal_rule_from_draft_if_needed(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = recovered_signal_rule or response
    planned = (
        await _plan_underfilled_signal_rule_if_needed(
            response=response,
            preferred_model=preferred_model,
            request=request,
        )
        or response
    )
    audited = await _audit_signal_rule_grounding_if_needed(
        response=planned,
        preferred_model=preferred_model,
        request=request,
    )
    return audited or planned


async def _recover_supported_signal_rule_from_draft_if_needed(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_supported_signal_rule_recovery(
        response,
        current_user_message=request.current_user_message,
    ):
        return None
    planning_response = _supported_signal_rule_planning_response(response)
    planning_response = _augment_signal_planning_context_from_message(
        response=planning_response,
        request=request,
    )
    plan = await repair_signal_rule_plan(
        current_user_message=request.current_user_message,
        candidate_strategy=planning_response.candidate_strategy_draft.model_dump(
            mode="json"
        ),
        prior_strategy=_prior_strategy_payload(request),
        preferred_model=preferred_model,
    )
    if plan is None or plan.outcome != "ready_to_confirm":
        return None
    return _response_from_signal_rule_plan(
        response=planning_response,
        plan=plan,
    )


def _augment_signal_planning_context_from_message(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    draft = response.candidate_strategy_draft
    if draft.asset_universe:
        return response
    assets = _resolved_asset_mentions_from_message(request.current_user_message)
    if not assets:
        return response
    repaired = response.model_copy(deep=True)
    repaired_draft = repaired.candidate_strategy_draft
    repaired_draft.asset_universe = [asset.canonical_symbol for asset in assets]
    asset_classes = {asset.asset_class for asset in assets}
    if len(asset_classes) == 1:
        repaired_draft.asset_class = next(iter(asset_classes))
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "provider_catalog_asset_recovery",
            ]
        )
    )
    return repaired


def _augment_strategy_assets_from_resolvable_context(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    asset_grounding_removed_symbols = any(
        code in response.reason_codes
        for code in {
            "asset_grounding_audit_low_confidence_cleared_suspicious_symbols",
            "asset_grounding_audit_removed_unsubstantiated_symbols",
            "asset_grounding_audit_unavailable_cleared_suspicious_symbols",
        }
    )
    draft = response.candidate_strategy_draft
    if draft.asset_universe:
        return response
    if not _llm_strategy_draft_has_non_asset_strategy_anchor(draft):
        return response
    assets = _resolved_asset_mentions_from_values(
        request.current_user_message,
        exact_tickers_only=not (
            canonical_strategy_type(draft.strategy_type) == "signal_strategy"
            or _llm_strategy_draft_has_rule_or_indicator_fields(draft)
        ),
    )
    if not assets:
        return response
    asset_classes = {asset.asset_class for asset in assets}
    if asset_grounding_removed_symbols and len(asset_classes) <= 1:
        return response
    repaired = response.model_copy(deep=True)
    repaired_draft = repaired.candidate_strategy_draft
    repaired_draft.asset_universe = [asset.canonical_symbol for asset in assets]
    if len(asset_classes) == 1:
        repaired_draft.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        repaired_draft.asset_class = "mixed"
        if not any(
            item.category == "unsupported_asset_mix"
            for item in repaired.unsupported_constraints
        ):
            repaired.unsupported_constraints.append(
                LLMUnsupportedConstraint(
                    category="unsupported_asset_mix",
                    raw_value=", ".join(repaired_draft.asset_universe),
                    explanation=(
                        "Argus Alpha cannot run equity, crypto, and currency pairs "
                        "together in one simulation yet."
                    ),
                    simplification_labels=[
                        "Run one asset class at a time",
                        "Run the equity symbols only",
                        "Run the crypto or currency pair symbols only",
                    ],
                )
            )
        repaired.requires_clarification = True
        repaired.assistant_response = None
    repaired.missing_required_fields = [
        field
        for field in repaired.missing_required_fields
        if field != "asset_universe"
    ]
    repaired.ambiguous_fields = [
        field
        for field in repaired.ambiguous_fields
        if field.field_name != "asset_universe"
    ]
    if (
        repaired.requires_clarification
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and bool(canonical_strategy_type(repaired_draft.strategy_type))
        and _llm_strategy_draft_has_extractable_fields(repaired_draft)
        and not _llm_signal_strategy_is_underfilled(repaired_draft)
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "provider_catalog_asset_recovery",
            ]
        )
    )
    return repaired


def _resolved_asset_mentions_from_values(
    *values: str | None,
    exact_tickers_only: bool = True,
) -> list[Any]:
    resolved_assets: list[Any] = []
    seen: set[str] = set()

    def _resolve_candidate(query: str) -> AssetResolution | None:
        if not _asset_recovery_query_is_explicit_ticker(query):
            return None
        try:
            return _resolve_asset_candidate(
                query,
                field="asset_universe[0]",
                source="user_mention",
            )
        except ValueError:
            return None

    for value in values:
        if not value:
            continue
        assets = (
            provider_ticker_assets_from_text(
                value,
                resolve_candidate=_resolve_candidate,
                limit=5,
            )
            if exact_tickers_only
            else _resolved_asset_mentions_from_message(value)
        )
        for asset in assets:
            symbol = asset.canonical_symbol
            if symbol in seen:
                continue
            seen.add(symbol)
            resolved_assets.append(asset)
            if len(resolved_assets) >= 5:
                return resolved_assets
    return resolved_assets


def _resolved_asset_mentions_from_message(message: str) -> list[Any]:
    def _resolve_candidate(query: str) -> AssetResolution | None:
        try:
            return _resolve_asset_candidate(
                query,
                field="asset_universe[0]",
                source="user_mention",
            )
        except ValueError:
            return None

    return [
        mention.asset
        for mention in grounded_asset_mentions_from_text(
            message,
            resolve_candidate=_resolve_candidate,
            limit=5,
        )
    ]


async def _repair_pending_signal_rule_answer_if_needed(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _request_targets_pending_signal_rule(request):
        return None
    if _response_needs_signal_rule_grounding_audit(response):
        return None
    prior_strategy = _prior_strategy_payload(request)
    if not prior_strategy:
        return None
    if canonical_strategy_type(prior_strategy.get("strategy_type")) != "signal_strategy":
        return None

    planning_response = _pending_signal_rule_planning_response(
        response=response,
        prior_strategy=prior_strategy,
        current_user_message=request.current_user_message,
    )
    plan = await repair_signal_rule_plan(
        current_user_message=request.current_user_message,
        candidate_strategy=planning_response.candidate_strategy_draft.model_dump(
            mode="json"
        ),
        prior_strategy=prior_strategy,
        preferred_model=preferred_model,
    )
    if plan is None:
        return None
    return _response_from_signal_rule_plan(
        response=planning_response,
        plan=plan,
    )


async def _plan_underfilled_signal_rule_if_needed(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_signal_rule_plan(response):
        return None
    plan = await repair_signal_rule_plan(
        current_user_message=request.current_user_message,
        candidate_strategy=response.candidate_strategy_draft.model_dump(mode="json"),
        prior_strategy=_prior_strategy_payload(request),
        preferred_model=preferred_model,
    )
    if plan is None:
        return None
    return _response_from_signal_rule_plan(
        response=response,
        plan=plan,
    )


def _unique_repair_models(
    preferred_model: str,
    *,
    task: OpenRouterTask = "interpretation",
) -> list[str]:
    task_candidates = openrouter_structured_model_candidates(task=task)
    if task == "interpretation":
        candidates = [preferred_model, *task_candidates]
    else:
        candidates = [*task_candidates, preferred_model]
    seen: set[str] = set()
    ordered: list[str] = []
    for model_name in candidates:
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        ordered.append(model_name)
    return ordered


def _response_needs_artifact_context_repair(
    response: LLMInterpretationResponse,
) -> bool:
    if response.unsupported_constraints:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_structural_execution_fields(draft):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return bool(response.assistant_response)
    return (
        response.intent == "conversation_followup"
        and response.semantic_turn_act == "educational_question"
        and bool(response.assistant_response)
        and _llm_strategy_draft_has_unstructured_strategy_text(draft)
    )


def _response_needs_testable_idea_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if _is_vague_strategy_start_guidance(response):
        return False
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field:
        return False
    draft = response.candidate_strategy_draft
    if _supported_anchor_needs_focused_run_window_repair(
        response=response,
        request=request,
    ):
        return True
    if _supported_partial_strategy_needs_focused_schema_repair(
        response=response,
        request=request,
    ):
        return True
    if _noncanonical_strategy_text_needs_focused_schema_repair(
        response=response,
        request=request,
    ):
        return True
    if (
        response.intent == "unsupported_or_out_of_scope"
        and response.semantic_turn_act == "unsupported_request"
        and any(
            item.category == "unsupported_strategy_logic"
            for item in response.unsupported_constraints
        )
        and bool(draft.raw_user_phrasing or draft.strategy_thesis)
    ):
        return True
    if _llm_strategy_draft_has_semantic_execution_anchor(draft):
        return False
    if (
        response.intent in {"strategy_drafting", "backtest_execution"}
        and response.requires_clarification
        and bool(response.assistant_response)
        and bool(draft.raw_user_phrasing or draft.strategy_thesis)
    ):
        return True
    if (
        response.intent == "unsupported_or_out_of_scope"
        and response.semantic_turn_act == "unsupported_request"
    ):
        return True
    if response.intent in {"beginner_guidance", "conversation_followup"} and (
        response.semantic_turn_act == "unsupported_request"
    ):
        return True
    if response.intent in {"beginner_guidance", "conversation_followup"} and (
        response.semantic_turn_act in {None, "educational_question", "new_idea"}
    ):
        return True
    return False


def _supported_anchor_needs_focused_run_window_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not (
        response.intent in {"strategy_drafting", "backtest_execution"}
        and response.requires_clarification
        and bool(response.assistant_response)
    ):
        return False
    if _semantic_turn_act_blocks_supported_schema_repair(
        response=response,
        request=request,
    ):
        return False
    if (
        response.capability_question_focus is not None
        or response.context_question_focus is not None
        or response.unsupported_constraints
        or response.ambiguous_fields
    ):
        return False
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
        "indicator_threshold",
        "signal_strategy",
    }:
        return False
    if not (draft.raw_user_phrasing or draft.strategy_thesis):
        return False
    return _llm_value_is_empty(draft.date_range) and (
        _date_range_from_intent_or_bounded_evidence(draft) is None
    )


def _supported_partial_strategy_needs_focused_schema_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not (
        response.intent in {"strategy_drafting", "backtest_execution"}
        and response.requires_clarification
        and bool(response.assistant_response)
    ):
        return False
    if _semantic_turn_act_blocks_supported_schema_repair(
        response=response,
        request=request,
    ):
        return False
    if (
        response.capability_question_focus is not None
        or response.context_question_focus is not None
        or response.unsupported_constraints
        or response.ambiguous_fields
    ):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
        "indicator_threshold",
        "signal_strategy",
    }:
        return False
    if not (
        draft.raw_user_phrasing
        or draft.strategy_thesis
        or request.current_user_message.strip()
    ):
        return False
    missing_fields = {
        _field_path_base(field)
        for field in response.missing_required_fields
        if str(field).strip()
    }
    if not missing_fields:
        return _llm_value_is_empty(
            draft.date_range
        ) and _supported_partial_draft_has_repairable_shape(draft)
    if not missing_fields.intersection(
        {
            "asset_universe",
            "capital_amount",
            "cadence",
            "date_range",
            "entry_logic",
            "entry_rule",
            "entry_threshold",
            "exit_logic",
            "exit_rule",
            "exit_threshold",
            "indicator",
            "indicator_period",
            "rule_spec",
        }
    ):
        return False
    return _supported_partial_draft_has_repairable_shape(draft)


def _supported_partial_draft_has_repairable_shape(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.date_range),
            bool(draft.date_range_raw_text),
            bool(draft.comparison_baseline),
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            draft.recurring_contribution is not None,
            bool(draft.evidence_spans),
            bool(draft.field_provenance),
            bool(draft.extra_parameters),
        ]
    )


def _noncanonical_strategy_text_needs_focused_schema_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.intent not in {
        "backtest_execution",
        "beginner_guidance",
        "conversation_followup",
        "strategy_drafting",
        "unsupported_or_out_of_scope",
    }:
        return False
    if not (
        response.requires_clarification
        and bool(response.assistant_response)
        and _request_current_turn_has_material_execution_evidence(request)
    ):
        return False
    if (
        response.capability_question_focus is not None
        or response.context_question_focus is not None
        or response.unsupported_constraints
        or response.ambiguous_fields
    ):
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "educational_question",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) in SUPPORTED_STRATEGY_TYPES:
        return False
    if _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft):
        return False
    return bool(
        draft.raw_user_phrasing
        or draft.strategy_thesis
        or draft.strategy_type
        or request.current_user_message.strip()
    )


def _semantic_turn_act_blocks_supported_schema_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.semantic_turn_act == "answer_pending_need":
        return _request_has_active_strategy_context(
            request
        ) and not _request_current_turn_has_material_execution_evidence(request)
    return response.semantic_turn_act in {
        "approval",
        "educational_question",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }


def _response_needs_material_evidence_strategy_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if not response.requires_clarification or not response.assistant_response:
        return False
    if response.capability_question_focus is not None:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_semantic_execution_anchor(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _response_needs_pre_guidance_focused_strategy_extraction(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act not in {None, "new_idea"}:
        return False
    if response.requires_clarification and response.assistant_response:
        return False
    if (
        response.capability_question_focus is not None
        or response.context_question_focus is not None
        or response.unsupported_constraints
        or response.ambiguous_fields
    ):
        return False
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_semantic_execution_anchor(draft):
        return bool(
            _capability_required_missing_fields_for_canonical_strategy([], draft=draft)
        )
    return bool(
        draft.raw_user_phrasing
        or draft.strategy_thesis
        or request.current_user_message.strip()
    )


def _vague_strategy_start_as_guidance(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    if not _is_vague_strategy_start(response):
        return response
    return response.model_copy(
        update={
            "intent": "beginner_guidance",
            "requires_clarification": True,
            "missing_required_fields": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "vague_strategy_start_guidance",
                    ]
                )
            ),
        }
    )


def _is_vague_strategy_start_guidance(response: LLMInterpretationResponse) -> bool:
    return "vague_strategy_start_guidance" in response.reason_codes


def _is_vague_strategy_start(response: LLMInterpretationResponse) -> bool:
    if response.intent != "strategy_drafting":
        return False
    if response.capability_question_focus is not None:
        return False
    if response.semantic_turn_act not in {None, "new_idea"}:
        return False
    if response.unsupported_constraints or response.ambiguous_fields:
        return False
    draft = response.candidate_strategy_draft
    return not _llm_strategy_draft_has_semantic_execution_anchor(draft)


def _response_needs_structured_strategy_repair(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if not response.requires_clarification:
        return False
    if response.intent not in {
        "strategy_drafting",
        "backtest_execution",
        "unsupported_or_out_of_scope",
    }:
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.unsupported_constraints:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type):
        return False
    if _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft):
        return False
    if not _llm_strategy_draft_has_extractable_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _llm_strategy_draft_has_semantic_execution_anchor(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.strategy_type),
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.entry_logic),
            bool(draft.exit_logic),
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
            bool(draft.date_range),
            bool(draft.risk_rules),
            bool(draft.extra_parameters),
        ]
    )


async def _audit_executable_strategy_grounding(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_executable_strategy_grounding_audit(response=response):
        return None
    messages = _executable_strategy_grounding_messages(
        response=response,
        request=request,
    )
    for model_name in _unique_repair_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=ExecutableStrategyGroundingAudit,
                schema_name="ExecutableStrategyGroundingAudit",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(audit, ExecutableStrategyGroundingAudit):
            continue
        repaired = _response_from_executable_strategy_grounding_audit(
            response=response,
            audit=audit,
        )
        if repaired is not None:
            return repaired
        return None
    return None


async def _audit_stated_run_field_fidelity(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    del preferred_model
    if not _response_needs_stated_run_field_fidelity_audit(
        response=response,
        request=request,
    ):
        return None
    deterministic_repair = _response_from_current_message_run_field_contract(
        response=response,
        request=request,
    )
    if deterministic_repair is not None:
        response = deterministic_repair
        if not _response_needs_stated_run_field_fidelity_audit(
            response=response,
            request=request,
        ):
            return response
    messages = _stated_run_field_fidelity_messages(
        response=response,
        request=request,
    )
    try:
        audit = await invoke_openrouter_json_schema(
            task="field_fidelity",
            messages=messages,
            schema_model=StatedRunFieldFidelityAudit,
            schema_name="StatedRunFieldFidelityAudit",
        )
    except Exception:
        capital_recheck = await _audit_stated_starting_capital_fidelity(
            response=deterministic_repair or response,
            request=request,
        )
        if capital_recheck is not None:
            return capital_recheck
        return deterministic_repair
    if not isinstance(audit, StatedRunFieldFidelityAudit):
        capital_recheck = await _audit_stated_starting_capital_fidelity(
            response=deterministic_repair or response,
            request=request,
        )
        if capital_recheck is not None:
            return capital_recheck
        return deterministic_repair
    repaired = _response_from_stated_run_field_fidelity_audit(
        response=response,
        audit=audit,
        current_message=request.current_user_message,
    )
    candidate_response = repaired or deterministic_repair or response
    capital_recheck = await _audit_stated_starting_capital_fidelity(
        response=candidate_response,
        request=request,
    )
    if capital_recheck is not None:
        return capital_recheck
    if repaired is None:
        return deterministic_repair
    return repaired


async def _audit_supported_strategy_capability_conflict(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_supported_strategy_capability_conflict_audit(response):
        return None
    messages = _supported_strategy_capability_conflict_messages(
        response=response,
        request=request,
    )
    try:
        audit = await invoke_openrouter_json_schema(
            task="capability_conflict",
            messages=messages,
            schema_model=SupportedStrategyCapabilityConflictAudit,
            schema_name="SupportedStrategyCapabilityConflictAudit",
        )
    except Exception:
        return _structured_supported_strategy_capability_conflict_fallback(
            response
        )
    if not isinstance(audit, SupportedStrategyCapabilityConflictAudit):
        return _structured_supported_strategy_capability_conflict_fallback(
            response
        )
    if (
        audit.drop_unsupported_strategy_logic
        and not audit.keep_unsupported_strategy_logic
        and audit.confidence >= 0.7
    ):
        strategy_type = canonical_strategy_type(audit.selected_strategy_type)
        if not strategy_type:
            strategy_type = canonical_strategy_type(
                response.candidate_strategy_draft.strategy_type
            )
        if strategy_type not in {"buy_and_hold", "dca_accumulation"}:
            return None
        repaired = _response_with_supported_strategy_capability_conflict_removed(
            response=response,
            strategy_type=strategy_type,
        )
        return await _dca_contribution_role_audited_response(
            response=repaired,
            preferred_model=preferred_model,
            request=request,
        )
    if audit.confidence < 0.7:
        return _structured_supported_strategy_capability_conflict_fallback(
            response
        )
    return None


def _response_needs_stated_run_field_fidelity_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest | None = None,
) -> bool:
    if (
        response.requires_clarification
        and not _llm_strategy_draft_has_concrete_execution_target(
            response.candidate_strategy_draft
        )
    ):
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "unsupported_request",
    }:
        return False
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    if _pending_dca_assumption_reply_needs_stated_run_field_audit(
        response=response,
        request=request,
    ):
        return True
    if request is not None and _response_replays_prior_strategy_without_current_turn_update(
        response=response,
        request=request,
    ):
        return False
    draft = response.candidate_strategy_draft
    current_message = request.current_user_message if request is not None else ""
    requested_field = ""
    if request is not None:
        requested_field = _field_path_base(
            request.selected_thread_metadata.get("requested_field")
        )
    if (
        canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
        and _dca_response_needs_semantic_field_audit(response)
    ):
        return True
    if _response_needs_current_message_date_repair(
        response=response,
        current_message=current_message,
    ):
        return True
    if _response_needs_missing_benchmark_fidelity_audit(response):
        return True
    if _draft_has_unprovenanced_benchmark(draft):
        return True
    if _response_has_current_message_date_range_reconciliation(
        response=response,
        request=request,
    ):
        return True
    if response.semantic_turn_act == "answer_pending_need":
        if _supported_pending_need_has_recoverable_current_turn_run_fields(
            response=response,
            request=request,
            current_message=current_message,
            requested_field=requested_field,
        ):
            return True
        if requested_field == "date_range":
            return any(
                [
                    not _llm_value_is_empty(draft.date_range),
                    _draft_has_semantic_date_window_evidence(draft),
                    _draft_missing_comparison_baseline_needs_stated_run_field_audit(
                        draft,
                        current_message=current_message,
                    ),
                    _draft_capital_needs_stated_run_field_audit(
                        draft,
                        current_message=current_message,
                    ),
                ]
            )
        if requested_field == "assumption":
            return _draft_capital_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            )
        return False
    if not any(
        code in response.reason_codes
        for code in {
            "focused_strategy_extraction_repair",
            "signal_rule_plan_repair",
            "focused_repair_preserved_structured_context",
        }
    ):
        return _ready_response_has_unreconciled_stated_run_fields(
            draft,
            current_message=current_message,
        )
    if "focused_repair_from_unsupported_context" in response.reason_codes:
        return draft.capital_amount is None
    if "signal_rule_plan_repair" in response.reason_codes:
        return any(
            [
                _draft_capital_needs_stated_run_field_audit(
                    draft,
                    current_message=current_message,
                ),
                _llm_value_is_empty(draft.timeframe)
                and _draft_has_timeframe_evidence_for_audit(draft),
                _draft_date_range_needs_stated_run_field_audit(
                    draft,
                    current_message=current_message,
                ),
            ]
        )
    return any(
        [
            _focused_repair_benchmark_needs_fidelity_audit(
                draft,
                current_message=current_message,
            ),
            _focused_repair_capital_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
            _llm_value_is_empty(draft.timeframe)
            and _draft_has_timeframe_evidence_for_audit(draft),
            _draft_date_range_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
        ]
    )


def _response_has_current_message_date_range_reconciliation(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest | None,
) -> bool:
    if request is None:
        return False
    date_range = _date_range_from_intent_or_bounded_evidence(
        response.candidate_strategy_draft,
        language=request.user.language_preference,
    )
    if date_range is None:
        return False
    draft = response.candidate_strategy_draft
    if _llm_value_is_empty(draft.date_range):
        return True
    if has_partial_explicit_date_range(draft.date_range):
        return True
    if (
        resolve_date_range_intent(draft.date_range_intent) is not None
        and _draft_has_semantic_date_window_evidence(draft)
    ):
        return True
    if not isinstance(draft.date_range, dict):
        return False
    has_complete_date_range = _has_complete_date_range_payload(
        normalize_date_range_candidate(draft.date_range)
    )
    if _complete_date_range_needs_current_turn_date_audit(
        response=response,
        request=request,
        has_complete_date_range=has_complete_date_range,
    ):
        return True
    return _normalized_stated_field(draft.date_range) != _normalized_stated_field(
        date_range
    )


def _supported_pending_need_has_recoverable_current_turn_run_fields(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest | None,
    current_message: str,
    requested_field: str,
) -> bool:
    if request is None:
        return False
    if requested_field:
        return False
    if response.unsupported_constraints or response.ambiguous_fields:
        return False
    if (
        response.capability_question_focus is not None
        or response.context_question_focus is not None
    ):
        return False
    if _request_has_active_strategy_context(
        request
    ) and not _request_current_turn_has_material_execution_evidence(request):
        return False
    if not _request_current_turn_has_material_execution_evidence(request):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return any(
        [
            _draft_missing_comparison_baseline_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
            _draft_capital_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
        ]
    )


def _focused_repair_benchmark_needs_fidelity_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if _llm_value_is_empty(draft.comparison_baseline):
        return False
    if _comparison_baseline_has_trusted_provenance(
        draft
    ) and _comparison_baseline_has_provider_ticker_support(
        draft,
        current_message=current_message,
    ):
        return False
    return current_message_has_extra_provider_asset_for_benchmark(
        draft,
        current_message=current_message,
        resolved_asset_mentions=_resolved_asset_mentions_from_message(current_message),
        resolve_candidate=_resolve_benchmark_candidate_from_message,
    )


def _ready_response_has_unreconciled_stated_run_fields(
    draft: LLMStrategyDraft,
    *,
    current_message: str = "",
) -> bool:
    return any(
        [
            _draft_missing_comparison_baseline_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
            _draft_capital_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
            _llm_value_is_empty(draft.timeframe)
            and _draft_has_timeframe_evidence_for_audit(draft),
            _draft_date_range_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            ),
        ]
    )


def _draft_missing_comparison_baseline_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if not _llm_value_is_empty(draft.comparison_baseline):
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    if _draft_has_comparison_baseline_evidence(draft):
        return True
    return current_message_has_extra_provider_asset_for_benchmark(
        draft,
        current_message=current_message,
        resolved_asset_mentions=_resolved_asset_mentions_from_message(current_message),
        resolve_candidate=_resolve_benchmark_candidate_from_message,
    )


def _draft_missing_exact_ticker_benchmark_needs_fidelity_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if not _llm_value_is_empty(draft.comparison_baseline):
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    draft_symbols = {
        str(symbol or "").strip().upper()
        for symbol in draft.asset_universe
        if str(symbol or "").strip()
    }
    if not draft_symbols:
        return False
    draft_asset_class = str(draft.asset_class or "").strip().lower()
    for query in _explicit_benchmark_ticker_queries(current_message):
        resolution = _resolve_benchmark_candidate_from_message(query)
        if (
            resolution is None
            or resolution.status != "resolved"
            or resolution.asset is None
        ):
            continue
        asset = resolution.asset
        symbol = str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        if not symbol or symbol in draft_symbols:
            continue
        asset_class = str(getattr(asset, "asset_class", "") or "").strip().lower()
        if draft_asset_class and asset_class and asset_class != draft_asset_class:
            continue
        return True
    return False


def _resolve_benchmark_candidate_from_message(query: str) -> AssetResolution | None:
    try:
        return _resolve_asset_candidate(
            query,
            field="comparison_baseline",
            source="user_mention",
        )
    except ValueError:
        return None


async def _latest_result_routing_audited_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if not _response_needs_latest_result_routing_audit(response, request=request):
        return response
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=_latest_result_routing_audit_messages(
                response=response,
                request=request,
            ),
            schema_model=LatestResultRoutingAudit,
            schema_name="LatestResultRoutingAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message=(
                "Latest result routing audit failed; preserving primary "
                "interpreter decision"
            ),
        )
        return response
    if not isinstance(audit, LatestResultRoutingAudit):
        return response
    if not audit.targets_latest_result or audit.confidence < 0.6:
        return response
    save_requested = audit.save_requested
    if not save_requested:
        save_requested = await _latest_result_save_request_audit(
            preferred_model=preferred_model,
            request=request,
        )
    reason_codes = ["latest_result_routing_audit"]
    if save_requested:
        reason_codes.append("latest_result_save_requested")
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "requires_clarification": False,
            "missing_required_fields": [],
            "assistant_response": None,
            "semantic_turn_act": "result_followup",
            "result_followup_focus": audit.focus or "general",
            "capability_question_focus": None,
            "context_question_focus": None,
            "uses_latest_result_context": True,
            "artifact_target": "latest_result",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        *reason_codes,
                    ]
                )
            ),
        }
    )


async def _latest_result_save_request_audit(
    *,
    preferred_model: str,
    request: InterpretationRequest,
) -> bool:
    try:
        audit = await invoke_openrouter_json_schema(
            task="interpretation",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Argus's latest-result save-intent audit. "
                        "Classify only whether the current user message asks to "
                        "save, keep, bookmark, store, or promote the latest "
                        "completed result artifact. Return false for explanation, "
                        "breakdown, refinement, rerun, or education requests. "
                        "If a latest result exists, messages like 'save this', "
                        "'save this result', 'keep this', 'bookmark this run', "
                        "or 'save that strategy from the result' are save requests."
                    ),
                },
                {
                    "role": "system",
                    "content": (
                        "Latest result fact bank JSON: "
                        + json.dumps(_latest_result_fact_bank_for_routing(request))
                    ),
                },
                {"role": "user", "content": request.current_user_message},
            ],
            schema_model=LatestResultSaveAudit,
            schema_name="LatestResultSaveAudit",
            model_name=preferred_model,
        )
    except Exception as exc:
        log_openrouter_failure(
            task="interpretation",
            model_name=preferred_model,
            exc=exc,
            message="Latest result save-intent audit failed; preserving routing audit",
        )
        return False
    return bool(
        isinstance(audit, LatestResultSaveAudit)
        and audit.save_requested
        and audit.confidence >= 0.6
    )


async def _audit_stated_starting_capital_fidelity(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_stated_starting_capital_recheck(
        response=response,
        request=request,
    ):
        return None
    try:
        audit = await invoke_openrouter_json_schema(
            task="field_fidelity",
            messages=_stated_starting_capital_messages(
                response=response,
                request=request,
            ),
            schema_model=StatedStartingCapitalAudit,
            schema_name="StatedStartingCapitalAudit",
        )
    except Exception:
        return None
    if not isinstance(audit, StatedStartingCapitalAudit):
        return None
    return _response_from_stated_starting_capital_audit(
        response=response,
        audit=audit,
    )


def _response_needs_stated_starting_capital_recheck(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "unsupported_request",
    }:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if _draft_has_grounded_non_dca_starting_capital(draft):
        return False
    if not _llm_strategy_draft_has_concrete_execution_target(draft):
        return False
    return _text_contains_capital_audit_signal(
        request.current_user_message,
        draft=draft,
    ) or _draft_contains_structured_capital_context(draft)


async def _early_starting_capital_rechecked_response(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if (
        _optional_runtime_readiness_audit_blocker(
            response=response,
            request=request,
        )
        != "stated_starting_capital_recheck"
    ):
        return None
    _log_runtime_readiness_step(
        "starting_capital_recheck_started",
        response=response,
    )
    repaired = await _audit_stated_starting_capital_fidelity(
        response=response,
        request=request,
    )
    if repaired is None:
        _log_runtime_readiness_step(
            "starting_capital_recheck_no_repair",
            response=response,
        )
        return None
    _log_runtime_readiness_step(
        "starting_capital_recheck_repaired",
        response=repaired,
    )
    return repaired


async def _early_focused_strategy_repaired_response(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    blocker = _optional_runtime_readiness_audit_blocker(
        response=response,
        request=request,
    )
    if blocker not in {
        "missing_required_execution_fields",
        "required_shape_missing",
        "stated_starting_capital_recheck",
    }:
        return None
    if (
        response.requires_clarification
        or response.capability_question_focus is not None
        or response.context_question_focus is not None
        or response.unsupported_constraints
        or response.ambiguous_fields
    ):
        return None
    if not _request_current_turn_has_material_execution_evidence(request):
        return None
    _log_runtime_readiness_step(
        "early_focused_strategy_repair_started",
        response=response,
    )
    repaired = await _repair_incomplete_strategy_extraction(
        failed_response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if repaired is None:
        _log_runtime_readiness_step(
            "early_focused_strategy_repair_no_repair",
            response=response,
        )
        return None
    _log_runtime_readiness_step(
        "early_focused_strategy_repaired",
        response=repaired,
    )
    return repaired


def _draft_has_grounded_non_dca_starting_capital(draft: LLMStrategyDraft) -> bool:
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if draft.capital_amount is not None:
        return True
    field_provenance = draft.field_provenance or {}
    if (
        draft.initial_capital is not None
        and _capital_source(field_provenance, "initial_capital") in _TOTAL_CAPITAL_SOURCES
    ):
        return True
    return (
        draft.total_capital is not None
        and _capital_source(field_provenance, "total_capital") in _TOTAL_CAPITAL_SOURCES
    )


def _stated_starting_capital_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's focused starting-capital verifier. The broad "
                "run-field audit may have omitted a money amount. Decide only "
                "whether the current user message explicitly states starting "
                "capital for the runnable idea. Return starting_capital as a "
                "normalized number only when the message uses the amount as the "
                "cash to test, invest, allocate, put on, or use as capital. This "
                "is language-agnostic: normalize numeric magnitude shorthand "
                "such as 100k -> 100000 and 2.5m -> 2500000 when it is the "
                "allocation amount. Include confidence; use high confidence for "
                "an exact literal amount from the current message. For example, "
                "a non-recurring buy-and-hold request that says 'con 10000 dolares' "
                "should return starting_capital 10000 with high confidence. "
                "Use structured draft prose as supporting "
                "evidence when it says an amount from the current message is "
                "starting capital but the numeric field is missing; the current "
                "user message remains authoritative. Treat draft prose that captures "
                "a user-stated starting-capital amount while capital_amount is null "
                "as a contradiction to reconcile from the current message, not as "
                "evidence that no capital was stated. A standalone numeric magnitude "
                "at the end of an otherwise complete strategy, asset, and "
                "date-window request is a starting-capital candidate when it is "
                "not serving as a date, lookback window, percentage, indicator "
                "parameter, share count, or asset identifier. Do not require a "
                "currency symbol. Return null for dates, calendar years, "
                "indicator periods, lookback windows, percentages, share counts, "
                "asset names, ticker symbols, or benchmark names. For DCA or "
                "recurring buys, do not return per-purchase contribution here. "
                "Do not copy default assumptions from the draft. If unsure, "
                "return null with low confidence. Return only JSON matching the "
                "schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Draft prose evidence JSON: "
                f"{json.dumps(_starting_capital_prose_evidence_payload(response), ensure_ascii=False)}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _starting_capital_prose_evidence_payload(
    response: LLMInterpretationResponse,
) -> dict[str, Any]:
    draft = response.candidate_strategy_draft
    return {
        "raw_user_phrasing": draft.raw_user_phrasing,
        "strategy_thesis": draft.strategy_thesis,
        "evidence_spans": draft.evidence_spans,
        "date_range_raw_text": draft.date_range_raw_text,
        "capital_amount": draft.capital_amount,
        "field_provenance": dict(draft.field_provenance or {}),
    }


def _response_from_stated_starting_capital_audit(
    *,
    response: LLMInterpretationResponse,
    audit: StatedStartingCapitalAudit,
) -> LLMInterpretationResponse | None:
    if audit.starting_capital is None or audit.confidence < 0.8:
        return None
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return None
    if draft.capital_amount == audit.starting_capital and draft.field_provenance.get(
        "capital_amount"
    ) == "starting_capital":
        return None
    draft.capital_amount = float(audit.starting_capital)
    draft.field_provenance["capital_amount"] = "starting_capital"
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "stated_run_field_fidelity_audit",
                "stated_starting_capital_recheck",
            ]
        )
    )
    return repaired


def _focused_strategy_extraction_has_material_fields(
    extraction: FocusedStrategyExtraction,
) -> bool:
    if not extraction.is_testable_strategy:
        return False
    return any(
        [
            bool(extraction.strategy_type),
            bool(extraction.asset_universe),
            bool(extraction.asset_class),
            bool(extraction.timeframe),
            bool(extraction.date_range),
            extraction.date_range_intent is not None,
            bool(extraction.comparison_baseline),
            extraction.capital_amount is not None,
            extraction.recurring_contribution is not None,
            bool(extraction.cadence),
            bool(extraction.entry_rule),
            bool(extraction.exit_rule),
            bool(extraction.rule_spec),
            bool(extraction.indicator),
            extraction.indicator_period is not None,
            extraction.entry_threshold is not None,
            extraction.exit_threshold is not None,
            bool(extraction.entry_logic),
            bool(extraction.exit_logic),
        ]
    )


def _strategy_extraction_repair_is_allowed(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> bool:
    if response.task_relation == "refine":
        return False
    if response.semantic_turn_act == "retry_failed_action":
        return not _request_has_failed_action_launch_payload(request)
    if response.semantic_turn_act == "unsupported_request":
        if _noncanonical_strategy_text_needs_focused_schema_repair(
            response=response,
            request=request,
        ):
            return True
        if response.intent not in {
            "unsupported_or_out_of_scope",
            "beginner_guidance",
            "conversation_followup",
        }:
            return False
        if not response.unsupported_constraints:
            return True
        if not any(
            item.category == "unsupported_strategy_logic"
            for item in response.unsupported_constraints
        ):
            return False
        if (
            _request_has_active_strategy_context(request)
            and not _request_current_turn_has_material_execution_evidence(request)
        ):
            return False
        return bool(
            response.candidate_strategy_draft.raw_user_phrasing
            or response.candidate_strategy_draft.strategy_thesis
            or request.current_user_message.strip()
        )
    if response.semantic_turn_act == "answer_pending_need":
        return _request_current_turn_has_material_execution_evidence(request)
    return response.semantic_turn_act not in {
        "refine_current_idea",
        "approval",
        "result_followup",
    }


async def _focused_strategy_repair_after_candidate_failures(
    *,
    request: InterpretationRequest,
    preferred_model: str,
) -> LLMInterpretationResponse | None:
    if _request_has_active_strategy_context(
        request
    ) and not _request_current_turn_has_material_execution_evidence(request):
        return None
    seed_response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=request.current_user_message,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=request.current_user_message,
            strategy_thesis=request.current_user_message,
        ),
        reason_codes=["structured_interpretation_candidates_failed"],
        semantic_turn_act="new_idea",
    )
    logger.bind(
        llm_task=_INTERPRETATION_REPAIR_TASK,
        preferred_model=preferred_model,
        current_message_length=len(request.current_user_message),
        reason_codes=list(seed_response.reason_codes),
    ).info("Structured interpretation candidates failed; attempting focused repair")
    return await _repair_incomplete_strategy_extraction(
        failed_response=seed_response,
        preferred_model=preferred_model,
        request=request,
    )


def _response_from_focused_strategy_extraction(
    *,
    extraction: FocusedStrategyExtraction,
    request: InterpretationRequest,
    base_response: LLMInterpretationResponse | None = None,
) -> LLMInterpretationResponse:
    strategy_type = executable_strategy_type_from_extracted_fields(
        extraction.model_dump(mode="python")
    )
    entry_logic = extraction.entry_logic or moving_average_crossover_text(
        extraction.entry_rule
    )
    exit_logic = extraction.exit_logic or moving_average_crossover_text(
        extraction.exit_rule
    ) or moving_average_crossover_text(
        opposite_moving_average_crossover_rule(extraction.entry_rule)
    )
    asset_universe, resolved_asset_class = _canonical_asset_universe_from_llm_extraction(
        extraction.asset_universe
    )
    if strategy_type is None:
        return LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary=extraction.user_goal_summary,
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message,
                language=extraction.language,
                strategy_thesis=extraction.strategy_thesis
                or extraction.user_goal_summary,
                asset_universe=asset_universe,
                asset_class=extraction.asset_class or resolved_asset_class,
                timeframe=extraction.timeframe,
                date_range=extraction.date_range,
                date_range_raw_text=extraction.date_range_raw_text,
                date_range_intent=extraction.date_range_intent,
                comparison_baseline=extraction.comparison_baseline,
                capital_amount=extraction.capital_amount,
                recurring_contribution=extraction.recurring_contribution,
                cadence=extraction.cadence,
                entry_logic=entry_logic,
                exit_logic=exit_logic,
                indicator=extraction.indicator,
                indicator_period=extraction.indicator_period,
                entry_threshold=extraction.entry_threshold,
                exit_threshold=extraction.exit_threshold,
                evidence_spans=dict(extraction.evidence_spans or {}),
                field_provenance=_focused_extraction_field_provenance(
                    extraction=extraction,
                    current_message=request.current_user_message,
                ),
                extra_parameters={
                    "raw_strategy_type": extraction.strategy_type,
                }
                if extraction.strategy_type
                else {},
            ),
            unsupported_constraints=[
                LLMUnsupportedConstraint(
                    category="unsupported_strategy_logic",
                    raw_value=(
                        extraction.entry_logic
                        or extraction.strategy_thesis
                        or extraction.strategy_type
                        or extraction.user_goal_summary
                    ),
                    explanation=(
                        extraction.assistant_response
                        or "This idea depends on strategy logic that is not executable yet."
                    ),
                    simplification_labels=[
                        "Use a supported RSI threshold rule",
                        "Compare with buy and hold",
                        "Use a supported moving-average crossover",
                    ],
                )
            ],
            confidence=extraction.confidence,
            reason_codes=["focused_strategy_extraction_unrecognized_contract"],
            semantic_turn_act="unsupported_request",
        )
    response = LLMInterpretationResponse(
        intent="strategy_drafting"
        if extraction.requires_clarification
        else "backtest_execution",
        task_relation="new_task",
        requires_clarification=extraction.requires_clarification,
        user_goal_summary=extraction.user_goal_summary,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=request.current_user_message,
            language=extraction.language,
            strategy_type=strategy_type,
            strategy_thesis=extraction.strategy_thesis or extraction.user_goal_summary,
            asset_universe=asset_universe,
            asset_class=extraction.asset_class or resolved_asset_class,
            timeframe=extraction.timeframe,
            date_range=extraction.date_range,
            date_range_raw_text=extraction.date_range_raw_text,
            date_range_intent=extraction.date_range_intent,
            comparison_baseline=extraction.comparison_baseline,
            capital_amount=extraction.capital_amount,
            recurring_contribution=extraction.recurring_contribution,
            cadence=extraction.cadence,
            entry_logic=entry_logic,
            exit_logic=exit_logic,
            entry_rule=extraction.entry_rule,
            exit_rule=extraction.exit_rule,
            rule_spec=extraction.rule_spec,
            indicator=extraction.indicator,
            indicator_period=extraction.indicator_period,
            entry_threshold=extraction.entry_threshold,
            exit_threshold=extraction.exit_threshold,
            evidence_spans=dict(extraction.evidence_spans or {}),
            field_provenance=_focused_extraction_field_provenance(
                extraction=extraction,
                current_message=request.current_user_message,
            ),
        ),
        missing_required_fields=list(extraction.missing_required_fields),
        assistant_response=extraction.assistant_response,
        confidence=extraction.confidence,
        reason_codes=["focused_strategy_extraction_repair"],
        semantic_turn_act="new_idea",
    )
    response.missing_required_fields = (
        _capability_required_missing_fields_for_canonical_strategy(
            response.missing_required_fields,
            draft=response.candidate_strategy_draft,
        )
    )
    if response.missing_required_fields or response.ambiguous_fields:
        response.intent = "strategy_drafting"
        response.requires_clarification = True
        response.assistant_response = None
    return _merge_focused_repair_with_base(
        response=response,
        base_response=base_response,
    )


def _canonical_asset_universe_from_llm_extraction(
    values: list[str],
) -> tuple[list[str], str | None]:
    symbols: list[str] = []
    seen: set[str] = set()
    asset_classes: set[str] = set()
    for index, value in enumerate(values):
        raw_text = str(value or "").strip()
        if not raw_text:
            continue
        symbol = ""
        try:
            resolution = _resolve_asset_candidate(
                raw_text,
                field=f"asset_universe[{index}]",
                source="llm_extraction",
            )
        except Exception:
            resolution = None
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset is not None
        ):
            symbol = str(resolution.asset.canonical_symbol or "").upper()
            asset_class = str(resolution.asset.asset_class or "").strip()
            if asset_class:
                asset_classes.add(asset_class)
        if not symbol:
            symbol = raw_text.upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    resolved_asset_class = next(iter(asset_classes)) if len(asset_classes) == 1 else None
    return symbols, resolved_asset_class


def _structured_interpretation_has_required_shape(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> bool:
    if response.intent == "results_explanation" and not _request_has_latest_result(
        request
    ):
        return False
    if (
        response.semantic_turn_act in {"answer_pending_need", "approval"}
        and not _request_has_active_strategy_context(request)
        and not _llm_strategy_draft_has_extractable_fields(
            response.candidate_strategy_draft
        )
    ):
        return False
    if (
        response.intent == "unsupported_or_out_of_scope"
        and response.requires_clarification
        and not response.unsupported_constraints
        and not _llm_strategy_draft_has_extractable_fields(
            response.candidate_strategy_draft
        )
    ):
        return bool(response.assistant_response)
    if _response_underfills_pending_result_refinement(
        response=response,
        request=request,
    ):
        return False
    if response.semantic_turn_act == "retry_failed_action":
        return _request_has_failed_action_launch_payload(request)
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return True
    if response.semantic_turn_act == "approval":
        return True
    if _response_underfills_active_artifact_assumption_edit(
        response=response,
        request=request,
    ):
        return False
    if _response_underfills_active_artifact_rule_edit(
        response=response,
        request=request,
    ):
        return False
    if response.requires_clarification and response.assistant_response:
        if _supported_anchor_needs_focused_run_window_repair(
            response=response,
            request=request,
        ):
            return False
        if _supported_partial_strategy_needs_focused_schema_repair(
            response=response,
            request=request,
        ):
            return False
        if _noncanonical_strategy_text_needs_focused_schema_repair(
            response=response,
            request=request,
        ):
            return False
        return True
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_extractable_fields(draft):
        if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
            missing = _capability_required_missing_fields_for_canonical_strategy(
                response.missing_required_fields,
                draft=draft,
            )
            if missing:
                if _structured_strategy_missing_fields_can_clarify(
                    response=response,
                    draft=draft,
                    missing=missing,
                ):
                    return True
                return False
        if _llm_signal_strategy_is_underfilled(draft):
            return False
        if _response_replays_prior_strategy_without_current_turn_update(
            response=response,
            request=request,
        ):
            return False
        return True
    if response.task_relation == "refine" or response.semantic_turn_act in {
        "refine_current_idea",
        "answer_pending_need",
    }:
        return False
    return False


def _normalize_response_for_runtime_context(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if _request_has_latest_result(request):
        return response
    if (
        response.intent in {"strategy_drafting", "backtest_execution"}
        and response.semantic_turn_act is None
        and not _request_has_active_strategy_context(request)
        and (
            _llm_strategy_draft_has_extractable_fields(
                response.candidate_strategy_draft
            )
            or _request_current_turn_has_material_execution_evidence(request)
        )
    ):
        response = response.model_copy(
            update={
                "semantic_turn_act": "new_idea",
                "reason_codes": list(
                    dict.fromkeys(
                        [
                            *response.reason_codes,
                            "coerced_missing_turn_act_to_new_idea",
                        ]
                    )
                ),
            }
        )
    if response.intent != "results_explanation":
        return response
    if (
        response.semantic_turn_act == "result_followup"
        and response.result_followup_focus == "assumptions"
        and _request_has_active_strategy_context(request)
    ):
        return response.model_copy(
            update={
                "intent": "conversation_followup",
                "assistant_response": None,
                "uses_latest_result_context": False,
                "reason_codes": [
                    *response.reason_codes,
                    "routed_pending_artifact_assumptions_followup",
                ],
            }
        )
    if response.semantic_turn_act == "educational_question":
        return response.model_copy(
            update={
                "intent": "conversation_followup",
                "uses_latest_result_context": False,
                "reason_codes": [
                    *response.reason_codes,
                    "coerced_result_explanation_without_result_context",
                ],
            }
        )
    if not _llm_strategy_draft_has_extractable_fields(response.candidate_strategy_draft):
        return response
    semantic_turn_act = response.semantic_turn_act
    if semantic_turn_act not in {
        "new_idea",
        "refine_current_idea",
        "answer_pending_need",
    }:
        semantic_turn_act = "new_idea"
    return response.model_copy(
        update={
            "intent": "strategy_drafting",
            "semantic_turn_act": semantic_turn_act,
            "assistant_response": None,
            "uses_latest_result_context": False,
            "reason_codes": [
                *response.reason_codes,
                "coerced_result_explanation_to_strategy_draft",
            ],
        }
    )


def _request_current_turn_has_material_execution_evidence(
    request: InterpretationRequest,
) -> bool:
    return current_turn_has_material_execution_evidence(
        request.current_user_message,
        has_provider_asset_mention=bool(
            _resolved_asset_mentions_from_message(request.current_user_message)
        )
        or _request_has_provider_exact_execution_asset(request),
        active_strategy_context=_request_has_active_strategy_context(request),
        requested_field=request.selected_thread_metadata.get("requested_field"),
    )


def _validate_capability_boundaries(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> None:
    symbols = list(strategy.asset_universe)
    canonical_symbols: list[str] = []
    asset_classes = set()
    invalid_symbols: list[str] = []
    field_owned_indicator_symbols: list[str] = []
    resolution_provenance = []
    for index, symbol in enumerate(symbols):
        if _field_owned_indicator_asset_candidate(
            strategy=strategy,
            symbol=symbol,
            request=request,
        ):
            field_owned_indicator_symbols.append(symbol)
            continue
        resolution = _resolve_asset_candidate(
            symbol,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
        resolution_provenance.append(resolution.provenance)
        if resolution.status == "ambiguous":
            response.ambiguous_fields.append(
                LLMAmbiguousField(
                    field_name=f"asset_universe[{index}]",
                    raw_value=symbol,
                    candidate_normalized_value=None,
                    reason_code="asset_resolution_ambiguous",
                )
            )
            continue
        if resolution.status != "resolved" or resolution.asset is None:
            invalid_symbols.append(symbol)
            continue
        canonical_symbols.append(resolution.asset.canonical_symbol)
        asset_classes.add(resolution.asset.asset_class)
    strategy.asset_universe = list(dict.fromkeys(canonical_symbols))
    if field_owned_indicator_symbols and (
        "field_owned_indicator_asset_token_removed" not in response.reason_codes
    ):
        response.reason_codes.append("field_owned_indicator_asset_token_removed")
    strategy.resolution_provenance = _dedupe_resolution_provenance(
        [*strategy.resolution_provenance, *resolution_provenance]
    )
    if len(asset_classes) == 1:
        strategy.asset_class = next(iter(asset_classes))
    elif len(asset_classes) > 1:
        strategy.asset_class = "mixed"
        if not any(
            item.category == "unsupported_asset_mix"
            for item in response.unsupported_constraints
        ):
            response.unsupported_constraints.append(
                LLMUnsupportedConstraint(
                    category="unsupported_asset_mix",
                    raw_value=", ".join(symbols),
                    explanation=(
                        "Argus Alpha cannot run equity, crypto, and currency pairs "
                        "together in one simulation yet."
                    ),
                    simplification_labels=[
                        "Run one asset class at a time",
                        "Run the equity symbols only",
                        "Run the crypto or currency pair symbols only",
                    ],
                )
            )
    if invalid_symbols and not any(
        item.category == "unsupported_symbol" for item in response.unsupported_constraints
    ):
        response.unsupported_constraints.append(
            LLMUnsupportedConstraint(
                category="unsupported_symbol",
                raw_value=", ".join(invalid_symbols),
                explanation=(
                    "I understood the symbol, but I could not verify it in the "
                    "supported market data universe for this run."
                ),
                simplification_labels=["Use a supported stock or crypto symbol"],
            )
        )
    _validate_indicator_rule_support(strategy=strategy, response=response)
    canonical_type = executable_strategy_type(strategy)
    if canonical_type in {"buy_and_hold", "dca_accumulation"}:
        strategy.strategy_type = canonical_type
        strategy.entry_logic = None
        strategy.exit_logic = None
        _remove_unstated_model_defaults(strategy)
    if canonical_type == "indicator_threshold":
        strategy.strategy_type = canonical_type
        _apply_executable_indicator_defaults(strategy)
    if canonical_type == "signal_strategy":
        strategy.strategy_type = canonical_type
        _apply_signal_strategy_defaults(strategy)
    if (
        canonical_type == "dca_accumulation"
        and strategy.capital_amount is not None
        and not _dca_amount_has_user_provenance(strategy=strategy, request=request)
    ):
        strategy.capital_amount = None
        strategy.sizing_mode = None
    if (
        canonical_type == "dca_accumulation"
        and strategy.cadence not in (None, "", [], {})
        and not _dca_cadence_has_user_provenance(strategy=strategy, request=request)
    ):
        ungrounded_cadence = str(strategy.cadence).casefold()
        strategy.cadence = None
        strategy.assumptions = [
            assumption
            for assumption in strategy.assumptions
            if ungrounded_cadence not in str(assumption).casefold()
        ]
    if canonical_type == "dca_accumulation":
        _ensure_dca_missing_execution_fields(strategy=strategy, response=response)
    _remove_stale_indicator_constraints(
        response=response,
        strategy=strategy,
        current_message=request.current_user_message,
    )


def _resolve_asset_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    if resolve_asset is _DEFAULT_RESOLVE_ASSET:
        return runtime_resolve_asset_candidate(query, field=field, source=source)
    resolved = resolve_asset(query)
    provenance = ResolutionProvenance(
        field=field,
        raw_text=query,
        source=source,
        candidate_kind="asset",
        resolution_status="resolved",
        canonical_symbol=resolved.canonical_symbol,
        asset_class=resolved.asset_class,
        validated_by="provider_catalog",
        confidence="high",
    )
    return AssetResolution(
        status="resolved",
        raw_text=query,
        asset=resolved,
        candidates=(resolved,),
        provenance=provenance,
    )


