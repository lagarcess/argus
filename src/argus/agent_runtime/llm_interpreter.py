from __future__ import annotations

import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
)
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    explicit_buy_and_hold_requested,
    normalize_date_range_candidate,
)
from argus.domain.indicators import (
    detect_executable_indicator_key,
    executable_indicator_spec,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import build_openrouter_model, log_openrouter_failure


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
    date_range: str | dict[str, str] | None = None
    sizing_mode: str | None = None
    capital_amount: float | None = None
    position_size: float | None = None
    risk_rules: list[LLMRiskRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    comparison_baseline: str | None = None
    refinement_of: str | None = None
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


class OpenRouterStructuredInterpreter:
    def __init__(
        self,
        *,
        contract: CapabilityContract,
        model_name: str | None = None,
    ) -> None:
        self.contract = contract
        self.model_name = (
            model_name or os.getenv("AGENT_MODEL") or ("google/gemini-2.0-flash-001")
        )
        self.last_status: str | None = None

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation | None:
        model = build_openrouter_model("interpretation", model_name=self.model_name)
        if model is None:
            self.last_status = "missing_api_key"
            return None

        try:
            structured = model.with_structured_output(LLMInterpretationResponse)
            response = structured.invoke(self._messages(request))
        except Exception as exc:
            self.last_status = "failed"
            log_openrouter_failure(
                task="interpretation",
                model_name=self.model_name,
                exc=exc,
                message="LLM interpretation failed; falling back",
            )
            return None

        if not isinstance(response, LLMInterpretationResponse):
            self.last_status = "invalid_response"
            return None
        self.last_status = "used"
        return self._to_runtime_interpretation(response, request=request)

    def _messages(self, request: InterpretationRequest) -> list[dict[str, str]]:
        prior_strategy = None
        if request.latest_task_snapshot is not None:
            prior_strategy = (
                request.latest_task_snapshot.pending_strategy_summary
                or request.latest_task_snapshot.confirmed_strategy_summary
            )
        history = [
            {
                "role": item.role,
                "content": item.content,
            }
            for item in request.recent_thread_history[-6:]
            if hasattr(item, "role") and hasattr(item, "content")
        ]
        return [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "system",
                "content": (
                    f"User language preference: {request.user.language_preference}.\n"
                    f"Prior strategy JSON, if any: "
                    f"{prior_strategy.model_dump(mode='json') if prior_strategy else 'none'}"
                ),
            },
            *history,
            {"role": "user", "content": request.current_user_message},
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
            "dca_accumulation, and registry-backed indicator threshold rules are "
            "executable. RSI is executable with user-specified thresholds from 0 to "
            "100, a default period of 14, a default entry threshold of 30, and a "
            "default exit threshold of 55 when the user leaves one side unspecified. "
            "Moving-average crossovers, volume filters, price plus indicator "
            "confluence, and indicator rules without an executable registry spec can "
            "be understood and drafted, but are not executable yet unless the user "
            "chooses a supported simplification. Same asset class only; max 5 symbols; "
            "equity benchmark is "
            "SPY; crypto benchmark is BTC; no brokerage trading, shorting, mixed "
            "equity+crypto runs, custom scripting, or real slippage/fee realism.\n\n"
            "When the user says something like 'buy Nvidia when the 50-day moving average "
            "crosses above the 200-day', preserve that as entry_logic. Do not ask what "
            "the buy trigger is. Explain that the crossover is understood but not directly "
            "executable yet, then offer to keep drafting it or simplify to a supported run.\n\n"
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
            uses_latest_result_context=response.uses_latest_result_context,
        )


def _strategy_from_llm(draft: LLMStrategyDraft) -> StrategySummary:
    payload = draft.model_dump(mode="python")
    payload["date_range"] = normalize_date_range_candidate(
        payload.get("date_range"),
        raw_user_phrasing=payload.get("raw_user_phrasing"),
    )
    if explicit_buy_and_hold_requested(
        payload.get("raw_user_phrasing"),
        payload.get("strategy_thesis"),
    ):
        payload["strategy_type"] = "buy_and_hold"
        payload["entry_logic"] = None
        payload["exit_logic"] = None
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
            raw_user_phrasing=current_message,
        )
    if explicit_buy_and_hold_requested(
        current_message,
        strategy.strategy_thesis,
    ):
        strategy.strategy_type = "buy_and_hold"
        strategy.entry_logic = None
        strategy.exit_logic = None


def _merge_prior_strategy(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
    response: LLMInterpretationResponse,
) -> None:
    if request.latest_task_snapshot is None or response.task_relation != "refine":
        return
    if _current_turn_starts_fresh_strategy(request.current_user_message):
        response.task_relation = "new_task"
        if "semantic_boundary_new_strategy" not in response.reason_codes:
            response.reason_codes.append("semantic_boundary_new_strategy")
        return
    prior = (
        request.latest_task_snapshot.pending_strategy_summary
        or request.latest_task_snapshot.confirmed_strategy_summary
    )
    if prior is None:
        return
    merged = prior.model_copy(deep=True)
    incoming = strategy.model_dump(mode="python")
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        setattr(merged, key, value)
    for key, value in merged.model_dump(mode="python").items():
        setattr(strategy, key, value)


def _current_turn_starts_fresh_strategy(message: str) -> bool:
    lowered = " ".join(message.lower().strip().split())
    if not lowered:
        return False
    if re.search(r"\b(actually|instead|keep|same|change|modify|make that)\b", lowered):
        return False
    return bool(
        re.search(
            r"\b(what if|backtest|test|try|simulate|bought|buy|invest)\b",
            lowered,
        )
        and re.search(
            r"\b(after|when|every|over|since|from|hold|dca|rsi|dip|drops?)\b", lowered
        )
    )


def _validate_capability_boundaries(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> None:
    symbols = [symbol.upper() for symbol in strategy.asset_universe]
    strategy.asset_universe = symbols
    asset_classes = set()
    invalid_symbols: list[str] = []
    for symbol in symbols:
        try:
            resolved = resolve_asset(symbol)
        except Exception:
            invalid_symbols.append(symbol)
            continue
        asset_classes.add(resolved.asset_class)
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
                        "Argus Alpha cannot run equity and crypto together in one "
                        "simulation yet."
                    ),
                    simplification_labels=[
                        "Run separate equity and crypto tests",
                        "Run the equity symbols only",
                        "Run the crypto symbols only",
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
                    "available Alpaca asset universe for this run."
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
    if canonical_type == "dca_accumulation" and not strategy.cadence:
        strategy.cadence = "monthly"
    if (
        canonical_type == "dca_accumulation"
        and strategy.capital_amount is not None
        and not _dca_amount_has_user_provenance(strategy=strategy, request=request)
    ):
        strategy.capital_amount = None
        strategy.sizing_mode = None


def _validate_indicator_rule_support(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
) -> None:
    if executable_strategy_type(strategy) != "indicator_threshold":
        return
    combined_logic = " ".join(
        value
        for value in [strategy.entry_logic, strategy.exit_logic]
        if isinstance(value, str)
    ).lower()
    if _indicator_rule_is_registry_executable(combined_logic):
        response.unsupported_constraints = [
            item
            for item in response.unsupported_constraints
            if item.category != "unsupported_indicator_rule"
        ]
        return
    if not _contains_unsupported_indicator_terms(combined_logic):
        return
    if any(
        item.category == "unsupported_indicator_rule"
        for item in response.unsupported_constraints
    ):
        return
    response.unsupported_constraints.append(
        LLMUnsupportedConstraint(
            category="unsupported_indicator_rule",
            raw_value=combined_logic,
            explanation=(
                "I understand this as a custom indicator rule, but Argus Alpha "
                "cannot execute that exact moving-average or compound indicator "
                "logic yet."
            ),
            simplification_labels=[
                "Keep drafting the full crossover strategy",
                "Simplify to the supported RSI strategy",
                "Compare NVDA with buy and hold",
            ],
        )
    )


def _contains_unsupported_indicator_terms(text: str) -> bool:
    unsupported_terms = (
        "moving average",
        "sma",
        "ema",
        "crossover",
        "crosses above",
        "crosses below",
        "volume",
        "200-day",
        "50-day",
    )
    return any(term in text for term in unsupported_terms)


def _indicator_rule_is_registry_executable(text: str) -> bool:
    if not text:
        return False
    if _contains_unsupported_indicator_terms(text):
        return False
    key = detect_executable_indicator_key(text, default="rsi")
    return executable_indicator_spec(key) is not None


def _apply_executable_indicator_defaults(strategy: StrategySummary) -> None:
    combined_logic = " ".join(
        value
        for value in (strategy.entry_logic, strategy.exit_logic, strategy.strategy_thesis)
        if isinstance(value, str)
    )
    indicator_key = detect_executable_indicator_key(combined_logic, default="rsi")
    spec = executable_indicator_spec(indicator_key)
    if spec is None:
        return
    if strategy.entry_logic and not strategy.exit_logic:
        strategy.exit_logic = spec.format_threshold_rule("exit")


def _dca_amount_has_user_provenance(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> bool:
    current_text = " ".join(
        value
        for value in [request.current_user_message, strategy.raw_user_phrasing]
        if isinstance(value, str)
    )
    if _text_contains_amount(current_text):
        return True
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    return prior is not None and prior.capital_amount is not None


def _text_contains_amount(text: str) -> bool:
    lowered = text.lower()
    if re.search(
        r"\$\s*\d|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:dollars?|bucks?|usd|k|m)\b", lowered
    ):
        return True
    return bool(
        re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|"
            r"hundred|thousand|million)\b.+\b(dollars?|bucks?|usd)\b",
            lowered,
        )
    )


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
