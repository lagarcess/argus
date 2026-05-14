from __future__ import annotations

import asyncio
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    ResultFollowupFocus,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ResolutionProvenance,
    ResolutionSource,
    ResponseProfileOverrides,
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
)
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import (
    build_openrouter_model,
    invoke_openrouter_json_schema,
    log_openrouter_failure,
    openrouter_structured_model_candidates,
    openrouter_task_timeout_seconds,
)

_DEFAULT_RESOLVE_ASSET = resolve_asset


class LLMRiskRule(BaseModel):
    type: str
    value_pct: float | None = None
    mode: str | None = None


class LLMStrategyDraft(BaseModel):
    raw_user_phrasing: str | None = None
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_class: str | None = None
    timeframe: str | None = None
    cadence: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    indicator: str | None = None
    indicator_period: int | None = None
    entry_threshold: float | None = None
    exit_threshold: float | None = None
    date_range: str | dict[str, str] | None = None
    sizing_mode: str | None = None
    capital_amount: float | None = None
    recurring_contribution: float | None = None
    initial_capital: float | None = None
    total_capital: float | None = None
    position_size: float | None = None
    risk_rules: list[LLMRiskRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    comparison_baseline: str | None = None
    refinement_of: str | None = None
    field_provenance: dict[str, str] = Field(default_factory=dict)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


class LLMUnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_labels: list[str] = Field(default_factory=list)


class LLMAmbiguousField(BaseModel):
    field_name: str
    raw_value: str
    candidate_normalized_value: Any | None = None
    reason_code: str


class LLMInterpretationResponse(BaseModel):
    intent: Literal[
        "beginner_guidance",
        "strategy_drafting",
        "backtest_execution",
        "results_explanation",
        "collection_management",
        "conversation_followup",
        "unsupported_or_out_of_scope",
    ]
    task_relation: Literal["new_task", "continue", "refine", "ambiguous"]
    requires_clarification: bool = False
    user_goal_summary: str
    candidate_strategy_draft: LLMStrategyDraft = Field(default_factory=LLMStrategyDraft)
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    uses_latest_result_context: bool | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    ambiguous_fields: list[LLMAmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[LLMUnsupportedConstraint] = Field(default_factory=list)
    response_profile_overrides: ResponseProfileOverrides = Field(
        default_factory=ResponseProfileOverrides
    )
    semantic_turn_act: (
        Literal[
            "new_idea",
            "answer_pending_need",
            "refine_current_idea",
            "educational_question",
            "result_followup",
            "retry_failed_action",
            "approval",
            "unsupported_request",
        ]
        | None
    ) = None
    result_followup_focus: ResultFollowupFocus | None = None


class FocusedStrategyExtraction(BaseModel):
    is_testable_strategy: bool
    requires_clarification: bool = False
    user_goal_summary: str
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    date_range: str | dict[str, str] | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    indicator: str | None = None
    indicator_period: int | None = None
    entry_threshold: float | None = None
    exit_threshold: float | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
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
            for index, candidate_model in enumerate(openrouter_structured_model_candidates()):
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
                    response = _normalize_response_for_runtime_context(
                        response,
                        request=request,
                    )
                    needs_artifact_context_repair = (
                        _response_needs_artifact_context_repair(response)
                    )
                    if needs_artifact_context_repair:
                        repaired_response = (
                            await _repair_incomplete_strategy_extraction(
                                failed_response=response,
                                preferred_model=candidate_model,
                                request=request,
                            )
                        )
                        if repaired_response is not None:
                            self.last_status = (
                                "used" if index == 0 else "fallback_used"
                            )
                            return self._to_runtime_interpretation(
                                repaired_response,
                                request=request,
                            )
                        raise ValueError(
                            "OpenRouter unsupported clarification omitted "
                            "recoverable artifact context"
                        )
                    if not _structured_interpretation_has_required_shape(
                        response,
                        request=request,
                    ):
                        repaired_response = await _repair_incomplete_artifact_patch(
                            model_name=candidate_model,
                            request=request,
                        )
                        if repaired_response is None:
                            repaired_response = (
                                await _repair_incomplete_strategy_extraction(
                                    failed_response=response,
                                    preferred_model=candidate_model,
                                    request=request,
                                )
                            )
                        if repaired_response is not None:
                            self.last_status = (
                                "used" if index == 0 else "fallback_used"
                            )
                            return self._to_runtime_interpretation(
                                repaired_response,
                                request=request,
                            )
                        raise ValueError(
                            "OpenRouter interpretation returned an incomplete "
                            "strategy draft"
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
            self.last_status = "failed"
            return None

        # 1. Try Primary Model
        model = build_openrouter_model("interpretation", model_name=self.model_name)
        if model:
            try:
                structured = model.with_structured_output(LLMInterpretationResponse)
                response = await asyncio.wait_for(
                    structured.ainvoke(messages),
                    timeout=openrouter_task_timeout_seconds("interpretation"),
                )
                if isinstance(response, LLMInterpretationResponse):
                    self.last_status = "used"
                    return self._to_runtime_interpretation(response, request=request)
            except Exception as exc:
                log_openrouter_failure(
                    task="interpretation",
                    model_name=self.model_name,
                    exc=exc,
                    message="Primary LLM interpretation failed; attempting fallback",
                )

        # 2. Try Fallback Model (if primary failed or was unavailable)
        from argus.llm.openrouter import resolve_openrouter_model

        fallback_model_name = resolve_openrouter_model(fallback=True)

        # Don't retry with the same model name if resolve returned the same thing
        primary_model_name = resolve_openrouter_model(self.model_name)
        if not fallback_model_name or fallback_model_name == primary_model_name:
            self.last_status = "failed"
            return None

        fallback_model = build_openrouter_model(
            "interpretation", model_name=fallback_model_name
        )
        if fallback_model:
            try:
                structured = fallback_model.with_structured_output(
                    LLMInterpretationResponse
                )
                response = await asyncio.wait_for(
                    structured.ainvoke(messages),
                    timeout=openrouter_task_timeout_seconds("interpretation"),
                )
                if isinstance(response, LLMInterpretationResponse):
                    self.last_status = "fallback_used"
                    return self._to_runtime_interpretation(response, request=request)
            except Exception as exc:
                self.last_status = "failed"
                log_openrouter_failure(
                    task="interpretation",
                    model_name=fallback_model_name,
                    exc=exc,
                    message="Fallback LLM interpretation failed",
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
                latest_failed_action = (
                    request.latest_task_snapshot.latest_failed_action_reference.model_dump(
                        mode="json"
                    )
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
                    f"{latest_failed_action if latest_failed_action else 'none'}"
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
            "When the user says something like 'buy Nvidia when the 50-day moving average "
            "crosses above the 200-day', classify it as signal_strategy, preserve "
            "the crossover as entry_logic, and default the exit to the same fast "
            "average crossing back below the slow average when the user leaves the "
            "exit unspecified. Do not ask what the buy trigger is.\n\n"
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
            "idea. "
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
            "For natural periods, return date_range as a normalized string when exact dates "
            "are not available, or as {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'} when the "
            "user provides exact dates. For recurring buys, extract cadence as daily, weekly, "
            "monthly, or yearly and never invent capital_amount. For DCA, capital_amount means "
            "the recurring contribution. If the user gives both a starting principal or total "
            "budget and a recurring contribution, put the recurring amount in capital_amount "
            "and put the starting principal in initial_capital or total_capital. If the user "
            "gives only a total budget, leave capital_amount null and set initial_capital or "
            "total_capital. When you set a recurring capital_amount, set "
            "field_provenance.capital_amount='recurring_contribution' only if the user "
            "explicitly stated that recurring contribution in the message; use "
            "'total_capital' when the number is merely a total budget, available cash, or "
            "starting principal.\n\n"
            "If the user explicitly says buy and hold, hold, or buy-and-hold, classify it as "
            "buy_and_hold even when the sentence also contains a start date like Jan 1. "
            "A start date is the backtest period, not entry logic.\n\n"
            "Clarify only when required meaning is missing, genuinely ambiguous, "
            "or unsupported in a way that requires the user to choose a simplification. "
            "Starting capital, timeframe, benchmark, fees, and slippage have safe defaults; "
            "do not ask for them before confirmation unless the user explicitly wants to change them. "
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
            "invent metrics. Assumption questions about a visible confirmation or "
            "draft should use the active draft/card context instead of regenerating "
            "a new card. Retry turns should preserve the failed action payload; do "
            "not reinterpret the original investing idea from scratch. "
            "Social turns are conversation_followup with assistant_response and no "
            "strategy draft unless they also contain a real investing idea. "
            "When the user explicitly asks for response style, verbosity, or expertise "
            "for this turn, set response_profile_overrides; do not rely on backend "
            "regex for those preferences.\n\n"
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
        )


async def _repair_incomplete_artifact_patch(
    *,
    model_name: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    messages = _focused_artifact_patch_messages(request)
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
    if not _structured_interpretation_has_required_shape(response, request=request):
        return None
    return response


async def _repair_incomplete_strategy_extraction(
    *,
    failed_response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _strategy_extraction_repair_is_allowed(failed_response):
        return None
    messages = _focused_strategy_extraction_messages(request)
    for model_name in _unique_repair_models(preferred_model):
        try:
            extraction = await invoke_openrouter_json_schema(
                task="interpretation",
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
        )
        response = _normalize_response_for_runtime_context(response, request=request)
        if _structured_interpretation_has_required_shape(response, request=request):
            return response
    return None


def _unique_repair_models(preferred_model: str) -> list[str]:
    candidates = [preferred_model, *openrouter_structured_model_candidates()]
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
    if response.intent != "unsupported_or_out_of_scope":
        return False
    if not response.requires_clarification:
        return False
    if _llm_strategy_draft_has_extractable_fields(response.candidate_strategy_draft):
        return False
    return bool(response.assistant_response)


def _focused_strategy_extraction_has_material_fields(
    extraction: FocusedStrategyExtraction,
) -> bool:
    if not extraction.is_testable_strategy:
        return bool(extraction.assistant_response)
    return any(
        [
            bool(extraction.strategy_type),
            bool(extraction.asset_universe),
            bool(extraction.date_range),
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
) -> bool:
    if response.task_relation == "refine":
        return False
    return response.semantic_turn_act not in {
        "refine_current_idea",
        "answer_pending_need",
        "approval",
        "retry_failed_action",
        "result_followup",
    }


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
                "details.\n\n"
                "Supported strategy_type values are buy_and_hold, dca_accumulation, "
                "rsi_mean_reversion, and signal_strategy. Normalize obvious company "
                "names or crypto names to common symbols when you are confident, such "
                "as Nvidia to NVDA, Apple to AAPL, Tesla to TSLA, Microsoft to MSFT, "
                "Bitcoin to BTC, and Ethereum to ETH. Natural date periods should be "
                "compact strings such as 'past 2 years' or 'last 3 months'.\n\n"
                "For moving-average crossovers, set strategy_type to signal_strategy "
                "and set entry_rule to {'type':'moving_average_crossover', "
                "'fast_indicator':'sma' or 'ema', 'fast_period':number, "
                "'slow_indicator':'sma' or 'ema', 'slow_period':number, "
                "'direction':'bullish' for crosses above or 'bearish' for crosses "
                "below}. If the user does not state an exit, leave exit_rule null "
                "and set exit_logic to the opposite crossover default.\n\n"
                "For RSI threshold ideas, set strategy_type to rsi_mean_reversion, "
                "indicator to rsi, indicator_period only when supplied, and threshold "
                "overrides as numbers. For explicit buy-and-hold ideas, set "
                "strategy_type to buy_and_hold."
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _response_from_focused_strategy_extraction(
    *,
    extraction: FocusedStrategyExtraction,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    strategy_type = _strategy_type_from_focused_extraction(extraction)
    if not extraction.is_testable_strategy and extraction.assistant_response:
        return LLMInterpretationResponse(
            intent="conversation_followup",
            task_relation="new_task",
            requires_clarification=extraction.requires_clarification,
            user_goal_summary=extraction.user_goal_summary,
            assistant_response=extraction.assistant_response,
            confidence=extraction.confidence,
            semantic_turn_act="educational_question",
        )
    return LLMInterpretationResponse(
        intent="strategy_drafting"
        if extraction.requires_clarification
        else "backtest_execution",
        task_relation="new_task",
        requires_clarification=extraction.requires_clarification,
        user_goal_summary=extraction.user_goal_summary,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=request.current_user_message,
            strategy_type=strategy_type,
            strategy_thesis=extraction.strategy_thesis or extraction.user_goal_summary,
            asset_universe=list(extraction.asset_universe),
            date_range=extraction.date_range,
            entry_logic=extraction.entry_logic,
            exit_logic=extraction.exit_logic,
            entry_rule=extraction.entry_rule,
            exit_rule=extraction.exit_rule,
            rule_spec=extraction.rule_spec,
            indicator=extraction.indicator,
            indicator_period=extraction.indicator_period,
            entry_threshold=extraction.entry_threshold,
            exit_threshold=extraction.exit_threshold,
        ),
        missing_required_fields=list(extraction.missing_required_fields),
        assistant_response=extraction.assistant_response,
        confidence=extraction.confidence,
        reason_codes=["focused_strategy_extraction_repair"],
        semantic_turn_act="new_idea",
    )


def _strategy_type_from_focused_extraction(
    extraction: FocusedStrategyExtraction,
) -> str | None:
    if extraction.entry_rule or extraction.rule_spec:
        return "signal_strategy"
    raw_strategy_type = str(extraction.strategy_type or "").strip().lower()
    strategy_type_aliases = {
        "buy_and_hold": "buy_and_hold",
        "buy-and-hold": "buy_and_hold",
        "dca_accumulation": "dca_accumulation",
        "dca": "dca_accumulation",
        "recurring_buy": "dca_accumulation",
        "recurring-buys": "dca_accumulation",
        "rsi_mean_reversion": "rsi_mean_reversion",
        "rsi_threshold": "rsi_mean_reversion",
        "indicator_threshold": "rsi_mean_reversion",
        "signal_strategy": "signal_strategy",
        "moving_average_crossover": "signal_strategy",
        "ma_crossover": "signal_strategy",
        "macd_crossover": "signal_strategy",
    }
    if raw_strategy_type in strategy_type_aliases:
        return strategy_type_aliases[raw_strategy_type]
    indicator = str(extraction.indicator or "").strip().lower()
    if indicator == "rsi" or (
        indicator
        and extraction.entry_threshold is not None
        and extraction.exit_threshold is not None
    ):
        return "rsi_mean_reversion"
    return None


def _focused_artifact_patch_messages(
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
                "Focused artifact patch repair. The previous interpretation replayed "
                "or under-filled the active artifact. Interpret only the current user "
                "message against the canonical prior artifact. The current user message "
                "is authoritative. Return a structured patch or answer; do not replay "
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
            "Do not include reasoning, markdown, prose, or omitted strategy fields "
            "for a strategy/backtest request. For an indicator-threshold request like "
            "'Backtest TSLA using RSI entry at 20 or lower and exit at 60 or higher "
            "over the last 3 months', the JSON must include candidate_strategy_draft "
            "with strategy_type='rsi_mean_reversion', asset_universe=['TSLA'], "
            "date_range='last 3 months', indicator='rsi', entry_threshold=20, "
            "and exit_threshold=60. For a moving-average crossover request, include "
            "candidate_strategy_draft.entry_rule as the typed moving_average_crossover "
            "object described above."
        )
    return wire_messages


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
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return True
    if response.semantic_turn_act == "approval":
        return True
    if response.requires_clarification and response.assistant_response:
        return True
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_extractable_fields(draft):
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
    if response.semantic_turn_act == "retry_failed_action":
        snapshot = request.latest_task_snapshot
        return bool(snapshot and snapshot.latest_failed_action_reference is not None)
    return False


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


def _response_replays_prior_strategy_without_current_turn_update(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
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
    return response.task_relation == "refine" or request.current_user_message.strip() not in {
        str(prior.raw_user_phrasing or "").strip(),
        str(prior.strategy_thesis or "").strip(),
    }


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
        normalized = normalize_date_range_candidate(value)
        try:
            resolved = resolve_date_range(normalized)
        except Exception:
            return normalized
        return (resolved.start.isoformat(), resolved.end.isoformat())
    if key == "asset_universe" and isinstance(value, list):
        return [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]
    return value


def _normalize_response_for_runtime_context(
    response: LLMInterpretationResponse,
    *,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    if _request_has_latest_result(request):
        return response
    if response.intent != "results_explanation":
        return response
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


def _strategy_from_llm(draft: LLMStrategyDraft) -> StrategySummary:
    payload = draft.model_dump(mode="python")
    field_provenance = payload.pop("field_provenance", {}) or {}
    initial_capital = payload.pop("initial_capital", None)
    total_capital = payload.pop("total_capital", None)
    recurring_contribution = payload.pop("recurring_contribution", None)
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
    if field_provenance:
        payload.setdefault("extra_parameters", {})["field_provenance"] = dict(
            field_provenance
        )
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
    payload["date_range"] = normalize_date_range_candidate(
        payload.get("date_range"),
    )
    if draft.strategy_type:
        payload.setdefault("extra_parameters", {})["raw_strategy_type"] = (
            draft.strategy_type
        )
    payload["risk_rules"] = [
        rule.model_dump(mode="python") if isinstance(rule, LLMRiskRule) else rule
        for rule in draft.risk_rules
    ]
    return StrategySummary.model_validate(payload)


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
    if canonical_type == "indicator_threshold":
        strategy.strategy_type = canonical_type
        _apply_executable_indicator_defaults(strategy)
    if canonical_type == "signal_strategy":
        strategy.strategy_type = canonical_type
        _apply_signal_strategy_defaults(strategy)
    if canonical_type == "dca_accumulation" and not strategy.cadence:
        strategy.cadence = "monthly"
    if (
        canonical_type == "dca_accumulation"
        and strategy.capital_amount is not None
        and not _dca_amount_has_user_provenance(strategy=strategy, request=request)
    ):
        strategy.capital_amount = None
        strategy.sizing_mode = None
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
    if entry_rule is None:
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
    if not strategy.entry_logic:
        strategy.entry_logic = moving_average_crossover_text(strategy.entry_rule)
    if not strategy.exit_logic:
        strategy.exit_logic = moving_average_crossover_text(strategy.exit_rule)


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
    explanation = item.explanation
    if (
        item.category == "unsupported_indicator_rule"
        and not explanation.lower().startswith("i understand")
    ):
        explanation = (
            "I understand the indicator rule, but "
            + explanation[0].lower()
            + explanation[1:]
            if explanation
            else "I understand the indicator rule, but Argus cannot execute that exact rule yet."
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
    items: list[ResolutionProvenance],
) -> list[ResolutionProvenance]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[ResolutionProvenance] = []
    for item in items:
        key = (item.field, item.raw_text, item.source, item.candidate_kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
