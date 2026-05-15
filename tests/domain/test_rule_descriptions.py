from argus.domain.backtesting.rules import canonicalize_rule_spec, describe_rule_spec
from argus.domain.engine_launch.result_facts import resolved_rule_summary


def test_describe_rule_spec_includes_default_indicator_period() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi"},
                    "operator": "lte",
                    "right": 20,
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi"},
                    "operator": "gte",
                    "right": 60,
                }
            ]
        },
    }

    assert describe_rule_spec(rule_spec, "entry") == "RSI(14) is 20 or lower"
    assert describe_rule_spec(rule_spec, "exit") == "RSI(14) is 60 or higher"


def test_signal_result_summary_uses_generic_rule_spec_descriptions() -> None:
    facts = {
        "resolved_strategy": {
            "strategy_type": "signal_strategy",
            "rule_spec": {
                "entry": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "lte",
                            "right": 20,
                        }
                    ]
                },
                "exit": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "gte",
                            "right": 60,
                        }
                    ]
                },
            },
        }
    }

    assert resolved_rule_summary(facts) == (
        "Entry rule: RSI(14) is 20 or lower; "
        "exit rule: RSI(14) is 60 or higher."
    )


def test_canonicalize_rule_spec_keeps_fast_ma_on_left_for_crossovers() -> None:
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
                    "left": {"kind": "indicator", "key": "sma", "period": 200},
                    "operator": "cross_above",
                    "right": {"kind": "indicator", "key": "sma", "period": 50},
                }
            ]
        },
    }

    canonical = canonicalize_rule_spec(rule_spec)

    exit_condition = canonical["exit"]["conditions"][0]
    assert exit_condition["left"]["period"] == 50
    assert exit_condition["operator"] == "cross_below"
    assert exit_condition["right"]["period"] == 200
    assert describe_rule_spec(canonical, "exit") == (
        "50-day SMA crosses below 200-day SMA"
    )
