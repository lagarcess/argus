from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import ConfirmationPayload, RunState
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    resolve_date_range,
)
from argus.domain.market_data import resolve_asset


def execute_stage(*, state: RunState, tool: Any, max_retries: int = 2) -> StageResult:
    payload = _launch_payload(state)
    records: list[dict[str, Any]] = []
    last_error_type: str | None = None

    for attempt in range(1, max(max_retries, 1) + 1):
        envelope = tool.run(payload)
        record = _build_tool_call_record(
            tool=tool,
            attempt=attempt,
            envelope=envelope,
        )
        records.append(record)

        if envelope.get("success"):
            return StageResult(
                outcome="execution_succeeded",
                stage_patch={
                    "tool_call_records": records,
                    "failure_classification": None,
                    "final_response_payload": _final_response_payload(
                        envelope.get("payload")
                    ),
                },
            )

        error_type = _as_optional_str(envelope.get("error_type"))
        failure_classification = _runtime_failure_classification(error_type)
        last_error_type = failure_classification
        retryable = bool(envelope.get("retryable"))
        capability_context = dict(envelope.get("capability_context") or {})
        corrected_payload: dict[str, Any] | None = None
        if error_type == "parameter_validation_error":
            corrected_payload = _corrected_payload(capability_context)
            if corrected_payload is None or not _correction_preserves_user_intent(
                original_payload=payload,
                corrected_payload=corrected_payload,
            ):
                return StageResult(
                    outcome="execution_failed_terminally",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": _fallback_prompt(
                            error_type=failure_classification,
                            error_message=_as_optional_str(
                                envelope.get("error_message")
                            ),
                        ),
                        "final_response_payload": {
                            "error": _as_optional_str(envelope.get("error_message")),
                        },
                    },
                )
        if not should_retry(
            error_type=error_type,
            retryable=retryable,
            attempt=attempt,
            max_retries=max_retries,
            capability_context=capability_context,
        ):
            if failure_classification in {
                "missing_required_input",
                "unsupported_capability",
                "ambiguous_user_intent",
            }:
                return StageResult(
                    outcome="needs_clarification",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": _fallback_prompt(
                            error_type=failure_classification,
                            error_message=_as_optional_str(
                                envelope.get("error_message")
                            ),
                        ),
                        "missing_required_fields": _missing_required_fields(
                            capability_context
                        ),
                        "final_response_payload": {
                            "error": _as_optional_str(envelope.get("error_message")),
                        },
                    },
                )
            return StageResult(
                outcome="execution_failed_terminally",
                stage_patch={
                    "tool_call_records": records,
                    "failure_classification": failure_classification,
                    "assistant_prompt": _fallback_prompt(
                        error_type=failure_classification,
                        error_message=_as_optional_str(envelope.get("error_message")),
                    ),
                    "final_response_payload": {
                        "error": _as_optional_str(envelope.get("error_message")),
                    },
                    },
                )
        if error_type == "parameter_validation_error":
            payload = corrected_payload

    return StageResult(
        outcome="execution_failed_terminally",
        stage_patch={
            "tool_call_records": records,
            "failure_classification": last_error_type,
            "assistant_prompt": _fallback_prompt(
                error_type=last_error_type,
                error_message=_retry_exhausted_message(records),
            ),
            "final_response_payload": {"error": _retry_exhausted_message(records)},
        },
    )


def _confirmation_payload(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.model_dump(mode="python")
    return dict(payload)


def _launch_payload(state: RunState) -> dict[str, Any]:
    confirmation_payload = _confirmation_payload(state)
    if _is_launch_request_payload(confirmation_payload):
        return confirmation_payload

    strategy = _strategy_payload(confirmation_payload, state)
    optional_parameters = _optional_parameters_payload(confirmation_payload)
    strategy_type = _resolve_strategy_type(strategy, optional_parameters)
    symbol = _resolve_symbol(strategy)
    sizing_mode = _resolve_sizing_mode(optional_parameters)
    position_size = _resolve_position_size(optional_parameters)
    capital_amount = (
        None
        if sizing_mode == "position_size"
        else _resolve_capital_amount(strategy, optional_parameters, strategy_type)
    )

    return {
        "strategy_type": strategy_type,
        "symbol": symbol,
        "timeframe": _resolve_optional_value(optional_parameters, "timeframe", default="1D"),
        "date_range": _resolve_date_range(strategy.get("date_range")),
        "entry_rule": _resolve_entry_rule(strategy, strategy_type),
        "exit_rule": _resolve_exit_rule(strategy, strategy_type),
        "sizing_mode": sizing_mode,
        "capital_amount": capital_amount,
        "position_size": position_size if sizing_mode == "position_size" else None,
        "cadence": _resolve_cadence(strategy, optional_parameters, strategy_type),
        "parameters": _resolve_parameters(optional_parameters),
        "risk_rules": _resolve_risk_rules(strategy),
        "benchmark_symbol": _resolve_benchmark_symbol(symbol, optional_parameters),
    }


def _build_tool_call_record(
    *,
    tool: Any,
    attempt: int,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    payload = envelope.get("payload")
    return {
        "tool_name": _tool_name(tool),
        "attempt": attempt,
        "success": bool(envelope.get("success")),
        "error_type": _as_optional_str(envelope.get("error_type")),
        "error_message": _as_optional_str(envelope.get("error_message")),
        "retryable": bool(envelope.get("retryable")),
        "capability_context": dict(envelope.get("capability_context") or {}),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _tool_name(tool: Any) -> str:
    return getattr(tool.__class__, "__name__", "backtest_tool").lower()


def _final_response_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"result": payload}
    if {"envelope", "result_card", "explanation_context"}.intersection(payload):
        return {
            "result": payload.get("envelope"),
            "result_card": payload.get("result_card"),
            "explanation_context": payload.get("explanation_context"),
        }
    return {"result": payload}


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _missing_required_fields(capability_context: dict[str, Any]) -> list[str]:
    missing_fields = capability_context.get("missing_required_fields", [])
    if not isinstance(missing_fields, list):
        return []
    return [str(field_name) for field_name in missing_fields]


def _fallback_prompt(*, error_type: str | None, error_message: str | None) -> str | None:
    if _is_lookback_limit_error(error_message):
        return (
            "That date range is longer than the current backtest engine supports. "
            "Argus can run up to 3 years at a time right now. Choose a shorter "
            "window, like February 7, 2021 - February 7, 2024, or change the "
            "start and end dates."
        )
    if error_type == "unsupported_capability":
        if error_message:
            return (
                f"{error_message} I can help you reframe this into a supported backtest "
                "or simplify it to a same-asset strategy Argus can run now."
            )
        return (
            "That request is outside the current backtest capability. "
            "I can help you reframe it into a supported same-asset strategy."
        )
    if error_type == "ambiguous_user_intent":
        if error_message:
            return (
                f"{error_message} Should I keep working on the current idea, "
                "or are you starting a new backtest?"
            )
        return (
            "I need one clarification before I run anything. "
            "Should I keep working on the current idea, or are you starting a new backtest?"
        )
    return error_message


def _is_lookback_limit_error(error_message: str | None) -> bool:
    if not error_message:
        return False
    normalized = error_message.strip().lower()
    return "invalid_lookback_window" in normalized or "lookback" in normalized


def _corrected_payload(capability_context: dict[str, Any]) -> dict[str, Any] | None:
    corrected_payload = capability_context.get("corrected_payload")
    if not isinstance(corrected_payload, dict) or not corrected_payload:
        return None
    return deepcopy(corrected_payload)


def _correction_preserves_user_intent(
    *,
    original_payload: dict[str, Any],
    corrected_payload: dict[str, Any] | None,
) -> bool:
    if corrected_payload is None:
        return False
    original_strategy = _strategy_fields(original_payload)
    corrected_strategy = _strategy_fields(corrected_payload)
    protected_fields = (
        "strategy_thesis",
        "asset_universe",
        "entry_logic",
        "exit_logic",
        "date_range",
    )
    return all(
        _protected_field_matches(
            field_name=field_name,
            original_value=original_strategy.get(field_name),
            corrected_value=corrected_strategy.get(field_name),
            field_supplied=field_name in corrected_strategy,
        )
        for field_name in protected_fields
    )


def _strategy_fields(payload: dict[str, Any]) -> dict[str, Any]:
    if _is_launch_request_payload(payload):
        return {
            "strategy_thesis": None,
            "asset_universe": [payload.get("symbol")],
            "entry_logic": payload.get("entry_rule"),
            "exit_logic": payload.get("exit_rule"),
            "date_range": payload.get("date_range"),
        }
    strategy = payload.get("strategy", {})
    if isinstance(strategy, dict):
        return dict(strategy)
    return {}


def _protected_field_matches(
    *,
    field_name: str,
    original_value: Any,
    corrected_value: Any,
    field_supplied: bool,
) -> bool:
    if not field_supplied:
        return True
    if original_value is None:
        return True
    if field_name == "asset_universe":
        return _normalize_asset_universe(original_value) == _normalize_asset_universe(
            corrected_value
        )
    return _normalize_scalar_field(original_value) == _normalize_scalar_field(
        corrected_value
    )


def _normalize_asset_universe(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip().upper() for item in value)


def _normalize_scalar_field(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _runtime_failure_classification(error_type: str | None) -> str:
    known_taxonomy = {
        "parameter_validation_error",
        "missing_required_input",
        "unsupported_capability",
        "tool_execution_error",
        "upstream_dependency_error",
        "ambiguous_user_intent",
        "internal_system_error",
    }
    if error_type in known_taxonomy:
        return str(error_type)
    if error_type in {"service_overloaded", "rate_limited", "timeout"}:
        return "upstream_dependency_error"
    return "tool_execution_error"


def _retry_exhausted_message(records: list[dict[str, Any]]) -> str:
    if not records:
        return "Retry limit reached"
    last_record = records[-1]
    error_message = _as_optional_str(last_record.get("error_message"))
    if error_message:
        return f"Retry limit reached after the last upstream failure: {error_message}"
    error_type = _as_optional_str(last_record.get("error_type"))
    if error_type:
        return f"Retry limit reached after the last upstream failure: {error_type}"
    return "Retry limit reached"


def _is_launch_request_payload(payload: dict[str, Any]) -> bool:
    required_fields = {
        "strategy_type",
        "symbol",
        "timeframe",
        "date_range",
        "sizing_mode",
        "benchmark_symbol",
    }
    return required_fields.issubset(payload)


def _strategy_payload(
    confirmation_payload: dict[str, Any],
    state: RunState,
) -> dict[str, Any]:
    strategy = confirmation_payload.get("strategy")
    if isinstance(strategy, dict):
        return dict(strategy)
    candidate_strategy = state.candidate_strategy_draft
    if hasattr(candidate_strategy, "model_dump"):
        return candidate_strategy.model_dump(mode="python")
    if isinstance(candidate_strategy, dict):
        return dict(candidate_strategy)
    return {}


def _optional_parameters_payload(confirmation_payload: dict[str, Any]) -> dict[str, Any]:
    optional_parameters = confirmation_payload.get("optional_parameters")
    if isinstance(optional_parameters, dict):
        return dict(optional_parameters)
    return {}


def _resolve_strategy_type(
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
) -> str:
    explicit_strategy_type = strategy.get("strategy_type")
    if isinstance(explicit_strategy_type, str) and explicit_strategy_type:
        return canonical_strategy_type(
            explicit_strategy_type,
            entry_logic=strategy.get("entry_logic"),
            exit_logic=strategy.get("exit_logic"),
            cadence=strategy.get("cadence"),
        )

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_strategy_type = extra_parameters.get("strategy_type")
        if isinstance(nested_strategy_type, str) and nested_strategy_type:
            return canonical_strategy_type(
                nested_strategy_type,
                entry_logic=strategy.get("entry_logic"),
                exit_logic=strategy.get("exit_logic"),
                cadence=strategy.get("cadence"),
            )
        if extra_parameters.get("cadence"):
            return "dca_accumulation"

    cadence = _resolve_cadence(strategy, optional_parameters, "dca_accumulation")
    if cadence is not None:
        return "dca_accumulation"
    if strategy.get("entry_logic") or strategy.get("exit_logic"):
        return "indicator_threshold"
    return "buy_and_hold"


def _normalize_strategy_type(value: str) -> str:
    return canonical_strategy_type(value)


def _resolve_symbol(strategy: dict[str, Any]) -> str:
    asset_universe = strategy.get("asset_universe")
    if isinstance(asset_universe, list) and asset_universe:
        return str(asset_universe[0]).strip().upper()
    if isinstance(asset_universe, str) and asset_universe:
        return asset_universe.strip().upper()
    return ""


def _resolve_date_range(value: Any) -> dict[str, str]:
    return resolve_date_range(value).payload


def _resolve_entry_rule(
    strategy: dict[str, Any],
    strategy_type: str,
) -> dict[str, Any] | None:
    if strategy_type != "indicator_threshold":
        return None
    return _parse_indicator_rule(strategy.get("entry_logic"))


def _resolve_exit_rule(
    strategy: dict[str, Any],
    strategy_type: str,
) -> dict[str, Any] | None:
    if strategy_type != "indicator_threshold":
        return None
    return _parse_indicator_rule(
        strategy.get("exit_logic"),
        default_indicator="rsi",
    )


def _parse_indicator_rule(
    value: Any,
    *,
    default_indicator: str = "rsi",
) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None

    text = value.strip().lower()
    if not text:
        return None

    threshold_match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if threshold_match is None:
        return None

    if any(token in text for token in ("below", "under", "<")):
        operator = "below"
    elif any(token in text for token in ("above", "over", ">")):
        operator = "above"
    else:
        return None

    indicator = default_indicator
    if "rsi" in text:
        indicator = "rsi"

    return {
        "indicator": indicator,
        "operator": operator,
        "threshold": float(threshold_match.group(1)),
    }


def _resolve_sizing_mode(optional_parameters: dict[str, Any]) -> str:
    position_size = _resolve_position_size(optional_parameters)
    if position_size is not None:
        return "position_size"
    return "capital_amount"


def _resolve_capital_amount(
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    strategy_type: str,
) -> float | None:
    strategy_capital = _resolve_strategy_capital_amount(strategy)
    if strategy_capital is not None:
        return strategy_capital
    if strategy_type == "dca_accumulation":
        nested_capital = _resolve_nested_strategy_capital_amount(strategy)
        if nested_capital is not None:
            return nested_capital
    value = _resolve_optional_value(optional_parameters, "initial_capital")
    if value is None:
        return 10000.0
    return _as_optional_float(value)


def _resolve_strategy_capital_amount(strategy: dict[str, Any]) -> float | None:
    return _as_optional_float(strategy.get("capital_amount"))


def _resolve_nested_strategy_capital_amount(strategy: dict[str, Any]) -> float | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    for key in ("capital_amount", "recurring_amount", "contribution_amount"):
        amount = _as_optional_float(extra_parameters.get(key))
        if amount is not None:
            return amount
    return None


def _resolve_position_size(optional_parameters: dict[str, Any]) -> float | None:
    value = _resolve_optional_value(optional_parameters, "position_size")
    return _as_optional_float(value)


def _resolve_cadence(
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    strategy_type: str,
) -> str | None:
    if strategy_type != "dca_accumulation":
        return None

    cadence = strategy.get("cadence")
    if isinstance(cadence, str) and cadence:
        return cadence

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_cadence = extra_parameters.get("cadence")
        if isinstance(nested_cadence, str) and nested_cadence:
            return nested_cadence

    optional_value = _resolve_optional_value(optional_parameters, "cadence")
    if isinstance(optional_value, str) and optional_value:
        return optional_value
    return None


def _resolve_parameters(optional_parameters: dict[str, Any]) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for field_name in ("fees", "slippage", "engine_options"):
        value = _resolve_optional_value(optional_parameters, field_name)
        if value is not None:
            parameters[field_name] = value
    return parameters


def _resolve_risk_rules(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    risk_rules = strategy.get("risk_rules")
    if isinstance(risk_rules, list):
        return [rule for rule in risk_rules if isinstance(rule, dict)]

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        nested_risk_rules = extra_parameters.get("risk_rules")
        if isinstance(nested_risk_rules, list):
            return [rule for rule in nested_risk_rules if isinstance(rule, dict)]
    return []


def _resolve_benchmark_symbol(symbol: str, optional_parameters: dict[str, Any]) -> str:
    value = _resolve_optional_value(optional_parameters, "benchmark_symbol")
    if isinstance(value, str) and value:
        return value.strip().upper()
    try:
        asset = resolve_asset(symbol)
    except Exception:
        asset = None
    if asset is not None and asset.asset_class == "crypto":
        return "BTC"
    return "SPY"


def _resolve_optional_value(
    optional_parameters: dict[str, Any],
    field_name: str,
    *,
    default: Any = None,
) -> Any:
    value = optional_parameters.get(field_name, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _as_optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
