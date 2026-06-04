from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from argus.agent_runtime.rule_specs import executable_rule_spec_from_strategy
from argus.agent_runtime.state.models import ArtifactReference
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type,
    resolve_date_range,
)
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.strategies import validate_launch_supported


@dataclass(frozen=True)
class ConfirmationExecutionValidation:
    executable: bool
    launch_payload: dict[str, Any] | None = None
    failure_code: str | None = None


def new_confirmation_id() -> str:
    return f"confirmation-{uuid4()}"


def validate_confirmation_execution_payload(
    confirmation_payload: dict[str, Any],
) -> ConfirmationExecutionValidation:
    launch_payload = confirmation_payload.get("launch_payload")
    if not isinstance(launch_payload, dict) or not launch_payload:
        return ConfirmationExecutionValidation(
            executable=False,
            failure_code="missing_launch_payload",
        )
    try:
        request = LaunchBacktestRequest.model_validate(launch_payload)
        validate_launch_supported(request)
    except ValueError as exc:
        return ConfirmationExecutionValidation(
            executable=False,
            failure_code=str(exc) or "invalid_launch_payload",
        )
    except Exception:
        return ConfirmationExecutionValidation(
            executable=False,
            failure_code="invalid_launch_payload",
        )
    contract_failure = _strategy_contract_failure(confirmation_payload, request)
    if contract_failure is not None:
        return ConfirmationExecutionValidation(
            executable=False,
            failure_code=contract_failure,
        )
    return ConfirmationExecutionValidation(
        executable=True,
        launch_payload=dict(request.model_dump(mode="python")),
    )


def confirmation_artifact_reference(
    *,
    confirmation_id: str,
    confirmation_payload: dict[str, Any],
    confirmation_card: dict[str, Any] | None = None,
) -> ArtifactReference:
    validation = validate_confirmation_execution_payload(confirmation_payload)
    metadata: dict[str, Any] = {
        "confirmation_id": confirmation_id,
        "artifact_type": "confirmation",
        "confirmation_payload": confirmation_payload,
        "launch_payload_hash": stable_payload_hash(validation.launch_payload),
        "strategy_hash": stable_payload_hash(confirmation_payload.get("strategy")),
        "validation": {
            "executable": validation.executable,
            "failure_code": validation.failure_code,
        },
    }
    if validation.launch_payload is not None:
        metadata["launch_payload"] = validation.launch_payload
    if confirmation_card is not None:
        metadata["confirmation_card"] = confirmation_card
    return ArtifactReference(
        artifact_kind="confirmation",
        artifact_id=confirmation_id,
        artifact_status="active" if validation.executable else "needs_change",
        metadata=metadata,
    )


def confirmation_id_from_payload(
    confirmation_payload: dict[str, Any],
    fallback: str | None = None,
) -> str:
    for key in ("confirmation_id", "artifact_id"):
        value = confirmation_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback or new_confirmation_id()


def stable_payload_hash(value: Any) -> str | None:
    if value is None:
        return None
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _strategy_contract_failure(
    confirmation_payload: dict[str, Any],
    request: LaunchBacktestRequest,
) -> str | None:
    strategy = confirmation_payload.get("strategy")
    if not isinstance(strategy, dict):
        return None

    expected_strategy_type = executable_strategy_type(strategy)
    if expected_strategy_type and request.strategy_type != expected_strategy_type:
        return "launch_payload_strategy_mismatch"

    expected_symbols = _strategy_symbols(strategy)
    if expected_symbols and request.symbols != expected_symbols:
        return "launch_payload_symbols_mismatch"

    expected_date_range = _strategy_date_range(strategy)
    if (
        expected_date_range is not None
        and request.date_range.model_dump(mode="python") != expected_date_range
    ):
        return "launch_payload_date_range_mismatch"

    expected_benchmark = _expected_benchmark(confirmation_payload, strategy)
    if expected_benchmark is not None and request.benchmark_symbol != expected_benchmark:
        return "launch_payload_benchmark_mismatch"

    if expected_strategy_type == "signal_strategy":
        expected_rule_spec = executable_rule_spec_from_strategy(strategy)
        if expected_rule_spec is None or request.rule_spec != expected_rule_spec:
            return "launch_payload_rule_mismatch"
        return None

    if expected_strategy_type in {"buy_and_hold", "dca_accumulation"} and any(
        [
            request.entry_rule,
            request.exit_rule,
            request.rule_spec,
        ]
    ):
        return "launch_payload_rule_mismatch"

    if expected_strategy_type == "indicator_threshold" and request.rule_spec is not None:
        return "launch_payload_rule_mismatch"

    return None


def _strategy_symbols(strategy: dict[str, Any]) -> list[str]:
    asset_universe = strategy.get("asset_universe")
    if not isinstance(asset_universe, list):
        return []
    symbols: list[str] = []
    for value in asset_universe:
        symbol = str(value).strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _strategy_date_range(strategy: dict[str, Any]) -> dict[str, str] | None:
    value = strategy.get("date_range")
    if not isinstance(value, dict) or value in ({}, []):
        return None
    try:
        return resolve_date_range(value).payload
    except Exception:
        return None


def _strategy_benchmark(strategy: dict[str, Any]) -> str | None:
    for key in ("comparison_baseline", "benchmark_symbol"):
        value = strategy.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _expected_benchmark(
    confirmation_payload: dict[str, Any],
    strategy: dict[str, Any],
) -> str | None:
    return _strategy_benchmark(strategy) or _optional_benchmark(confirmation_payload)


def _optional_benchmark(confirmation_payload: dict[str, Any]) -> str | None:
    optional_parameters = confirmation_payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        return None
    value = optional_parameters.get("benchmark_symbol")
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return None
