from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.profile.response_profile import resolve_effective_response_profile
from argus.agent_runtime.signals.task_relation import ExtractedSignals, extract_signals
from argus.agent_runtime.state.models import (
    IntentName,
    ResponseProfile,
    RunState,
    StrategySummary,
    TaskRelation,
    TaskSnapshot,
    UserState,
)

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
            },
            "effective_response_profile": self.effective_response_profile,
            "reason_codes": list(self.reason_codes),
        }


class StageResult(BaseModel):
    outcome: StageOutcome
    decision: InterpretDecision | None = None
    stage_patch: dict[str, Any] = Field(default_factory=dict)

    @property
    def patch(self) -> dict[str, Any]:
        if self.decision is not None:
            return self.decision.to_patch()
        return dict(self.stage_patch)


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


class StructuredArbitrator(Protocol):
    def __call__(
        self,
        request: ArbitrationRequest,
    ) -> ArbitrationDecision | None: ...


def interpret_stage(
    *,
    state: RunState,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | dict[str, Any] | None,
    structured_arbitrator: StructuredArbitrator | None = None,
) -> StageResult:
    capability_contract = build_default_capability_contract()
    signals = extract_signals(
        message=state.current_user_message,
        latest_task_snapshot=latest_task_snapshot,
    )
    effective_profile = resolve_effective_response_profile(
        user=user,
        explicit_overrides=signals.response_profile_overrides,
    )
    arbitration_request = ArbitrationRequest(
        current_user_message=state.current_user_message,
        signals=signals,
        latest_task_snapshot=normalize_task_snapshot(latest_task_snapshot),
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
    candidate_strategy = build_candidate_strategy(
        current_message=state.current_user_message,
        signals=signals,
    )
    missing_required_fields: list[str] = []
    if should_track_execution_requirements(
        intent=preliminary_intent,
        task_relation=preliminary_task_relation,
        signals=signals,
    ):
        missing_required_fields = [
            field_name
            for field_name in capability_contract.required_fields
            if strategy_field_missing(candidate_strategy, field_name)
        ]
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
        or (
            should_track_execution_requirements(
                intent=intent,
                task_relation=task_relation,
                signals=signals,
            )
            and bool(missing_required_fields)
        )
    )
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
            merge_reason_codes(
                arbitration.reason_codes,
                arbitration.decision.reason_codes
                if arbitration.decision is not None
                else [],
            ),
        ),
        effective_response_profile=effective_profile,
        user_preference_overridden_for_turn=has_response_profile_overrides(signals),
        normalized_signals=signals.to_patch_payload(),
    )

    outcome: StageOutcome = "needs_clarification"
    if not requires_clarification:
        outcome = "ready_for_confirmation"

    return StageResult(outcome=outcome, decision=decision)


def build_candidate_strategy(
    *,
    current_message: str,
    signals: ExtractedSignals,
) -> StrategySummary:
    strategy = StrategySummary(asset_universe=list(signals.detected_symbols))
    if signals.detected_date_range is not None:
        strategy.date_range = signals.detected_date_range
    strategy.entry_logic = extract_entry_logic(current_message)
    strategy.exit_logic = extract_exit_logic(current_message)
    if signals.detected_symbols and not signals.beginner_language_detected:
        strategy.strategy_thesis = current_message.strip()
    return strategy


def strategy_field_missing(strategy: StrategySummary, field_name: str) -> bool:
    value = getattr(strategy, field_name)
    if isinstance(value, list):
        return len(value) == 0
    return value is None or value == ""


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


def extract_entry_logic(message: str) -> str | None:
    match = re.search(
        r"(?:enter|buy)\s+when\s+(.+?)(?=,\s*exit\s+when\b| and exit\s+when\b|$)",
        message,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return normalize_clause(match.group(1))


def extract_exit_logic(message: str) -> str | None:
    match = re.search(
        r"exit\s+when\s+(.+?)(?=[\.,;]|$)",
        message,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return normalize_clause(match.group(1))


def normalize_clause(clause: str) -> str | None:
    normalized = clause.strip(" .,:;")
    if not normalized:
        return None
    return normalized[0].upper() + normalized[1:]


def merge_reason_codes(
    signal_reason_codes: list[str],
    arbitration_reason_codes: list[str],
) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for reason_code in [*signal_reason_codes, *arbitration_reason_codes]:
        if reason_code in seen:
            continue
        seen.add(reason_code)
        merged.append(reason_code)
    return merged
