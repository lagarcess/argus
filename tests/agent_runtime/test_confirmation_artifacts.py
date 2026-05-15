from __future__ import annotations

from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
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
