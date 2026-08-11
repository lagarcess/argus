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

from argus.agent_runtime.confirmation_revalidation import (
    launch_date_range_of,
    revalidated_confirmation_candidate,
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

    candidate, error_code = revalidated_confirmation_candidate(
        patched_strategy=patched_strategy,
        patched_launch=patched_launch,
        source_payload=source_payload,
    )
    if candidate is None:
        return BasketGrowthPreparation(error_code=error_code)
    adjustment: dict[str, Any] = {
        "code": "assets_added",
        "added": additions,
        "previous_symbols": current_symbols,
        "symbols": merged,
    }
    source_range = _date_range_of(launch)
    effective_range = _date_range_of(candidate["launch_payload"])
    if (
        source_range is not None
        and effective_range is not None
        and source_range != effective_range
    ):
        # The one consequence a peer add can actually produce: the shared
        # history window clamps. Disclosed inline next to the period field;
        # the deliberate action itself is never narrated back.
        adjustment["period_change"] = {
            "from": source_range,
            "to": effective_range,
        }
    candidate["assets_adjustment"] = adjustment
    return BasketGrowthPreparation(confirmation_payload=candidate)


def confirmation_symbols_restoration(
    source_payload: dict[str, Any],
    *,
    language: str = "en",
) -> BasketGrowthPreparation:
    """Undo for a peer add: re-materialize the exact previous asset set.

    Deterministic like the add itself: the previous symbols come from the
    active payload's own typed adjustment data, and the restored draft passes
    the same execution and coverage validation chain.
    """
    strategy = source_payload.get("strategy")
    launch = source_payload.get("launch_payload")
    adjustment = source_payload.get("assets_adjustment")
    if (
        not isinstance(strategy, dict)
        or not isinstance(launch, dict)
        or not isinstance(adjustment, dict)
    ):
        return BasketGrowthPreparation(error_code="nothing_to_restore")
    previous = [
        str(symbol).strip().upper()
        for symbol in adjustment.get("previous_symbols") or []
        if str(symbol).strip()
    ]
    current = [
        str(symbol).strip().upper()
        for symbol in strategy.get("asset_universe") or []
        if str(symbol).strip()
    ]
    if not previous or previous == current:
        return BasketGrowthPreparation(error_code="nothing_to_restore")

    patched_strategy = dict(strategy)
    patched_strategy["asset_universe"] = previous
    patched_launch = {
        key: value for key, value in launch.items() if key != "coverage_preflight"
    }
    patched_launch["symbols"] = previous
    patched_launch["symbol"] = previous[0]
    patched_launch["language"] = language

    candidate, error_code = revalidated_confirmation_candidate(
        patched_strategy=patched_strategy,
        patched_launch=patched_launch,
        source_payload=source_payload,
    )
    if candidate is None:
        return BasketGrowthPreparation(error_code=error_code)
    restoration: dict[str, Any] = {
        "code": "assets_restored",
        "added": [],
        "previous_symbols": current,
        "symbols": previous,
    }
    source_range = _date_range_of(launch)
    effective_range = _date_range_of(candidate["launch_payload"])
    if (
        source_range is not None
        and effective_range is not None
        and source_range != effective_range
    ):
        restoration["period_change"] = {
            "from": source_range,
            "to": effective_range,
        }
    candidate["assets_adjustment"] = restoration
    return BasketGrowthPreparation(confirmation_payload=candidate)


def _date_range_of(payload: dict[str, Any]) -> dict[str, str] | None:
    return launch_date_range_of(payload)


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


# The row parser requires a label_key; this one is deliberately absent from
# the catalogs so the backend-localized label renders as supplied.
_DYNAMIC_LABEL_KEY = "chat.next_experiments.labels.research_dynamic"


def peer_add_rows(
    peers: Any,
    *,
    basket_symbols: list[str],
    basket_asset_class: str | None,
    language: str,
) -> dict[str, Any] | None:
    """Peer adds as ordinary typed Try-next rows below the card's turn.

    Same component, same position, same behavior as every other row; the
    ``why`` payload carries the resolver-verified symbols the tap adds, so
    the frontend never derives identity from the label. Naming is the shared
    short-name-plus-ticker-part vocabulary.
    """
    offers = remaining_peer_offers(
        peers,
        basket_symbols=basket_symbols,
        basket_asset_class=basket_asset_class,
    )
    if not offers:
        return None
    from argus.agent_runtime.asset_identity import (
        asset_label_parts,
        label_from_parts,
    )

    spanish = str(language or "").lower().startswith("es")
    rows: list[dict[str, Any]] = []
    for offer in offers:
        parts = [
            {"type": "text", "value": "Agregar " if spanish else "Add "},
            *asset_label_parts([offer]),
            {
                "type": "text",
                "value": " a esta prueba" if spanish else " to this test",
            },
        ]
        rows.append(
            {
                # The kind doubles as the row's render identity, so each add
                # row carries its symbol to stay unique within the group.
                "kind": f"research_add_peer:{offer['symbol']}",
                "label": label_from_parts(parts),
                "label_parts": parts,
                "label_key": _DYNAMIC_LABEL_KEY,
                "why": {
                    "code": "research_add_peer",
                    "params": {"symbols": [offer["symbol"]]},
                },
            }
        )
    if len(offers) > 1:
        parts = [{"type": "text", "value": "Agregar " if spanish else "Add "}]
        for index, offer in enumerate(offers):
            if index:
                last = index == len(offers) - 1
                parts.append(
                    {
                        "type": "text",
                        "value": (" y " if spanish else " and ") if last else ", ",
                    }
                )
            parts.extend(asset_label_parts([offer]))
        rows.append(
            {
                "kind": "research_add_peer_set",
                "label": label_from_parts(parts),
                "label_parts": parts,
                "label_key": _DYNAMIC_LABEL_KEY,
                "why": {
                    "code": "research_add_peer",
                    "params": {"symbols": [offer["symbol"] for offer in offers]},
                },
            }
        )
    from argus.agent_runtime.next_experiments import NEXT_EXPERIMENTS_VERSION

    return {"version": NEXT_EXPERIMENTS_VERSION, "rows": rows}
