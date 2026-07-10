from __future__ import annotations

from pathlib import Path

from argus.agent_runtime.recovery_messages import recovery_message, recovery_state
from argus.api.chat.result_actions import missing_refine_strategy_action_turn
from argus.api.schemas import ChatActionPayload

REPO_ROOT = Path(__file__).resolve().parents[2]

S3_BACKEND_SURFACES = [
    REPO_ROOT / "src/argus/agent_runtime/recovery_messages.py",
    REPO_ROOT / "src/argus/agent_runtime/clarification_contract.py",
    REPO_ROOT / "src/argus/agent_runtime/artifact_action_recovery.py",
    REPO_ROOT / "src/argus/agent_runtime/stages/execute.py",
    REPO_ROOT / "src/argus/api/chat/result_actions.py",
]


def test_recovery_state_is_code_payload_not_language_bucket() -> None:
    state = recovery_state(
        "execution_data_unavailable",
        retryable=True,
        language="es-419",
        data_kind="benchmark",
    )

    assert state == {
        "code": "execution_data_unavailable",
        "retryable": True,
        "params": {"data_kind": "benchmark"},
    }
    assert "language" not in state


def test_recovery_message_accepts_language_only_for_legacy_text_compatibility() -> None:
    text = recovery_message("runtime_failure", language="es-419")

    assert text == "Something went wrong. Your conversation is saved. Please try again."


def test_missing_refine_action_turn_emits_recovery_code_for_web_i18n() -> None:
    turn = missing_refine_strategy_action_turn(
        action=ChatActionPayload(type="refine_strategy", label="Refine idea"),
        language="es-419",
    )

    assert turn.metadata["recovery"] == {
        "code": "result_refine_missing",
        "retryable": False,
    }
    assert turn.final_payload["recovery"] == turn.metadata["recovery"]
    assert "language" not in turn.final_payload["recovery"]


def test_s3_backend_surfaces_do_not_reintroduce_runtime_language_gates() -> None:
    forbidden = (
        "_is_spanish",
        'Literal["en", "es-419"]',
        "resolve_recovery_language",
        'startswith("es")',
        "startswith('es')",
        "es-419",
    )
    offenders: dict[str, list[str]] = {}
    for path in S3_BACKEND_SURFACES:
        text = path.read_text()
        hits = [needle for needle in forbidden if needle in text]
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits

    assert not offenders
