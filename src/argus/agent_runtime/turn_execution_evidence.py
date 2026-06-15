from __future__ import annotations

from argus.agent_runtime.run_field_contract import (
    field_fidelity_tokens,
)


def current_turn_has_material_execution_evidence(
    message: str,
    *,
    has_provider_asset_mention: bool,
    active_strategy_context: bool,
    requested_field: str | None = None,
) -> bool:
    """Return whether focused strategy repair has current-turn facts to work with."""

    text = str(message or "")
    if not text.strip():
        return False

    if _message_has_numeric_execution_fact(text):
        return True
    if active_strategy_context:
        return has_provider_asset_mention and _requested_field_accepts_asset_fact(
            requested_field
        )
    return has_provider_asset_mention


def _requested_field_accepts_asset_fact(requested_field: str | None) -> bool:
    base_field = str(requested_field or "").split("[", 1)[0].strip()
    return base_field in {"asset_universe", "comparison_baseline", "benchmark_symbol"}


def _message_has_numeric_execution_fact(message: str) -> bool:
    for token in field_fidelity_tokens(message):
        if any(char.isdigit() for char in token):
            return True
    return False
