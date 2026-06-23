from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.agent_runtime.artifacts.asset_edits import (
    AssetUniverseOperation,
    apply_asset_universe_edit,
    normalized_asset_universe_operation,
)
from argus.agent_runtime.state.models import StrategySummary

PatchSource = Literal["structured_action", "llm_patch", "user_patch", "retry"]


class ArtifactPatch(BaseModel):
    source: PatchSource
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] | None = None
    asset_universe_operation: AssetUniverseOperation | None = None
    asset_class: str | None = None
    timeframe: str | None = None
    cadence: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    date_range: str | dict[str, Any] | None = None
    sizing_mode: str | None = None
    capital_amount: float | None = None
    position_size: float | None = None
    assumptions: list[str] | None = None
    comparison_baseline: str | None = None
    refinement_of: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    extra_parameters: dict[str, Any] | None = None
    clear_fields: list[str] = Field(default_factory=list)


def apply_artifact_patch(
    base: StrategySummary,
    patch: ArtifactPatch,
) -> StrategySummary:
    values = base.model_dump(mode="python")
    changed_fields: list[str] = []
    for field_name in _patchable_fields():
        value = getattr(patch, field_name)
        if _blank(value):
            continue
        if field_name == "asset_universe":
            operation = normalized_asset_universe_operation(
                patch.asset_universe_operation
            )
            if operation is None:
                raise ValueError(
                    "asset_universe patches require asset_universe_operation"
                )
            values[field_name] = apply_asset_universe_edit(
                base_symbols=base.asset_universe,
                patch_symbols=value,
                operation=operation,
            )
        else:
            values[field_name] = _normalize_value(field_name, value)
        changed_fields.append(field_name)

    for field_name in _validated_clear_fields(patch.clear_fields):
        values[field_name] = None if field_name != "asset_universe" else []
        changed_fields.append(field_name)

    updated = StrategySummary.model_validate(values)
    metadata = dict(updated.extra_parameters or {})
    metadata.pop("asset_universe_operation", None)
    metadata["artifact_patch"] = {
        "source": patch.source,
        "changed_fields": list(dict.fromkeys(changed_fields)),
    }
    if "asset_universe" in changed_fields:
        operation = normalized_asset_universe_operation(patch.asset_universe_operation)
        if operation is None:
            raise ValueError(
                "asset_universe patches require asset_universe_operation"
            )
        metadata["artifact_patch"]["asset_universe_operation"] = operation
    updated.extra_parameters = metadata
    return updated


def patchable_strategy_fields(*, include_prose: bool = True) -> tuple[str, ...]:
    excluded = {"raw_user_phrasing", "resolution_provenance"}
    if not include_prose:
        excluded.add("strategy_thesis")
    return tuple(
        field_name
        for field_name in ArtifactPatch.model_fields
        if field_name in StrategySummary.model_fields and field_name not in excluded
    )


def _patchable_fields() -> tuple[str, ...]:
    return patchable_strategy_fields()


def _validated_clear_fields(values: list[str]) -> list[str]:
    allowed = set(_patchable_fields()) - {
        "strategy_type",
        "asset_class",
        "asset_universe",
    }
    return [
        field_name
        for field_name in values
        if field_name in allowed
    ]


def _normalize_value(field_name: str, value: Any) -> Any:
    if field_name == "asset_universe" and isinstance(value, list):
        return _symbols(value)
    if field_name == "comparison_baseline":
        return _symbol(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _symbols(values: list[str]) -> list[str]:
    symbols: list[str] = []
    for value in values:
        symbol = _symbol(value)
        if symbol is not None:
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def _symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace("-", "/")
    return symbol or None


def _blank(value: Any) -> bool:
    return value in (None, "", [], {})
