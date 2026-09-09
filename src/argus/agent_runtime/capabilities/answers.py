from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argus.domain.tool_declaration import ToolCatalog

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret_types import CapabilityQuestionFocus
from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES
from argus.domain.capability_registry import indicator_template
from argus.domain.indicators import EXECUTABLE_INDICATORS
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

EXECUTABLE_STRATEGY_FAMILIES: tuple[str, ...] = tuple(
    capability.display_name
    for capability in STRATEGY_CAPABILITIES.values()
    if capability.status == "executable"
)


def capability_fact_packet(
    *,
    focus: CapabilityQuestionFocus | None,
    contract: CapabilityContract,
    tool_catalog: ToolCatalog | None = None,
) -> str:
    if tool_catalog is None:
        from argus.domain.capability_registry import get_tool_catalog

        tool_catalog = get_tool_catalog()
    if focus == "supported_indicators":
        focused_facts = _supported_indicators_answer()
    elif focus == "supported_strategies":
        focused_facts = _supported_strategies_answer()
    elif focus == "limits":
        focused_facts = _limits_answer(contract)
    elif focus == "assets":
        focused_facts = _assets_answer()
    else:
        focused_facts = _general_answer(contract)
    return f"Declared tools: {tool_catalog.capability_text()} {focused_facts}"


def _supported_indicators_answer() -> str:
    # Inputs are single-sourced from the capability registry: the executable indicator
    # specs (what computes) and, separately, which of those are reachable through a
    # dedicated supported template (the registry's reachability truth).
    indicators = _join_labels(spec.label for spec in EXECUTABLE_INDICATORS.values())
    parameter_summary = "; ".join(
        _indicator_parameter_summary(spec.label, spec.default_parameters)
        for spec in EXECUTABLE_INDICATORS.values()
    )
    reachable = _join_labels(
        spec.label
        for key, spec in EXECUTABLE_INDICATORS.items()
        if indicator_template(key) is not None
    )
    return (
        f"Executable indicators right now are {indicators}. "
        f"Defaults are configurable when you say them: {parameter_summary}. "
        f"{reachable} are reachable through a dedicated strategy template today; the "
        "others compute and can be combined inside a signal rule. "
        "Other catalog indicators can be used for drafting and discovery, "
        "but they stay draft-only until Argus has an execution spec that maps their "
        "outputs, defaults, warmup, and rule operators into the backtesting engine."
    )


def _supported_strategies_answer() -> str:
    cadences = _join_labels(SUPPORTED_DCA_CADENCE_VALUES)
    families = _join_labels(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        f"Executable strategy families right now are {families}. "
        f"Recurring buys support {cadences} cadences when a contribution amount is provided. "
        "Indicator and signal strategies are runnable when Argus can validate an "
        "engine rule against the indicator registry."
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
