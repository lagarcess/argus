from __future__ import annotations

import argparse
import json
import string
import uuid
from pathlib import Path
from typing import Any

from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.state.models import RunState

SECRET_KEY_PARTS = ("password", "token", "secret", "service_role", "apikey", "email")
ID_KEY_NAMES = {
    "id",
    "conversation_id",
    "run_id",
    "result_run_id",
    "backtest_job_id",
    "message_id",
    "user_id",
}


def replay_capture(capture: dict[str, Any]) -> dict[str, Any]:
    """Replay the deterministic result-readout contract from a canary capture."""

    _assert_sanitized(capture)
    language = str(
        capture.get("language")
        or (capture.get("launch_payload") or {}).get("language")
        or "en"
    )
    resolved_language = _resolve_language(language)
    state = RunState.new(
        current_user_message="replay failed canary capture",
        recent_thread_history=[],
    )
    launch_payload = capture.get("launch_payload")
    if isinstance(launch_payload, dict):
        confirmation_payload = launch_payload.get("confirmation_payload")
        if isinstance(confirmation_payload, dict):
            state.confirmation_payload = confirmation_payload

    final_response_payload = _final_response_payload(capture)
    if not final_response_payload:
        raise ValueError("capture does not include final_response_payload")
    state.final_response_payload = final_response_payload

    result = explain_stage(state=state, language=resolved_language)
    quick_take = str(result.stage_patch.get("assistant_response") or "")
    if not quick_take:
        raise ValueError("capture replay did not render a quick take")

    return {
        "language": language,
        "resolved_language": resolved_language,
        "failure": capture.get("failure") or {},
        "route_receipt": capture.get("route_receipt") or {"status": "missing"},
        "quick_take": quick_take,
    }


def load_capture(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("capture root must be a JSON object")
    return payload


def _final_response_payload(capture: dict[str, Any]) -> dict[str, Any]:
    payload = capture.get("final_response_payload")
    if isinstance(payload, dict):
        return dict(payload)
    result = capture.get("result")
    explanation_context = capture.get("explanation_context")
    if isinstance(result, dict):
        response_payload: dict[str, Any] = {"result": result}
        if isinstance(explanation_context, dict):
            response_payload["explanation_context"] = explanation_context
        return response_payload
    return {}


def _assert_sanitized(value: Any, *, key: str = "") -> None:
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            key_text = str(nested_key)
            lowered_key = key_text.lower()
            if any(part in lowered_key for part in SECRET_KEY_PARTS):
                if nested_value != "<redacted>":
                    raise ValueError(f"secret-like field is not allowed: {key_text}")
                continue
            _assert_sanitized(nested_value, key=key_text)
        return
    if isinstance(value, list):
        for nested in value:
            _assert_sanitized(nested, key=key)
        return
    if isinstance(value, str):
        if _is_uuid(value):
            raise ValueError("raw UUID is not allowed in canary capture")
        if key.lower() in ID_KEY_NAMES and value.strip():
            if _is_hashed_label(key, value):
                return
            raise ValueError(f"raw id-like field is not allowed: {key}")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value.strip())
    except (TypeError, ValueError):
        return False
    return True


def _is_hashed_label(key: str, value: str) -> bool:
    stripped = value.strip()
    prefixes = ("uuid", key.lower())
    for prefix in prefixes:
        marker = f"{prefix}_"
        if not stripped.startswith(marker):
            continue
        digest = stripped.removeprefix(marker)
        return len(digest) == 12 and all(char in string.hexdigits for char in digest)
    return False


def _resolve_language(language: str) -> str:
    return "es-419" if str(language or "").lower().startswith("es") else "en"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a sanitized failed private-alpha canary capture locally."
    )
    parser.add_argument("capture_path", help="Path to sanitized canary capture JSON")
    args = parser.parse_args()

    report = replay_capture(load_capture(args.capture_path))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
