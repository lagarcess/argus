from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    plan_artifact_assumption_edit,
)
from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMAmbiguousField,
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.resolution import (
    resolve_asset_candidate as runtime_resolve_asset_candidate,
)
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
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
    audit_signal_rule_grounding,
    repair_signal_rule_plan,
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
)
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type,
    executable_strategy_type_from_extracted_fields,
    normalize_date_range_candidate,
    resolve_date_range,
)
from argus.domain.backtesting.rules import (
    canonicalize_rule_spec,
    describe_rule_spec,
    explicit_signal_rule_intent_from_text,
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
    record_openrouter_route_receipt,
)

_DEFAULT_RESOLVE_ASSET = resolve_asset


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


class StatedRunFieldFidelityAudit(BaseModel):
    capital_amount: float | None = Field(
        default=None,
        description=(
            "Starting capital explicitly stated by the current user message, "
            "normalized as a number. Examples: 10k -> 10000, $500 -> 500. "
            "Leave null when the user did not state starting capital."
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
            "date. Leave null when the user did not state a date range."
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
    focus: ResultFollowupFocus | None = Field(
        default=None,
        description=(
            "Closest result follow-up focus when targets_latest_result is true."
        ),
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
            "Benchmark language matters: phrases like 'against SPY', 'versus QQQ', "
            "'compared with BTC', or 'beat the market' describe comparison_baseline "
            "or the benchmark, not additional assets to buy. Do not add benchmark "
            "symbols to asset_universe unless the user explicitly says to buy, hold, "
            "or test both as assets. When the user gives exact start/end dates, "
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
            "If the user explicitly says buy and hold, hold, or buy-and-hold, classify it as "
            "buy_and_hold even when the sentence also contains a start date like Jan 1. "
            "A start date is the backtest period, not entry logic.\n\n"
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
            "about a visible confirmation or draft should set semantic_turn_act="
            "result_followup and result_followup_focus=assumptions even when no "
            "completed run exists; use the active draft/card context instead of "
            "regenerating a new card. "
            "Set artifact_target to latest_result only when the current user message "
            "is actually about the latest completed run. Set artifact_target to "
            "pending_refinement when the user is answering a Refine strategy prompt. "
            "Set artifact_target to active_confirmation for visible draft/card "
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
            "clearly targets a visible result or current draft. "
            "Retry turns should preserve the failed action payload; do "
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
    suspicious_symbols = _suspicious_lowercase_asset_symbols(
        response=response,
        request=request,
    )
    if not suspicious_symbols:
        return response
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
    return _response_without_ungrounded_symbols(
        response=response,
        grounded_symbols=audit.grounded_symbols,
        reason_code="asset_grounding_audit_removed_unsubstantiated_symbols",
    )


def _suspicious_lowercase_asset_symbols(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[str]:
    symbols = [str(symbol).strip().upper() for symbol in response.candidate_strategy_draft.asset_universe if str(symbol).strip()]
    if not symbols:
        return []
    raw_tokens = set(request.current_user_message.translate(_ASSET_TOKEN_MAP).split())
    lower_tokens = {token.casefold() for token in raw_tokens}
    cashtag_tokens = {
        token.lstrip("$").casefold()
        for token in raw_tokens
        if token.startswith("$")
    }
    suspicious: list[str] = []
    for symbol in symbols:
        folded = symbol.casefold()
        if symbol in raw_tokens or f"${symbol}" in raw_tokens or folded in cashtag_tokens:
            continue
        if folded in lower_tokens:
            suspicious.append(symbol)
    return suspicious


def _response_without_ungrounded_symbols(
    *,
    response: LLMInterpretationResponse,
    grounded_symbols: list[str],
    reason_code: str,
) -> LLMInterpretationResponse:
    grounded = {symbol.strip().upper() for symbol in grounded_symbols if symbol.strip()}
    draft = response.candidate_strategy_draft.model_copy(deep=True)
    original_symbols = [str(symbol).strip().upper() for symbol in draft.asset_universe]
    draft.asset_universe = [symbol for symbol in original_symbols if symbol in grounded]
    if len(draft.asset_universe) == len(original_symbols):
        return response
    if not draft.asset_universe:
        draft.asset_class = None
    return response.model_copy(
        update={
            "candidate_strategy_draft": draft,
            "assistant_response": None,
            "reason_codes": list(
                dict.fromkeys([*response.reason_codes, reason_code])
            ),
        }
    )


_ASSET_TOKEN_MAP = str.maketrans(
    {char: " " for char in ".,;:!?()[]{}<>\"'`"}
)


def _asset_grounding_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    suspicious_symbols: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's asset-grounding audit. The interpreter extracted "
                "asset symbols that may have come from ordinary lowercase words in "
                "the current user message. Return only the extracted symbols that "
                "the user clearly intended as assets or tickers. Do not treat "
                "pronouns, helper words, verbs, or generic conversation words as "
                "assets. Keep a symbol when the user clearly named the company, "
                "asset, ticker, or cashtag. Do not invent new symbols."
            ),
        },
        {
            "role": "system",
            "content": f"Extracted symbols to audit: {suspicious_symbols}",
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
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    if pending_field.split("[", 1)[0] == "refinement":
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
    if pending_field.split("[", 1)[0] == "refinement":
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
    if (
        not isinstance(audit, DcaContributionRoleAudit)
        or audit.confidence < 0.65
        or audit.recurring_contribution_explicit
        or not audit.total_budget_not_recurring
    ):
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


async def _response_ready_for_runtime(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    response = _normalize_response_for_runtime_context(response, request=request)
    response = await _asset_grounding_audited_response(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    response = await _capability_side_question_audited_response(
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
    response = await _context_question_audited_response(
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
    audited_response = await _audit_stated_run_field_fidelity(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if audited_response is not None:
        response = audited_response
    grounded_response = await _audit_executable_strategy_grounding(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    if grounded_response is not None:
        response = grounded_response
    if _structured_interpretation_has_required_shape(response, request=request):
        return response

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
        planned_response = await _repair_incomplete_strategy_extraction(
            failed_response=response,
            preferred_model=preferred_model,
            request=request,
        )
    if planned_response is not None:
        return await _stated_run_field_audited_response(
            response=planned_response,
            preferred_model=preferred_model,
            request=request,
        )
    raise ValueError("OpenRouter interpretation returned an incomplete strategy draft")


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
    audited_response = await _audit_stated_run_field_fidelity(
        response=response,
        preferred_model=preferred_model,
        request=request,
    )
    return audited_response or response


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
            base_response=failed_response,
        )
        response = _normalize_response_for_runtime_context(response, request=request)
        response = await _signal_rule_checked_response(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        audited_response = await _audit_stated_run_field_fidelity(
            response=response,
            preferred_model=model_name,
            request=request,
        )
        if audited_response is not None:
            response = audited_response
        if _structured_interpretation_has_required_shape(response, request=request):
            return response
    return None


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
    requested_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).split("[", 1)[0]
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
    if plan.initial_capital is not None:
        draft.capital_amount = plan.initial_capital
        field_provenance["capital_amount"] = "starting_capital"
    if plan.timeframe is not None:
        draft.timeframe = plan.timeframe
    extra_parameters: dict[str, Any] = {}
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
                plan.user_goal_summary or "User changed a visible draft assumption."
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
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "signal_strategy":
        return False
    if draft.rule_spec or draft.entry_rule:
        return False
    if not (draft.raw_user_phrasing or draft.strategy_thesis):
        return False
    if not _has_explicit_signal_rule_intent(
        current_user_message,
        draft.raw_user_phrasing,
        draft.strategy_thesis,
    ):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return True
    if response.requires_clarification and response.assistant_response:
        return True
    return any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    )


def _has_explicit_signal_rule_intent(*values: str | None) -> bool:
    for value in values:
        if not value:
            continue
        try:
            if explicit_signal_rule_intent_from_text(value) is not None:
                return True
        except ValueError:
            continue
    return False


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
    draft = response.candidate_strategy_draft
    if draft.asset_universe:
        return response
    if not _llm_strategy_draft_has_non_asset_strategy_anchor(draft):
        return response
    assets = _resolved_asset_mentions_from_values(request.current_user_message)
    if not assets:
        return response
    repaired = response.model_copy(deep=True)
    repaired_draft = repaired.candidate_strategy_draft
    repaired_draft.asset_universe = [asset.canonical_symbol for asset in assets]
    asset_classes = {asset.asset_class for asset in assets}
    if len(asset_classes) == 1:
        repaired_draft.asset_class = next(iter(asset_classes))
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


def _resolved_asset_mentions_from_values(*values: str | None) -> list[Any]:
    resolved_assets: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        for asset in _resolved_asset_mentions_from_message(value):
            symbol = asset.canonical_symbol
            if symbol in seen:
                continue
            seen.add(symbol)
            resolved_assets.append(asset)
            if len(resolved_assets) >= 5:
                return resolved_assets
    return resolved_assets


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
    resolved_assets: list[Any] = []
    seen: set[str] = set()
    for phrase in _asset_candidate_phrases(message):
        try:
            resolution = _resolve_asset_candidate(
                phrase,
                field=f"asset_universe[{len(resolved_assets)}]",
                source="llm_extraction",
            )
        except ValueError:
            continue
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        if not _candidate_text_supports_resolved_asset(phrase, resolution.asset):
            continue
        symbol = resolution.asset.canonical_symbol
        if symbol in seen:
            continue
        seen.add(symbol)
        resolved_assets.append(resolution.asset)
        if len(resolved_assets) >= 5:
            break
    return resolved_assets


def _candidate_text_supports_resolved_asset(phrase: str, asset: Any) -> bool:
    candidate = str(phrase or "").strip()
    if not candidate:
        return False
    tokens = _asset_candidate_tokens(candidate)
    if not tokens:
        return False
    lowered_tokens = [token.lower() for token in tokens]
    symbol_texts = _asset_symbol_texts(asset)
    compact_candidate = _compact_asset_candidate(candidate)

    if len(tokens) != 1:
        name_words = set(_asset_name_tokens(getattr(asset, "name", "")))
        meaningful_tokens = [
            token
            for token in lowered_tokens
            if token not in _ASSET_CONTEXT_WORDS and len(token) >= 2
        ]
        if compact_candidate in symbol_texts and len(compact_candidate) >= 2:
            return True
        return bool(meaningful_tokens) and all(
            token in name_words for token in meaningful_tokens
        )

    token = tokens[0]
    lowered = token.lower()
    has_uppercase_signal = _token_has_uppercase_letter(token)
    if lowered in _ASSET_MENTION_NOISE_TOKENS and not has_uppercase_signal:
        return False
    compact_token = _compact_asset_candidate(token)
    if len(compact_token) < 2:
        return False

    name_words = {
        word
        for word in _asset_name_tokens(getattr(asset, "name", ""))
        if len(word) >= 3
    }
    if lowered in name_words:
        return True

    if has_uppercase_signal:
        return compact_token in symbol_texts and len(compact_token) >= 2
    if compact_token in symbol_texts and len(compact_token) >= 3:
        return True
    return False


_ASSET_CONTEXT_WORDS = {
    "asset",
    "coin",
    "company",
    "crypto",
    "equity",
    "etf",
    "pair",
    "share",
    "shares",
    "stock",
    "ticker",
    "token",
}

_ASSET_MENTION_NOISE_TOKENS = {
    "above",
    "bb",
    "below",
    "bollinger",
    "buy",
    "buying",
    "cross",
    "crossed",
    "crosses",
    "crossing",
    "day",
    "days",
    "ema",
    "for",
    "from",
    "hold",
    "holding",
    "last",
    "macd",
    "ma",
    "month",
    "months",
    "over",
    "past",
    "rsi",
    "sell",
    "selling",
    "sma",
    "the",
    "to",
    "today",
    "test",
    "under",
    "want",
    "week",
    "weeks",
    "when",
    "with",
    "year",
    "years",
}


def _asset_symbol_texts(asset: Any) -> set[str]:
    values = {
        str(getattr(asset, "canonical_symbol", "") or ""),
        str(getattr(asset, "raw_symbol", "") or ""),
    }
    return {
        compact
        for value in values
        if (compact := _compact_asset_candidate(value))
    }


def _compact_asset_candidate(value: str) -> str:
    compact: list[str] = []
    for char in str(value or "").lower():
        if char.isalnum():
            compact.append(char)
    return "".join(compact)


def _token_has_uppercase_letter(value: str) -> bool:
    return any(char.isalpha() and char.isupper() for char in str(value or ""))


def _asset_name_tokens(name: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in str(name or "").lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _asset_candidate_phrases(message: str) -> list[str]:
    tokens = _asset_candidate_tokens(message)
    phrases: list[str] = []
    seen: set[str] = set()
    max_window = min(3, len(tokens))
    for window_size in range(max_window, 0, -1):
        for start in range(0, len(tokens) - window_size + 1):
            phrase = " ".join(tokens[start : start + window_size]).strip()
            if not phrase or phrase in seen:
                continue
            if not any(char.isalpha() for char in phrase):
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


def _asset_candidate_tokens(message: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in str(message or ""):
        if char.isalnum() or char in {"/", "-"}:
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


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
    requested_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).split("[", 1)[0]
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
    requested_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).split("[", 1)[0]
    if requested_field:
        return False
    draft = response.candidate_strategy_draft
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
        response.semantic_turn_act in {None, "educational_question", "new_idea"}
    ):
        return True
    return False


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
    if _has_explicit_signal_rule_intent(
        draft.raw_user_phrasing,
        draft.strategy_thesis,
        draft.entry_logic,
        draft.exit_logic,
    ):
        return False
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
                "plumbing. Write assistant_response in warm, plain English, with short "
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
    if not _response_needs_stated_run_field_fidelity_audit(response=response):
        return None
    messages = _stated_run_field_fidelity_messages(
        response=response,
        request=request,
    )
    for model_name in _unique_repair_models(preferred_model):
        try:
            audit = await invoke_openrouter_json_schema(
                task="interpretation",
                messages=messages,
                schema_model=StatedRunFieldFidelityAudit,
                schema_name="StatedRunFieldFidelityAudit",
                model_name=model_name,
            )
        except Exception:
            continue
        if not isinstance(audit, StatedRunFieldFidelityAudit):
            continue
        repaired = _response_from_stated_run_field_fidelity_audit(
            response=response,
            audit=audit,
        )
        if repaired is not None:
            return repaired
    return None


def _response_needs_stated_run_field_fidelity_audit(
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
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    if not any(
        code in response.reason_codes
        for code in {
            "focused_strategy_extraction_repair",
            "signal_rule_plan_repair",
            "focused_repair_preserved_structured_context",
        }
    ):
        return _ready_response_has_unreconciled_stated_run_fields(draft)
    if "focused_repair_from_unsupported_context" in response.reason_codes:
        return draft.capital_amount is None
    if "signal_rule_plan_repair" in response.reason_codes:
        return any(
            [
                draft.capital_amount is None
                and _draft_contains_structured_capital_context(draft),
                _llm_value_is_empty(draft.timeframe)
                and _draft_contains_structured_timeframe_context(draft),
                _draft_contains_structured_date_context(draft),
            ]
        )
    return any(
        [
            draft.capital_amount is None
            and _draft_contains_structured_capital_context(draft),
            _llm_value_is_empty(draft.timeframe)
            and _draft_contains_structured_timeframe_context(draft),
            _draft_contains_structured_date_context(draft),
        ]
    )


def _ready_response_has_unreconciled_stated_run_fields(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            draft.capital_amount is None
            and _draft_contains_structured_capital_context(draft),
            _llm_value_is_empty(draft.timeframe)
            and _draft_contains_structured_timeframe_context(draft),
            _llm_value_is_empty(draft.date_range)
            and _draft_contains_structured_date_context(draft),
        ]
    )


def _draft_contains_structured_capital_context(draft: LLMStrategyDraft) -> bool:
    text = _structured_draft_context_text(draft)
    folded = text.casefold()
    if "$" in text or "usd" in folded or "dollar" in folded:
        return True
    for token in _field_fidelity_tokens(folded):
        if token.endswith("k") and any(character.isdigit() for character in token):
            return True
    return False


def _draft_contains_structured_timeframe_context(draft: LLMStrategyDraft) -> bool:
    text = _structured_draft_context_text(draft).casefold()
    return any(token in text for token in ("hour", "daily", "bars", "candles"))


def _draft_contains_structured_date_context(draft: LLMStrategyDraft) -> bool:
    text = _structured_draft_context_text(draft).casefold()
    return any(
        token in text
        for token in ("from", "since", "through", "until", "today", "year")
    )


def _field_fidelity_tokens(text: str) -> list[str]:
    separators = ",.;:!?()[]{}"
    cleaned = text
    for separator in separators:
        cleaned = cleaned.replace(separator, " ")
    return [token for token in cleaned.split() if token]


def _structured_draft_context_text(draft: LLMStrategyDraft) -> str:
    values = (
        draft.raw_user_phrasing,
        draft.strategy_thesis,
        draft.entry_logic,
        draft.exit_logic,
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
                        "latest_result_routing_audit",
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
        return response.result_followup_focus in (None, "general", "what_tested")
    if response.intent == "results_explanation":
        return False
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
                "latest-result context rather than a new strategy. Use "
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
                "for that field. Normalize starting capital such as 10k or $10,000 "
                "to 10000. Normalize one-hour/hourly bars to 1h, four-hour bars to "
                "4h, and daily bars to 1D. Preserve today/current as today or the "
                f"runtime date {date.today().isoformat()}. Return only JSON matching "
                "the schema."
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
) -> LLMInterpretationResponse | None:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    changed = False
    if audit.capital_amount is not None and draft.capital_amount != audit.capital_amount:
        draft.capital_amount = audit.capital_amount
        draft.field_provenance["capital_amount"] = "starting_capital"
        changed = True
    if audit.timeframe and draft.timeframe != audit.timeframe:
        draft.timeframe = audit.timeframe
        changed = True
    if audit.date_range not in (None, "", [], {}):
        date_range, date_changed = _date_range_with_fidelity_audit(
            current=draft.date_range,
            audited=audit.date_range,
        )
        if date_changed:
            draft.date_range = date_range
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
            extraction.capital_amount is not None,
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
    if response.semantic_turn_act == "unsupported_request":
        return (
            response.intent == "unsupported_or_out_of_scope"
            and not response.unsupported_constraints
        )
    return response.semantic_turn_act not in {
        "refine_current_idea",
        "answer_pending_need",
        "approval",
        "retry_failed_action",
        "result_followup",
    }


async def _focused_strategy_repair_after_candidate_failures(
    *,
    request: InterpretationRequest,
    preferred_model: str,
) -> LLMInterpretationResponse | None:
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
                "details. is_testable_strategy means the user is asking for a strategy "
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
                "canonicalize assets after interpretation. Natural date periods should "
                "be compact strings such as 'past 2 years' or 'last 3 months'. If the "
                "user gives a start date and says today, preserve the end as 'today' or "
                f"{date.today().isoformat()}, not a stale model date. Preserve "
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
                "a supported default. For explicit buy-and-hold ideas, set strategy_type "
                "to buy_and_hold."
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
    )
    if strategy_type is None:
        return LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary=extraction.user_goal_summary,
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message,
                strategy_thesis=extraction.strategy_thesis
                or extraction.user_goal_summary,
                asset_universe=list(extraction.asset_universe),
                asset_class=extraction.asset_class,
                timeframe=extraction.timeframe,
                date_range=extraction.date_range,
                capital_amount=extraction.capital_amount,
                entry_logic=entry_logic,
                exit_logic=exit_logic,
                indicator=extraction.indicator,
                indicator_period=extraction.indicator_period,
                entry_threshold=extraction.entry_threshold,
                exit_threshold=extraction.exit_threshold,
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
            strategy_type=strategy_type,
            strategy_thesis=extraction.strategy_thesis or extraction.user_goal_summary,
            asset_universe=list(extraction.asset_universe),
            asset_class=extraction.asset_class,
            timeframe=extraction.timeframe,
            date_range=extraction.date_range,
            capital_amount=extraction.capital_amount,
            entry_logic=entry_logic,
            exit_logic=exit_logic,
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
    return _merge_focused_repair_with_base(
        response=response,
        base_response=base_response,
    )


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
            "Do not include reasoning, markdown, prose, or omitted strategy fields "
            "for a strategy/backtest request. For an indicator-threshold request like "
            "'Backtest TSLA using RSI entry at 20 or lower and exit at 60 or higher "
            "over the last 3 months', the JSON must include candidate_strategy_draft "
            "with strategy_type='rsi_mean_reversion', asset_universe=['TSLA'], "
            "date_range='last 3 months', indicator='rsi', entry_threshold=20, "
            "and exit_threshold=60. For a moving-average crossover request, include "
            "candidate_strategy_draft.entry_rule as the typed moving_average_crossover "
            "object described above. For a MACD crossover request, include "
            "candidate_strategy_draft.rule_spec with the MACD line crossing its "
            "signal line using the default 12/26/9 parameters unless the user "
            "overrides them."
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


def _response_underfills_pending_result_refinement(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    requested_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).split("[", 1)[0]
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
    if strategy_type == "dca":
        return bool(draft.cadence)
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


def _strategy_from_llm(draft: LLMStrategyDraft) -> StrategySummary:
    payload = draft.model_dump(mode="python")
    field_provenance = payload.pop("field_provenance", {}) or {}
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
    payload["date_range"] = normalize_date_range_candidate(
        payload.get("date_range"),
        raw_user_phrasing=payload.get("raw_user_phrasing"),
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
    "total_capital",
    "total_budget",
    "max_budget",
    "investment_budget",
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
    if _message_contains_cadence_evidence(
        cadence=cadence,
        message=request.current_user_message,
    ):
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


def _message_contains_cadence_evidence(*, cadence: str, message: str) -> bool:
    words = set(_field_fidelity_tokens(message.casefold()))
    compact_message = "".join(
        char
        for char in message.casefold()
        if char.isalnum()
    )
    evidence_words = {
        "daily": {"daily", "day", "days"},
        "weekly": {"weekly", "week", "weeks"},
        "biweekly": {"biweekly", "bi-weekly"},
        "monthly": {"monthly", "month", "months"},
        "quarterly": {"quarterly", "quarter", "quarters"},
    }.get(cadence, {cadence})
    if words.intersection(evidence_words):
        return True
    return cadence.replace("-", "") in compact_message


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
