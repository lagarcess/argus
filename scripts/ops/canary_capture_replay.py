from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.state.models import RunState

if __package__:
    from scripts.ops.canary_capture_sanitizer import assert_sanitized_capture
else:
    from canary_capture_sanitizer import (  # type: ignore[no-redef]
        assert_sanitized_capture,
    )


def replay_capture(capture: dict[str, Any]) -> dict[str, Any]:
    """Replay the deterministic result-readout contract from a canary capture."""

    assert_sanitized_capture(capture)
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
