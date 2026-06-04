from __future__ import annotations

import pandas as pd
from argus.domain.backtesting.rules import (
    compile_rule_signals,
    rule_spec_from_signal_rule,
)


def _sample_ohlcv(rows: int = 60) -> pd.DataFrame:
    pattern = [100, 98, 96, 94, 95, 98, 101, 104, 102, 99]
    close = [float(pattern[i % len(pattern)] + i * 0.05) for i in range(rows)]
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "open": close,
            "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "volume": [1_000_000 + i * 100 for i in range(rows)],
        },
        index=index,
    )


def test_macd_shorthand_rule_normalizes_to_compilable_rule_spec() -> None:
    rule_spec = rule_spec_from_signal_rule(
        {
            "type": "macd_crossover",
            "direction": "bullish",
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
        }
    )

    assert rule_spec is not None
    entry = rule_spec["entry"]["conditions"][0]
    exit_condition = rule_spec["exit"]["conditions"][0]
    assert entry["operator"] == "cross_above"
    assert entry["left"]["key"] == "macd"
    assert entry["left"]["output"] == "macd"
    assert entry["right"]["output"] == "signal"
    assert exit_condition["operator"] == "cross_below"

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(80))
    assert len(entries) == 80
    assert len(exits) == 80


def test_threshold_rule_compiles_entries_and_exits() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 3},
                    "operator": "lte",
                    "right": 30,
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 3},
                    "operator": "gte",
                    "right": 55,
                }
            ]
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(30))

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert len(entries) == 30
    assert len(exits) == 30
    assert entries.index.equals(exits.index)


def test_sma_crossover_rule_compiles_boolean_signals() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 3},
                    "operator": "cross_above",
                    "right": {"kind": "indicator", "key": "sma", "period": 7},
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 3},
                    "operator": "cross_below",
                    "right": {"kind": "indicator", "key": "sma", "period": 7},
                }
            ]
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(80))

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert len(entries) == 80
    assert len(exits) == 80


def test_price_above_ema_rule_compiles_with_group_combinators() -> None:
    rule_spec = {
        "entry": {
            "combinator": "all",
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "gt",
                    "right": {"kind": "indicator", "key": "ema", "period": 5},
                },
                {
                    "left": {"kind": "volume", "field": "volume"},
                    "operator": "gt",
                    "right": 999_000,
                },
            ],
        },
        "exit": {
            "combinator": "any",
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "lt",
                    "right": {"kind": "indicator", "key": "ema", "period": 5},
                }
            ],
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(50))

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert entries.index.equals(exits.index)


def test_macd_crossover_rule_compiles_multi_output_indicator_signals() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 3, "slow": 6, "signal": 2},
                    },
                    "operator": "cross_above",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 3, "slow": 6, "signal": 2},
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 3, "slow": 6, "signal": 2},
                    },
                    "operator": "cross_below",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 3, "slow": 6, "signal": 2},
                    },
                }
            ]
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(80))

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert entries.index.equals(exits.index)


def test_bollinger_band_rule_compiles_price_against_named_outputs() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "lte",
                    "right": {
                        "kind": "indicator",
                        "key": "bbands",
                        "output": "lower",
                        "parameters": {"length": 10, "std": 2},
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "price", "field": "close"},
                    "operator": "gte",
                    "right": {
                        "kind": "indicator",
                        "key": "bbands",
                        "output": "middle",
                        "parameters": {"length": 10, "std": 2},
                    },
                }
            ]
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(60))

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert entries.index.equals(exits.index)


def test_volume_sma_rule_uses_requested_source_column() -> None:
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "volume", "field": "volume"},
                    "operator": "gt",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 5,
                        "field": "volume",
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "volume", "field": "volume"},
                    "operator": "lt",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 5,
                        "field": "volume",
                    },
                }
            ]
        },
    }

    entries, exits = compile_rule_signals(rule_spec, data=_sample_ohlcv(50))

    assert entries.dtype == bool
    assert exits.dtype == bool
