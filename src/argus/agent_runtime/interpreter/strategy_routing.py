"""Canonical typed ownership of the strategy route."""

from __future__ import annotations

from typing import Literal

from argus.agent_runtime.stages.interpret_types import SemanticTurnAct
from argus.agent_runtime.state.models import IntentName

RouteOwner = Literal["strategy", "result"]

INTENT_ROUTE_OWNERS: dict[IntentName, RouteOwner] = {
    "strategy_drafting": "strategy",
    "backtest_execution": "strategy",
    "results_explanation": "result",
}

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
    owner = INTENT_ROUTE_OWNERS.get(intent)
    if owner is not None:
        return owner
    return "strategy" if semantic_turn_act in STRATEGY_TURN_ACTS else None


def strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return (
        route_owner(intent=intent, semantic_turn_act=semantic_turn_act) == "strategy"
    )
