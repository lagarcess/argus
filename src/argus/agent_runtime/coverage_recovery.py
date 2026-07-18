from __future__ import annotations

from typing import Any, Mapping

from argus.agent_runtime.state.models import RunState
from argus.agent_runtime.strategy_contract import requested_date_range_from_strategy
from argus.domain.engine_launch.results import user_safe_failure_detail

COVERAGE_RECOVERY_CODES = {
    "no_common_data_window",
    "insufficient_common_data",
    "market_data_unavailable",
}
APPROVED_WINDOW_DRIFT_CODE = "approved_data_window_unavailable"
PRESERVED_OPTIONAL_PARAMETER_STATUS_FACT = "preserved_optional_parameter_status"

_COVERAGE_RECOVERY_OPTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "change_dates",
        "replacement_values": {"requested_field": "date_range"},
    },
    {
        "id": "change_asset",
        "replacement_values": {"requested_field": "asset_universe"},
    },
    {
        "id": "change_benchmark",
        "replacement_values": {"requested_field": "comparison_baseline"},
    },
)


def coverage_recovery_options() -> list[dict[str, Any]]:
    return [
        {
            "id": option["id"],
            "replacement_values": dict(option["replacement_values"]),
        }
        for option in _COVERAGE_RECOVERY_OPTIONS
    ]


def coverage_recovery_stage_patch(
    *,
    error_code: str,
    launch_payload: Mapping[str, Any],
    optional_parameter_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    code = (
        error_code if error_code in COVERAGE_RECOVERY_CODES else "market_data_unavailable"
    )
    requested_date_range = _structured_date_range(
        launch_payload.get("requested_date_range")
    ) or _structured_date_range(launch_payload.get("date_range"))
    status = dict(optional_parameter_status or {})
    status["coverage_recovery"] = {
        "code": code,
        "requested_date_range": requested_date_range,
        "asset_universe": _symbols(launch_payload),
        "benchmark_symbol": _clean_string(launch_payload.get("benchmark_symbol")),
    }
    return {
        "outcome": "needs_clarification",
        "missing_required_fields": [],
        "requested_field": None,
        "assistant_prompt": None,
        "optional_parameter_status": status,
    }


def coverage_recovery_from_status(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    raw_recovery = value.get("coverage_recovery")
    if not isinstance(raw_recovery, Mapping):
        return None
    code = _clean_string(raw_recovery.get("code"))
    if code not in COVERAGE_RECOVERY_CODES:
        return None
    return {
        "code": code,
        "requested_date_range": _structured_date_range(
            raw_recovery.get("requested_date_range")
        ),
        "asset_universe": _string_list(raw_recovery.get("asset_universe")),
        "benchmark_symbol": _clean_string(raw_recovery.get("benchmark_symbol")),
    }


def optional_parameter_status_without_coverage_recovery(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    status = dict(value or {})
    status.pop("coverage_recovery", None)
    return status


def preserved_optional_parameter_status_from_response_intent(
    value: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    facts = value.get("facts")
    if not isinstance(facts, Mapping):
        return None
    preserved = facts.get(PRESERVED_OPTIONAL_PARAMETER_STATUS_FACT)
    if not isinstance(preserved, Mapping):
        return None
    return optional_parameter_status_without_coverage_recovery(preserved)


def approved_window_reconfirmation_patch(
    *,
    state: RunState,
    tool_call_records: list[dict[str, Any]],
) -> dict[str, Any]:
    strategy = state.candidate_strategy_draft.model_dump(mode="python")
    confirmation = state.confirmation_payload
    confirmation_payload = (
        confirmation.model_dump(mode="python")
        if hasattr(confirmation, "model_dump")
        else dict(confirmation or {})
        if isinstance(confirmation, Mapping)
        else {}
    )
    launch_payload = confirmation_payload.get("launch_payload")
    requested = (
        _structured_date_range(launch_payload.get("requested_date_range"))
        if isinstance(launch_payload, Mapping)
        else None
    ) or requested_date_range_from_strategy(strategy)
    if requested is not None:
        extra_parameters = dict(strategy.get("extra_parameters") or {})
        extra_parameters["requested_date_range"] = dict(requested)
        extra_parameters.pop("effective_date_range", None)
        strategy = {
            **strategy,
            "date_range": dict(requested),
            "extra_parameters": extra_parameters,
        }
    optional_parameter_status = dict(state.optional_parameter_status or {})
    optional_parameter_status.pop("coverage_recovery", None)
    return {
        "candidate_strategy_draft": strategy,
        "confirmation_payload": None,
        "artifact_references": [],
        "optional_parameter_status": optional_parameter_status,
        "tool_call_records": tool_call_records,
        "failure_classification": None,
        "assistant_prompt": None,
        "requested_field": None,
    }


def is_approved_window_drift(capability_context: Mapping[str, Any]) -> bool:
    return capability_context.get("failure_code") == APPROVED_WINDOW_DRIFT_CODE


def safe_capability_context(
    value: Any,
    *,
    failure_category: str | None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    raw_failure_value = value.get("failure_reason") or value.get("failure_code")
    raw_failure_reason = (
        str(raw_failure_value) if raw_failure_value is not None else None
    )
    safe_context = {
        str(key): nested
        for key, nested in value.items()
        if key not in {"failure_reason", "failure_code"}
    }
    if raw_failure_reason is not None and "failure_detail" not in safe_context:
        safe_context["failure_detail"] = user_safe_failure_detail(
            failure_reason=raw_failure_reason,
            failure_category=failure_category,
        )
    return safe_context


def _symbols(payload: Mapping[str, Any]) -> list[str]:
    symbols = _string_list(payload.get("symbols"))
    if symbols:
        return symbols
    symbol = _clean_string(payload.get("symbol"))
    return [symbol] if symbol is not None else []


def _structured_date_range(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    start = _clean_string(value.get("start"))
    end = _clean_string(value.get("end"))
    if start is None or end is None:
        return None
    return {"start": start, "end": end}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [cleaned for item in value if (cleaned := _clean_string(item)) is not None]


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
