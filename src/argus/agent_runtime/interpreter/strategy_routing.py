"""Canonical typed ownership of the strategy route."""

from __future__ import annotations

from argus.agent_runtime.stages.interpret_types import SemanticTurnAct
from argus.agent_runtime.state.models import IntentName

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
}


def strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return intent in {"strategy_drafting", "backtest_execution"} or (
        semantic_turn_act in STRATEGY_TURN_ACTS
    )
