from __future__ import annotations

import hashlib
import re
from typing import Any

SECRET_KEY_PARTS = ("password", "token", "secret", "service_role", "apikey", "email")
ID_KEY_NAMES = {
    "id",
    "artifact_id",
    "backtest_job_id",
    "confirmation_id",
    "conversation_id",
    "decision_note_id",
    "evidence_artifact_id",
    "idea_id",
    "idea_version_id",
    "message_id",
    "result_run_id",
    "run_id",
    "strategy_id",
    "user_id",
}
UUID_PATTERN = re.compile(
    r"(?<![0-9a-f])"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"(?![0-9a-f])",
    re.IGNORECASE,
)
_HASHED_LABEL_PATTERN = re.compile(r"^[a-z0-9_]+_[0-9a-f]{12}$")


def sanitize_capture_value(value: Any, *, key: str = "") -> Any:
    key_lower = key.lower()
    if any(part in key_lower for part in SECRET_KEY_PARTS):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(nested_key): sanitize_capture_value(
                nested_value,
                key=str(nested_key),
            )
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_capture_value(item, key=key) for item in value]
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if key_lower in ID_KEY_NAMES and stripped:
        if _is_hashed_label(stripped, key=key_lower):
            return stripped
        return _hash_label(key_lower, stripped)
    return UUID_PATTERN.sub(lambda match: _hash_label("uuid", match.group(0)), value)


def assert_sanitized_capture(value: Any, *, key: str = "") -> None:
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            key_text = str(nested_key)
            lowered_key = key_text.lower()
            if any(part in lowered_key for part in SECRET_KEY_PARTS):
                if nested_value != "<redacted>":
                    raise ValueError(f"secret-like field is not allowed: {key_text}")
                continue
            assert_sanitized_capture(nested_value, key=key_text)
        return
    if isinstance(value, list):
        for nested in value:
            assert_sanitized_capture(nested, key=key)
        return
    if not isinstance(value, str):
        return
    if UUID_PATTERN.search(value):
        raise ValueError("raw UUID is not allowed in canary capture")
    if key.lower() in ID_KEY_NAMES and value.strip():
        if _is_hashed_label(value, key=key.lower()):
            return
        raise ValueError(f"raw id-like field is not allowed: {key}")


def _hash_label(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _is_hashed_label(value: str, *, key: str) -> bool:
    stripped = value.strip()
    if not _HASHED_LABEL_PATTERN.fullmatch(stripped):
        return False
    return stripped.startswith(("uuid_", f"{key}_"))
