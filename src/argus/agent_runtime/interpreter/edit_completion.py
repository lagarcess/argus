"""Plan completion from the primary interpretation's typed extraction (§3.2).

The primary interpretation and the artifact edit planner are independent
structured reads of the same turn; a fact either one extracted must reach the
operation set, or one model's blind spot silently halves a compound edit
(issue #498). Values come from the primary read's typed fields, so completion
stays deterministic; the applier still validates each value.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifact_edit_planner import EditOperation
from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_symbols,
    normalized_asset_universe_operation,
)
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _STATED_COST_TARGETS,
    _normalized_ticker_symbol,
    _required_edit_targets_from_primary_draft,
    _stated_cost_changes,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMDateRangeIntent,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary


def stated_edit_operations(
    draft: LLMStrategyDraft | None,
    *,
    current_strategy: StrategySummary | None,
    request: InterpretationRequest | None,
) -> list[EditOperation]:
    """Typed operations for facts the primary read extracted."""

    if draft is None:
        return []
    operations = [
        EditOperation(op="set", target=_STATED_COST_TARGETS[field_name], number=value)
        for field_name, value in _stated_cost_changes(
            draft, current_strategy=current_strategy, request=request
        ).items()
    ]
    required = _required_edit_targets_from_primary_draft(
        draft, current_strategy=current_strategy, request=request
    )
    if "benchmark" in required:
        benchmark = _normalized_ticker_symbol(draft.comparison_baseline)
        if benchmark:
            operations.append(
                EditOperation(op="set", target="benchmark", value=benchmark)
            )
    if "date_window" in required:
        intent = draft.date_range_intent or _explicit_range_intent(draft.date_range)
        if intent is not None:
            operations.append(
                EditOperation(op="set", target="date_window", date_window=intent)
            )
    if "asset" in required:
        operations.extend(_stated_asset_operations(draft))
    return operations


def _explicit_range_intent(date_range: Any) -> LLMDateRangeIntent | None:
    if not isinstance(date_range, dict):
        return None
    start = str(date_range.get("start") or "").strip() or None
    end = str(date_range.get("end") or "").strip() or None
    if start is None and end is None:
        return None
    return LLMDateRangeIntent(
        kind="explicit_range", start=start, end=end, confidence=1.0
    )


def _stated_asset_operations(draft: LLMStrategyDraft) -> list[EditOperation]:
    inclusions = normalized_asset_symbols(draft.asset_inclusions)
    exclusions = normalized_asset_symbols(draft.asset_exclusions)
    if inclusions or exclusions:
        operations = []
        if inclusions:
            operations.append(
                EditOperation(op="add", target="asset", symbols=inclusions)
            )
        if exclusions:
            operations.append(
                EditOperation(op="remove", target="asset", symbols=exclusions)
            )
        return operations
    operation = normalized_asset_universe_operation(draft.asset_universe_operation)
    universe = normalized_asset_symbols(draft.asset_universe)
    if operation is None or not universe:
        return []
    return [
        EditOperation(
            op="replace" if operation == "replace" else "add",
            target="asset",
            symbols=universe,
        )
    ]
