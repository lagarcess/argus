from __future__ import annotations

import asyncio
import hashlib
import json
from copy import deepcopy
from typing import Any

from argus.agent_runtime.coverage_recovery import (
    approved_window_reconfirmation_patch,
    is_approved_window_drift,
    safe_capability_context,
)
from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.recovery_messages import recovery_state
from argus.agent_runtime.rule_specs import (
    executable_rule_spec_from_strategy,
    indicator_threshold_rule,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConfirmationPayload,
    RunState,
)
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    requested_date_range_from_strategy,
    resolve_executable_date_range,
)
from argus.domain.backtesting.config import _execution_realism_feature_enabled
from argus.domain.engine_launch.results import (
    is_user_safe_failure_code,
    user_safe_failure_message,
)
from argus.domain.market_data import resolve_asset


def execute_stage(
    *,
    state: RunState,
    tool: Any,
    max_retries: int = 2,
    language: str = "en",
) -> StageResult:
    payload = _launch_payload(state, language=language)
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
            async_job = _async_backtest_job_payload(envelope.get("payload"))
            if async_job is not None:
                return StageResult(
                    outcome="ready_to_respond",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": None,
                        "assistant_response": _async_backtest_job_message(async_job),
                        "backtest_job": async_job,
                        "final_response_payload": {"backtest_job": async_job},
                        "artifact_references": [
                            ArtifactReference(
                                artifact_kind="backtest_job",
                                artifact_id=str(async_job["id"]),
                                artifact_status=str(async_job.get("status") or ""),
                                metadata=async_job,
                            ).model_dump(mode="python")
                        ],
                    },
                )
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
        if is_approved_window_drift(capability_context):
            return StageResult(
                outcome="ready_for_confirmation",
                stage_patch=approved_window_reconfirmation_patch(
                    state=state,
                    tool_call_records=records,
                ),
            )
        corrected_payload: dict[str, Any] | None = None
        if error_type == "parameter_validation_error":
            corrected_payload = _corrected_payload(capability_context)
            if corrected_payload is None or not _correction_preserves_user_intent(
                original_payload=payload,
                corrected_payload=corrected_payload,
            ):
                assistant_prompt = _fallback_prompt(
                    error_type=failure_classification,
                    error_message=_as_optional_str(envelope.get("error_message")),
                    capability_context=capability_context,
                )
                return StageResult(
                    outcome="execution_failed_terminally",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": assistant_prompt,
                        "final_response_payload": {"error": assistant_prompt},
                        **_failed_action_reference_patch(
                            payload=payload,
                            failure_classification=failure_classification,
                            error=assistant_prompt,
                            retryable=False,
                        ),
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
                assistant_prompt = _fallback_prompt(
                    error_type=failure_classification,
                    error_message=_as_optional_str(envelope.get("error_message")),
                    capability_context=capability_context,
                )
                return StageResult(
                    outcome="needs_clarification",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": assistant_prompt,
                        "missing_required_fields": _missing_required_fields(
                            capability_context
                        ),
                        "final_response_payload": {"error": assistant_prompt},
                    },
                )
            recovery_prompt = _recoverable_execution_prompt(
                payload=payload,
                error_type=failure_classification,
                error_message=_as_optional_str(envelope.get("error_message")),
                records=records,
                language=language,
            )
            if recovery_prompt is not None:
                recovery = _recoverable_execution_recovery_state(
                    error_message=_as_optional_str(envelope.get("error_message")),
                    records=records,
                )
                return StageResult(
                    outcome="execution_failed_recoverably",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": recovery_prompt,
                        "final_response_payload": {
                            "error": recovery_prompt,
                        },
                        **({"recovery": recovery} if recovery is not None else {}),
                        **_failed_action_reference_patch(
                            payload=payload,
                            failure_classification=failure_classification,
                            error=recovery_prompt,
                            retryable=True,
                        ),
                    },
                )
            assistant_prompt = _fallback_prompt(
                error_type=failure_classification,
                error_message=_as_optional_str(envelope.get("error_message")),
                capability_context=capability_context,
            )
            return StageResult(
                outcome="execution_failed_terminally",
                stage_patch={
                    "tool_call_records": records,
                    "failure_classification": failure_classification,
                    "assistant_prompt": assistant_prompt,
                    "final_response_payload": {"error": assistant_prompt},
                    **_failed_action_reference_patch(
                        payload=payload,
                        failure_classification=failure_classification,
                        error=assistant_prompt,
                        retryable=False,
                    ),
                },
            )
        if error_type == "parameter_validation_error":
            payload = corrected_payload
            if isinstance(payload, dict):
                payload["language"] = language

    retry_exhausted = _retry_exhausted_message(records)
    recovery_prompt = _recoverable_execution_prompt(
        payload=payload,
        error_type=last_error_type,
        error_message=retry_exhausted,
        records=records,
        language=language,
    )
    if recovery_prompt is not None:
        recovery = _recoverable_execution_recovery_state(
            error_message=retry_exhausted,
            records=records,
        )
        return StageResult(
            outcome="execution_failed_recoverably",
            stage_patch={
                "tool_call_records": records,
                "failure_classification": last_error_type,
                "assistant_prompt": recovery_prompt,
                "final_response_payload": {"error": recovery_prompt},
                **({"recovery": recovery} if recovery is not None else {}),
                **_failed_action_reference_patch(
                    payload=payload,
                    failure_classification=last_error_type,
                    error=recovery_prompt,
                    retryable=True,
                ),
            },
        )

    assistant_prompt = _fallback_prompt(
        error_type=last_error_type,
        error_message=retry_exhausted,
    )
    return StageResult(
        outcome="execution_failed_terminally",
        stage_patch={
            "tool_call_records": records,
            "failure_classification": last_error_type,
            "assistant_prompt": assistant_prompt,
            "final_response_payload": {"error": assistant_prompt},
            **_failed_action_reference_patch(
                payload=payload,
                failure_classification=last_error_type,
                error=assistant_prompt,
                retryable=False,
            ),
        },
    )


async def execute_stage_async(
    *,
    state: RunState,
    tool: Any,
    max_retries: int = 2,
    language: str = "en",
) -> StageResult:
    return await asyncio.to_thread(
        execute_stage,
        state=state,
        tool=tool,
        max_retries=max_retries,
        language=language,
    )


def _confirmation_payload(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.model_dump(mode="python")
    return dict(payload)


def _launch_payload(state: RunState, *, language: str = "en") -> dict[str, Any]:
    confirmation_payload = _confirmation_payload(state)
    if _is_launch_request_payload(confirmation_payload):
        payload = _normalize_launch_request_payload(dict(confirmation_payload))
        payload["language"] = language
        return payload
    embedded_launch_payload = confirmation_payload.get("launch_payload")
    if isinstance(embedded_launch_payload, dict) and _is_launch_request_payload(
        embedded_launch_payload
    ):
        payload = _normalize_launch_request_payload(deepcopy(embedded_launch_payload))
        payload["language"] = language
        return payload

    strategy = _strategy_payload(confirmation_payload, state)
    optional_parameters = _optional_parameters_payload(confirmation_payload)
    strategy_type = _resolve_strategy_type(strategy, optional_parameters)
    symbols = _resolve_symbols(strategy)
    symbol = symbols[0] if symbols else ""
    sizing_mode = _resolve_sizing_mode(optional_parameters)
    position_size = _resolve_position_size(optional_parameters)
    capital_amount = (
        None
        if sizing_mode == "position_size"
        else _resolve_capital_amount(strategy, optional_parameters, strategy_type)
    )

    payload = {
        "strategy_type": strategy_type,
        "symbol": symbol,
        "symbols": symbols,
        "asset_class": strategy.get("asset_class"),
        "timeframe": _resolve_optional_value(
            optional_parameters, "timeframe", default="1D"
        ),
        "date_range": _resolve_date_range(
            strategy.get("date_range"),
            extra_parameters=strategy.get("extra_parameters"),
        ),
        "entry_rule": _resolve_entry_rule(strategy, strategy_type),
        "exit_rule": _resolve_exit_rule(strategy, strategy_type),
        "rule_spec": (
            executable_rule_spec_from_strategy(strategy)
            if strategy_type == "signal_strategy"
            else None
        ),
        "sizing_mode": sizing_mode,
        "capital_amount": capital_amount,
        "position_size": position_size if sizing_mode == "position_size" else None,
        "cadence": _resolve_cadence(strategy, optional_parameters, strategy_type),
        "parameters": _resolve_parameters(optional_parameters),
        "risk_rules": _resolve_risk_rules(strategy),
        "benchmark_symbol": _resolve_benchmark_symbol(
            symbol,
            optional_parameters,
            strategy=strategy,
        ),
        "language": language,
    }
    requested_date_range = requested_date_range_from_strategy(strategy)
    if requested_date_range is not None:
        payload["requested_date_range"] = requested_date_range
    execution_realism = _resolve_execution_realism(strategy, optional_parameters)
    if execution_realism is not None:
        payload["_execution_realism"] = execution_realism
    return payload


def _build_tool_call_record(
    *,
    tool: Any,
    attempt: int,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    payload = envelope.get("payload")
    error_type = _as_optional_str(envelope.get("error_type"))
    capability_context = safe_capability_context(
        envelope.get("capability_context"),
        failure_category=error_type,
    )
    return {
        "tool_name": _tool_name(tool),
        "attempt": attempt,
        "success": bool(envelope.get("success")),
        "error_type": error_type,
        "error_message": _safe_error_message(
            _as_optional_str(envelope.get("error_message")),
            failure_category=error_type,
        ),
        "retryable": bool(envelope.get("retryable")),
        "capability_context": capability_context,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _tool_name(tool: Any) -> str:
    return getattr(tool.__class__, "__name__", "backtest_tool").lower()


def _final_response_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"result": payload}
    if isinstance(payload.get("backtest_job"), dict):
        return {"backtest_job": dict(payload["backtest_job"])}
    if {"envelope", "result_card", "explanation_context"}.intersection(payload):
        return {
            "result": payload.get("envelope"),
            "result_card": payload.get("result_card"),
            "explanation_context": payload.get("explanation_context"),
        }
    return {"result": payload}


def _async_backtest_job_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    job = payload.get("backtest_job")
    if not isinstance(job, dict):
        return None
    job_id = _as_optional_str(job.get("id"))
    conversation_id = _as_optional_str(job.get("conversation_id"))
    status = _as_optional_str(job.get("status"))
    if not job_id or not conversation_id or not status:
        return None
    return dict(job)


def _async_backtest_job_message(job: dict[str, Any]) -> str:
    status = _as_optional_str(job.get("status")) or "queued"
    if status == "succeeded":
        return "The backtest finished. I am loading the result card now."
    if status in {"failed", "canceled", "expired"}:
        return "The backtest could not finish. I will show the saved status here."
    return (
        "I started the backtest. You can leave this chat and come back; "
        "I will show the result here as soon as it is ready."
    )


def _failed_action_reference_patch(
    *,
    payload: dict[str, Any],
    failure_classification: str | None,
    error: str | None,
    retryable: bool,
) -> dict[str, Any]:
    reference = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id=_failed_action_id(payload=payload, error=error),
        artifact_status="failed",
        metadata={
            "action_type": "run_backtest",
            "launch_payload": deepcopy(payload),
            "failure_classification": failure_classification,
            "error": error,
            "user_safe_message": error,
            "retryable": retryable,
            "recovery_mode": "reopen_confirmation",
        },
    )
    return {
        "latest_failed_action_reference": reference.model_dump(mode="python"),
        "artifact_references": [reference.model_dump(mode="python")],
    }


def _failed_action_id(*, payload: dict[str, Any], error: str | None) -> str:
    stable_payload = {"payload": payload, "error": error}
    digest = hashlib.sha256(
        json.dumps(stable_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"failed-action-{digest}"


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _safe_error_message(
    error_message: str | None,
    *,
    failure_category: str | None,
) -> str | None:
    if error_message is None:
        return None
    if not is_user_safe_failure_code(error_message):
        return error_message
    safe_message = user_safe_failure_message(
        failure_reason=error_message,
        failure_category=failure_category,
    )
    return safe_message


def _missing_required_fields(capability_context: dict[str, Any]) -> list[str]:
    missing_fields = capability_context.get("missing_required_fields", [])
    if not isinstance(missing_fields, list):
        return []
    return [str(field_name) for field_name in missing_fields]


def _fallback_prompt(
    *,
    error_type: str | None,
    error_message: str | None,
    capability_context: dict[str, Any] | None = None,
) -> str | None:
    if _is_kraken_window_limit_error(error_message):
        return (
            "That date range is too wide for currency-pair data at the selected "
            "bar size. "
            "Use a shorter window, or choose 1h, 4h, or 1D bars based on what "
            "still fits the idea."
        )
    if _is_provider_history_start_error(error_message):
        return (
            "That start date is earlier than the equity history Argus can use "
            "right now. Choose a 2016-or-later start date and I can keep the "
            "same idea."
        )
    if _is_lookback_limit_error(error_message):
        return (
            "That date range is outside the available data history for the "
            "selected asset and timeframe. Choose a shorter available window, or "
            "change the start and end dates while keeping the same idea."
        )
    if error_type == "missing_required_input":
        return (
            "I need one more executable detail before I can run this. Tell me the "
            "missing rule, asset, or date range and I will keep the current setup intact."
        )
    if error_type == "unsupported_capability":
        return (
            "That request is outside the current backtest capability. "
            "I can help you reframe this into a supported backtest or simplify "
            "it to a same-asset strategy Argus can run now."
        )
    if error_type == "ambiguous_user_intent":
        return (
            "I need one clarification before I run anything. "
            "Should I keep working on the current idea, or are you starting a new backtest?"
        )
    if error_type == "parameter_validation_error":
        if _failure_detail(capability_context) == "future_date_window":
            return user_safe_failure_message(
                failure_reason="future_end_date",
                failure_category=error_type,
            )
        return (
            "I could not run this because one detail is not valid for the current "
            "backtest. Adjust the asset, rules, or dates and I can try again from "
            "the current setup."
        )
    if error_type == "upstream_dependency_error":
        return (
            "The run hit a temporary data or service issue. Try again from the "
            "current setup or adjust it first."
        )
    return (
        "The backtest could not complete. Try again from the current setup or "
        "adjust it first."
    )


def _failure_detail(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    detail = value.get("failure_detail")
    return str(detail).strip() if detail is not None else None


def _recoverable_execution_prompt(
    *,
    payload: dict[str, Any],
    error_type: str | None,
    error_message: str | None,
    records: list[dict[str, Any]],
    language: str = "en",
) -> str | None:
    _ = language
    if error_type != "upstream_dependency_error":
        return None
    unavailable_data_kind = _unavailable_data_kind(
        error_message=error_message,
        records=records,
    )
    if unavailable_data_kind is None:
        return None

    draft_label = _draft_label_from_payload(payload)
    data_label = _unavailable_data_label(
        data_kind=unavailable_data_kind,
    )
    return (
        f"The {draft_label} setup is still here, but I could not get {data_label} "
        "for that run right now. Try again, change the dates, or choose a different "
        "supported asset."
    )


def _recoverable_execution_recovery_state(
    *,
    error_message: str | None,
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    unavailable_data_kind = _unavailable_data_kind(
        error_message=error_message,
        records=records,
    )
    if unavailable_data_kind is None:
        return None
    return recovery_state(
        "execution_data_unavailable",
        retryable=True,
        data_kind=unavailable_data_kind,
    )


def _unavailable_data_kind(
    *,
    error_message: str | None,
    records: list[dict[str, Any]],
) -> str | None:
    values = [_normalized_failure_value(error_message)]
    for record in records:
        if not isinstance(record, dict):
            continue
        values.append(_normalized_failure_value(record.get("error_message")))
        context = record.get("capability_context")
        if not isinstance(context, dict):
            continue
        values.extend(
            _normalized_failure_value(context.get(field_name))
            for field_name in ("failure_detail", "failure_reason", "failure_code")
        )

    if any(
        value in {"benchmark_data_unavailable", "benchmark_data_issue"}
        for value in values
    ):
        return "benchmark"
    if any(value in {"market_data_unavailable", "market_data_issue"} for value in values):
        return "market"
    return None


def _normalized_failure_value(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _unavailable_data_label(*, data_kind: str) -> str:
    return "benchmark data" if data_kind == "benchmark" else "market data"


def _draft_label_from_payload(payload: dict[str, Any]) -> str:
    symbols = _resolve_symbols(_strategy_fields(payload))
    symbol = symbols[0] if symbols else str(payload.get("symbol") or "").strip().upper()
    symbol_prefix = f"{symbol} " if symbol else ""
    strategy_type = _normalize_strategy_type(
        str(payload.get("strategy_type") or "strategy")
    )
    if strategy_type == "dca_accumulation":
        return f"{symbol_prefix}recurring-buys draft".strip()
    if strategy_type == "buy_and_hold":
        return f"{symbol_prefix}buy-and-hold draft".strip()
    if strategy_type == "indicator_threshold":
        return f"{symbol_prefix}indicator-rule draft".strip()
    if strategy_type == "signal_strategy":
        return f"{symbol_prefix}signal-strategy draft".strip()
    return f"{symbol_prefix}strategy draft".strip()


def _is_lookback_limit_error(error_message: str | None) -> bool:
    if not error_message:
        return False
    normalized = error_message.strip().lower()
    return "invalid_lookback_window" in normalized


def _is_kraken_window_limit_error(error_message: str | None) -> bool:
    if not error_message:
        return False
    normalized = error_message.strip().lower()
    return "kraken_ohlc_window_exceeded" in normalized


def _is_provider_history_start_error(error_message: str | None) -> bool:
    if not error_message:
        return False
    normalized = error_message.strip().lower()
    return "provider_history_start_unavailable" in normalized


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
        "rule_spec",
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
            "rule_spec": payload.get("rule_spec"),
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
    error_type = _as_optional_str(last_record.get("error_type"))
    if error_type:
        return (
            _fallback_prompt(
                error_type=_runtime_failure_classification(error_type),
                error_message=None,
            )
            or "Retry limit reached"
        )
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


def _normalize_launch_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    parameters = normalized.get("parameters")
    if isinstance(parameters, dict):
        normalized["parameters"] = _strategy_parameters_from_launch_payload(parameters)
    return normalized


def _strategy_parameters_from_launch_payload(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(parameters)
    for field_name in ("fees", "slippage"):
        value = normalized.get(field_name)
        if _is_zero_like(value):
            normalized.pop(field_name, None)
    engine_options = normalized.get("engine_options")
    if isinstance(engine_options, dict) and not engine_options:
        normalized.pop("engine_options", None)
    return normalized


def _is_zero_like(value: Any) -> bool:
    if value in (None, "", 0, 0.0, "0", "0.0"):
        return True
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


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
    explicit_strategy_type = _explicit_strategy_type(strategy)
    if explicit_strategy_type in {"buy_and_hold", "dca_accumulation"}:
        return explicit_strategy_type
    entry_rule = strategy_rule(strategy, "entry")
    if (
        isinstance(entry_rule, dict)
        and entry_rule.get("type") == "moving_average_crossover"
    ):
        return "signal_strategy"
    if executable_rule_spec_from_strategy(strategy) is not None:
        return "signal_strategy"
    if explicit_strategy_type == "indicator_threshold":
        return explicit_strategy_type
    if indicator_threshold_rule(strategy, "entry") is not None:
        return "indicator_threshold"
    if explicit_strategy_type == "signal_strategy":
        return "signal_strategy"

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
    return "buy_and_hold"


def _explicit_strategy_type(strategy: dict[str, Any]) -> str | None:
    candidates: list[Any] = [strategy.get("strategy_type")]
    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        candidates.extend(
            [
                extra_parameters.get("raw_strategy_type"),
                extra_parameters.get("strategy_type"),
                extra_parameters.get("template"),
            ]
        )
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        normalized = canonical_strategy_type(
            candidate,
            entry_logic=strategy.get("entry_logic"),
            exit_logic=strategy.get("exit_logic"),
            cadence=strategy.get("cadence"),
        )
        if normalized in {
            "buy_and_hold",
            "dca_accumulation",
            "indicator_threshold",
            "signal_strategy",
        }:
            return normalized
    return None


def _normalize_strategy_type(value: str) -> str:
    return canonical_strategy_type(value)


def _resolve_symbol(strategy: dict[str, Any]) -> str:
    symbols = _resolve_symbols(strategy)
    if symbols:
        return symbols[0]
    return ""


def _resolve_symbols(strategy: dict[str, Any]) -> list[str]:
    asset_universe = strategy.get("asset_universe")
    symbols: list[str] = []
    if isinstance(asset_universe, list) and asset_universe:
        for value in asset_universe:
            symbol = str(value).strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
        return symbols
    if isinstance(asset_universe, str) and asset_universe:
        return [asset_universe.strip().upper()]
    return []


def _resolve_date_range(
    value: Any,
    *,
    extra_parameters: Any = None,
) -> dict[str, str]:
    if (
        isinstance(value, dict)
        and isinstance(value.get("start"), str)
        and isinstance(value.get("end"), str)
    ):
        return resolve_executable_date_range(value).payload
    return resolve_executable_date_range(
        value,
        extra_parameters=extra_parameters if isinstance(extra_parameters, dict) else None,
    ).payload


def _resolve_entry_rule(
    strategy: dict[str, Any],
    strategy_type: str,
) -> dict[str, Any] | None:
    if strategy_type == "signal_strategy":
        return strategy_rule(strategy, "entry")
    if strategy_type == "indicator_threshold":
        return indicator_threshold_rule(strategy, "entry")
    return None


def _resolve_exit_rule(
    strategy: dict[str, Any],
    strategy_type: str,
) -> dict[str, Any] | None:
    if strategy_type == "signal_strategy":
        return strategy_rule(strategy, "exit") or opposite_moving_average_crossover_rule(
            strategy_rule(strategy, "entry")
        )
    if strategy_type != "indicator_threshold":
        return None
    return indicator_threshold_rule(strategy, "exit")


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
        return 1000.0
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
    del optional_parameters
    # User-visible execution assumptions are rendered on confirmation cards, but
    # launch parameters are reserved for strategy inputs the backtest engine can
    # execute. Leaking display assumptions into this namespace makes a valid card
    # fail at run time with unsupported_parameters.
    return {}


def _resolve_execution_realism(
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not _execution_realism_feature_enabled():
        return None
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        extra_parameters = {}
    fee_rate = _as_optional_float(extra_parameters.get("fee_rate"))
    slippage = _as_optional_float(extra_parameters.get("slippage"))
    if isinstance(optional_parameters, dict):
        if fee_rate is None:
            fee_rate = _as_optional_float(
                _resolve_optional_value(optional_parameters, "fees")
            )
        if slippage is None:
            slippage = _as_optional_float(
                _resolve_optional_value(optional_parameters, "slippage")
            )
    # Costs are opt-in and never negative: values at or below zero mean the
    # component is not modeled.
    if fee_rate is None or fee_rate <= 0.0:
        fee_rate = 0.0
    if slippage is None or slippage <= 0.0:
        slippage = 0.0
    if fee_rate == 0.0 and slippage == 0.0:
        return None
    return {
        "enabled": True,
        "fee_bps": _decimal_rate_to_bps(fee_rate),
        "slippage_bps": _decimal_rate_to_bps(slippage),
    }


def _decimal_rate_to_bps(value: float | None) -> float:
    if value is None:
        return 0.0
    return value * 10000.0


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


def _resolve_benchmark_symbol(
    symbol: str,
    optional_parameters: dict[str, Any],
    *,
    strategy: dict[str, Any],
) -> str:
    benchmark = strategy.get("comparison_baseline")
    if isinstance(benchmark, str) and benchmark.strip():
        return benchmark.strip().upper()
    strategy_benchmark = strategy.get("benchmark_symbol")
    if isinstance(strategy_benchmark, str) and strategy_benchmark.strip():
        return strategy_benchmark.strip().upper()
    value = _resolve_optional_value(optional_parameters, "benchmark_symbol")
    if isinstance(value, str) and value:
        return value.strip().upper()
    asset_class = strategy.get("asset_class")
    if asset_class == "equity":
        return "SPY"
    if asset_class == "crypto":
        return "BTC"
    if asset_class == "currency_pair":
        try:
            asset = resolve_asset(symbol)
        except Exception:
            asset = None
        if asset is not None and asset.asset_class == "currency_pair":
            return str(getattr(asset, "canonical_symbol", symbol)).strip().upper()
        return _compact_benchmark_symbol(symbol)
    try:
        asset = resolve_asset(symbol)
    except Exception:
        asset = None
    if asset is not None:
        if asset.asset_class == "crypto":
            return "BTC"
        if asset.asset_class == "currency_pair":
            return str(getattr(asset, "canonical_symbol", symbol)).strip().upper()
    return "SPY"


def _compact_benchmark_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "").replace("-", "").replace(" ", "")


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
