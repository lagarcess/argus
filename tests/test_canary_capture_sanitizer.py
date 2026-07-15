from __future__ import annotations

import pytest

from scripts.ops.canary_capture_sanitizer import (
    assert_sanitized_capture,
    sanitize_capture_value,
)

RAW_ARTIFACT_ID = "453523c4-164c-423f-814c-2afad15d7ce0"
RAW_CONFIRMATION_ID = "c149fa82-7fd1-4e2d-b298-5e057826fd43"
RAW_FUTURE_UUID = "019f5e26-4ec3-7053-814c-e81fa730c0b4"


def test_capture_sanitizer_hashes_artifact_ids_and_embedded_uuids() -> None:
    sanitized = sanitize_capture_value(
        {
            "artifact_id": RAW_ARTIFACT_ID,
            "confirmation_id": f"confirmation:{RAW_CONFIRMATION_ID}",
            "nested": f"source/{RAW_ARTIFACT_ID}/result",
            "future_uuid": f"source/{RAW_FUTURE_UUID}/result",
            "workflow_version_id": "wfv-safe-render-id",
        }
    )

    assert sanitized["artifact_id"].startswith("artifact_id_")
    assert sanitized["confirmation_id"].startswith("confirmation_id_")
    assert RAW_ARTIFACT_ID not in sanitized["nested"]
    assert RAW_FUTURE_UUID not in sanitized["future_uuid"]
    assert sanitized["workflow_version_id"] == "wfv-safe-render-id"
    assert_sanitized_capture(sanitized)


def test_capture_validator_rejects_uuid_embedded_in_longer_string() -> None:
    with pytest.raises(ValueError, match="raw UUID"):
        assert_sanitized_capture(
            {"confirmation_id": f"confirmation:{RAW_CONFIRMATION_ID}"}
        )

    with pytest.raises(ValueError, match="raw UUID"):
        assert_sanitized_capture({"source": f"result:{RAW_FUTURE_UUID}"})
