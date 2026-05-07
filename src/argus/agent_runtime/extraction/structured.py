from __future__ import annotations

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.resolution import resolve_asset_candidate
from argus.agent_runtime.state.models import StrategySummary, UnsupportedConstraint


def detect_unsupported_constraints(
    *,
    strategy: StrategySummary,
    contract: CapabilityContract,
) -> list[UnsupportedConstraint]:
    symbols = [symbol for symbol in strategy.asset_universe if symbol]
    asset_classes: dict[str, str] = {}
    unsupported_constraints: list[UnsupportedConstraint] = []

    for index, symbol in enumerate(symbols):
        resolution = resolve_asset_candidate(
            symbol,
            field=f"asset_universe[{index}]",
            source="llm_extraction",
        )
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        asset_classes[resolution.asset.canonical_symbol] = resolution.asset.asset_class

    if len(set(asset_classes.values())) > 1:
        unsupported_constraints.append(
            UnsupportedConstraint(
                category="unsupported_asset_mix",
                raw_value=", ".join(asset_classes),
                explanation=(
                    "Argus Alpha cannot run mixed asset classes in one simulation."
                ),
                simplification_options=contract.get_simplification_options(
                    "unsupported_asset_mix"
                ),
            )
        )
    return unsupported_constraints
