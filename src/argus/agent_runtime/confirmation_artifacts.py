from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from argus.agent_runtime.state.models import ArtifactReference
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
