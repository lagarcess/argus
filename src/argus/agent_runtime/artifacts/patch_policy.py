from __future__ import annotations

from argus.agent_runtime.state.models import StrategySummary, UnsupportedConstraint
from argus.agent_runtime.strategy_contract import strategy_can_be_approved

ASSET_PATCH_FIELDS = frozenset({"asset_universe", "asset_class"})
DATA_AVAILABILITY_PATCH_FIELDS = frozenset(
    {"asset_universe", "asset_class", "date_range", "timeframe"}
)
# Result fields a follow-up patch can execute; also the fields an inferred
# result edit may carry without being read as a new-strategy draft.
RESULT_FOLLOWUP_EXECUTABLE_PATCH_FIELDS = frozenset(
    {
        "asset_universe",
        "asset_class",
        "cadence",
        "capital_amount",
        "date_range",
        "timeframe",
        "comparison_baseline",
    }
)
STRATEGY_LOGIC_PATCH_FIELDS = frozenset(
    {
        "strategy_type",
        "entry_logic",
        "exit_logic",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "risk_rules",
    }
)


def executable_artifact_patch_missing_fields(
    *,
    strategy: StrategySummary,
    missing_fields: list[str],
) -> list[str]:
    if not strategy_can_be_approved(strategy):
        return list(missing_fields)
    return [
        field
        for field in missing_fields
        if field != "strategy_thesis"
    ]


def relevant_unsupported_constraints_for_artifact_patch(
    *,
    strategy: StrategySummary,
    constraints: list[UnsupportedConstraint],
) -> list[UnsupportedConstraint]:
    if not constraints or not strategy_can_be_approved(strategy):
        return list(constraints)
    changed_fields = artifact_patch_changed_fields(strategy)
    if not changed_fields:
        return list(constraints)
    return [
        constraint
        for constraint in constraints
        if _constraint_still_applies_to_patch(
            constraint=constraint,
            changed_fields=changed_fields,
        )
    ]


def _constraint_still_applies_to_patch(
    *,
    constraint: UnsupportedConstraint,
    changed_fields: set[str],
) -> bool:
    category = constraint.category
    if category == "unsupported_strategy_logic":
        return bool(changed_fields & STRATEGY_LOGIC_PATCH_FIELDS)
    if category in {"unsupported_asset", "unsupported_currency_pair"}:
        return bool(changed_fields & ASSET_PATCH_FIELDS)
    if category == "unavailable_for_requested_run":
        return bool(changed_fields & DATA_AVAILABILITY_PATCH_FIELDS)
    return True


def strategy_has_structured_non_patch_evidence(
    *,
    strategy: StrategySummary,
    patch_fields: frozenset[str],
) -> bool:
    ignored_fields = {
        "raw_user_phrasing",
        "strategy_thesis",
        "resolution_provenance",
        "extra_parameters",
    }
    for field_name in StrategySummary.model_fields:
        if field_name in patch_fields or field_name in ignored_fields:
            continue
        if getattr(strategy, field_name) not in (None, "", [], {}):
            return True
    return False


def artifact_patch_changed_fields(strategy: StrategySummary) -> set[str]:
    artifact_patch = dict(strategy.extra_parameters or {}).get("artifact_patch")
    if not isinstance(artifact_patch, dict):
        return set()
    changed_fields = artifact_patch.get("changed_fields")
    if not isinstance(changed_fields, list):
        return set()
    return {
        str(field).strip()
        for field in changed_fields
        if str(field).strip()
    }
