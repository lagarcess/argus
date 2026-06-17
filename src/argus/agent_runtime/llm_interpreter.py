from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, Field

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    plan_artifact_assumption_edit,
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
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.result_followups import result_followup_fact_bank
from argus.agent_runtime.rule_specs import (
    executable_rule_spec_from_strategy,
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.run_field_contract import (
    current_message_execution_context_tokens,
)
from argus.agent_runtime.run_field_contract import (
    field_fidelity_tokens as _field_fidelity_tokens,
)
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
    audit_signal_rule_grounding,
    repair_signal_rule_plan,
)
from argus.agent_runtime.stages.artifact_context import (
    launch_payload_from_failed_action,
)
from argus.agent_runtime.stages.interpret_types import (
    CapabilityQuestionFocus,
    ContextQuestionFocus,
    InterpretationRequest,
    ResultFollowupFocus,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ResolutionProvenance,
    ResolutionSource,
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
    dedupe_resolution_provenance_items,
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
from argus.domain.backtesting.rules import (
    canonicalize_rule_spec,
    describe_rule_spec,
)
from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import is_ticker_like_query, resolve_asset
from argus.domain.slot_normalizer import normalize_parameter_value
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
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
    dateparser_languages_for_user_language,
    resolve_date_range_intent,
    resolve_date_range_text,
    resolve_rolling_window_intent_text,
)

_DEFAULT_RESOLVE_ASSET = resolve_asset
_INTERPRETATION_REPAIR_TASK: OpenRouterTask = "interpretation_repair"
_DATE_EVIDENCE_SPAN_KEYS = (
    "date_range",
    "date_range_raw_text",
    "date_range_intent",
    "date_window",
    "period",
    "temporal_window",
    "time_window",
    "window",
)
_COMPARISON_BASELINE_EVIDENCE_KEYS = (
    "baseline",
    "benchmark",
    "comparison_baseline",
    "comparison_baseline_evidence",
    "comparison_target",
    "reference",
)


def _field_path_base(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for separator in ("[", "."):
        text = text.split(separator, 1)[0]
    return text.strip()


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


class CapabilitySideQuestionAudit(BaseModel):
    is_capability_question: bool = Field(
        description=(
            "True only when the current user message is asking what Argus supports, "
            "what it can run, what a supported concept means, or what limits apply."
        )
    )
    focus: CapabilityQuestionFocus | None = Field(
        default=None,
        description=(
            "Capability focus when is_capability_question is true. Use "
            "supported_indicators, supported_strategies, limits, assets, or general."
        ),
    )
    assistant_response: str | None = Field(
        default=None,
        description=(
            "Optional warm answer. Leave null when runtime should compose from the "
            "capability contract."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextQuestionAudit(BaseModel):
    is_context_question: bool = Field(
        description=(
            "True only when the current user message asks for broad market, macro, "
            "corporate-event, or movers context rather than supplying executable "
            "strategy details."
        )
    )
    focus: ContextQuestionFocus | None = Field(
        default=None,
        description=(
            "Context focus when is_context_question is true. Use macro_context, "
            "corporate_events, or market_movers."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AssetGroundingAudit(BaseModel):
    grounded_symbols: list[str] = Field(
        default_factory=list,
        description=(
            "Subset of the extracted symbols that the current user message clearly "
            "intended as assets. Use the symbols exactly as provided in the audit prompt."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AssetAnswerCandidateAudit(BaseModel):
    candidate_symbols: list[str] = Field(
        default_factory=list,
        description=(
            "One to three likely public market symbols for the current asset answer, "
            "normalized as tickers or crypto symbols. A common public-company or "
            "public-asset name is a valid answer even when the user did not type the "
            "ticker. Return likely candidates in preference order when the answer is "
            "recognizable. Leave empty only when there is no credible candidate, the "
            "answer is unsupported, or the answer is not an asset answer."
        ),
    )
    needs_clarification: bool = Field(
        default=False,
        description=(
            "True when multiple plausible assets remain and the user should choose "
            "instead of the runtime guessing. If candidate_symbols is non-empty, "
            "the runtime will still validate those candidates in order before "
            "falling back to clarification."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StrategyFamilyContinuityAudit(BaseModel):
    should_rebind_strategy_family: bool = Field(
        description=(
            "True only when the user is continuing a specific visible strategy-family "
            "setup from recent conversation and the primary interpretation chose the "
            "wrong executable family."
        )
    )
    strategy_type: str | None = Field(
        default=None,
        description=(
            "Executable strategy family to use when rebinding is needed. Use one of "
            "buy_and_hold, dca_accumulation, indicator_threshold, or signal_strategy."
        ),
    )
    total_budget_not_recurring: bool = Field(
        default=False,
        description=(
            "True when a money amount in the current interpretation is a total budget, "
            "starting principal, or cap rather than a recurring DCA contribution."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DcaContributionRoleAudit(BaseModel):
    recurring_contribution_explicit: bool = Field(
        description=(
            "True only when the current user message clearly states the money amount "
            "as the amount invested on each recurring DCA purchase."
        )
    )
    total_budget_not_recurring: bool = Field(
        description=(
            "True when the money amount is a total budget, starting capital, or "
            "capital available across the whole DCA plan rather than each purchase."
        )
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DcaContractAudit(BaseModel):
    is_recurring_buy_request: bool = Field(
        description=(
            "True only when the current user message is asking for a DCA or "
            "recurring fixed-dollar buy backtest."
        )
    )
    recurring_contribution_amount: float | None = Field(
        default=None,
        description=(
            "The per-purchase contribution explicitly stated by the user. Leave "
            "null when the message only states total budget, starting principal, "
            "or cap."
        ),
    )
    cadence: str | None = Field(
        default=None,
        description=(
            "User-stated recurring cadence normalized to one allowed DCA cadence "
            "such as daily, weekly, biweekly, monthly, or quarterly. Leave null "
            "when absent."
        ),
    )
    total_budget_amount: float | None = Field(
        default=None,
        description=(
            "Optional total budget, starting principal, or contribution cap stated "
            "for the whole DCA plan. Do not use this as the recurring contribution."
        ),
    )
    total_budget_source: str | None = Field(
        default=None,
        description=(
            "Semantic role for total_budget_amount, for example cap, max_budget, "
            "total_budget, starting_capital, or initial_capital."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PendingResponseOptionSelectionAudit(BaseModel):
    is_selection: bool = Field(
        description=(
            "True when the current user message semantically selects one of the "
            "pending response-intent options."
        )
    )
    selected_option_index: int | None = Field(
        default=None,
        description=(
            "Zero-based index of the selected option from the provided option list. "
            "Leave null when no option is selected."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StatedRunFieldFidelityAudit(BaseModel):
    capital_amount: float | None = Field(
        default=None,
        description=(
            "Starting capital explicitly stated by the current user message, "
            "normalized as a number. Examples: 10k -> 10000, $500 -> 500, "
            "100k -> 100000, 100000 -> 100000 when the message uses that "
            "plain number or shorthand as the amount to test or invest. "
            "Leave null when the user did not state starting capital. Do not "
            "treat dates, indicator windows, percentages, or asset names as "
            "capital. For DCA or recurring buys, do not put the per-purchase "
            "contribution here; use recurring_contribution_amount."
        ),
    )
    recurring_contribution_amount: float | None = Field(
        default=None,
        description=(
            "For DCA or recurring-buy requests only: the amount explicitly stated "
            "as each recurring purchase contribution, normalized as a number. "
            "Leave null when the current user message gives only a total budget, "
            "starting principal, cap, or no per-purchase contribution."
        ),
    )
    cadence: str | None = Field(
        default=None,
        description=(
            "For DCA or recurring-buy requests only: user-stated cadence normalized "
            "to daily, weekly, biweekly, monthly, or quarterly. Leave null when "
            "the current user message did not state cadence."
        ),
    )
    timeframe: str | None = Field(
        default=None,
        description=(
            "User-stated bar interval, normalized to 1h, 4h, or 1D when present. "
            "Leave null when the user did not state a timeframe."
        ),
    )
    date_range: str | dict[str, str] | None = Field(
        default=None,
        description=(
            "User-stated date range. Preserve today/current as today or the runtime "
            "date only when the user stated it. If the user stated only one endpoint, "
            "return only that endpoint. Leave null when the user did not state a date "
            "range."
        ),
    )
    comparison_baseline: str | None = Field(
        default=None,
        description=(
            "Benchmark or comparison asset explicitly stated by the current user "
            "message. This is language-agnostic: if the current message states "
            "an asset as a benchmark, reference, baseline, against/versus target, "
            "or comparison target, return that asset here. Leave null when the "
            "user did not state one."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class StatedStartingCapitalAudit(BaseModel):
    starting_capital: float | None = Field(
        default=None,
        description=(
            "Starting capital explicitly stated by the current user message, "
            "normalized as a number. Return null when the current message does "
            "not state starting capital. Preserve plain numeric allocation "
            "amounts in any language when they are used as the amount to test, "
            "invest, allocate, put on, or use as capital."
        ),
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the starting_capital extraction. Use high confidence "
            "for an exact current-message amount; leave the default acceptable "
            "confidence when starting_capital is directly present but no separate "
            "confidence value is needed."
        ),
    )


class SupportedStrategyCapabilityConflictAudit(BaseModel):
    selected_strategy_type: str | None = Field(
        default=None,
        description=(
            "Canonical executable strategy family when the current user message "
            "semantically selects a supported Alpha strategy. Use buy_and_hold or "
            "dca_accumulation only when the message itself supports that choice. "
            "Leave null when the request contains unsupported custom logic or "
            "does not clearly select a supported strategy."
        ),
    )
    drop_unsupported_strategy_logic: bool = Field(
        description=(
            "True only when the unsupported_strategy_logic constraint is a model "
            "contradiction because the current user message asks for a supported "
            "buy_and_hold or dca_accumulation run without any extra unsupported "
            "entry, exit, fundamental, sentiment, event, custom scripting, or "
            "brokerage/trading rule."
        ),
    )
    keep_unsupported_strategy_logic: bool = Field(
        description=(
            "True when the current user message includes an extra unsupported "
            "strategy rule or condition beyond the supported canonical strategy."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ExecutableStrategyGroundingAudit(BaseModel):
    outcome: str = Field(
        description="grounded when the executable draft faithfully matches the user message; otherwise needs_clarification."
    )
    assistant_response: str | None = Field(
        default=None,
        description="Warm clarification to show the user when the draft was over-simplified.",
    )
    missing_required_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LatestResultRoutingAudit(BaseModel):
    targets_latest_result: bool = Field(
        description=(
            "True when the current user message should be answered from the "
            "latest completed result artifact instead of general capability copy."
        )
    )
    save_requested: bool = Field(
        default=False,
        description=(
            "True when the user is asking to save, keep, bookmark, or promote "
            "the latest completed result artifact."
        ),
    )
    focus: ResultFollowupFocus | None = Field(
        default=None,
        description=(
            "Closest result follow-up focus when targets_latest_result is true."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LatestResultSaveAudit(BaseModel):
    save_requested: bool = Field(
        description=(
            "True only when the user is asking to save, keep, bookmark, or "
            "promote the latest completed result artifact."
        )
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


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
        )
        if repaired_response is not None:
            self.last_status = "fallback_used"
            return self._to_runtime_interpretation(repaired_response, request=request)
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


def _artifact_target_from_response(
    response: LLMInterpretationResponse,
) -> str | None:
    if response.artifact_target is not None:
        return response.artifact_target
    if response.uses_latest_result_context is True:
        return "latest_result"
    if response.uses_latest_result_context is False:
        return "none"
    return None


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


def _provider_exact_ticker_supports_extracted_symbol(
    symbol: str,
    *,
    provider_ticker_symbol_map: dict[str, Any],
) -> bool:
    asset = provider_ticker_symbol_map.get(symbol)
    if asset is None:
        return False
    asset_class = str(getattr(asset, "asset_class", "") or "").strip()
    return asset_class in {"crypto", "currency_pair"} and len(symbol) >= 3


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


def _normalized_extracted_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def _normalized_extracted_symbols(values: list[Any]) -> set[str]:
    symbols: set[str] = set()
    for value in values:
        symbol = _normalized_extracted_symbol(value)
        if symbol is not None:
            symbols.add(symbol)
    return symbols


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


def _comparison_baseline_has_trusted_provenance(draft: LLMStrategyDraft) -> bool:
    provenance = draft.field_provenance or {}
    return provenance.get("comparison_baseline") in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }


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


def _context_inheritable_asset_symbols(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    current_grounded_symbols: set[str],
) -> set[str]:
    if (
        response.semantic_turn_act == "answer_pending_need"
        and _selected_requested_field_base(request) != "asset_universe"
    ):
        return _prior_strategy_symbols(request)
    if current_grounded_symbols:
        return set()
    if response.semantic_turn_act not in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
    }:
        return set()
    return _prior_strategy_symbols(request)


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


def _selected_requested_field_base(request: InterpretationRequest) -> str:
    return _field_path_base(request.selected_thread_metadata.get("requested_field"))


def _prior_strategy_symbols(request: InterpretationRequest) -> set[str]:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return set()
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return set()
    return {
        str(symbol).strip().upper()
        for symbol in prior.asset_universe
        if str(symbol).strip()
    }


def _requested_asset_answer_candidate_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    prior = None
    snapshot = request.latest_task_snapshot
    if snapshot is not None:
        prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    interpretation_context = response.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"assistant_response", "user_goal_summary"},
    )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's asset-answer candidate audit. The user is answering "
                "a visible request to change the asset in an existing strategy draft. "
                "Use semantic meaning and common public-market knowledge to propose "
                "likely listed symbols for the current answer only. The current answer "
                "does not need to be a ticker; a well-known public company, fund, crypto "
                "asset, or currency-pair name can be mapped to likely symbols. Provider "
                "validation will verify your candidates afterward. The primary "
                "interpretation may have rejected the answer without the pending-field "
                "context; do not copy that classification. Do not preserve the prior "
                "asset unless the current answer explicitly asks for it. Do not invent "
                "support for private companies, themes, sectors, or vague references. "
                "If a common public asset maps to multiple listed share classes or "
                "similar instruments, return likely symbols in preference order so "
                "provider validation can check them. Return an empty list only when "
                "there is no credible ordering, the answer is unsupported, or it is "
                "not an asset."
            ),
        },
        {
            "role": "system",
            "content": (
                "Prior strategy JSON, if any: "
                f"{prior.model_dump(mode='json') if prior else 'none'}"
            ),
        },
        {
            "role": "system",
            "content": f"Current asset answer: {request.current_user_message.strip()}",
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation context without assistant prose: "
                f"{interpretation_context}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


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


def _response_needs_strategy_family_continuity_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.capability_question_focus is not None:
        return False
    if response.artifact_target == "latest_result":
        return False
    if response.semantic_turn_act in {
        "approval",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.task_relation == "refine":
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if not request.recent_thread_history:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return False
    return bool(
        draft.asset_universe
        or draft.date_range
        or draft.capital_amount is not None
        or draft.total_capital is not None
        or draft.initial_capital is not None
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


def _response_from_dca_contract_audit(
    *,
    response: LLMInterpretationResponse,
    audit: Any,
) -> LLMInterpretationResponse | None:
    if (
        not isinstance(audit, DcaContractAudit)
        or not audit.is_recurring_buy_request
        or audit.confidence < 0.7
    ):
        return None
    cadence = _supported_dca_cadence_value(audit.cadence)
    recurring_amount = audit.recurring_contribution_amount
    if cadence is None or recurring_amount is None or recurring_amount <= 0:
        return None

    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft.strategy_type = "dca_accumulation"
    draft.capital_amount = float(recurring_amount)
    draft.recurring_contribution = float(recurring_amount)
    draft.cadence = cadence
    draft.sizing_mode = "capital_amount"

    field_provenance = dict(draft.field_provenance or {})
    field_provenance["capital_amount"] = "recurring_contribution"
    field_provenance["recurring_contribution"] = "recurring_contribution"

    extra_parameters = dict(draft.extra_parameters or {})
    extra_parameters["recurring_contribution"] = float(recurring_amount)
    extra_parameters["recurring_cadence"] = cadence

    if audit.total_budget_amount is not None and audit.total_budget_amount > 0:
        budget_source = _dca_total_budget_source(audit.total_budget_source)
        draft.total_capital = float(audit.total_budget_amount)
        field_provenance["total_capital"] = budget_source
        extra_parameters["total_budget"] = float(audit.total_budget_amount)

    draft.field_provenance = field_provenance
    draft.extra_parameters = extra_parameters

    missing_required_fields = _dca_contract_missing_fields(
        response.missing_required_fields,
        draft=draft,
    )
    return response.model_copy(
        update={
            "intent": "strategy_drafting"
            if missing_required_fields
            else "backtest_execution",
            "task_relation": "new_task",
            "requires_clarification": bool(missing_required_fields),
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing_required_fields,
            "assistant_response": None,
            "semantic_turn_act": "new_idea",
            "capability_question_focus": None,
            "artifact_target": "none",
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys([*response.reason_codes, "dca_contract_audit"])
            ),
        }
    )


def _dca_contract_missing_fields(
    current_missing: list[str],
    *,
    draft: LLMStrategyDraft,
) -> list[str]:
    stale_rule_fields = {"entry_logic", "exit_logic", "strategy_type"}
    missing = [
        field
        for field in current_missing
        if _field_path_base(field) not in stale_rule_fields
    ]
    if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
        draft.date_range
    ):
        resolved_date_range = _date_range_from_intent_or_bounded_evidence(draft)
        if resolved_date_range is not None:
            draft.date_range = resolved_date_range
    present_fields: set[str] = set()
    if draft.asset_universe:
        present_fields.add("asset_universe")
    if draft.date_range not in (None, "", [], {}):
        present_fields.add("date_range")
    if _dca_draft_has_recurring_amount(draft):
        present_fields.add("capital_amount")
    if draft.cadence not in (None, "", [], {}):
        present_fields.add("cadence")
    required_fields = ["asset_universe", "date_range", "capital_amount", "cadence"]
    missing = list(dict.fromkeys([*missing, *required_fields]))
    return [
        field
        for field in missing
        if _field_path_base(field) not in present_fields
    ]


def _capability_required_missing_fields_for_canonical_strategy(
    current_missing: list[str],
    *,
    draft: LLMStrategyDraft,
) -> list[str]:
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type == "buy_and_hold":
        if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
            draft.date_range
        ):
            resolved_date_range = _date_range_from_intent_or_bounded_evidence(draft)
            if resolved_date_range is not None:
                draft.date_range = resolved_date_range
        missing: list[str] = []
        if not draft.asset_universe:
            missing.append("asset_universe")
        if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
            draft.date_range
        ):
            missing.append("date_range")
        return missing
    if strategy_type == "dca_accumulation":
        return _dca_contract_missing_fields(current_missing, draft=draft)
    return list(current_missing)


def _supported_dca_cadence_value(value: Any) -> str | None:
    normalized_value = normalize_parameter_value(
        "dca_accumulation",
        "dca_cadence",
        value,
    )
    normalized = str(normalized_value or "").strip().casefold()
    if not normalized:
        return None
    capability = STRATEGY_CAPABILITIES.get("dca_accumulation")
    cadence_spec = capability.parameters.get("dca_cadence") if capability else None
    if cadence_spec is None:
        return None
    for allowed in cadence_spec.allowed_values:
        candidate = str(allowed).strip().casefold()
        if normalized == candidate:
            return candidate
    return None


def _dca_draft_has_recurring_amount(draft: LLMStrategyDraft) -> bool:
    if draft.recurring_contribution is not None:
        return True
    if draft.capital_amount is None:
        return False
    return _capital_source(draft.field_provenance, "capital_amount") in {
        "recurring_contribution",
        "explicit_recurring_contribution",
    }


def _dca_total_budget_source(value: Any) -> str:
    source = str(value or "").strip().casefold()
    if source in _TOTAL_CAPITAL_SOURCES:
        return source
    return "total_budget"


def _dca_contract_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's DCA contract audit. The primary interpreter may "
                "have misclassified a supported recurring-buy request as unsupported "
                "or may have mixed up recurring contribution and total budget/cap. "
                "Use semantic meaning, not keywords. Return true only when the "
                "current user message asks for a fixed contribution on a recurring "
                "cadence. The per-purchase amount belongs in "
                "recurring_contribution_amount. A total budget, starting principal, "
                "or cap belongs in total_budget_amount and must not replace the "
                "recurring contribution. Do not infer missing contribution or "
                "cadence. Provider and capability validation will run after this "
                "audit; return only JSON matching the schema."
            ),
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


def _response_needs_dca_contribution_role_audit(
    response: LLMInterpretationResponse,
) -> bool:
    if "pending_response_option_selected" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    return (
        canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
        and draft.capital_amount is not None
        and response.semantic_turn_act not in {
            "approval",
            "result_followup",
            "retry_failed_action",
        }
    )


def _dca_contribution_role_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's DCA money-role audit. Decide whether the money "
                "amount in the current user message is the recurring contribution "
                "for each DCA purchase, or a total budget/capital amount for the "
                "whole plan. Use semantic meaning, not keywords. A recurring "
                "contribution is explicit only when the user clearly ties the amount "
                "to each recurring purchase. If the amount is merely available "
                "capital, a budget, a starting principal, or an amount spread over "
                "the date range, mark total_budget_not_recurring true. If ambiguous, "
                "do not treat it as a recurring contribution."
            ),
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


def _strategy_family_continuity_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    recent_history = [
        item.model_dump(mode="json")
        for item in request.recent_thread_history[-6:]
        if hasattr(item, "role") and hasattr(item, "content")
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's strategy-family continuity audit. Decide whether "
                "the current user message is answering a visible recent setup offer "
                "for a specific executable strategy family, and whether the primary "
                "interpretation chose the wrong family. Use semantic meaning from "
                "the recent visible conversation, not keywords. Do not infer from "
                "hidden state. Return false when the user is starting a standalone "
                "idea, explicitly asked for buy-and-hold, switched to another "
                "strategy, asked a capability question, or is talking about a result. "
                "If a prior assistant turn offered a recurring-buy/DCA setup and "
                "the current user supplies asset, date, or budget facts to continue "
                "that setup, return dca_accumulation. For DCA, mark "
                "total_budget_not_recurring true when the stated money is a total "
                "budget, starting principal, or cap instead of a per-purchase "
                "recurring contribution."
            ),
        },
        {
            "role": "system",
            "content": f"Recent visible conversation: {recent_history}",
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


def _move_dca_total_budget_out_of_recurring_amount(
    draft: LLMStrategyDraft,
) -> None:
    if draft.capital_amount is None:
        return
    total_budget = draft.total_capital or draft.initial_capital or draft.capital_amount
    draft.total_capital = total_budget
    draft.capital_amount = None
    draft.sizing_mode = None
    field_provenance = dict(draft.field_provenance or {})
    field_provenance.pop("capital_amount", None)
    field_provenance["total_capital"] = "total_budget"
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    extra_parameters["total_budget"] = total_budget
    draft.extra_parameters = extra_parameters


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
    if resolve_date_range_intent(draft.date_range_intent) is not None:
        return False
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
    if _draft_has_semantic_date_window_evidence(draft):
        return False
    if resolve_date_range_intent(draft.date_range_intent) is not None:
        return False
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


def _draft_has_semantic_date_window_evidence(draft: LLMStrategyDraft) -> bool:
    if not _llm_value_is_empty(draft.date_range_raw_text):
        return True
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return any(
        not _llm_value_is_empty(evidence_spans.get(key))
        for key in _DATE_EVIDENCE_SPAN_KEYS
    )


def _draft_has_comparison_baseline_evidence(draft: LLMStrategyDraft) -> bool:
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return any(
        not _llm_value_is_empty(evidence_spans.get(key))
        for key in _COMPARISON_BASELINE_EVIDENCE_KEYS
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


def _draft_semantic_evidence_spans(draft: LLMStrategyDraft) -> dict[str, str]:
    evidence_spans: dict[str, str] = {
        str(key): str(value)
        for key, value in (draft.evidence_spans or {}).items()
        if not _llm_value_is_empty(value)
    }
    extra_evidence_spans = (draft.extra_parameters or {}).get("evidence_spans")
    if isinstance(extra_evidence_spans, Mapping):
        for key, value in extra_evidence_spans.items():
            normalized_key = str(key)
            if normalized_key not in evidence_spans and not _llm_value_is_empty(value):
                evidence_spans[normalized_key] = str(value)
    return evidence_spans


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
) -> LLMInterpretationResponse | None:
    if not _request_targets_pending_artifact_assumption_edit(request):
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
    )
    if plan is None:
        return None
    return _response_from_artifact_assumption_edit_plan(plan=plan, request=request)


def _request_targets_pending_artifact_assumption_edit(
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field != "assumption":
        return False
    snapshot = request.latest_task_snapshot
    return bool(
        snapshot
        and (
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or snapshot.active_confirmation_reference
        )
    )


def _response_from_artifact_assumption_edit_plan(
    *,
    plan: ArtifactAssumptionEditPlan,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    draft = LLMStrategyDraft(raw_user_phrasing=request.current_user_message)
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    if plan.initial_capital is not None:
        draft.capital_amount = plan.initial_capital
        field_provenance["capital_amount"] = "starting_capital"
    if plan.recurring_contribution_amount is not None:
        recurring_amount = float(plan.recurring_contribution_amount)
        draft.capital_amount = recurring_amount
        draft.recurring_contribution = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
        field_provenance["recurring_contribution"] = "recurring_contribution"
        extra_parameters["recurring_contribution"] = recurring_amount
    if plan.cadence is not None:
        cadence = _supported_dca_cadence_value(plan.cadence)
        if cadence is not None:
            draft.cadence = cadence
            field_provenance["cadence"] = "explicit_user"
            extra_parameters["recurring_cadence"] = cadence
    if plan.timeframe is not None:
        draft.timeframe = plan.timeframe
    if plan.fee_rate is not None:
        extra_parameters["fee_rate"] = plan.fee_rate
    if plan.slippage is not None:
        extra_parameters["slippage"] = plan.slippage
    if extra_parameters:
        draft.extra_parameters.update(extra_parameters)
    if field_provenance:
        draft.field_provenance = field_provenance

    if plan.outcome == "ready_to_confirm":
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary=(
                plan.user_goal_summary or "User changed a visible confirmation assumption."
            ),
            candidate_strategy_draft=draft,
            confidence=plan.confidence,
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
        )

    return LLMInterpretationResponse(
        intent=(
            "unsupported_or_out_of_scope"
            if plan.outcome == "unsupported"
            else "conversation_followup"
        ),
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary=(
            plan.user_goal_summary
            or "The requested assumption change needs clarification."
        ),
        candidate_strategy_draft=draft,
        missing_required_fields=list(plan.missing_required_fields),
        assistant_response=plan.assistant_response,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act=(
            "unsupported_request"
            if plan.outcome == "unsupported"
            else "answer_pending_need"
        ),
    )


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


def _response_needs_supported_signal_rule_recovery(
    response: LLMInterpretationResponse,
    *,
    current_user_message: str,
) -> bool:
    del current_user_message
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "signal_strategy":
        return False
    if draft.rule_spec or draft.entry_rule:
        return False
    if not (draft.raw_user_phrasing or draft.strategy_thesis):
        return False
    if not _response_has_signal_rule_shape(response):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return True
    if response.requires_clarification and response.assistant_response:
        return True
    return any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    )


def _response_has_signal_rule_shape(response: LLMInterpretationResponse) -> bool:
    if any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    ):
        return True
    return any(
        _field_path_base(field) in {"entry_logic", "exit_logic", "rule_spec"}
        for field in response.missing_required_fields
    ) or any(
        _field_path_base(field.field_name)
        in {"entry_logic", "exit_logic", "rule_spec"}
        for field in response.ambiguous_fields
    )


def _supported_signal_rule_planning_response(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    planning = response.model_copy(deep=True)
    planning.intent = "strategy_drafting"
    planning.requires_clarification = True
    planning.assistant_response = None
    planning.missing_required_fields = ["entry_logic", "exit_logic"]
    planning.unsupported_constraints = []
    planning.candidate_strategy_draft.strategy_type = "signal_strategy"
    planning.reason_codes = list(
        dict.fromkeys(
            [
                *planning.reason_codes,
                "supported_signal_rule_contract_recovery",
            ]
        )
    )
    return planning


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


def _asset_recovery_query_is_explicit_ticker(query: str) -> bool:
    candidate = str(query or "").strip().lstrip("$")
    if not candidate:
        return False
    compact = "".join(
        character
        for character in candidate
        if character.isalnum()
    )
    return (
        len(compact) >= 2
        and any(character.isalpha() for character in compact)
        and candidate == candidate.upper()
    )


def _llm_strategy_draft_has_non_asset_strategy_anchor(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(canonical_strategy_type(draft.strategy_type)),
            bool(draft.cadence),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
        ]
    )


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


def _request_targets_pending_signal_rule(request: InterpretationRequest) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    return requested_field in {"entry_logic", "exit_logic"}


def _pending_signal_rule_planning_response(
    *,
    response: LLMInterpretationResponse,
    prior_strategy: dict[str, Any],
    current_user_message: str,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    payload = _signal_rule_planning_context_from_prior(prior_strategy)
    incoming = response.candidate_strategy_draft.model_dump(mode="json")
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        payload[key] = value
    payload["raw_user_phrasing"] = current_user_message
    repaired.candidate_strategy_draft = LLMStrategyDraft.model_validate(payload)
    return repaired


def _signal_rule_planning_context_from_prior(
    prior_strategy: dict[str, Any],
) -> dict[str, Any]:
    context_fields = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "timeframe",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "assumptions",
        "comparison_baseline",
        "refinement_of",
        "resolution_provenance",
    }
    return {
        key: value
        for key, value in prior_strategy.items()
        if key in context_fields and value not in (None, "", [], {})
    }


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


async def _audit_signal_rule_grounding_if_needed(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_signal_rule_grounding_audit(response):
        return None
    audit = await audit_signal_rule_grounding(
        current_user_message=request.current_user_message,
        candidate_strategy=response.candidate_strategy_draft.model_dump(mode="json"),
        prior_strategy=_prior_strategy_payload(request),
        preferred_model=preferred_model,
    )
    if audit is None or audit.outcome == "grounded":
        return None
    return _response_from_signal_grounding_audit(
        response=response,
        audit=audit,
    )


def _response_needs_signal_rule_grounding_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    return bool(draft.rule_spec or draft.entry_rule)


def _response_from_signal_grounding_audit(
    *,
    response: LLMInterpretationResponse,
    audit: SignalRuleGroundingAudit,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    draft.entry_logic = None
    draft.exit_logic = None
    draft.entry_rule = None
    draft.exit_rule = None
    draft.rule_spec = None
    for key in ("entry_rule", "exit_rule", "rule_spec"):
        draft.extra_parameters.pop(key, None)

    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = audit.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(audit.missing_required_fields or ["entry_logic"])
    )
    repaired.confidence = min(repaired.confidence, audit.confidence)
    repaired.reason_codes = list(
        dict.fromkeys(
            [*repaired.reason_codes, "signal_rule_grounding_needs_clarification"]
        )
    )
    return repaired


def _response_needs_signal_rule_plan(response: LLMInterpretationResponse) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    if draft.rule_spec or draft.entry_rule:
        return False
    return _llm_strategy_draft_has_extractable_fields(draft)


def _response_needs_indicator_parameter_repair(
    response: LLMInterpretationResponse,
) -> bool:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    indicator_spec = _llm_draft_executable_indicator_spec(draft)
    if indicator_spec is None:
        return False
    if not _llm_strategy_draft_has_extractable_fields(draft):
        return False
    missing_executable_parameter = any(
        [
            draft.indicator is None and indicator_spec is None,
            draft.entry_threshold is None,
            draft.exit_threshold is None,
        ]
    )
    return missing_executable_parameter


def _response_needs_indicator_default_grounding_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    del request
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "indicator_threshold":
        return False
    indicator_spec = _llm_draft_executable_indicator_spec(draft)
    if indicator_spec is None:
        return False
    default_like_fields = [
        draft.indicator_period == indicator_spec.default_period,
        draft.entry_threshold == indicator_spec.default_entry_threshold,
        draft.exit_threshold == indicator_spec.default_exit_threshold,
    ]
    return any(default_like_fields)


def _llm_draft_executable_indicator_spec(
    draft: LLMStrategyDraft,
):
    for candidate in (
        draft.indicator,
        draft.strategy_type,
        draft.extra_parameters.get("raw_strategy_type"),
        draft.extra_parameters.get("indicator"),
    ):
        spec = executable_indicator_spec(candidate)
        if spec is not None:
            return spec
    return None


def _response_from_signal_rule_plan(
    *,
    response: LLMInterpretationResponse,
    plan: SignalRulePlan,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    if plan.user_goal_summary:
        repaired.user_goal_summary = plan.user_goal_summary
    if plan.strategy_thesis:
        draft.strategy_thesis = plan.strategy_thesis
    if plan.entry_logic:
        draft.entry_logic = plan.entry_logic
    if plan.exit_logic:
        draft.exit_logic = plan.exit_logic
    if plan.rule_spec is not None:
        draft.rule_spec = canonicalize_rule_spec(plan.rule_spec)

    repaired.confidence = min(repaired.confidence, plan.confidence)
    repaired.reason_codes = list(
        dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_repair"])
    )
    if plan.outcome == "draft_only":
        draft.strategy_type = None
        draft.entry_rule = None
        draft.exit_rule = None
        draft.rule_spec = None
        draft.risk_rules = []
        repaired.intent = "unsupported_or_out_of_scope"
        repaired.semantic_turn_act = "unsupported_request"
        repaired.requires_clarification = True
        repaired.assistant_response = plan.assistant_response
        repaired.missing_required_fields = []
        repaired.unsupported_constraints = [
            *repaired.unsupported_constraints,
            LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=_signal_rule_plan_raw_value(draft),
                explanation=(
                    plan.assistant_response
                    or "This idea depends on strategy logic that is not executable yet."
                ),
                simplification_labels=[
                    "Use a supported RSI threshold rule",
                    "Compare with buy and hold",
                    "Use a supported moving-average crossover",
                ],
            ),
        ]
        repaired.reason_codes = list(
            dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_draft_only"])
        )
        return repaired

    draft.strategy_type = "signal_strategy"
    if plan.outcome == "ready_to_confirm":
        # A ready signal-rule plan is the executable contract. Drop unrelated
        # non-executable draft fields that the planner did not ground in the rule.
        draft.risk_rules = []
        repaired.intent = "backtest_execution"
        repaired.requires_clarification = False
        repaired.missing_required_fields = []
        repaired.assistant_response = None
        return repaired

    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = plan.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(plan.missing_required_fields or ["entry_logic"])
    )
    repaired.reason_codes = list(
        dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_needs_clarification"])
    )
    return repaired


def _signal_rule_plan_raw_value(draft: LLMStrategyDraft) -> str:
    value = (
        draft.entry_logic
        or draft.strategy_thesis
        or draft.raw_user_phrasing
        or draft.strategy_type
        or "unsupported signal strategy"
    )
    return str(value)


def _prior_strategy_payload(
    request: InterpretationRequest,
) -> dict[str, Any] | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return None
    return prior.model_dump(mode="json")


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


def _llm_strategy_draft_has_concrete_execution_target(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.date_range),
            bool(draft.timeframe),
            bool(draft.cadence),
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            bool(draft.position_size),
            bool(draft.risk_rules),
            bool(draft.comparison_baseline),
        ]
    )


_EXECUTABLE_TIMEFRAMES = {"1h", "2h", "4h", "6h", "12h", "1D"}


def _response_needs_launch_field_fidelity_repair(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if response.requires_clarification:
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
        "result_followup",
        "unsupported_request",
    }:
        return False
    if "focused_strategy_extraction_repair" in response.reason_codes:
        return False
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.timeframe):
        return str(draft.timeframe).strip() in _EXECUTABLE_TIMEFRAMES
    asset_class = str(draft.asset_class or "").strip().lower()
    return asset_class in {"crypto", "currency_pair"} and not _llm_value_is_empty(
        draft.date_range
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


def _response_needs_executable_strategy_grounding_audit(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if response.requires_clarification:
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.task_relation != "new_task":
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
        "result_followup",
        "unsupported_request",
    }:
        return False
    if "executable_strategy_grounding_audit" in response.reason_codes:
        return False
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    if _response_needs_launch_field_fidelity_repair(response=response):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return False
    return _draft_has_non_executable_timeframe_label(
        draft
    ) or _draft_uses_launch_default_window(draft)


def _draft_has_non_executable_timeframe_label(draft: LLMStrategyDraft) -> bool:
    if _llm_value_is_empty(draft.timeframe):
        return False
    return str(draft.timeframe).strip() not in _EXECUTABLE_TIMEFRAMES


def _draft_uses_launch_default_window(draft: LLMStrategyDraft) -> bool:
    date_range_value = draft.date_range
    if not isinstance(date_range_value, dict):
        return False
    start = str(date_range_value.get("start") or "").strip()
    end = str(date_range_value.get("end") or "").strip()
    return start == "2016-01-01" and end in {"today", date.today().isoformat()}


def _executable_strategy_grounding_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's executable-strategy grounding audit. Decide whether "
                "a runnable draft faithfully represents the current user message before "
                "the product shows a confirmation card. Return grounded only when the "
                "user actually supplied enough meaning for this executable draft. "
                "Return needs_clarification when the draft silently turns a valuation, "
                "fundamental, sentiment, news, vague momentum, or otherwise ambiguous "
                "idea into buy-and-hold, DCA, or another executable strategy without "
                "the user's choice. Valuation language like cheap, undervalued, or P/E "
                "is financially valid context, but Argus needs a supported historical "
                "proxy or explicit baseline before running it. Do not expose provider "
                "plumbing. "
                f"{response_language_instruction(request.user.language_preference)} "
                "Write assistant_response in warm, plain language, with short "
                "sentences and no report tone. Return only JSON matching the schema."
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


def _response_from_executable_strategy_grounding_audit(
    *,
    response: LLMInterpretationResponse,
    audit: ExecutableStrategyGroundingAudit,
) -> LLMInterpretationResponse | None:
    if audit.outcome == "grounded":
        return None
    if audit.outcome != "needs_clarification" or not audit.assistant_response:
        return None
    repaired = response.model_copy(deep=True)
    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = audit.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(audit.missing_required_fields or ["entry_logic"])
    )
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "executable_strategy_grounding_audit",
                "executable_strategy_grounding_needs_clarification",
            ]
        )
    )
    if canonical_strategy_type(
        repaired.candidate_strategy_draft.strategy_type
    ) in {"buy_and_hold", "dca_accumulation"}:
        repaired.candidate_strategy_draft.strategy_type = None
    return repaired


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


def _structured_supported_strategy_capability_conflict_fallback(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse | None:
    if not _response_needs_supported_strategy_capability_conflict_audit(response):
        return None
    if any(
        item.category != "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    ):
        return None
    draft = response.candidate_strategy_draft
    strategy_type = canonical_strategy_type(draft.strategy_type)
    if strategy_type not in {"buy_and_hold", "dca_accumulation"}:
        return None
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return None
    if not (draft.asset_universe or draft.asset_class):
        return None
    if strategy_type == "buy_and_hold" and not (
        draft.date_range
        or _draft_has_semantic_date_window_evidence(draft)
        or resolve_date_range_intent(draft.date_range_intent) is not None
    ):
        return None
    if strategy_type == "dca_accumulation" and not (
        draft.recurring_contribution is not None
        or draft.capital_amount is not None
        or draft.total_capital is not None
        or draft.initial_capital is not None
    ):
        return None
    repaired = _response_with_supported_strategy_capability_conflict_removed(
        response=response,
        strategy_type=strategy_type,
    )
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                code
                for code in repaired.reason_codes
                if code != "supported_strategy_capability_conflict_audit"
            ]
            + ["supported_strategy_capability_structured_fallback"]
        )
    )
    return repaired


def _response_needs_supported_strategy_capability_conflict_audit(
    response: LLMInterpretationResponse,
) -> bool:
    if response.intent not in {
        "strategy_drafting",
        "backtest_execution",
        "unsupported_or_out_of_scope",
    }:
        return False
    has_unsupported_strategy_logic = any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    )
    if response.capability_question_focus is not None and (
        not has_unsupported_strategy_logic
    ):
        return False
    if not has_unsupported_strategy_logic:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return True
    if response.semantic_turn_act != "unsupported_request":
        return False
    if _llm_value_is_empty(draft.strategy_type) and _llm_value_is_empty(
        draft.strategy_thesis
    ):
        return False
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return _llm_strategy_draft_has_concrete_execution_target(draft)
    return _llm_strategy_draft_has_concrete_execution_target(draft)


def _supported_strategy_capability_conflict_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    constraints = [
        item.model_dump(mode="json")
        for item in response.unsupported_constraints
        if item.category == "unsupported_strategy_logic"
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's capability-conflict audit. The primary interpreter "
                "returned both a supported canonical strategy and an "
                "unsupported_strategy_logic constraint, or returned a raw natural-"
                "language strategy phrase as unsupported while preserving executable "
                "field evidence. Decide whether the current user message semantically "
                "selects a supported Alpha strategy or asks for real unsupported "
                "custom logic. Use semantic meaning, not keyword or phrase matching. "
                "Supported Alpha strategy families include buy_and_hold and "
                "dca_accumulation when the user is only asking to test holding or "
                "recurring fixed-dollar buys over a period. A plain performance, "
                "return, or benchmark comparison between one primary asset and a "
                "reference asset over a stated window is a supported buy_and_hold "
                "comparison with comparison_baseline; it is not unsupported custom "
                "strategy logic unless the user adds a separate unsupported rule. "
                "Keep the unsupported "
                "constraint when the current message adds an extra unsupported entry "
                "condition, exit condition, fundamental rule, sentiment/news/event "
                "rule, custom script, brokerage action, shorting, or other logic "
                "beyond the supported strategy family. Drop it only when the message "
                "semantically asks for the supported strategy itself and no extra "
                "unsupported rule. Set selected_strategy_type to the canonical "
                "supported family when dropping the constraint. Reason from the "
                "current message and structured draft meaning. Return only JSON "
                "matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Unsupported strategy constraints JSON: "
                f"{json.dumps(constraints, ensure_ascii=False)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_with_supported_strategy_capability_conflict_removed(
    *,
    response: LLMInterpretationResponse,
    strategy_type: str,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    repaired.candidate_strategy_draft.strategy_type = strategy_type
    if strategy_type in {"buy_and_hold", "dca_accumulation"}:
        _clear_rule_or_indicator_fields(repaired.candidate_strategy_draft)
    repaired.unsupported_constraints = [
        item
        for item in repaired.unsupported_constraints
        if item.category != "unsupported_strategy_logic"
    ]
    repaired.missing_required_fields = (
        _capability_required_missing_fields_for_canonical_strategy(
            repaired.missing_required_fields,
            draft=repaired.candidate_strategy_draft,
        )
    )
    repaired.intent = "strategy_drafting"
    repaired.semantic_turn_act = "new_idea"
    repaired.requires_clarification = bool(
        repaired.missing_required_fields
        or repaired.ambiguous_fields
        or repaired.unsupported_constraints
    )
    repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "supported_strategy_capability_conflict_audit",
            ]
        )
    )
    repaired.capability_question_focus = None
    if (
        not repaired.unsupported_constraints
        and not repaired.ambiguous_fields
        and not repaired.missing_required_fields
        and _llm_strategy_draft_has_concrete_execution_target(
            repaired.candidate_strategy_draft
        )
    ):
        repaired.intent = "backtest_execution"
        repaired.requires_clarification = False
        repaired.assistant_response = None
        repaired.semantic_turn_act = "new_idea"
    return repaired


def _clear_rule_or_indicator_fields(draft: LLMStrategyDraft) -> None:
    draft.entry_logic = None
    draft.exit_logic = None
    draft.entry_rule = None
    draft.exit_rule = None
    draft.rule_spec = None
    draft.indicator = None
    draft.indicator_period = None
    draft.entry_threshold = None
    draft.exit_threshold = None


def _response_with_executable_fields_preferred_over_clarification_prose(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    draft = response.candidate_strategy_draft
    if not (
        response.requires_clarification
        and response.assistant_response
        and response.intent
        in {
            "strategy_drafting",
            "backtest_execution",
            "unsupported_or_out_of_scope",
        }
        and response.semantic_turn_act
        not in {
            "answer_pending_need",
            "approval",
            "educational_question",
            "refine_current_idea",
            "result_followup",
            "retry_failed_action",
        }
        and response.capability_question_focus is None
        and response.context_question_focus is None
        and not response.unsupported_constraints
        and not response.ambiguous_fields
        and not response.missing_required_fields
        and canonical_strategy_type(draft.strategy_type)
        in {"buy_and_hold", "dca_accumulation"}
        and not _llm_strategy_draft_has_rule_or_indicator_fields(draft)
        and _llm_strategy_draft_has_executable_shape(draft)
        and not has_partial_explicit_date_range(draft.date_range)
    ):
        return response
    return response.model_copy(
        update={
            "intent": "backtest_execution",
            "requires_clarification": False,
            "assistant_response": None,
            "semantic_turn_act": "new_idea",
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "executable_fields_overrode_clarification_prose",
                    ]
                )
            ),
        }
    )


def _response_from_current_message_run_field_contract(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    """Preserve obvious run facts from the current turn when audit models omit them."""

    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    current_message = request.current_user_message
    changed = False

    date_range = _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
    )
    if date_range is None:
        return None
    if (
        date_range is not None
        and (
            _draft_date_range_needs_stated_run_field_audit(
                draft,
                current_message=current_message,
            )
            or _response_needs_current_message_date_repair(
                response=repaired,
                current_message=current_message,
                language=request.user.language_preference,
            )
        )
    ):
        draft.date_range = date_range
        if _draft_has_non_executable_timeframe_label(draft):
            draft.timeframe = None
        if has_partial_explicit_date_range(date_range):
            repaired.requires_clarification = True
            repaired.assistant_response = None
            repaired.missing_required_fields = list(
                dict.fromkeys([*repaired.missing_required_fields, "date_range"])
            )
        else:
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
        changed = True

    if (
        changed
        and repaired.requires_clarification
        and not has_partial_explicit_date_range(draft.date_range)
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
    if (
        changed
        and not repaired.requires_clarification
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    ):
        repaired.intent = "backtest_execution"
        repaired.semantic_turn_act = "new_idea"

    if not changed:
        return None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "current_message_run_field_contract_repair",
            ]
        )
    )
    return repaired


def _natural_time_language_candidates_from_hints(
    *language_hints: str | None,
) -> tuple[tuple[str, ...] | None, ...]:
    hinted_languages: list[tuple[str, ...] | None] = []
    for language in language_hints:
        if not str(language or "").strip():
            continue
        hints = dateparser_languages_for_user_language(language)
        if hints not in hinted_languages:
            hinted_languages.append(hints)
    if None not in hinted_languages:
        hinted_languages.append(None)
    return tuple(hinted_languages)


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
    if not isinstance(draft.date_range, dict):
        return False
    return _normalized_stated_field(draft.date_range) != _normalized_stated_field(
        date_range
    )


def _response_with_resolved_runtime_date_range(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    date_range = _resolved_runtime_date_range_from_draft(
        response.candidate_strategy_draft,
        request=request,
    )
    if date_range is None:
        return response
    draft = response.candidate_strategy_draft
    if _normalized_stated_field(draft.date_range) == _normalized_stated_field(
        date_range
    ):
        return response
    repaired = response.model_copy(deep=True)
    repaired.candidate_strategy_draft.date_range = date_range
    if not has_partial_explicit_date_range(date_range):
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
        repaired.requires_clarification
        and not has_partial_explicit_date_range(date_range)
        and not repaired.missing_required_fields
        and not repaired.ambiguous_fields
        and not repaired.unsupported_constraints
        and _llm_strategy_draft_has_concrete_execution_target(
            repaired.candidate_strategy_draft
        )
    ):
        repaired.requires_clarification = False
        repaired.assistant_response = None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "runtime_date_range_normalization",
            ]
        )
    )
    return repaired


def _resolved_runtime_date_range_from_draft(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> dict[str, str] | None:
    normalized = normalize_date_range_candidate(draft.date_range)
    if isinstance(normalized, dict) and _has_complete_date_range_payload(normalized):
        try:
            resolved = resolve_date_range(normalized)
        except Exception:
            resolved = None
        if resolved is not None and not resolved.used_default:
            return resolved.payload
    return _date_range_from_intent_or_bounded_evidence(
        draft,
        language=request.user.language_preference,
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


def _pending_dca_assumption_reply_needs_stated_run_field_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest | None,
) -> bool:
    if request is None or response.semantic_turn_act != "answer_pending_need":
        return False
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field != "assumption":
        return False
    return canonical_strategy_type(
        response.candidate_strategy_draft.strategy_type
    ) == "dca_accumulation"


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


def _focused_repair_capital_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if draft.capital_amount is not None:
        return False
    return _draft_capital_needs_stated_run_field_audit(
        draft,
        current_message=current_message,
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


def _draft_capital_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str,
) -> bool:
    if canonical_strategy_type(draft.strategy_type) == "dca_accumulation":
        return False
    if not _draft_has_non_money_execution_anchor(draft):
        return False
    if _text_contains_capital_audit_signal(current_message, draft=draft):
        return True
    return draft.capital_amount is None and _draft_contains_structured_capital_context(draft)


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


def _explicit_benchmark_ticker_queries(message: str) -> list[str]:
    tokens = _field_fidelity_tokens(str(message or ""))
    queries: list[str] = []
    seen: set[str] = set()
    benchmark_cues = {"against", "vs", "versus", "contra"}
    for index, token in enumerate(tokens):
        candidate = token.strip().lstrip("$")
        if not candidate:
            continue
        compact = "".join(
            character
            for character in candidate
            if character.isalnum()
        )
        if len(compact) < 2 or not any(character.isalpha() for character in compact):
            continue
        previous = tokens[index - 1].strip().casefold() if index > 0 else ""
        is_cued_lowercase_ticker = (
            previous in benchmark_cues
            and candidate == candidate.lower()
            and len(compact) <= 5
        )
        if not (
            _asset_recovery_query_is_explicit_ticker(token)
            or is_cued_lowercase_ticker
        ):
            continue
        normalized = candidate.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        queries.append(candidate)
    return queries


def _resolve_benchmark_candidate_from_message(query: str) -> AssetResolution | None:
    try:
        return _resolve_asset_candidate(
            query,
            field="comparison_baseline",
            source="user_mention",
        )
    except ValueError:
        return None


def _response_needs_current_message_date_repair(
    *,
    response: LLMInterpretationResponse,
    current_message: str,
    language: str | None = None,
) -> bool:
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.date_range):
        return False
    del current_message
    if _date_range_from_intent_or_bounded_evidence(draft, language=language) is None:
        return False
    if _llm_strategy_draft_has_concrete_execution_target(draft):
        return True
    if _response_has_pending_base_field(response, "date_range"):
        return True
    return response.requires_clarification and _llm_strategy_draft_has_concrete_execution_target(
        draft
    )


def _response_needs_missing_benchmark_fidelity_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    return (
        response.requires_clarification
        and not response.missing_required_fields
        and not response.ambiguous_fields
        and _llm_value_is_empty(draft.comparison_baseline)
        and _llm_strategy_draft_has_concrete_execution_target(draft)
    )


def _dca_response_needs_semantic_field_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "dca_accumulation":
        return False
    field_provenance = dict(draft.field_provenance or {})
    amount_source = str(field_provenance.get("capital_amount") or "").strip()
    cadence_source = str(field_provenance.get("cadence") or "").strip()
    if draft.capital_amount is None or amount_source not in {
        "explicit_user",
        "prior",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }:
        return True
    if draft.cadence in (None, "", [], {}) or cadence_source not in {
        "explicit_user",
        "prior",
        "visible_draft",
    }:
        return True
    return False


def _response_has_pending_base_field(
    response: LLMInterpretationResponse,
    field_name: str,
) -> bool:
    return any(
        _field_path_base(field) == field_name
        for field in response.missing_required_fields
    ) or any(
        _field_path_base(field.field_name) == field_name
        for field in response.ambiguous_fields
    )


def _draft_has_unprovenanced_benchmark(draft: LLMStrategyDraft) -> bool:
    if _llm_value_is_empty(draft.comparison_baseline):
        return False
    provenance = draft.field_provenance or {}
    return provenance.get("comparison_baseline") not in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }


def _draft_date_range_needs_stated_run_field_audit(
    draft: LLMStrategyDraft,
    *,
    current_message: str = "",
) -> bool:
    if _llm_value_is_empty(draft.date_range):
        return False
    current_message_range = _date_range_from_intent_or_bounded_evidence(draft)
    if (
        current_message_range is not None
        and not has_partial_explicit_date_range(current_message_range)
        and isinstance(draft.date_range, dict)
        and not has_partial_explicit_date_range(draft.date_range)
        and _normalized_stated_field(draft.date_range)
        != _normalized_stated_field(current_message_range)
    ):
        return True
    if (
        current_message_range is None
        and _draft_date_range_has_unstated_current_endpoint(draft.date_range)
    ):
        return True
    if has_partial_explicit_date_range(draft.date_range):
        return current_message_range is not None and not has_partial_explicit_date_range(
            current_message_range
        )
    if isinstance(draft.date_range, str) and current_message_range is not None:
        normalized_range = draft.date_range.strip().casefold()
        return bool(normalized_range and normalized_range not in current_message.casefold())
    return False


def _draft_date_range_has_unstated_current_endpoint(
    date_range_value: Any,
) -> bool:
    if not isinstance(date_range_value, dict):
        return False
    for key in ("end", "to"):
        endpoint = date_range_value.get(key)
        if _date_endpoint_is_runtime_current(endpoint):
            return True
    return False


def _date_endpoint_is_runtime_current(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    normalized = str(value).strip().casefold()
    return normalized in {
        "today",
        "now",
        "present",
        "current",
        "current_date",
        date.today().isoformat(),
    }


def _draft_contains_structured_capital_context(draft: LLMStrategyDraft) -> bool:
    text = _structured_draft_context_text(draft)
    if "$" in str(text or ""):
        return True
    non_capital_tokens = _draft_non_capital_numeric_evidence_tokens(draft)
    for token in _field_fidelity_tokens(str(text or "")):
        normalized = token.strip().casefold()
        if normalized in non_capital_tokens:
            continue
        if any(character.isdigit() for character in normalized) and any(
            character.isalpha() for character in normalized
        ):
            return True
    return False


def _draft_has_non_money_execution_anchor(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            canonical_strategy_type(draft.strategy_type) in SUPPORTED_STRATEGY_TYPES,
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.date_range),
            draft.date_range_intent is not None,
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.comparison_baseline),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
            _draft_has_semantic_date_window_evidence(draft),
            _draft_has_comparison_baseline_evidence(draft),
        ]
    )


def _text_contains_capital_audit_signal(
    text: str,
    *,
    draft: LLMStrategyDraft,
) -> bool:
    if "$" in str(text or ""):
        return True
    tokens = _field_fidelity_tokens(str(text or "").casefold())
    if not tokens:
        return False
    non_capital_tokens = _draft_non_capital_numeric_evidence_tokens(draft)
    return any(
        token not in non_capital_tokens
        and any(character.isdigit() for character in token)
        for token in tokens
    )


def _draft_non_capital_numeric_evidence_tokens(draft: LLMStrategyDraft) -> set[str]:
    tokens = set(_draft_date_evidence_tokens(draft))
    if not _llm_value_is_empty(draft.timeframe):
        tokens.update(_field_fidelity_tokens(str(draft.timeframe).casefold()))
    return tokens


def _draft_date_evidence_tokens(draft: LLMStrategyDraft) -> set[str]:
    candidates = list(_bounded_date_evidence_candidates(draft))
    date_range = normalize_date_range_candidate(draft.date_range)
    if isinstance(date_range, Mapping):
        candidates.extend(str(value) for value in date_range.values() if value)
    date_range_intent = draft.date_range_intent
    intent_evidence = getattr(date_range_intent, "evidence", None)
    if intent_evidence:
        candidates.append(str(intent_evidence))
    return {
        token
        for candidate in candidates
        for token in _date_evidence_tokens_from_text(candidate)
    }


def _date_evidence_tokens_from_text(value: Any) -> set[str]:
    text = str(value or "").casefold()
    tokens = set(_field_fidelity_tokens(text))
    for separator in ("-", "/"):
        if separator in text:
            tokens.update(_field_fidelity_tokens(text.replace(separator, " ")))
    return tokens


def _draft_has_timeframe_evidence_for_audit(draft: LLMStrategyDraft) -> bool:
    if not _llm_value_is_empty(draft.timeframe):
        return True
    evidence_spans = _draft_semantic_evidence_spans(draft)
    return not _llm_value_is_empty(evidence_spans.get("timeframe"))


def _structured_draft_context_text(
    draft: LLMStrategyDraft,
    *,
    extra_text: str = "",
) -> str:
    values = (
        extra_text,
        draft.raw_user_phrasing,
        draft.date_range_raw_text,
        draft.strategy_thesis,
        draft.entry_logic,
        draft.exit_logic,
        " ".join((draft.evidence_spans or {}).values()),
    )
    return " ".join(str(value) for value in values if value)


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


def _response_needs_latest_result_routing_audit(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> bool:
    if not _request_has_latest_result(request):
        return False
    if response.semantic_turn_act == "result_followup":
        return True
    if response.intent == "results_explanation":
        return True
    if _llm_strategy_draft_has_executable_shape(response.candidate_strategy_draft):
        return response.task_relation == "continue"
    if _llm_strategy_draft_has_extractable_fields(response.candidate_strategy_draft):
        return True
    return bool(
        response.capability_question_focus is not None
        or (
            response.task_relation == "continue"
            and response.assistant_response is None
        )
    )


def _response_targets_latest_result_followup(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    return (
        _request_has_latest_result(request)
        and response.semantic_turn_act == "result_followup"
    )


def _latest_result_routing_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's post-result routing audit. Decide whether the "
                "current user message should be answered from the latest completed "
                "result artifact or as a general product/capability question. "
                "Choose targets_latest_result=true for questions about what "
                "happened, what was tested, assumptions in the run, drawdown, "
                "benchmark comparison, or what experiment to try next from the "
                "latest result. Choose false for new investing ideas, beginner "
                "education, and direct questions about Argus capabilities that do "
                "not depend on the latest result. If the primary interpreter copied "
                "symbols, dates, timeframe, or strategy labels out of the latest "
                "result but did not produce a new executable rule, treat that as "
                "latest-result context rather than a new strategy. Set "
                "save_requested=true when the user is asking to save, keep, "
                "bookmark, or promote the latest completed result artifact. "
                "Examples that must set save_requested=true when a latest result "
                "exists: 'save this', 'save this result', 'keep this', "
                "'bookmark this run', 'save that strategy from the result'. Use "
                "why_underperformed for questions that ask why a result matched, "
                "beat, lagged, or compared with its benchmark; use what_tested only "
                "when the user is asking for the run setup itself."
            ),
        },
        {
            "role": "system",
            "content": (
                "Latest result fact bank JSON: "
                + json.dumps(_latest_result_fact_bank_for_routing(request))
            ),
        },
        {
            "role": "system",
            "content": (
                "Primary interpreter decision JSON: " + response.model_dump_json()
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


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


def _latest_result_fact_bank_for_routing(
    request: InterpretationRequest,
) -> dict[str, str]:
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return {}
    metadata = dict(snapshot.latest_backtest_result_reference.metadata)
    fact_bank = result_followup_fact_bank(metadata)
    return {
        key: fact_bank[key]
        for key in (
            "symbols",
            "strategy",
            "date_range",
            "total_return",
            "benchmark_symbol",
            "benchmark_return",
            "benchmark_delta",
            "max_drawdown",
            "runnable_next_tests",
        )
        if key in fact_bank
    }


def _stated_run_field_fidelity_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's run-field fidelity audit. Compare the current "
                "user message with the structured draft and return only run fields "
                "the user explicitly stated but the draft may have dropped or "
                "reshaped. Do not infer defaults, fees, slippage, symbols, or rules. "
                "If a field is absent from the current user message, return null "
                "for that field. Normalize starting capital exactly from the "
                "current message: 10k -> 10000, 100K -> 100000, $10,000 "
                "-> 10000, 100k -> 100000, and a plain number such as "
                "100000 -> 100000 when the message uses it as the amount to "
                "test, invest, allocate, put on, or use as capital. This is "
                "language-agnostic: preserve bare numeric amounts and numeric "
                "magnitude shorthand that appear in the user's investing idea. "
                "A standalone numeric magnitude at the end of an otherwise "
                "complete strategy, asset, and date-window request is a "
                "starting-capital candidate when it is not serving as a date, "
                "lookback window, percentage, indicator parameter, share count, "
                "or asset identifier. Do not require currency symbols. Do not "
                "treat dates, calendar years, "
                "indicator windows, lookback windows, percentages, share counts, "
                "or asset names as capital. For DCA or recurring buys, return the per-purchase "
                "recurring contribution as recurring_contribution_amount, not "
                "capital_amount; return cadence only when the current message states "
                "one. If a money amount is total budget, starting principal, or cap, "
                "leave recurring_contribution_amount null. Normalize one-hour/hourly "
                "bars to 1h, four-hour bars to "
                "4h, and daily bars to 1D. Preserve today/current as today or the "
                f"runtime date {date.today().isoformat()} only when the user stated "
                "today/current. If the user stated only a start or only an end date, "
                "return only that endpoint; do not infer the missing endpoint or "
                "rewrite the unstated endpoint. For pending date answers such as "
                "'end of 2023' or 'through December 2024', return only the end "
                "endpoint. Date phrases such as 'at the start of 2024', 'from "
                "the beginning of 2024', or 'since 2024' state only a start "
                "endpoint unless the message also states an end. Return explicit "
                "comparison assets as comparison_baseline, "
                "not asset_universe. Treat benchmark/reference/baseline/comparison "
                "relationships semantically in any language; if a user names an "
                "asset as a reference, benchmark, against/versus target, or "
                "comparison target, that asset belongs in comparison_baseline. "
                "If the draft has a default benchmark but the current "
                "message states a different comparison asset, return the user-stated "
                "comparison asset. Return "
                "only JSON matching the schema."
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


def _response_from_stated_run_field_fidelity_audit(
    *,
    response: LLMInterpretationResponse,
    audit: StatedRunFieldFidelityAudit,
    current_message: str = "",
) -> LLMInterpretationResponse | None:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    changed = False
    if audit.capital_amount is not None and draft.capital_amount != audit.capital_amount:
        draft.capital_amount = audit.capital_amount
        draft.field_provenance["capital_amount"] = "starting_capital"
        changed = True
    if audit.recurring_contribution_amount is not None:
        recurring_amount = float(audit.recurring_contribution_amount)
        if draft.capital_amount != recurring_amount:
            draft.capital_amount = recurring_amount
            changed = True
        if draft.field_provenance.get("capital_amount") != "recurring_contribution":
            draft.field_provenance["capital_amount"] = "recurring_contribution"
            changed = True
    if audit.cadence:
        cadence = _supported_dca_cadence_value(audit.cadence)
        if cadence is not None:
            if draft.cadence != cadence:
                draft.cadence = cadence
                changed = True
            if draft.field_provenance.get("cadence") != "explicit_user":
                draft.field_provenance["cadence"] = "explicit_user"
                changed = True
    if audit.timeframe and draft.timeframe != audit.timeframe:
        draft.timeframe = audit.timeframe
        changed = True
    if audit.date_range not in (None, "", [], {}):
        audited_date_range: Any = audit.date_range
        del current_message
        expected_date_range = _date_range_from_intent_or_bounded_evidence(draft)
        if (
            isinstance(expected_date_range, dict)
            and not has_partial_explicit_date_range(expected_date_range)
            and isinstance(audited_date_range, dict)
            and _normalized_stated_field(audited_date_range)
            != _normalized_stated_field(expected_date_range)
        ):
            audited_date_range = expected_date_range
        date_range, date_changed = _date_range_with_fidelity_audit(
            current=draft.date_range,
            audited=audited_date_range,
        )
        if date_changed:
            draft.date_range = date_range
            changed = True
    if audit.comparison_baseline:
        baseline = str(audit.comparison_baseline).strip().upper()
        if baseline:
            if draft.comparison_baseline != baseline:
                draft.comparison_baseline = baseline
                changed = True
            if draft.field_provenance.get("comparison_baseline") != (
                "stated_run_field_fidelity_audit"
            ):
                draft.field_provenance["comparison_baseline"] = (
                    "stated_run_field_fidelity_audit"
                )
                changed = True
    if not changed:
        return None
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "stated_run_field_fidelity_audit",
            ]
        )
    )
    return repaired


def _stated_run_field_audit_omitted_expected_fields(
    *,
    response: LLMInterpretationResponse,
    audit: StatedRunFieldFidelityAudit,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    del request
    expected_date_range = _date_range_from_intent_or_bounded_evidence(draft)
    if expected_date_range is None and isinstance(draft.date_range, dict):
        expected_date_range = draft.date_range
    if (
        not _llm_value_is_empty(draft.date_range)
        and expected_date_range is not None
        and audit.date_range in (None, "", [], {})
    ):
        return True
    return False


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


def _normalized_stated_field(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value or "").strip()


def _date_range_with_fidelity_audit(
    *,
    current: Any,
    audited: Any,
) -> tuple[Any, bool]:
    if _llm_value_is_empty(current):
        return audited, True
    if _normalized_stated_field(audited) == _normalized_stated_field(current):
        return current, False
    if isinstance(current, dict) and isinstance(audited, dict):
        if _date_range_audit_has_partial_endpoint(audited):
            return audited, _normalized_stated_field(audited) != _normalized_stated_field(
                current
            )
        merged = dict(current)
        changed = False
        for key, audited_value in audited.items():
            if audited_value in (None, "", [], {}):
                continue
            current_value = merged.get(key)
            if current_value not in (None, "", [], {}) and _date_value_is_less_specific(
                audited_value,
                current_value,
            ):
                continue
            if _normalized_stated_field(current_value) != _normalized_stated_field(
                audited_value
            ):
                merged[key] = audited_value
                changed = True
        return merged, changed
    if isinstance(audited, dict):
        return audited, True
    return current, False


def _date_range_audit_has_partial_endpoint(value: dict[str, Any]) -> bool:
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return (start not in (None, "", [], {})) != (end not in (None, "", [], {}))


def _date_value_is_less_specific(candidate: Any, existing: Any) -> bool:
    candidate_text = str(candidate or "").strip()
    existing_text = str(existing or "").strip()
    if not candidate_text or not existing_text:
        return False
    if candidate_text.casefold() in {"today", "current", "now"}:
        return False
    if existing_text.casefold() in {"today", "current", "now"}:
        return True
    candidate_digits = sum(1 for char in candidate_text if char.isdigit())
    existing_digits = sum(1 for char in existing_text if char.isdigit())
    return candidate_digits < existing_digits and existing_text.startswith(
        candidate_text
    )


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
    return await _repair_incomplete_strategy_extraction(
        failed_response=seed_response,
        preferred_model=preferred_model,
        request=request,
    )


def _focused_strategy_extraction_messages(
    request: InterpretationRequest,
) -> list[BaseMessage]:
    return [
        SystemMessage(
            content=(
                "Focused strategy extraction repair. The general interpreter under-filled "
                "a current user message that may contain a testable investing idea. "
                "Interpret only the current user message and return all fields needed "
                "to draft an executable backtest. Do not omit a field that appears in "
                "the message. Do not invent fees, slippage, position size, or provider "
                "details. If the current message semantically gives a supported "
                "strategy family, primary asset, benchmark/reference asset, relative "
                "window, capital amount, recurring contribution, or recurring cadence, "
                "returning null or empty for that field is an extraction failure. Do "
                "not ask the user to choose a supported strategy when the current "
                "message already selected one semantically. "
                "Evidence spans are provenance only. Never put a supported "
                "strategy, asset, benchmark, time window, or capital amount only "
                "inside evidence_spans; populate the matching canonical field too. "
                "date_range_intent is the canonical object field, not an "
                "evidence_spans key; if a time window is visible, populate "
                "date_range_raw_text with the exact bounded phrase and "
                "date_range_intent with the canonical intent. "
                "is_testable_strategy means the user is asking for a strategy "
                "or backtest idea; it does not mean Argus can execute every part. For "
                "clear sentiment, news, fundamental, external-data, or other draft-only "
                "strategy requests, set is_testable_strategy=true, preserve the asset, "
                "period, unsupported rule, and raw strategy_type, and let the runtime "
                "route it to unsupported recovery.\n\n"
                "Executable strategy_type values are buy_and_hold, dca_accumulation, "
                "indicator_threshold, and signal_strategy. Treat this as an execution "
                "contract, not a taxonomy for every creative idea. If the user asks for "
                "sentiment, news, fundamentals, custom external data, or any rule you "
                "cannot express with these structured executable fields, do not force "
                "it into signal_strategy or indicator_threshold. Preserve the idea in "
                "user_goal_summary/assistant_response and mark it as needing a supported "
                "executable simplification. Valuation/P/E language is financially valid "
                "context, but it is not an executable rule in the current engine; preserve "
                "the valuation meaning and route toward the closest supported proxy. "
                "Preserve user-stated asset names or symbols "
                "in asset_universe; the provider-backed resolver will validate and "
                "canonicalize assets after interpretation. Preserve user-stated "
                "benchmark/comparison assets such as QQQ, SPY, BTC, or IWM in "
                "comparison_baseline, not asset_universe. In any language, a request "
                "to buy, hold, or test one primary asset over a window with another "
                "asset as a benchmark, reference, baseline, or comparison target is "
                "an executable buy_and_hold setup with that other asset in "
                "comparison_baseline; it is not unsupported custom logic. Relative windows such as "
                "'last 8 months' or equivalent phrases in any language must become "
                "date_range_intent with kind=rolling_window, count, unit, "
                "anchor=today, confidence, and evidence. Current-year-to-current-date "
                "windows in any language must become date_range_intent with "
                "kind=year_to_date, confidence, and evidence. Do not ask for exact "
                "endpoint dates when the current message states a relative window. "
                "Use date_range_raw_text only as bounded evidence for the same "
                "window, not as the executable date contract. If the user gives a "
                "start date and says today, preserve the end as 'today' or "
                f"{date.today().isoformat()}, not a stale model date. If the user gives "
                "only a start or only an end, preserve only that endpoint and include "
                "date_range in missing_required_fields; do not infer today. Preserve "
                "language, date_range_raw_text, date_range_intent, and evidence_spans "
                "when available. Use date_range_intent for relative or semantic time "
                "windows so deterministic code receives canonical date math inputs "
                "instead of localized prose. Preserve "
                "user-stated timeframes such as 1 hour candles, hourly bars, 1h, "
                "4 hour candles, 4h, daily candles, or 1D as timeframe. Normalize "
                "one-hour/hourly to 1h, four-hour to 4h, and daily to 1D. Preserve "
                "user-stated capital amounts as capital_amount; "
                "do not silently widen the timeframe, shorten dates, or drop stated "
                "money amounts to make a request look runnable.\n\n"
                "For moving-average crossovers, set strategy_type to signal_strategy "
                "and set entry_rule to {'type':'moving_average_crossover', "
                "'fast_indicator':'sma' or 'ema', 'fast_period':number, "
                "'slow_indicator':'sma' or 'ema', 'slow_period':number, "
                "'direction':'bullish' for crosses above or 'bearish' for crosses "
                "below}. If the user does not state an exit, leave exit_rule null "
                "and set exit_logic to the opposite crossover default. Shorthand "
                "like 'the 50 crosses the 200' or '50/200 cross' is enough to set "
                "a bullish SMA 50/200 crossover unless the user says EMA or bearish.\n\n"
                "For RSI threshold ideas, set strategy_type to indicator_threshold, "
                "indicator to rsi, indicator_period only when supplied, and threshold "
                "overrides as numbers. If the user states only one threshold side, "
                "fill that side and leave only the unstated side null so the runtime "
                "can apply the supported default. Do not ask about RSI period; it has "
                "a supported default.\n\n"
                "A one-time historical acquisition or purchase plus holding through "
                "a period is normal user language for the supported buy_and_hold "
                "simulation, not unsupported manual trade replay. Preserve the asset, "
                "capital_amount, and date_range_intent when present. Do not ask the "
                "user to choose buy-and-hold again when the current message already "
                "semantically selected holding and did not state a separate entry or "
                "exit rule. A recurring fixed-amount purchase over a period is normal "
                "user language for the supported dca_accumulation simulation. Preserve "
                "the asset, recurring_contribution, cadence, capital_amount, and "
                "date_range_intent when present. Do not route recurring fixed-amount "
                "buys to unsupported recovery when those executable fields are stated."
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


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


def _comparison_baseline_provenance(
    comparison_baseline: str | None,
    *,
    current_message: str,
) -> dict[str, str]:
    del comparison_baseline, current_message
    return {}


def _focused_extraction_field_provenance(
    *,
    extraction: FocusedStrategyExtraction,
    current_message: str,
) -> dict[str, str]:
    provenance = _comparison_baseline_provenance(
        extraction.comparison_baseline,
        current_message=current_message,
    )
    evidence_spans = dict(extraction.evidence_spans or {})
    if (
        extraction.comparison_baseline
        and _llm_value_is_empty(provenance.get("comparison_baseline"))
        and not _llm_value_is_empty(evidence_spans.get("comparison_baseline"))
    ):
        provenance["comparison_baseline"] = "explicit_user"
    if extraction.recurring_contribution is not None:
        provenance["recurring_contribution"] = "explicit_user"
        provenance["capital_amount"] = "recurring_contribution"
    elif extraction.capital_amount is not None:
        if canonical_strategy_type(extraction.strategy_type) == "dca_accumulation":
            provenance["capital_amount"] = "recurring_contribution"
        else:
            provenance["capital_amount"] = "starting_capital"
    if extraction.cadence:
        provenance["cadence"] = "explicit_user"
    return provenance


def _merge_focused_repair_with_base(
    *,
    response: LLMInterpretationResponse,
    base_response: LLMInterpretationResponse | None,
) -> LLMInterpretationResponse:
    if base_response is None:
        return response
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    base = base_response.candidate_strategy_draft
    for field_name in (
        "raw_user_phrasing",
        "strategy_thesis",
        "asset_universe",
        "asset_class",
        "date_range",
        "date_range_intent",
        "timeframe",
        "cadence",
        "capital_amount",
        "position_size",
        "comparison_baseline",
    ):
        current_value = getattr(draft, field_name)
        base_value = getattr(base, field_name)
        if _llm_value_is_empty(current_value) and not _llm_value_is_empty(base_value):
            setattr(draft, field_name, base_value)
    if not repaired.user_goal_summary and base_response.user_goal_summary:
        repaired.user_goal_summary = base_response.user_goal_summary
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *base_response.reason_codes,
                *repaired.reason_codes,
                "focused_repair_preserved_structured_context",
                *(
                    ["focused_repair_from_unsupported_context"]
                    if _base_response_was_unsupported(base_response)
                    else []
                ),
            ]
        )
    )
    return repaired


def _base_response_was_unsupported(response: LLMInterpretationResponse) -> bool:
    return bool(
        response.intent == "unsupported_or_out_of_scope"
        or response.semantic_turn_act == "unsupported_request"
        or response.unsupported_constraints
    )


def _llm_value_is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _focused_artifact_edit_messages(
    request: InterpretationRequest,
) -> list[BaseMessage] | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None and snapshot.active_confirmation_reference is None:
        return None
    active_confirmation = (
        snapshot.active_confirmation_reference.model_dump(mode="json")
        if snapshot.active_confirmation_reference is not None
        else None
    )
    return [
        SystemMessage(
            content=(
                "Focused artifact edit planning. The previous interpretation replayed "
                "or under-filled the active artifact. Interpret only the current user "
                "message against the canonical prior artifact. The current user message "
                "is authoritative. Return a structured edit or answer; do not replay "
                "the prior artifact unchanged. If the user changes the asset, date "
                "range, indicator, thresholds, or assumptions, candidate_strategy_draft "
                "must include the changed field. Preserve unchanged executable context "
                "from the prior artifact only when it is needed for a runnable draft."
            )
        ),
        SystemMessage(
            content=(
                "Prior strategy JSON, if any: "
                f"{prior.model_dump(mode='json') if prior else 'none'}\n"
                "Active confirmation reference JSON, if any: "
                f"{active_confirmation if active_confirmation else 'none'}"
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _openrouter_wire_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    wire_messages: list[dict[str, str]] = []
    for message in messages:
        role = "user"
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, HumanMessage):
            role = "user"
        content = message.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                item
                if isinstance(item, str)
                else str(item.get("text") or "")
                if isinstance(item, dict)
                else str(item)
                for item in content
            )
        else:
            text = str(content)
        wire_messages.append({"role": role, "content": text})
    if wire_messages:
        wire_messages[0]["content"] = (
            wire_messages[0]["content"]
            + "\n\nReturn only valid JSON matching the supplied schema. "
            "Do not include reasoning, markdown, prose, or fields that are not "
            "defined by the supplied schema. Use the schema descriptions and the "
            "task-specific instructions above as the contract for canonical values."
        )
    return wire_messages


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


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


def _structured_strategy_missing_fields_can_clarify(
    *,
    response: LLMInterpretationResponse,
    draft: LLMStrategyDraft,
    missing: list[str],
) -> bool:
    if not missing:
        return False
    if not response.requires_clarification:
        return False
    if not response.missing_required_fields:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.unsupported_constraints:
        return False
    if "supported_strategy_capability_conflict_audit" in response.reason_codes:
        return False
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    declared_missing = {
        _field_path_base(field) for field in response.missing_required_fields
    }
    return set(missing).issubset(
        declared_missing
    ) and _llm_strategy_draft_has_extractable_fields(draft)


def _request_has_failed_action_launch_payload(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    return (
        launch_payload_from_failed_action(snapshot.latest_failed_action_reference)
        is not None
    )


def _response_underfills_pending_result_refinement(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field != "refinement":
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return False
    if (
        _request_has_latest_result(request)
        and response.semantic_turn_act == "result_followup"
    ):
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return True
    return not _llm_strategy_draft_has_extractable_fields(
        response.candidate_strategy_draft
    )


def _response_underfills_active_artifact_rule_edit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not _request_has_active_strategy_context(request):
        return False
    if not response.requires_clarification or not response.assistant_response:
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_rule_or_indicator_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _response_underfills_active_artifact_assumption_edit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not _request_targets_pending_artifact_assumption_edit(request):
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_supported_artifact_assumption_edit(draft):
        return False
    if response.requires_clarification and response.assistant_response:
        return False
    return bool(response.intent in {"strategy_drafting", "backtest_execution"})


def _llm_strategy_draft_has_supported_artifact_assumption_edit(
    draft: LLMStrategyDraft,
) -> bool:
    field_provenance = draft.field_provenance or {}
    extra_parameters = draft.extra_parameters or {}
    return any(
        [
            draft.capital_amount is not None
            and field_provenance.get("capital_amount") in _TOTAL_CAPITAL_SOURCES,
            draft.initial_capital is not None
            and field_provenance.get("initial_capital") in _TOTAL_CAPITAL_SOURCES,
            draft.capital_amount is not None
            and field_provenance.get("capital_amount") == "recurring_contribution",
            draft.recurring_contribution is not None
            and field_provenance.get("recurring_contribution")
            == "recurring_contribution",
            bool(draft.timeframe),
            "fee_rate" in extra_parameters,
            "slippage" in extra_parameters,
        ]
    )


def _llm_strategy_draft_has_rule_or_indicator_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.entry_logic),
            bool(draft.exit_logic),
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
        ]
    )


def _llm_strategy_draft_has_structured_rule_or_indicator_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
        ]
    )


def _llm_strategy_draft_has_executable_shape(draft: LLMStrategyDraft) -> bool:
    strategy_type = canonical_strategy_type(draft.strategy_type)
    if strategy_type == "buy_and_hold":
        return bool(draft.asset_universe or draft.date_range)
    if strategy_type == "dca_accumulation":
        return bool(_supported_dca_cadence_value(draft.cadence)) and (
            _dca_draft_has_recurring_amount(draft)
        )
    if strategy_type == "signal_strategy":
        return _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft)
    return bool(
        draft.cadence or _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft)
    )


def _llm_signal_strategy_is_underfilled(draft: LLMStrategyDraft) -> bool:
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    return not any([draft.entry_rule, draft.rule_spec])


def _llm_strategy_draft_has_extractable_fields(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            bool(draft.strategy_type),
            bool(draft.strategy_thesis),
            bool(draft.asset_universe),
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
            draft.capital_amount is not None,
            draft.position_size is not None,
            bool(draft.risk_rules),
            bool(draft.extra_parameters),
        ]
    )


def _llm_strategy_draft_has_structural_execution_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return bool(_material_strategy_updates_from_draft(draft))


def _llm_strategy_draft_has_unstructured_strategy_text(
    draft: LLMStrategyDraft,
) -> bool:
    if _llm_strategy_draft_has_structural_execution_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _response_replays_prior_strategy_without_current_turn_update(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if "pending_response_option_selected" in response.reason_codes:
        return False
    if response.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.requires_clarification and response.assistant_response:
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return False
    draft = response.candidate_strategy_draft
    material_updates = _material_strategy_updates_from_draft(draft)
    if not material_updates:
        return True
    prior_payload = prior.model_dump(mode="python")
    for key, value in material_updates.items():
        if _normalized_material_strategy_value(key, prior_payload.get(key)) != value:
            return False
    return (
        response.task_relation == "refine"
        or request.current_user_message.strip()
        not in {
            str(prior.raw_user_phrasing or "").strip(),
            str(prior.strategy_thesis or "").strip(),
        }
    )


def _material_strategy_updates_from_draft(
    draft: LLMStrategyDraft,
) -> dict[str, Any]:
    payload = draft.model_dump(mode="python")
    material_fields = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "timeframe",
        "cadence",
        "entry_logic",
        "exit_logic",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "risk_rules",
        "comparison_baseline",
        "entry_rule",
        "exit_rule",
        "rule_spec",
    }
    updates = {
        key: _normalized_material_strategy_value(key, value)
        for key, value in payload.items()
        if key in material_fields and value not in (None, "", [], {})
    }
    if "date_range" not in updates and draft.date_range_intent is not None:
        intent_resolution = resolve_date_range_intent(draft.date_range_intent)
        if intent_resolution is not None:
            updates["date_range"] = _normalized_material_date_range_payload(
                intent_resolution.payload
            )
    indicator_updates = {
        key: payload.get(key)
        for key in {
            "indicator",
            "indicator_period",
            "entry_threshold",
            "exit_threshold",
        }
        if payload.get(key) is not None
    }
    if indicator_updates:
        updates["indicator_parameters"] = indicator_updates
    return updates


def _normalized_material_strategy_value(key: str, value: Any) -> Any:
    if key == "date_range":
        return _normalized_material_date_range_payload(value)
    if key == "asset_universe" and isinstance(value, list):
        return [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]
    return value


def _normalized_material_date_range_payload(value: Any) -> Any:
    normalized = normalize_date_range_candidate(value)
    if isinstance(normalized, str):
        natural = resolve_date_range_text(normalized)
        if natural is not None:
            return ("resolved", natural.start.isoformat(), natural.end.isoformat())
    try:
        resolved = resolve_date_range(normalized)
    except Exception:
        return normalized
    if resolved.used_default and isinstance(normalized, str) and normalized.strip():
        return (
            "unresolved_default",
            resolved.start.isoformat(),
            resolved.end.isoformat(),
        )
    return ("resolved", resolved.start.isoformat(), resolved.end.isoformat())


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


def _request_has_latest_result(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    return bool(snapshot and snapshot.latest_backtest_result_reference is not None)


def _request_has_active_strategy_context(request: InterpretationRequest) -> bool:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    return bool(
        snapshot.pending_strategy_summary
        or snapshot.confirmed_strategy_summary
        or snapshot.active_confirmation_reference
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


def _strategy_from_llm(draft: LLMStrategyDraft) -> StrategySummary:
    payload = draft.model_dump(mode="python")
    field_provenance = payload.pop("field_provenance", {}) or {}
    language = _clean_optional_text(payload.pop("language", None))
    date_range_raw_text = _clean_optional_text(payload.pop("date_range_raw_text", None))
    date_range_intent = _clean_date_range_intent_payload(
        payload.pop("date_range_intent", None)
    )
    evidence_spans = _clean_evidence_spans(payload.pop("evidence_spans", {}) or {})
    if not date_range_intent:
        date_range_intent = _date_range_intent_from_bounded_evidence(draft)
    initial_capital = payload.pop("initial_capital", None)
    total_capital = payload.pop("total_capital", None)
    recurring_contribution = payload.pop("recurring_contribution", None)
    initial_capital = _grounded_initial_capital(
        initial_capital,
        field_provenance=field_provenance,
    )
    total_capital = _grounded_total_capital(
        total_capital,
        field_provenance=field_provenance,
    )
    recurring_contribution = _grounded_recurring_contribution(
        recurring_contribution,
        field_provenance=field_provenance,
    )
    indicator_parameters = {
        key: value
        for key, value in {
            "indicator": payload.pop("indicator", None),
            "indicator_period": payload.pop("indicator_period", None),
            "entry_threshold": payload.pop("entry_threshold", None),
            "exit_threshold": payload.pop("exit_threshold", None),
        }.items()
        if value is not None
    }
    if indicator_parameters:
        extra_parameters = payload.setdefault("extra_parameters", {})
        if indicator_parameters.get("indicator") is not None:
            extra_parameters["indicator"] = indicator_parameters["indicator"]
        merged_indicator_parameters = dict(
            extra_parameters.get("indicator_parameters") or {}
        )
        merged_indicator_parameters.update(indicator_parameters)
        extra_parameters["indicator_parameters"] = merged_indicator_parameters
    capital_parameters = {
        "initial_capital": initial_capital,
        "total_capital": total_capital,
        "recurring_contribution": recurring_contribution,
    }
    if any(value is not None for value in capital_parameters.values()):
        extra_parameters = payload.setdefault("extra_parameters", {})
        for key, value in capital_parameters.items():
            if value is not None:
                extra_parameters[key] = value
        if payload.get("capital_amount") is None and recurring_contribution is not None:
            payload["capital_amount"] = recurring_contribution
        if payload.get("capital_amount") is None:
            starting_capital = _non_dca_starting_capital_from_total_fields(
                payload=payload,
                initial_capital=initial_capital,
                total_capital=total_capital,
            )
            if starting_capital is not None:
                payload["capital_amount"] = starting_capital
                field_provenance["capital_amount"] = "starting_capital"
    if field_provenance:
        payload.setdefault("extra_parameters", {})["field_provenance"] = dict(
            field_provenance
        )
    if language:
        payload.setdefault("extra_parameters", {})["language"] = language
    if date_range_raw_text:
        payload.setdefault("extra_parameters", {})["date_range_raw_text"] = (
            date_range_raw_text
        )
    if date_range_intent:
        payload.setdefault("extra_parameters", {})["date_range_intent"] = (
            date_range_intent
        )
    if evidence_spans:
        payload.setdefault("extra_parameters", {})["evidence_spans"] = evidence_spans
    _normalize_llm_domain_slots(payload)
    field_provenance = _evidence_backed_field_provenance(
        payload=payload,
        field_provenance=field_provenance,
        evidence_spans=evidence_spans,
    )
    if field_provenance:
        payload.setdefault("extra_parameters", {})["field_provenance"] = dict(
            field_provenance
        )
    payload["date_range"] = normalize_date_range_candidate(
        payload.get("date_range"),
        raw_user_phrasing=payload.get("raw_user_phrasing"),
    )
    if date_range_intent:
        intent_resolution = resolve_date_range_intent(date_range_intent)
        intent_kind = str(date_range_intent.get("kind") or "").strip()
        if intent_resolution is not None and (
            intent_kind != "endpoint_patch"
            or not _has_complete_date_range_payload(payload["date_range"])
        ):
            payload["date_range"] = intent_resolution.payload
    if draft.strategy_type:
        payload.setdefault("extra_parameters", {})["raw_strategy_type"] = (
            draft.strategy_type
        )
    payload["risk_rules"] = [
        rule.model_dump(mode="python") if isinstance(rule, LLMRiskRule) else rule
        for rule in draft.risk_rules
    ]
    return StrategySummary.model_validate(payload)


def _evidence_backed_field_provenance(
    *,
    payload: dict[str, Any],
    field_provenance: dict[str, Any],
    evidence_spans: dict[str, str],
) -> dict[str, Any]:
    updated = dict(field_provenance or {})
    evidence_backed_fields = {
        "cadence": "explicit_user",
        "comparison_baseline": "explicit_user",
        "timeframe": "explicit_user",
    }
    for field_name, source in evidence_backed_fields.items():
        if field_name in updated:
            continue
        if field_name not in evidence_spans:
            continue
        if payload.get(field_name) in (None, "", [], {}):
            continue
        updated[field_name] = source
    return updated


def _normalize_llm_domain_slots(payload: dict[str, Any]) -> None:
    strategy_type = canonical_strategy_type(
        payload.get("strategy_type"),
        cadence=payload.get("cadence"),
    )
    if strategy_type != "dca_accumulation":
        return
    raw_cadence = payload.get("cadence")
    if raw_cadence in (None, "", [], {}):
        return
    cadence = _supported_dca_cadence_value(raw_cadence)
    if cadence is None:
        payload.setdefault("extra_parameters", {})["raw_cadence"] = raw_cadence
        payload["cadence"] = None
        return
    payload["cadence"] = cadence
    extra_parameters = payload.setdefault("extra_parameters", {})
    extra_parameters["recurring_cadence"] = cadence


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_evidence_spans(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, span in value.items():
        normalized_key = str(key or "").strip()
        normalized_span = str(span or "").strip()
        if normalized_key and normalized_span:
            cleaned[normalized_key] = normalized_span
    return cleaned


def _clean_date_range_intent_payload(value: Any) -> dict[str, Any]:
    if value in (None, "", [], {}):
        return {}
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        return dict(dumped) if isinstance(dumped, dict) else {}
    return {}


def _has_complete_date_range_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start = value.get("start") or value.get("from")
    end = value.get("end") or value.get("to")
    return bool(start not in (None, "", [], {}) and end not in (None, "", [], {}))


def _date_range_from_intent_or_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
) -> dict[str, str] | None:
    intent_resolution = resolve_date_range_intent(draft.date_range_intent)
    if intent_resolution is not None:
        return intent_resolution.payload
    bounded = _date_range_from_bounded_evidence(draft, language=language)
    if bounded is not None:
        return bounded
    return None


def _date_range_from_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
) -> dict[str, str] | None:
    evidence_candidates = _bounded_date_evidence_candidates(draft)
    if not evidence_candidates:
        return None
    language_candidates = _natural_time_language_candidates_from_hints(
        draft.language,
        language,
    )
    for candidate in evidence_candidates:
        for languages in language_candidates:
            resolved = resolve_date_range_text(candidate, languages=languages)
            if resolved is not None:
                return resolved.payload
    return None


def _date_range_intent_from_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
) -> dict[str, Any]:
    evidence_candidates = _bounded_date_evidence_candidates(draft)
    if not evidence_candidates:
        return {}
    language_candidates = _natural_time_language_candidates_from_hints(
        draft.language,
        language,
    )
    for candidate in evidence_candidates:
        for languages in language_candidates:
            intent = resolve_rolling_window_intent_text(
                candidate,
                languages=languages,
            )
            if intent is not None:
                return intent
    return {}


def _bounded_date_evidence_candidates(draft: LLMStrategyDraft) -> list[str]:
    candidates: list[str] = []
    if draft.date_range_raw_text:
        candidates.append(draft.date_range_raw_text)
    evidence_spans = _draft_semantic_evidence_spans(draft)
    for key in _DATE_EVIDENCE_SPAN_KEYS:
        value = evidence_spans.get(key)
        if value:
            candidates.append(value)
    return list(dict.fromkeys(str(item).strip() for item in candidates if str(item).strip()))


def _non_dca_starting_capital_from_total_fields(
    *,
    payload: dict[str, Any],
    initial_capital: Any,
    total_capital: Any,
) -> Any:
    if canonical_strategy_type(payload.get("strategy_type")) == "dca_accumulation":
        return None
    return initial_capital if initial_capital is not None else total_capital


def _grounded_initial_capital(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if _capital_source(field_provenance, "initial_capital") in _TOTAL_CAPITAL_SOURCES:
        return value
    if _capital_source(field_provenance, "capital_amount") in _TOTAL_CAPITAL_SOURCES:
        return value
    return None


def _grounded_total_capital(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if _capital_source(field_provenance, "total_capital") in _TOTAL_CAPITAL_SOURCES:
        return value
    if _capital_source(field_provenance, "capital_amount") in _TOTAL_CAPITAL_SOURCES:
        return value
    return None


def _grounded_recurring_contribution(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if (
        _capital_source(field_provenance, "recurring_contribution")
        in _RECURRING_CAPITAL_SOURCES
    ):
        return value
    if _capital_source(field_provenance, "capital_amount") in _RECURRING_CAPITAL_SOURCES:
        return value
    return None


def _capital_source(field_provenance: dict[str, str], key: str) -> str:
    if not isinstance(field_provenance, dict):
        return ""
    return str(field_provenance.get(key) or "").strip()


_TOTAL_CAPITAL_SOURCES = {
    "user",
    "explicit_user",
    "prior",
    "initial_capital",
    "starting_capital",
    "starting_principal",
    "initial_lump_sum",
    "initial_lump",
    "lump_sum",
    "total_capital",
    "total_budget",
    "max_budget",
    "investment_budget",
    "cap",
    "contribution_cap",
    "capital_cap",
    "investment_cap",
}

_RECURRING_CAPITAL_SOURCES = {
    "user",
    "explicit_user",
    "prior",
    "recurring_contribution",
    "contribution_amount",
    "periodic_contribution",
    "dca_contribution",
}


def _ground_strategy_in_current_turn(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> None:
    current_message = request.current_user_message.strip()
    if current_message:
        strategy.raw_user_phrasing = current_message
        if not strategy.strategy_thesis:
            strategy.strategy_thesis = current_message
        strategy.date_range = normalize_date_range_candidate(
            strategy.date_range,
            raw_user_phrasing=current_message,
        )


def _merge_prior_strategy(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
    response: LLMInterpretationResponse,
) -> None:
    del strategy, request, response
    return None


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
    resolution_provenance = []
    for index, symbol in enumerate(symbols):
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


def _ensure_dca_missing_execution_fields(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
) -> None:
    missing = list(response.missing_required_fields or [])
    if strategy.capital_amount is None and "capital_amount" not in missing:
        missing.append("capital_amount")
    if strategy.cadence in (None, "", [], {}) and "cadence" not in missing:
        missing.append("cadence")
    response.missing_required_fields = missing


def _remove_unstated_model_defaults(strategy: StrategySummary) -> None:
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    capital_source = str(field_provenance.get("capital_amount") or "").strip()
    if capital_source in {
        "default",
        "default_assumption",
        "assumed_default",
        "model_default",
    }:
        strategy.capital_amount = None
        if strategy.sizing_mode in {"fixed", "capital_amount"}:
            strategy.sizing_mode = None
        field_provenance.pop("capital_amount", None)
    position_source = str(field_provenance.get("position_size") or "").strip()
    if strategy.position_size == 1.0 and position_source in {
        "",
        "default",
        "default_assumption",
        "assumed_default",
        "model_default",
    }:
        strategy.position_size = None
        if strategy.sizing_mode in {"fixed", "position_size"}:
            strategy.sizing_mode = None
    strategy.risk_rules = [
        rule
        for rule in strategy.risk_rules
        if not _risk_rule_is_unstated_full_position_default(rule)
    ]
    if field_provenance:
        strategy.extra_parameters["field_provenance"] = dict(field_provenance)
    else:
        strategy.extra_parameters.pop("field_provenance", None)


def _risk_rule_is_unstated_full_position_default(rule: Any) -> bool:
    payload = rule.model_dump(mode="python") if hasattr(rule, "model_dump") else rule
    if not isinstance(payload, dict):
        return False
    if payload.get("type") != "max_position_size":
        return False
    raw_value = payload.get("value_pct")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return False
    return value >= 100.0


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


def _validate_indicator_rule_support(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
) -> None:
    if executable_strategy_type(strategy) != "indicator_threshold":
        return
    if _strategy_has_executable_rule_semantics(strategy):
        response.unsupported_constraints = [
            item
            for item in response.unsupported_constraints
            if item.category != "unsupported_indicator_rule"
        ]


def _remove_stale_indicator_constraints(
    *,
    response: LLMInterpretationResponse,
    strategy: StrategySummary,
    current_message: str,
) -> None:
    del current_message
    if _strategy_has_rule_semantics(strategy):
        return
    response.unsupported_constraints = [
        item
        for item in response.unsupported_constraints
        if item.category != "unsupported_indicator_rule"
    ]


def _apply_executable_indicator_defaults(strategy: StrategySummary) -> None:
    indicator_key = _indicator_key_from_strategy(strategy)
    if indicator_key is None:
        return
    spec = executable_indicator_spec(indicator_key)
    if spec is None:
        return
    parameters = normalize_indicator_parameters(
        spec.key,
        {
            **_indicator_parameters_from_strategy(strategy),
            "indicator": spec.key,
        },
    )
    strategy.extra_parameters = {
        **strategy.extra_parameters,
        "indicator": spec.key,
        "indicator_parameters": parameters,
    }
    strategy.entry_logic = spec.format_threshold_rule(
        "entry",
        threshold=float(parameters["entry_threshold"]),
        period=int(parameters["indicator_period"]),
    )
    strategy.exit_logic = spec.format_threshold_rule(
        "exit",
        threshold=float(parameters["exit_threshold"]),
        period=int(parameters["indicator_period"]),
    )


def _apply_signal_strategy_defaults(strategy: StrategySummary) -> None:
    entry_rule = strategy_rule(strategy, "entry")
    rule_spec = executable_rule_spec_from_strategy(strategy)
    if entry_rule is None and rule_spec is None:
        return
    if strategy.entry_rule is None:
        strategy.entry_rule = entry_rule
    if strategy.exit_rule is None:
        strategy.exit_rule = strategy_rule(
            strategy, "exit"
        ) or opposite_moving_average_crossover_rule(entry_rule)
    strategy.extra_parameters = {
        **strategy.extra_parameters,
        "entry_rule": strategy.entry_rule,
        "exit_rule": strategy.exit_rule,
    }
    entry_text = describe_rule_spec(rule_spec, "entry") if rule_spec else None
    exit_text = describe_rule_spec(rule_spec, "exit") if rule_spec else None
    strategy.entry_logic = (
        entry_text
        or moving_average_crossover_text(strategy.entry_rule)
        or strategy.entry_logic
    )
    strategy.exit_logic = (
        exit_text
        or moving_average_crossover_text(strategy.exit_rule)
        or strategy.exit_logic
    )


def _dca_amount_has_user_provenance(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> bool:
    if strategy.capital_amount is None:
        return False
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        capital_source = field_provenance.get("capital_amount")
        if capital_source in {
            "user",
            "explicit_user",
            "prior",
            "recurring_contribution",
            "contribution_amount",
            "periodic_contribution",
            "dca_contribution",
        }:
            return True
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    return (
        prior is not None
        and prior.capital_amount is not None
        and strategy.capital_amount == prior.capital_amount
    )

def _dca_cadence_has_user_provenance(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> bool:
    cadence = str(strategy.cadence or "").strip().casefold()
    if not cadence:
        return False
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        cadence_source = field_provenance.get("cadence")
        if cadence_source in {"user", "explicit_user", "prior", "visible_draft"}:
            return True
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    return (
        prior is not None
        and prior.cadence not in (None, "", [], {})
        and str(prior.cadence).strip().casefold() == cadence
    )

def _strategy_has_indicator_parameters(strategy: StrategySummary) -> bool:
    return bool(_indicator_parameters_from_strategy(strategy))


def _strategy_has_rule_semantics(strategy: StrategySummary) -> bool:
    return bool(
        strategy.entry_logic
        or strategy.exit_logic
        or strategy.entry_rule
        or strategy.exit_rule
        or strategy.rule_spec
        or _indicator_parameters_from_strategy(strategy)
    )


def _strategy_has_executable_rule_semantics(strategy: StrategySummary) -> bool:
    return bool(
        strategy.entry_rule
        or strategy.exit_rule
        or strategy.rule_spec
        or _indicator_parameters_from_strategy(strategy)
    )


def _indicator_parameters_from_strategy(strategy: StrategySummary) -> dict[str, Any]:
    return canonical_indicator_parameters_from_strategy(strategy)


def _indicator_key_from_strategy(strategy: StrategySummary) -> str | None:
    raw_indicator = strategy.extra_parameters.get("indicator")
    if isinstance(raw_indicator, str) and raw_indicator.strip():
        return raw_indicator.strip()
    raw_parameters = strategy.extra_parameters.get("indicator_parameters")
    if isinstance(raw_parameters, dict):
        parameter_indicator = raw_parameters.get("indicator")
        if isinstance(parameter_indicator, str) and parameter_indicator.strip():
            return parameter_indicator.strip()
    return None


def _unsupported_from_llm(item: LLMUnsupportedConstraint) -> UnsupportedConstraint:
    explanation = item.explanation or (
        "That exact indicator rule is not executable yet, but Argus can reframe it "
        "into a supported historical test."
    )
    return UnsupportedConstraint(
        category=item.category,
        raw_value=item.raw_value,
        explanation=explanation,
        simplification_options=[
            SimplificationOption(
                label=_humanize_simplification_label(label), replacement_values={}
            )
            for label in item.simplification_labels
        ],
    )


def _humanize_simplification_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    labels = {
        "rsi_preset": "Use the supported RSI rule",
        "supported_rsi_strategy": "Use the supported RSI rule",
        "buy_and_hold": "Compare with buy and hold",
        "dca_accumulation": "Try recurring buys",
    }
    return labels.get(normalized, label.strip())


def _dedupe_resolution_provenance(
    items: list[ResolutionProvenance | dict[str, Any]],
) -> list[ResolutionProvenance]:
    return dedupe_resolution_provenance_items(items)
