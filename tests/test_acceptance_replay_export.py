"""Historical acceptance exporters must use the confirmed #653 projection."""

from __future__ import annotations

from tests.evals.acceptance_attribution import (
    FAILURE_METADATA_KEYS,
    allowlisted_failure_metadata,
)
from tests.evals.test_acceptance_attribution import (
    test_historical_exporters_call_the_durable_owner as _assert_drivers_use_owner,
)


def test_export_uses_top_level_clarification_reason() -> None:
    exported = allowlisted_failure_metadata(
        {"clarification": {"reason_code": "unsupported_time_granularity", "payload": {}}}
    )
    assert exported["clarification_reason"] == "unsupported_time_granularity"
    assert tuple(exported) == FAILURE_METADATA_KEYS


def test_export_drivers_no_longer_own_the_nested_path() -> None:
    _assert_drivers_use_owner()
