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


def _selected_response_intent(
    selected_thread_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    root_intent = selected_thread_metadata.get("response_intent")
    if isinstance(root_intent, dict):
        candidates.append(root_intent)
    pending_strategy = selected_thread_metadata.get("pending_strategy")
    if isinstance(pending_strategy, dict):
        nested_intent = pending_strategy.get("response_intent")
        if isinstance(nested_intent, dict):
            candidates.append(nested_intent)
    if not candidates or any(candidate != candidates[0] for candidate in candidates[1:]):
        return None
    return dict(candidates[0])


def _selected_requested_field(
    selected_thread_metadata: dict[str, Any],
) -> str:
    candidates: list[Any] = [selected_thread_metadata.get("requested_field")]
    pending_strategy = selected_thread_metadata.get("pending_strategy")
    if isinstance(pending_strategy, dict):
        candidates.append(pending_strategy.get("requested_field"))
    response_intent = _selected_response_intent(selected_thread_metadata)
    if response_intent is not None:
        requested_fields = response_intent.get("requested_fields")
        if isinstance(requested_fields, list) and len(requested_fields) == 1:
            candidates.append(requested_fields[0])
    normalized = {
        _field_base(str(candidate or "")).strip()
        for candidate in candidates
        if str(candidate or "").strip()
    }
    return next(iter(normalized)) if len(normalized) == 1 else ""


# Provenance sources meaning the user set the money field in THIS turn;
# "prior" (carried context) is deliberately excluded.
_EXPLICIT_TURN_MONEY_SOURCES = frozenset(
    {
        "user",
        "explicit_user",
        "starting_capital",
        "starting_principal",
        "recurring_contribution",
        "contribution_amount",
    }
)


def _strategy_supplies_explicit_turn_money(strategy: StrategySummary) -> bool:
    extra_parameters = strategy.extra_parameters or {}
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        return False
    has_money_value = strategy.capital_amount is not None or any(
        extra_parameters.get(key) is not None
        for key in ("initial_capital", "recurring_contribution")
    )
    if not has_money_value:
        return False
    return any(
        str(field_provenance.get(key) or "").strip() in _EXPLICIT_TURN_MONEY_SOURCES
        for key in ("capital_amount", "initial_capital", "recurring_contribution")
    )


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
