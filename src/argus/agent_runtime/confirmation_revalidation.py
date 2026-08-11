"""Shared revalidation tail for deterministic basket patches.

The peer add and peer restore flows patch the stored canonical payload and
must then re-pass the same execution and coverage gates an ordinary
confirmation passes, minting a new confirmation identity. One chain for both,
so neither can drift to weaker validation. Direct capital/date edits do not
patch the stored launch payload at all; they re-assemble through the real
confirm stage instead (see confirmation_direct_edit.py).
"""

from __future__ import annotations

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


def revalidated_confirmation_candidate(
    *,
    patched_strategy: dict[str, Any],
    patched_launch: dict[str, Any],
    source_payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Coverage preflight, materialization, execution validation, new identity.

    Returns ``(candidate, None)`` on success or ``(None, error_code)`` with the
    same error vocabulary every confirmation surface maps to transport codes.
    """
    preflight = prepare_confirmation_launch(dict(patched_launch))
    if preflight.outcome == "coverage_failure":
        return None, preflight.error_code or "market_data_unavailable"
    if preflight.outcome != "ready_to_confirm" or preflight.launch_payload is None:
        return None, "confirmation_not_executable"
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
        return None, "confirmation_not_executable"
    try:
        pending_strategy = StrategySummary.model_validate(materialized_strategy)
    except ValueError:
        return None, "confirmation_not_executable"
    if not strategy_can_be_approved(pending_strategy):
        return None, "confirmation_not_executable"

    active_id = new_confirmation_id()
    candidate["launch_payload"] = validation.launch_payload
    candidate["confirmation_id"] = active_id
    candidate["artifact_id"] = active_id
    candidate["validation"] = {
        "status": "ready_to_run",
        "executable": True,
        "date_adjusted": False,
    }
    return candidate, None


def launch_date_range_of(payload: dict[str, Any]) -> dict[str, str] | None:
    date_range = payload.get("date_range")
    if not isinstance(date_range, dict):
        return None
    start = str(date_range.get("start") or "")
    end = str(date_range.get("end") or "")
    if not start or not end:
        return None
    return {"start": start, "end": end}
