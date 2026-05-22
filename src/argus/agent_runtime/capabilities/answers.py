from __future__ import annotations

from collections.abc import Iterable

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret_types import CapabilityQuestionFocus
from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES
from argus.domain.indicators import EXECUTABLE_INDICATORS

EXECUTABLE_STRATEGY_FAMILIES: tuple[str, ...] = (
    "buy and hold",
    "recurring buys/DCA",
    "indicator threshold rules",
    "signal rules such as moving-average, MACD, price/indicator, and Bollinger Band conditions",
)


def compose_capability_answer(
    *,
    focus: CapabilityQuestionFocus | None,
    contract: CapabilityContract,
) -> str:
    if focus == "supported_indicators":
        return _supported_indicators_answer()
    if focus == "supported_strategies":
        return _supported_strategies_answer()
    if focus == "limits":
        return _limits_answer(contract)
    if focus == "assets":
        return _assets_answer()
    return _general_answer(contract)


def compose_capability_recovery_answer(
    *,
    focus: CapabilityQuestionFocus | None,
    contract: CapabilityContract,
) -> str:
    if focus == "supported_strategies":
        return _supported_strategies_recovery_answer(contract)
    return (
        "I can still keep this grounded. Tell me the asset, period, and the "
        "idea you want to test, and I'll shape the closest runnable historical "
        "experiment. This is simulation evidence, not investment advice."
    )


def _supported_indicators_answer() -> str:
    indicators = _join_labels(spec.label for spec in EXECUTABLE_INDICATORS.values())
    parameter_summary = "; ".join(
        _indicator_parameter_summary(spec.label, spec.default_parameters)
        for spec in EXECUTABLE_INDICATORS.values()
    )
    return (
        f"Executable indicators right now are {indicators}. "
        f"Defaults are configurable when you say them: {parameter_summary}. "
        "Other pandas-ta catalog indicators can be used for drafting and discovery, "
        "but they stay draft-only until Argus has an execution spec that maps their "
        "outputs, defaults, warmup, and rule operators into the backtesting engine."
    )


def _supported_strategies_answer() -> str:
    cadences = _join_labels(SUPPORTED_DCA_CADENCE_VALUES)
    families = _join_labels(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        f"Executable strategy families right now are {families}. "
        f"Recurring buys support {cadences} cadences when a contribution amount is provided. "
        "Indicator and signal strategies are runnable when the LLM can produce a valid "
        "engine rule and the capability layer validates it against the indicator registry."
    )


def _supported_strategies_recovery_answer(contract: CapabilityContract) -> str:
    options = contract.get_simplification_options("unsupported_strategy_logic")
    option_labels = _join_labels(option.label.lower() for option in options)
    if not option_labels:
        option_labels = _join_labels(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        "I can still keep this grounded and runnable.\n\n"
        f"The closest supported paths are to {option_labels}. Tell me the asset "
        "and period you want to explore, plus any recurring contribution or "
        "rule detail you already have.\n\n"
        "This stays inside historical simulation, not investment advice."
    )


def _limits_answer(contract: CapabilityContract) -> str:
    rule_messages = " ".join(rule.message for rule in contract.validation_rules)
    return (
        "Execution limits: runs are long-only, use one asset class per run, default "
        "to SPY for equities and BTC for crypto, and do not place real trades. "
        f"{rule_messages} Mixed asset-class runs, shorting, brokerage execution, "
        "custom scripts, and indicators without execution specs are not runnable yet."
    )


def _assets_answer() -> str:
    return (
        "Assets are resolved through the shared provider-backed catalog before a card "
        "is marked ready to run. Equities, crypto, and currency pairs are valid asset "
        "classes, but a single backtest must stay within one class. If an asset exists "
        "but the requested window is unavailable, Argus should preserve the draft and "
        "ask for a runnable window instead of pretending it can execute."
    )


def _general_answer(contract: CapabilityContract) -> str:
    strategies = _supported_strategies_answer()
    limits = _limits_answer(contract)
    return f"{strategies} {limits}"


def _indicator_parameter_summary(
    label: str,
    defaults: dict[str, int | float | str],
) -> str:
    if not defaults:
        return f"{label} uses its registry defaults"
    values = ", ".join(f"{key}={value}" for key, value in defaults.items())
    return f"{label} {values}"


def _join_labels(values: Iterable[str]) -> str:
    labels = [str(value) for value in values if str(value)]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"
