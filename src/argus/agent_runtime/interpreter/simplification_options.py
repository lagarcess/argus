"""Typed simplification options shared by interpreter recovery paths."""

from __future__ import annotations

from argus.agent_runtime.llm_interpreter_types import LLMSimplificationOption


def asset_class_simplification_options() -> list[LLMSimplificationOption]:
    return [
        LLMSimplificationOption(
            label="Run the strategy with stock symbols only",
            replacement_values={"asset_class": "equity"},
        ),
        LLMSimplificationOption(
            label="Run the strategy with crypto symbols only",
            replacement_values={"asset_class": "crypto"},
        ),
        LLMSimplificationOption(
            label="Split into separate asset-class runs",
            replacement_values={"split_runs": True},
        ),
    ]


def unsupported_strategy_logic_simplification_options() -> list[LLMSimplificationOption]:
    return [
        LLMSimplificationOption(
            label="Use a supported RSI threshold rule",
            replacement_values={"simplify_logic": "rsi_only"},
        ),
        LLMSimplificationOption(
            label="Compare with buy and hold",
            replacement_values={"strategy_type": "buy_and_hold"},
        ),
        LLMSimplificationOption(
            label="Use a supported moving-average crossover",
            replacement_values={
                "strategy_type": "signal_strategy",
                "rule_family": "moving_average_crossover",
            },
        ),
    ]
