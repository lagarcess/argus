"""Canonical typed ownership of the strategy route."""

from __future__ import annotations

from typing import Literal

from argus.agent_runtime.interpreter.repair_observability import repair_effect_metadata
from argus.agent_runtime.stages.interpret_types import InterpretDecision, SemanticTurnAct
from argus.agent_runtime.state.models import IntentName

RouteOwner = Literal["strategy", "result"]

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
}


def route_owner(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> RouteOwner | None:
    if semantic_turn_act == "result_followup":
        return "result"
    return "strategy" if semantic_turn_act in STRATEGY_TURN_ACTS else None


def strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return route_owner(intent=intent, semantic_turn_act=semantic_turn_act) == "strategy"


def decision_with_strategy_route_intent(decision: InterpretDecision) -> InterpretDecision:
    """Keep the effective label aligned with typed strategy work, and audit repair."""
    # A route label cannot promote a refusal; capability admission owns that verdict.
    if decision.intent not in {"explain", "follow_up"} or not strategy_route_expected(
        intent=decision.intent, semantic_turn_act=decision.semantic_turn_act
    ):
        return decision
    repaired = decision.model_copy(
        update={
            "intent": "calculate",
            "reason_codes": [*decision.reason_codes, "strategy_route_intent_normalized"],
        }
    )
    repaired.normalized_signals = {
        **decision.normalized_signals,
        "strategy_route_intent_repair": {
            "original_model_intent": decision.intent,
            **repair_effect_metadata(
                before=decision,
                after=repaired,
                trigger_reason="typed_strategy_route",
                repair_applied=True,
            ),
        },
    }
    return repaired
