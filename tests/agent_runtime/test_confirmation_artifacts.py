from __future__ import annotations

from argus.agent_runtime.confirmation_artifacts import (
    canonical_launch_identity_payload,
    stable_payload_hash,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.stages.artifact_context import (
    validated_approval_confirmation_payload,
)
from argus.agent_runtime.state.models import StrategySummary


def _coverage_launch_payload(
    *,
    adjustment_reason: str | None = None,
) -> dict[str, object]:
    coverage_preflight: dict[str, object] = {
        "schema_version": "market_data_coverage_v1",
        "outcome": "adjusted_coverage",
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "effective_date_range": {"start": "2024-01-03", "end": "2024-01-05"},
        "preflight_id": "coverage-fixture",
        "observations_by_symbol": {"AAPL": 3, "SPY": 3},
    }
    if adjustment_reason is not None:
        coverage_preflight["adjustment_reason"] = adjustment_reason
    return {
        "strategy_type": "buy_and_hold",
        "symbol": "AAPL",
        "symbols": ["AAPL"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": {"start": "2024-01-03", "end": "2024-01-05"},
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "coverage_preflight": coverage_preflight,
        "entry_rule": None,
        "exit_rule": None,
        "rule_spec": None,
        "sizing_mode": "capital_amount",
        "capital_amount": 10_000.0,
        "position_size": None,
        "cadence": None,
        "parameters": {},
        "risk_rules": [],
        "benchmark_symbol": "SPY",
        "_execution_realism": None,
        "language": "en",
    }


def test_legacy_coverage_reason_omission_is_accepted_without_hash_drift() -> None:
    legacy_launch_payload = _coverage_launch_payload()

    validation = validate_confirmation_execution_payload(
        {"launch_payload": legacy_launch_payload}
    )

    assert validation.executable is True
    assert validation.launch_payload is not None
    assert "adjustment_reason" not in validation.launch_payload["coverage_preflight"]
    assert stable_payload_hash(validation.launch_payload) == stable_payload_hash(
        legacy_launch_payload
    )


def test_canonical_launch_identity_excludes_coverage_provenance() -> None:
    without_reason = _coverage_launch_payload()
    with_reason = _coverage_launch_payload(adjustment_reason="calendar_alignment")

    assert canonical_launch_identity_payload(with_reason) == without_reason


def test_unknown_coverage_adjustment_reason_is_rejected() -> None:
    validation = validate_confirmation_execution_payload(
        {
            "launch_payload": _coverage_launch_payload(
                adjustment_reason="provider_calendar_guess"
            )
        }
    )

    assert validation.executable is False
    assert validation.failure_code is not None


def test_legacy_confirmation_without_coverage_preflight_requires_reconfirmation() -> None:
    strategy = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=10_000,
    )
    payload = {
        "strategy": strategy.model_dump(mode="python"),
        "launch_payload": {
            "strategy_type": "buy_and_hold",
            "symbol": "TSLA",
            "symbols": ["TSLA"],
            "asset_class": "equity",
            "timeframe": "1D",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "sizing_mode": "capital_amount",
            "capital_amount": 10_000,
            "benchmark_symbol": "SPY",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }

    assert (
        validated_approval_confirmation_payload(
            payload=payload,
            approved_strategy=strategy,
        )
        is None
    )


def test_confirmation_validation_rejects_split_brain_buy_hold_signal_payload() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_above",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_below",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
    }

    validation = validate_confirmation_execution_payload(
        {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["TSLA"],
                "asset_class": "equity",
                "date_range": "past year",
                "extra_parameters": {"raw_strategy_type": "buy_and_hold"},
            },
            "launch_payload": {
                "strategy_type": "signal_strategy",
                "symbol": "TSLA",
                "symbols": ["TSLA"],
                "timeframe": "1D",
                "date_range": {"start": "2025-05-15", "end": "2026-05-15"},
                "entry_rule": None,
                "exit_rule": None,
                "rule_spec": rule_spec,
                "sizing_mode": "capital_amount",
                "capital_amount": 1000.0,
                "position_size": None,
                "cadence": None,
                "parameters": {},
                "risk_rules": [],
                "benchmark_symbol": "SPY",
                "language": "en",
            },
        }
    )

    assert validation.executable is False
    assert validation.failure_code == "launch_payload_strategy_mismatch"
