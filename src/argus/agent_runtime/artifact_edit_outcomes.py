"""Backtest edit facts projected into the shared artifact edit contract."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
)
from argus.agent_runtime.artifacts.asset_edits import (
    apply_asset_universe_edit,
    normalized_asset_symbols,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.semantic_integrity import _supported_timeframe_value
from argus.domain.edit_contract import complete_edit_disclosure

if TYPE_CHECKING:
    from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import StrategySummary

# Legacy planner carriers are backtest vocabulary, not a universal input schema.
# The operation path already names its targets; only old flat plans need this
# projection. Values are counted before application so rejected carriers cannot
# disappear just because the applier omitted their provenance.
_LEGACY_PLAN_TARGETS = {
    "asset_universe": "asset",
    "comparison_baseline": "benchmark",
    "initial_capital": "capital",
    "recurring_contribution_amount": "recurring_contribution",
    "cadence": "cadence",
    "timeframe": "timeframe",
    "fee_rate": "fees",
    "slippage": "slippage",
}


def _canonical_target(target: str) -> str:
    return "capital" if target == "starting_capital" else target


def _requested_legacy_fields(plan: ArtifactAssumptionEditPlan) -> dict[str, Any]:
    """An explicit operation owns intent even when its value is empty."""
    return {
        field: value
        for field in _LEGACY_PLAN_TARGETS
        if (value := getattr(plan, field)) is not None
        and (
            field != "asset_universe"
            or value
            or plan.asset_universe_operation is not None
        )
    }


def canonical_artifact_edit_plan(
    plan: ArtifactAssumptionEditPlan,
) -> ArtifactAssumptionEditPlan:
    """Typed operations own a target in both adapters; flat-only targets stay.

    Keep the original plan for disclosure. Its shadowed flat values must still
    be compared with the resolved operation result, never silently discarded.
    """
    targets = {_canonical_target(operation.target) for operation in plan.operations}
    updates = {
        field: [] if field == "asset_universe" else None
        for field, target in _LEGACY_PLAN_TARGETS.items()
        if target in targets
    }
    return plan.model_copy(update=updates) if updates else plan


def _carrier_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, list):
        return sorted({_carrier_value(item) for item in value})
    return value


def normalized_edit_timeframe(value: str | None) -> str | None:
    """Use the same capability declaration as interpret-stage normalization."""
    parameter = build_default_capability_contract().get_optional_parameter("timeframe")
    allowed = (
        parameter.allowed_range.allowed_values
        if parameter and parameter.allowed_range
        else ()
    )
    return _supported_timeframe_value(value, supported_timeframes=tuple(allowed))


def executable_edit_targets(
    targets: set[str],
    *,
    timeframe: str | None,
) -> set[str]:
    """Do not count a field that downstream normalization must discard."""
    materialized = set(targets)
    if "timeframe" in materialized and normalized_edit_timeframe(timeframe) is None:
        materialized.remove("timeframe")
    return materialized


def artifact_edit_has_changes(
    *,
    materialized_targets: set[str],
    draft: LLMStrategyDraft | StrategySummary,
    current_strategy: StrategySummary | None,
    request: InterpretationRequest | None = None,
) -> bool:
    """Compare canonical targets using the existing backtest projection owners.

    Imports are deferred because the normal callee consumes this adapter too.
    Recovery has already resolved dates and needs no request rebinding.
    """
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _materialized_target_mutates_current,
    )
    from argus.agent_runtime.interpreter.pending_option import (
        _llm_draft_from_strategy_summary,
    )
    from argus.agent_runtime.state.models import StrategySummary

    if isinstance(draft, StrategySummary):
        draft = _llm_draft_from_strategy_summary(draft)
    return any(
        _materialized_target_mutates_current(
            target,
            materialized_draft=draft,
            current_strategy=current_strategy,
            request=request,
        )
        for target in materialized_targets
    )


def artifact_edit_disclosure(
    plan: ArtifactAssumptionEditPlan,
    *,
    current_asset_universe: list[str],
    materialized_targets: set[str],
    has_changes: bool,
    existing: dict[str, Any] | None = None,
    resolved: ResolvedArtifactEdit | None = None,
) -> dict[str, Any] | None:
    requested = [
        (operation.op, _canonical_target(operation.target))
        for operation in plan.operations
    ]
    operation_targets = {target for _, target in requested}
    unapplied = [
        {**entry, "target": _canonical_target(entry["target"])}
        for entry in (existing or {}).get("unapplied", [])
    ]
    refused_targets = {entry["target"] for entry in unapplied}
    legacy_fields = _requested_legacy_fields(plan)
    if resolved is not None:
        for field, flat in legacy_fields.items():
            target = _LEGACY_PLAN_TARGETS[field]
            if target not in operation_targets or target in refused_targets:
                continue
            # The typed resolver emits a final basket, while the legacy carrier
            # may be an append patch. Compare outcomes from the same starting
            # basket through the existing asset semantics owner.
            legacy_value = (
                apply_asset_universe_edit(
                    normalized_asset_symbols(current_asset_universe),
                    flat,
                    plan.asset_universe_operation,
                )
                if field == "asset_universe"
                else flat
            )
            if _carrier_value(legacy_value) != _carrier_value(getattr(resolved, field)):
                unapplied.append(
                    {"op": "set", "target": target, "reason": "conflicting_edit_carriers"}
                )
    requested.extend(
        ("set", _LEGACY_PLAN_TARGETS[field])
        for field in legacy_fields
        if _LEGACY_PLAN_TARGETS[field] not in operation_targets
    )
    return complete_edit_disclosure(
        requested=requested,
        materialized_targets=materialized_targets,
        has_changes=has_changes,
        unapplied=unapplied,
        note=plan.assistant_response,
    )
