"""Cross-cutting leaf helpers shared across interpret-stage modules (import sink).

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.capabilities.answers import EXECUTABLE_STRATEGY_FAMILIES
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    strategy_rule,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_requirements import (
    valid_rule_spec_from_strategy as _valid_rule_spec_from_strategy,
)
from argus.domain.indicators import executable_indicator_spec


def _supported_experiment_fact_packet() -> str:
    families = "; ".join(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        f"{families}. Macro, news, corporate-action, and movers context may frame "
        "a question or explain backdrop, but cannot alter simulation truth or become "
        "the executable rule. Suggested next experiments must stay inside these "
        "families instead of inventing unregistered triggers or holding-period rules."
    )


def _field_base(field_name: str) -> str:
    return field_name.split("[", 1)[0]


def _should_preserve_prior_asset_context(
    *,
    prior: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> bool:
    if not prior.asset_universe:
        return False
    if semantic_turn_act != "answer_pending_need":
        return False
    if task_relation not in {"continue", "refine"}:
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "asset_universe":
        return False
    return selected_thread_metadata.get("last_stage_outcome") == "await_user_reply"


def _strategy_supplies_executable_rule_edit(strategy: StrategySummary) -> bool:
    indicator_parameters = canonical_indicator_parameters_from_strategy(strategy)
    indicator = str(indicator_parameters.get("indicator") or "").strip()
    return bool(
        strategy_rule(strategy, "entry")
        or strategy_rule(strategy, "exit")
        or _valid_rule_spec_from_strategy(strategy)
        or (indicator and executable_indicator_spec(indicator) is not None)
    )
