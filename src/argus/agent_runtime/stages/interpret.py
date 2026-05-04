from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.extraction import (
    StrategyExtractionResult,
    extract_strategy_fields,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.signals.task_relation import ExtractedSignals, extract_signals
from argus.agent_runtime.state.models import (
    AmbiguousField,
    FieldExtractionStatus,
    IntentName,
    ResponseProfile,
    RunState,
    StrategySummary,
    TaskRelation,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    executable_strategy_type,
    normalize_date_range_candidate,
    resolve_date_range,
    strategy_can_be_approved,
)
from argus.domain.market_data import resolve_asset
from pydantic import BaseModel, Field

StageOutcome = Literal[
    "needs_clarification",
    "ready_for_confirmation",
    "await_user_reply",
    "await_approval",
    "approved_for_execution",
    "execution_succeeded",
    "execution_failed_recoverably",
    "execution_failed_terminally",
    "ready_to_respond",
    "end_run",
]
ArbitrationMode = Literal["deterministic", "structured_arbitration"]


class InterpretDecision(BaseModel):
    intent: IntentName
    task_relation: TaskRelation
    requires_clarification: bool
    user_goal_summary: str
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    optional_parameter_opportunity: list[str] = Field(default_factory=list)
    confidence: float
    arbitration_mode: ArbitrationMode = "deterministic"
    reason_codes: list[str] = Field(default_factory=list)
    effective_response_profile: ResponseProfile
    user_preference_overridden_for_turn: bool = False
    normalized_signals: dict[str, Any] = Field(default_factory=dict)
    field_status: dict[str, FieldExtractionStatus] = Field(default_factory=dict)
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)

    def to_patch(self) -> dict[str, Any]:
        return {
            "normalized_signals": self.normalized_signals,
            "intent": self.intent,
            "task_relation": self.task_relation,
            "requires_clarification": self.requires_clarification,
            "user_goal_summary": self.user_goal_summary,
            "candidate_strategy_draft": self.candidate_strategy_draft.model_dump(
                mode="python"
            ),
            "missing_required_fields": list(self.missing_required_fields),
            "optional_parameter_status": {
                "optional_parameter_opportunity": list(
                    self.optional_parameter_opportunity
                ),
                "user_preference_overridden_for_turn": (
                    self.user_preference_overridden_for_turn
                ),
                "confidence": self.confidence,
                "arbitration_mode": self.arbitration_mode,
                "ambiguous_fields": [
                    item.model_dump(mode="python") for item in self.ambiguous_fields
                ],
                "unsupported_constraints": [
                    item.model_dump(mode="python")
                    for item in self.unsupported_constraints
                ],
            },
            "effective_response_profile": self.effective_response_profile,
            "reason_codes": list(self.reason_codes),
            "field_status": dict(self.field_status),
            "ambiguous_fields": [
                item.model_dump(mode="python") for item in self.ambiguous_fields
            ],
            "unsupported_constraints": [
                item.model_dump(mode="python")
                for item in self.unsupported_constraints
            ],
        }


class StageResult(BaseModel):
    outcome: StageOutcome
    decision: InterpretDecision | None = None
    stage_patch: dict[str, Any] = Field(default_factory=dict)

    @property
    def patch(self) -> dict[str, Any]:
        patch = dict(self.stage_patch)
        if self.decision is not None:
            patch = {**self.decision.to_patch(), **patch}
        return patch


class ArbitrationRequest(BaseModel):
    current_user_message: str
    signals: ExtractedSignals
    latest_task_snapshot: TaskSnapshot | None = None


class ArbitrationDecision(BaseModel):
    intent: IntentName
    task_relation: TaskRelation
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class ArbitrationResolution(BaseModel):
    decision: ArbitrationDecision | None = None
    mode: ArbitrationMode = "deterministic"
    reason_codes: list[str] = Field(default_factory=list)
    unresolved: bool = False


class StructuredInterpretation(BaseModel):
    intent: IntentName
    task_relation: TaskRelation
    requires_clarification: bool = False
    user_goal_summary: str
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = 0.8
    reason_codes: list[str] = Field(default_factory=list)
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)


class InterpretationRequest(BaseModel):
    current_user_message: str
    recent_thread_history: list[Any] = Field(default_factory=list)
    latest_task_snapshot: TaskSnapshot | None = None
    user: UserState


class StructuredArbitrator(Protocol):
    def __call__(
        self,
        request: ArbitrationRequest,
    ) -> ArbitrationDecision | None: ...


class StructuredInterpreter(Protocol):
    def __call__(
        self,
        request: InterpretationRequest,
    ) -> StructuredInterpretation | None: ...


def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    structured_arbitrator: StructuredArbitrator | None = None,
    structured_interpreter: StructuredInterpreter | None = None,
) -> StageResult:
    capability_contract = build_default_capability_contract()
    snapshot = normalize_task_snapshot(latest_task_snapshot)

    approval_result = _approval_stage_result_if_applicable(
        state=state,
        user=user,
        snapshot=snapshot,
    )
    if approval_result is not None:
        return approval_result

    confirmation_action_result = _confirmation_edit_action_stage_result_if_applicable(
        state=state,
        user=user,
        snapshot=snapshot,
    )
    if confirmation_action_result is not None:
        return confirmation_action_result

    structured_result = _structured_stage_result(
        state=state,
        user=user,
        latest_task_snapshot=snapshot,
        structured_interpreter=structured_interpreter,
        capability_contract=capability_contract,
    )
    if structured_result is not None:
        return structured_result

    signals = extract_signals(
        message=state.current_user_message,
        latest_task_snapshot=snapshot,
    )
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=signals.response_profile_overrides,
    )
    arbitration_request = ArbitrationRequest(
        current_user_message=state.current_user_message,
        signals=signals,
        latest_task_snapshot=snapshot,
    )
    arbitration = resolve_gray_case_arbitration(
        request=arbitration_request,
        structured_arbitrator=structured_arbitrator,
    )
    preliminary_intent = resolve_intent(
        user=user,
        signals=signals,
        missing_required_fields=[],
        arbitration=arbitration,
    )
    preliminary_task_relation = resolve_task_relation(
        signals=signals,
        arbitration=arbitration,
    )
    extraction = extract_strategy_fields(
        state.current_user_message,
        capability_contract,
    )
    candidate_strategy = _candidate_strategy_for_turn(
        message=state.current_user_message,
        extraction=extraction,
        snapshot=snapshot,
        capability_contract=capability_contract,
    )
    missing_required_fields: list[str] = []
    if should_track_execution_requirements(
        intent=preliminary_intent,
        task_relation=preliminary_task_relation,
        signals=signals,
    ):
        missing_required_fields = missing_required_fields_for_strategy(
            candidate_strategy,
            extraction=extraction,
            contract=capability_contract,
        )
    intent = resolve_intent(
        user=user,
        signals=signals,
        missing_required_fields=missing_required_fields,
        arbitration=arbitration,
    )
    task_relation = resolve_task_relation(
        signals=signals,
        arbitration=arbitration,
    )
    requires_clarification = (
        intent == "beginner_guidance"
        or task_relation == "ambiguous"
        or bool(extraction.ambiguous_fields)
        or bool(extraction.unsupported_constraints)
        or (
            should_track_execution_requirements(
                intent=intent,
                task_relation=task_relation,
                signals=signals,
            )
            and bool(missing_required_fields)
        )
    )
    assistant_response = _direct_conversational_response(
        message=state.current_user_message,
        signals=signals,
        snapshot=snapshot,
    )
    if assistant_response is not None:
        intent = "conversation_followup"
        task_relation = "continue"
        requires_clarification = False
        missing_required_fields = []
    decision = InterpretDecision(
        intent=intent,
        task_relation=task_relation,
        requires_clarification=requires_clarification,
        user_goal_summary=build_user_goal_summary(
            intent=intent,
            task_relation=task_relation,
            signals=signals,
        ),
        candidate_strategy_draft=candidate_strategy,
        missing_required_fields=missing_required_fields,
        optional_parameter_opportunity=list(capability_contract.optional_defaults),
        confidence=resolve_confidence(
            signals=signals,
            requires_clarification=requires_clarification,
            arbitration=arbitration,
        ),
        arbitration_mode=arbitration.mode,
        reason_codes=merge_reason_codes(
            signals.reason_codes,
            extraction.reason_codes,
            arbitration.reason_codes,
            arbitration.decision.reason_codes
            if arbitration.decision is not None
            else [],
        ),
        effective_response_profile=effective_profile,
        user_preference_overridden_for_turn=has_response_profile_overrides(signals),
        normalized_signals=signals.to_patch_payload(),
        field_status=build_field_status_payload(extraction),
        ambiguous_fields=list(extraction.ambiguous_fields),
        unsupported_constraints=list(extraction.unsupported_constraints),
    )

    if assistant_response is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": assistant_response},
        )

    outcome: StageOutcome = "needs_clarification"
    if not requires_clarification:
        outcome = "ready_for_confirmation"

    return StageResult(outcome=outcome, decision=decision)


def build_candidate_strategy_from_extraction(
    extraction: StrategyExtractionResult,
) -> StrategySummary:
    strategy = StrategySummary()
    strategy.strategy_thesis = coerce_strategy_thesis(
        extraction.strategy_thesis.normalized_value
    )
    strategy.asset_universe = coerce_asset_universe(
        extraction.asset_universe.normalized_value
    )
    strategy.entry_logic = coerce_logic_clause(extraction.entry_logic.normalized_value)
    strategy.exit_logic = coerce_logic_clause(extraction.exit_logic.normalized_value)
    strategy.date_range = coerce_optional_string(extraction.date_range.normalized_value)
    return strategy


def _candidate_strategy_for_turn(
    *,
    message: str,
    extraction: StrategyExtractionResult,
    snapshot: TaskSnapshot | None,
    capability_contract: Any,
) -> StrategySummary:
    prior = (
        snapshot.pending_strategy_summary
        if snapshot is not None
        else None
    )
    strategy = prior.model_copy(deep=True) if prior is not None else StrategySummary()
    extracted = build_candidate_strategy_from_extraction(extraction)
    lowered = message.lower()
    extracted_symbols = list(extracted.asset_universe)

    if extracted_symbols:
        if prior is not None and _is_symbol_replacement(lowered):
            strategy.asset_universe = extracted_symbols
        elif prior is None:
            strategy.asset_universe = extracted_symbols
        else:
            strategy.asset_universe = extracted_symbols

    if extracted.strategy_thesis is not None and prior is None:
        strategy.strategy_thesis = extracted.strategy_thesis
    elif strategy.strategy_thesis is None:
        strategy.strategy_thesis = _fallback_thesis(message, strategy.asset_universe)

    if extracted.entry_logic is not None:
        strategy.entry_logic = extracted.entry_logic
    if extracted.exit_logic is not None:
        strategy.exit_logic = extracted.exit_logic
    if extracted.date_range is not None:
        strategy.date_range = normalize_date_range_candidate(
            extracted.date_range,
            raw_user_phrasing=message,
        )
    else:
        inferred_date_range = normalize_date_range_candidate(
            None,
            raw_user_phrasing=message,
        )
        if inferred_date_range is not None:
            strategy.date_range = inferred_date_range

    detected_type = _detect_strategy_type(message, strategy)
    if detected_type is not None:
        strategy.strategy_type = detected_type

    cadence = _detect_cadence(lowered)
    if cadence is not None:
        strategy.cadence = cadence
        if strategy.strategy_type is None or strategy.strategy_type == "buy_and_hold":
            strategy.strategy_type = "dca_accumulation"

    capital_amount = _detect_capital_amount(message)
    if capital_amount is not None:
        strategy.capital_amount = capital_amount
        strategy.sizing_mode = "capital_amount"

    risk_rules = _detect_risk_rules(message)
    if risk_rules:
        strategy.risk_rules = risk_rules

    if strategy.asset_universe:
        strategy.asset_class = _asset_class_for_symbols(strategy.asset_universe)

    executable_type = executable_strategy_type(strategy)
    if executable_type == "buy_and_hold":
        strategy.entry_logic = None
        strategy.exit_logic = None
        strategy.strategy_type = executable_type
    if executable_type == "dca_accumulation":
        strategy.entry_logic = None
        strategy.exit_logic = None
        strategy.strategy_type = executable_type
        if strategy.cadence is None:
            strategy.cadence = "monthly"
    if executable_type == "indicator_threshold":
        strategy.strategy_type = executable_type

    if strategy.raw_user_phrasing is None:
        strategy.raw_user_phrasing = message.strip()
    else:
        strategy.refinement_of = strategy.raw_user_phrasing
        strategy.raw_user_phrasing = message.strip()

    strategy.assumptions = _strategy_assumptions(strategy, capability_contract)
    return strategy


def missing_required_fields_for_strategy(
    strategy: StrategySummary,
    *,
    extraction: StrategyExtractionResult | None,
    contract: Any,
) -> list[str]:
    del extraction
    required = ["strategy_thesis", "asset_universe", "entry_logic", "exit_logic", "date_range"]
    strategy_type = executable_strategy_type(strategy)
    if strategy_type not in {"buy_and_hold", "dca_accumulation"}:
        pass
    else:
        required = ["strategy_thesis", "asset_universe", "date_range"]
    missing: list[str] = []
    payload = strategy.model_dump(mode="python")
    for field_name in required:
        if field_name not in contract.required_fields:
            continue
        value = payload.get(field_name)
        if isinstance(value, list):
            if not value:
                missing.append(field_name)
        elif value is None or value == "":
            missing.append(field_name)
    return missing


def _approval_stage_result_if_applicable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    del user
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    if not strategy_can_be_approved(snapshot.pending_strategy_summary):
        return None
    if not _is_approval_message(state.current_user_message):
        return None
    return StageResult(
        outcome="approved_for_execution",
        stage_patch={
            "intent": "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": False,
            "user_goal_summary": "User approved the pending backtest for execution.",
            "candidate_strategy_draft": snapshot.pending_strategy_summary.model_dump(
                mode="python"
            ),
            "confirmation_payload": {
                "strategy": snapshot.pending_strategy_summary.model_dump(mode="python"),
                "optional_parameters": {},
            },
        },
    )


def _confirmation_edit_action_stage_result_if_applicable(
    *,
    state: RunState,
    user: UserState,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None

    action = _confirmation_edit_action(state.current_user_message)
    if action is None:
        return None

    strategy = snapshot.pending_strategy_summary
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    prompts = {
        "date_range": (
            "What time period should I test instead? You can say something like "
            "'past 6 months', 'since 2021', or 'January 1, 2024 to today'."
        ),
        "asset_universe": (
            "Which asset should I use instead? You can give me the company name, "
            "crypto name, or ticker."
        ),
        "assumptions": (
            "Which assumption do you want to change: starting capital, bar timeframe, "
            "fees, or slippage?"
        ),
    }
    missing_fields = [action] if action in {"date_range", "asset_universe"} else []
    return StageResult(
        outcome="await_user_reply",
        decision=InterpretDecision(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=True,
            user_goal_summary=f"User wants to change the pending {action.replace('_', ' ')}.",
            candidate_strategy_draft=strategy,
            missing_required_fields=missing_fields,
            confidence=0.94,
            arbitration_mode="deterministic",
            reason_codes=["confirmation_action_chip"],
            effective_response_profile=effective_profile,
        ),
        stage_patch={
            "assistant_prompt": prompts[action],
            "requested_field": action if action != "assumptions" else None,
        },
    )


def _confirmation_edit_action(message: str) -> str | None:
    lowered = " ".join(message.lower().strip().split())
    if lowered in {
        "change the date range",
        "change dates",
        "change date",
        "edit dates",
        "edit date range",
    }:
        return "date_range"
    if lowered in {
        "use a different asset",
        "change asset",
        "change the asset",
        "edit asset",
        "switch asset",
    }:
        return "asset_universe"
    if lowered in {
        "change the assumptions",
        "change assumptions",
        "adjust assumptions",
        "edit assumptions",
    }:
        return "assumptions"
    return None


def _structured_stage_result(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | None,
    structured_interpreter: StructuredInterpreter | None,
    capability_contract: Any,
) -> StageResult | None:
    if structured_interpreter is None:
        return None
    interpretation = structured_interpreter(
        InterpretationRequest(
            current_user_message=state.current_user_message,
            recent_thread_history=list(state.recent_thread_history),
            latest_task_snapshot=latest_task_snapshot,
            user=user,
        )
    )
    if interpretation is None:
        return None

    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=None,
    )
    missing_required_fields = missing_required_fields_for_strategy(
        interpretation.candidate_strategy_draft,
        extraction=None,
        contract=capability_contract,
    )
    requires_clarification = bool(
        interpretation.requires_clarification
        or interpretation.ambiguous_fields
        or interpretation.unsupported_constraints
        or missing_required_fields
    )
    decision = InterpretDecision(
        intent=interpretation.intent,
        task_relation=interpretation.task_relation,
        requires_clarification=requires_clarification,
        user_goal_summary=interpretation.user_goal_summary,
        candidate_strategy_draft=interpretation.candidate_strategy_draft,
        missing_required_fields=missing_required_fields,
        optional_parameter_opportunity=list(capability_contract.optional_defaults),
        confidence=interpretation.confidence,
        arbitration_mode="structured_arbitration",
        reason_codes=["llm_interpreter_used", *interpretation.reason_codes],
        effective_response_profile=effective_profile,
        normalized_signals={},
        field_status={},
        ambiguous_fields=interpretation.ambiguous_fields,
        unsupported_constraints=interpretation.unsupported_constraints,
    )
    symbol_only_response = _symbol_only_strategy_response(
        message=state.current_user_message,
        strategy=interpretation.candidate_strategy_draft,
        assistant_response=interpretation.assistant_response,
    )
    if symbol_only_response is not None:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": symbol_only_response},
        )
    fragment_response = _fragment_strategy_response(
        message=state.current_user_message,
        strategy=interpretation.candidate_strategy_draft,
        assistant_response=interpretation.assistant_response,
    )
    if fragment_response is not None and not strategy_can_be_approved(
        interpretation.candidate_strategy_draft
    ):
        return StageResult(
            outcome="needs_clarification",
            decision=decision.model_copy(
                update={
                    "requires_clarification": True,
                    "missing_required_fields": ["entry_logic", "date_range"],
                    "ambiguous_fields": [
                        AmbiguousField(
                            field_name="entry_logic",
                            raw_value=_clean_fragment_label(fragment_response),
                            candidate_normalized_value=None,
                            reason_code="fragment_strategy_response",
                        )
                    ],
                }
            ),
            stage_patch={},
        )
    executable_without_clarification = bool(
        interpretation.intent in {"backtest_execution", "strategy_drafting"}
        and not requires_clarification
        and interpretation.candidate_strategy_draft.asset_universe
    )
    should_use_assistant_response = bool(
        interpretation.assistant_response
        and not executable_without_clarification
        and interpretation.intent not in {"backtest_execution", "strategy_drafting"}
    )
    if should_use_assistant_response:
        return StageResult(
            outcome="ready_to_respond",
            decision=decision,
            stage_patch={"assistant_response": interpretation.assistant_response},
        )
    return StageResult(
        outcome="needs_clarification" if requires_clarification else "ready_for_confirmation",
        decision=decision,
    )
def _direct_conversational_response(
    *,
    message: str,
    signals: ExtractedSignals,
    snapshot: TaskSnapshot | None,
) -> str | None:
    lowered = message.lower().strip()
    if re.search(r"\bwhat can you do\b", lowered):
        return (
            "I can help you turn plain-language investing ideas into backtests, "
            "explain concepts like RSI or DCA, and tell you where Argus has limits. "
            "For supported runs, I’ll confirm the strategy, run the backtest, and explain "
            "the result against the right benchmark."
        )
    if re.search(r"\bhow do i start\b|\bhelp me test an idea\b", lowered):
        return (
            "Start with the asset and the idea in normal language. For example: "
            "'Buy and hold Tesla over the last 2 years' or 'Invest $500 in Bitcoin "
            "every month since 2021.' I’ll only ask a follow-up if something material is missing."
        )
    if re.search(r"\bexplain rsi\b|\bwhat .*rsi\b", lowered):
        return (
            "RSI is a momentum gauge from 0 to 100. Traders often treat low readings, "
            "like below 30, as potentially oversold and high readings as potentially overbought. "
            "It is not a prediction by itself; it is a way to define a rule you can test."
        )
    if snapshot is not None and snapshot.pending_strategy_summary is not None:
        if re.search(r"\bwhat exactly are you testing\b|\bassumptions\b", lowered):
            strategy = snapshot.pending_strategy_summary
            return _strategy_summary_response(strategy)
    if signals.beginner_language_detected and not signals.detected_symbols:
        return (
            "Argus is for testing investing ideas without risking real money. "
            "You can ask a question, describe a strategy, or name an asset you want to learn about."
        )
    return None


def _symbol_only_strategy_response(
    *,
    message: str,
    strategy: StrategySummary,
    assistant_response: str | None,
) -> str | None:
    assets = list(strategy.asset_universe)
    if not assets:
        return None
    cleaned_message = message.strip().lower()
    asset_terms = {asset.lower() for asset in assets}
    asset_terms.update(_asset_name_aliases(assets))
    response_text = (assistant_response or "").strip().lower()
    looks_symbol_only = cleaned_message in asset_terms or response_text in asset_terms
    if not looks_symbol_only:
        return None
    asset_label = ", ".join(assets)
    return (
        f"I can work with {asset_label}. A few useful ways to start:\n\n"
        f"- Buy and hold {asset_label} over the last 2 years\n"
        f"- Invest a fixed amount into {asset_label} every month\n"
        f"- Test an RSI rule on {asset_label}, like buying when RSI drops below 30\n\n"
        "Tell me which direction you want, or just say 'simple' and I'll set up a basic buy-and-hold test for you to confirm."
    )


def _fragment_strategy_response(
    *,
    message: str,
    strategy: StrategySummary,
    assistant_response: str | None,
) -> str | None:
    del strategy
    if not assistant_response:
        return None
    words = assistant_response.strip().split()
    if len(words) > 5:
        return None
    lowered = message.lower()
    if not any(phrase in lowered for phrase in ["what if", "bought", "buy", "test"]):
        return None
    return assistant_response


def _clean_fragment_label(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped[0].lower() + stripped[1:]


def _asset_name_aliases(assets: list[str]) -> set[str]:
    aliases: set[str] = set()
    if "TSLA" in assets:
        aliases.add("tesla")
    if "NVDA" in assets:
        aliases.add("nvidia")
    if "BTC" in assets:
        aliases.update({"bitcoin", "btc"})
    if "ETH" in assets:
        aliases.update({"ethereum", "eth"})
    return aliases


def _strategy_summary_response(strategy: StrategySummary) -> str:
    assets = ", ".join(strategy.asset_universe) if strategy.asset_universe else "the asset"
    strategy_type = display_strategy_slug(strategy)
    date_range = (
        resolve_date_range(strategy.date_range).display
        if strategy.date_range
        else "the default recent period"
    )
    assumptions = " ".join(strategy.assumptions) if strategy.assumptions else (
        "Assumptions: long-only, daily bars by default, no fees or slippage unless stated."
    )
    return (
        f"I’m testing {assets} as a {strategy_type} over {date_range}. "
        f"{assumptions}"
    )


def _is_approval_message(message: str) -> bool:
    return bool(
        re.fullmatch(
            r"\s*(yes|yep|yeah|confirm|run it|run this|run backtest|run the backtest|start backtest|start the backtest|go|go ahead|execute|looks good)\s*[.!]?\s*",
            message,
            flags=re.IGNORECASE,
        )
    )


def _is_symbol_replacement(message: str) -> bool:
    return bool(re.search(r"\binstead\b|\buse\b.+\binstead\b|\bnot\b", message))


def _detect_strategy_type(message: str, strategy: StrategySummary) -> str | None:
    lowered = message.lower()
    if "buy and hold" in lowered or "buy-and-hold" in lowered:
        return "buy_and_hold"
    if re.search(r"\bdca\b|\bevery\s+(day|week|month|year)\b|\bweekly\b|\bmonthly\b", lowered):
        return "dca_accumulation"
    if strategy.entry_logic or strategy.exit_logic or "rsi" in lowered:
        return "indicator_threshold"
    return strategy.strategy_type


def _detect_cadence(message: str) -> str | None:
    if re.search(r"\bweekly\b|\bevery week\b", message):
        return "weekly"
    if re.search(r"\bmonthly\b|\bevery month\b", message):
        return "monthly"
    if re.search(r"\bdaily\b|\bevery day\b", message):
        return "daily"
    return None


def _detect_capital_amount(message: str) -> float | None:
    match = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)", message)
    if match is None:
        return None
    return float(match.group(1).replace(",", ""))


def _detect_risk_rules(message: str) -> list[dict[str, Any]]:
    lowered = message.lower()
    rules: list[dict[str, Any]] = []
    stop_match = re.search(r"(\d+(?:\.\d+)?)\s*percent\s+stop loss|(\d+(?:\.\d+)?)%\s+stop loss", lowered)
    if stop_match is not None:
        value = next(group for group in stop_match.groups() if group is not None)
        rules.append({"type": "stop_loss", "value_pct": float(value)})
    take_profit_match = re.search(
        r"take profit at\s+(\d+(?:\.\d+)?)\s*percent|take profit at\s+(\d+(?:\.\d+)?)%",
        lowered,
    )
    if take_profit_match is not None:
        value = next(group for group in take_profit_match.groups() if group is not None)
        rules.append({"type": "take_profit", "value_pct": float(value)})
    return rules


def _asset_class_for_symbols(symbols: list[str]) -> str | None:
    classes = set()
    for symbol in symbols:
        try:
            classes.add(resolve_asset(symbol).asset_class)
        except Exception:
            continue
    if len(classes) == 1:
        return next(iter(classes))
    if len(classes) > 1:
        return "mixed"
    return "mixed"


def _fallback_thesis(message: str, asset_universe: list[str]) -> str | None:
    if not asset_universe:
        return None
    return message.strip()


def _strategy_assumptions(strategy: StrategySummary, capability_contract: Any) -> list[str]:
    del capability_contract
    assumptions = ["Long-only simulation.", "No fees or slippage unless explicitly supported."]
    if strategy.asset_class == "crypto":
        assumptions.append("Benchmark: BTC.")
    elif strategy.asset_class == "equity":
        assumptions.append("Benchmark: SPY.")
    if strategy.strategy_type == "dca_accumulation" and strategy.cadence:
        assumptions.append(f"Recurring contribution cadence: {strategy.cadence}.")
    return assumptions


def build_field_status_payload(
    extraction: StrategyExtractionResult,
) -> dict[str, FieldExtractionStatus]:
    return {
        "strategy_thesis": extraction.strategy_thesis.status,
        "asset_universe": extraction.asset_universe.status,
        "entry_logic": extraction.entry_logic.status,
        "exit_logic": extraction.exit_logic.status,
        "date_range": extraction.date_range.status,
    }


def extraction_field_status(
    extraction: StrategyExtractionResult,
    field_name: str,
) -> FieldExtractionStatus:
    return getattr(extraction, field_name).status


def coerce_strategy_thesis(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def coerce_asset_universe(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def coerce_optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def coerce_logic_clause(value: Any) -> str | None:
    normalized = coerce_optional_string(value)
    if normalized is None:
        return None
    return normalize_clause(strip_logic_prefix(normalized))


def resolve_intent(
    *,
    user: UserState,
    signals: ExtractedSignals,
    missing_required_fields: list[str],
    arbitration: ArbitrationResolution,
) -> IntentName:
    if arbitration.unresolved:
        return "conversation_followup"
    if arbitration.decision is not None:
        return arbitration.decision.intent
    if signals.beginner_language_detected or (
        user.expertise_level == "beginner" and not signals.detected_symbols
    ):
        return "beginner_guidance"
    if signals.symbols_changed:
        return "backtest_execution"
    if signals.backtest_request_detected or signals.detected_symbols:
        if missing_required_fields:
            return "strategy_drafting"
        return "backtest_execution"
    if signals.continuation_request_detected:
        return "conversation_followup"
    return "conversation_followup"


def resolve_task_relation(
    *,
    signals: ExtractedSignals,
    arbitration: ArbitrationResolution,
) -> TaskRelation:
    if arbitration.unresolved:
        return "ambiguous"
    if arbitration.decision is not None:
        return arbitration.decision.task_relation
    if signals.symbols_changed or signals.explicit_new_request:
        return "new_task"
    if signals.explicit_refinement_request:
        return "refine"
    if signals.continuation_request_detected:
        return "continue"
    if signals.backtest_request_detected or signals.detected_symbols:
        return "new_task"
    return "ambiguous"


def build_user_goal_summary(
    *,
    intent: str,
    task_relation: str,
    signals: ExtractedSignals,
) -> str:
    if intent == "beginner_guidance":
        return "User needs beginner-friendly guidance before defining an executable strategy."
    if signals.symbols_changed:
        return "User wants to start a new backtest with a different symbol set."
    if (
        intent == "backtest_execution"
        and task_relation == "new_task"
        and not signals.request_is_under_specified
    ):
        return "User is ready to confirm a new backtest with the supplied strategy details."
    if intent == "strategy_drafting" and signals.request_is_under_specified:
        return "User has a recognizable backtest goal but still needs strategy details."
    if task_relation == "continue":
        return "User is continuing the current conversation thread."
    return "User intent needs clarification."


def resolve_confidence(
    *,
    signals: ExtractedSignals,
    requires_clarification: bool,
    arbitration: ArbitrationResolution,
) -> float:
    if arbitration.decision is not None:
        return arbitration.decision.confidence
    if arbitration.unresolved:
        return 0.2
    if signals.beginner_language_detected or signals.symbols_changed:
        return 0.92
    if signals.request_is_under_specified:
        return 0.84
    if requires_clarification:
        return 0.5
    return 0.75


def arbitrate_gray_case(
    request: ArbitrationRequest,
) -> ArbitrationDecision | None:
    if not request.signals.gray_case_detected:
        return None

    return ArbitrationDecision(
        intent="conversation_followup",
        task_relation="ambiguous",
        confidence=0.35,
        reason_codes=["deterministic_gray_case_fallback"],
    )


def default_structured_arbitrator(
    request: ArbitrationRequest,
) -> ArbitrationDecision | None:
    if not request.signals.gray_case_detected:
        return None

    return ArbitrationDecision(
        intent="conversation_followup",
        task_relation="ambiguous",
        confidence=0.35,
        reason_codes=["default_structured_gray_case_decision"],
    )


def resolve_gray_case_arbitration(
    *,
    request: ArbitrationRequest,
    structured_arbitrator: StructuredArbitrator | None,
) -> ArbitrationResolution:
    if not request.signals.gray_case_detected:
        return ArbitrationResolution()

    active_arbitrator = structured_arbitrator or default_structured_arbitrator
    if active_arbitrator is not None:
        decision = active_arbitrator(request)
        if decision is None:
            return ArbitrationResolution(
                mode="structured_arbitration",
                reason_codes=["structured_arbitration_unresolved"],
                unresolved=True,
            )
        return ArbitrationResolution(
            decision=decision,
            mode="structured_arbitration",
            reason_codes=["structured_arbitration_used"],
        )

    return ArbitrationResolution(
        decision=arbitrate_gray_case(request),
        mode="deterministic",
        reason_codes=["deterministic_fallback_used"],
    )


def normalize_task_snapshot(
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
) -> TaskSnapshot | None:
    if latest_task_snapshot is None:
        return None
    if isinstance(latest_task_snapshot, TaskSnapshot):
        return latest_task_snapshot
    return TaskSnapshot.model_validate(latest_task_snapshot)


def has_response_profile_overrides(signals: ExtractedSignals) -> bool:
    overrides = signals.response_profile_overrides
    return any(
        value is not None
        for value in (
            overrides.tone,
            overrides.verbosity,
            overrides.expertise_mode,
        )
    )


def should_track_execution_requirements(
    *,
    intent: IntentName,
    task_relation: TaskRelation,
    signals: ExtractedSignals,
) -> bool:
    if intent in {"strategy_drafting", "backtest_execution"}:
        return True
    return bool(
        task_relation != "continue"
        and (signals.backtest_request_detected or signals.detected_symbols)
    )


def normalize_clause(clause: str) -> str | None:
    normalized = clause.strip(" .,:;")
    if not normalized:
        return None
    normalized = normalized[0].upper() + normalized[1:]
    normalized = re.sub(r"^Rsi\b", "RSI", normalized)
    return normalized


def strip_logic_prefix(clause: str) -> str:
    return re.sub(
        r"^(?:enter|exit)\s+when\s+",
        "",
        clause,
        count=1,
        flags=re.IGNORECASE,
    )


def merge_reason_codes(*reason_code_groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for reason_code_group in reason_code_groups:
        for reason_code in reason_code_group:
            if reason_code in seen:
                continue
            seen.add(reason_code)
            merged.append(reason_code)
    return merged
