from __future__ import annotations

from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.stages.artifact_context import (
    validated_approval_confirmation_payload,
)
from argus.agent_runtime.state.models import StrategySummary


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
