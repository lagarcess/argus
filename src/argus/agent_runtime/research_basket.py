"""Deterministic basket growth for a pending confirmation.

Tapping a researched peer adds it to the pending confirmation without
spending a turn: no LLM call, no message allowance, no interpretation. The
patch is a pure function of the stored canonical confirmation payload plus a
resolver-verified peer, re-validated through the same execution and coverage
gates every confirmation passes. Adding an asset changes the experiment
materially, so the result is a new confirmation identity carrying a typed
``assets_adjustment`` disclosure; the previous card supersedes, never mutates
silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.confirmation_artifacts import (
    new_confirmation_id,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import strategy_can_be_approved
from argus.domain.backtesting.confirmation_preflight import (
    materialize_confirmation_strategy,
    prepare_confirmation_launch,
)

MAX_BASKET_SYMBOLS = 5


@dataclass(frozen=True)
class BasketGrowthPreparation:
    confirmation_payload: dict[str, Any] | None = None
    error_code: str | None = None


def peer_added_confirmation_preparation(
    source_payload: dict[str, Any],
    *,
    added: list[dict[str, str]],
    language: str = "en",
) -> BasketGrowthPreparation:
    """Patch the canonical payload with verified peers and re-validate."""
    strategy = source_payload.get("strategy")
    launch = source_payload.get("launch_payload")
    if not isinstance(strategy, dict) or not isinstance(launch, dict):
        return BasketGrowthPreparation(error_code="confirmation_payload_invalid")
    current_symbols = [
        str(symbol).strip().upper()
        for symbol in strategy.get("asset_universe") or []
        if str(symbol).strip()
    ]
    if not current_symbols:
        return BasketGrowthPreparation(error_code="confirmation_payload_invalid")
    base_class = str(strategy.get("asset_class") or "").strip() or "equity"
    additions: list[dict[str, str]] = []
    for peer in added:
        symbol = str(peer.get("symbol") or "").strip().upper()
        if not symbol or symbol in current_symbols:
            continue
        if str(peer.get("asset_class") or base_class) != base_class:
            return BasketGrowthPreparation(error_code="asset_class_mismatch")
        additions.append({"symbol": symbol, "name": str(peer.get("name") or symbol)})
    if not additions:
        return BasketGrowthPreparation(error_code="no_new_assets")
    merged = [*current_symbols, *(peer["symbol"] for peer in additions)]
    if len(merged) > MAX_BASKET_SYMBOLS:
        return BasketGrowthPreparation(error_code="asset_maximum_reached")

    patched_strategy = dict(strategy)
    patched_strategy["asset_universe"] = merged
    patched_launch = {
        key: value
        for key, value in launch.items()
        # Coverage truth must be recomputed for the new basket.
        if key != "coverage_preflight"
    }
    patched_launch["symbols"] = merged
    patched_launch["symbol"] = merged[0]
    patched_launch["language"] = language

    preflight = prepare_confirmation_launch(dict(patched_launch))
    if preflight.outcome == "coverage_failure":
        return BasketGrowthPreparation(
            error_code=preflight.error_code or "market_data_unavailable"
        )
    if preflight.outcome != "ready_to_confirm" or preflight.launch_payload is None:
        return BasketGrowthPreparation(error_code="confirmation_not_executable")
    materialized_strategy = materialize_confirmation_strategy(
        patched_strategy,
        launch_payload=preflight.launch_payload,
    )
    candidate: dict[str, Any] = {
        "strategy": materialized_strategy,
        "optional_parameters": source_payload.get("optional_parameters") or {},
        "launch_payload": preflight.launch_payload,
    }
    validation = validate_confirmation_execution_payload(candidate)
    if not validation.executable or validation.launch_payload is None:
        return BasketGrowthPreparation(error_code="confirmation_not_executable")
    try:
        pending_strategy = StrategySummary.model_validate(materialized_strategy)
    except ValueError:
        return BasketGrowthPreparation(error_code="confirmation_not_executable")
    if not strategy_can_be_approved(pending_strategy):
        return BasketGrowthPreparation(error_code="confirmation_not_executable")

    active_id = new_confirmation_id()
    candidate["launch_payload"] = validation.launch_payload
    candidate["confirmation_id"] = active_id
    candidate["artifact_id"] = active_id
    candidate["validation"] = {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": False,
    }
    candidate["assets_adjustment"] = {
        "code": "assets_added",
        "added": additions,
        "previous_symbols": current_symbols,
        "symbols": merged,
    }
    return BasketGrowthPreparation(confirmation_payload=candidate)


def remaining_peer_offers(
    peers: Any,
    *,
    basket_symbols: list[str],
    basket_asset_class: str | None,
) -> list[dict[str, str]]:
    """Peers not yet in the basket, class-matched, bounded by free slots."""
    if not isinstance(peers, list):
        return []
    slots = MAX_BASKET_SYMBOLS - len(basket_symbols)
    if slots <= 0:
        return []
    taken = {str(symbol).upper() for symbol in basket_symbols}
    offers: list[dict[str, str]] = []
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        symbol = str(peer.get("symbol") or "").strip().upper()
        name = str(peer.get("name") or symbol)
        peer_class = str(peer.get("asset_class") or "equity")
        if not symbol or symbol in taken:
            continue
        if basket_asset_class is not None and peer_class != basket_asset_class:
            continue
        offers.append({"symbol": symbol, "name": name, "asset_class": peer_class})
        taken.add(symbol)
        if len(offers) >= slots:
            break
    return offers
