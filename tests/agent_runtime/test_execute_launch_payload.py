from __future__ import annotations

from argus.agent_runtime.stages.execute import _launch_payload
from argus.agent_runtime.state.models import RunState


def test_buy_hold_launch_payload_ignores_stale_signal_rule_spec() -> None:
    stale_rule_spec = {
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
    state = RunState.new(
        current_user_message="Backtest buying and holding Tesla over the past year.",
        recent_thread_history=[],
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": "buy_and_hold",
            "strategy_thesis": "Buy and hold Tesla.",
            "asset_universe": ["TSLA"],
            "asset_class": "equity",
            "date_range": "past year",
            "rule_spec": stale_rule_spec,
            "extra_parameters": {
                "raw_strategy_type": "buy_and_hold",
                "rule_spec": stale_rule_spec,
            },
        },
        "optional_parameters": {},
    }

    payload = _launch_payload(state)

    assert payload["strategy_type"] == "buy_and_hold"
    assert payload["symbol"] == "TSLA"
    assert payload["rule_spec"] is None
    assert payload["entry_rule"] is None
    assert payload["exit_rule"] is None
