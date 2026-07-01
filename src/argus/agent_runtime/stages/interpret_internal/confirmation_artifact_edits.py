"""Helpers for applying active confirmation-card edits in interpret stage."""

from __future__ import annotations

from collections.abc import Callable

from argus.agent_runtime.artifact_edit_planner import ResolvedArtifactEdit
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.nlp.natural_time import resolve_date_range_intent

ResolveAssetCandidate = Callable[..., AssetResolution | None]


def asset_edit_symbol_resolver(
    resolve_asset_candidate: ResolveAssetCandidate,
) -> Callable[[str], str | None]:
    def _resolve(raw_symbol: str) -> str | None:
        resolution = resolve_asset_candidate(
            raw_symbol,
            field="asset_edit",
            source="user_mention",
        )
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset
        ):
            return resolution.asset.canonical_symbol
        return None

    return _resolve


def apply_resolved_artifact_edit_to_strategy_summary(
    resolved: ResolvedArtifactEdit,
    *,
    candidate: StrategySummary,
    field_provenance: dict[str, str],
    allow_indicator_parameters: bool = False,
) -> None:
    if resolved.asset_universe is not None:
        candidate.asset_universe = list(resolved.asset_universe)
        candidate.extra_parameters["asset_universe_operation"] = "replace"
        field_provenance["asset_universe"] = "explicit_user"
    if resolved.comparison_baseline:
        candidate.comparison_baseline = resolved.comparison_baseline
        field_provenance["comparison_baseline"] = "explicit_user"
    if resolved.date_window is not None:
        intent_resolution = resolve_date_range_intent(resolved.date_window)
        if intent_resolution is not None:
            candidate.date_range = intent_resolution.payload
            candidate.extra_parameters["date_range_intent"] = (
                resolved.date_window.model_dump(mode="python")
            )
            field_provenance["date_range"] = "explicit_user"
    if resolved.initial_capital is not None:
        candidate.capital_amount = float(resolved.initial_capital)
        field_provenance["capital_amount"] = "starting_capital"
    if resolved.recurring_contribution_amount is not None:
        recurring_amount = float(resolved.recurring_contribution_amount)
        candidate.capital_amount = recurring_amount
        candidate.extra_parameters["recurring_contribution"] = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
    if resolved.timeframe is not None:
        candidate.timeframe = resolved.timeframe
        field_provenance["timeframe"] = "explicit_user"
    if resolved.fee_rate is not None:
        candidate.extra_parameters["fee_rate"] = resolved.fee_rate
        field_provenance["fee_rate"] = "explicit_user"
    if resolved.slippage is not None:
        candidate.extra_parameters["slippage"] = resolved.slippage
        field_provenance["slippage"] = "explicit_user"
    if resolved.indicator_parameters and allow_indicator_parameters:
        candidate.strategy_type = "indicator_threshold"
        candidate.extra_parameters["indicator"] = "rsi"
        candidate.extra_parameters["indicator_parameters"] = {
            "indicator": "rsi",
            **resolved.indicator_parameters,
        }
        field_provenance["indicator_parameters"] = "explicit_user"


def strategy_summary_uses_rsi(strategy: StrategySummary) -> bool:
    parameters = canonical_indicator_parameters_from_strategy(strategy)
    indicator = str(
        parameters.get("indicator")
        or strategy.extra_parameters.get("indicator")
        or ""
    ).strip().casefold()
    return indicator == "rsi"
