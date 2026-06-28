"""Canonical capability registry: the single source of derived capability truth.

The typed *data* lives in its existing homes — `strategy_capabilities.STRATEGY_CAPABILITIES`
(strategies, each carrying a typed `status`) and `indicators.EXECUTABLE_INDICATORS`
(indicator execution specs). This module is the one place every other allow-list derives
from, so the same truth feeds the runtime contract, the engine config, the API schema,
the save passthrough, discovery, and capability answers.

Spine guardrail: everything here is typed structured data and set membership over enums
the LLM emits (`strategy_type`, `indicator.key`). Nothing scans prose or LLM free-text.
See `docs/specs/private-alpha-next-p2.1a-capability-registry-impl.md`.
"""

from __future__ import annotations

from argus.domain.capability_status import CapabilityStatus
from argus.domain.indicators import EXECUTABLE_INDICATORS
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

# --- Strategy derivations -------------------------------------------------------------

# User-facing templates that are reachable end-to-end (status == executable).
EXECUTABLE_TEMPLATES: frozenset[str] = frozenset(
    template
    for template, capability in STRATEGY_CAPABILITIES.items()
    if capability.status == "executable"
)

# Templates present in the registry but with no supported user-facing path.
DRAFT_TEMPLATES: frozenset[str] = frozenset(STRATEGY_CAPABILITIES) - EXECUTABLE_TEMPLATES

# Execution strategy types accepted by the runtime contract / confirm gate. Derived from
# the executable strategies' execution types (e.g. buy_the_dip + rsi_mean_reversion both
# map to indicator_threshold; moving_average_crossover maps to signal_strategy).
SUPPORTED_STRATEGY_TYPES: frozenset[str] = frozenset(
    capability.execution_strategy_type
    for capability in STRATEGY_CAPABILITIES.values()
    if capability.status == "executable" and capability.execution_strategy_type
)

# Templates accepted by engine config validation: the executable user-facing templates
# plus the generic `signal_strategy` execution template (an execution type the launch
# path uses directly, not a user-facing capability key).
ALLOWED_TEMPLATES: frozenset[str] = EXECUTABLE_TEMPLATES | {"signal_strategy"}


def strategy_status(template: str) -> CapabilityStatus | None:
    capability = STRATEGY_CAPABILITIES.get(template)
    return capability.status if capability is not None else None


def is_executable_strategy(template: str) -> bool:
    return template in EXECUTABLE_TEMPLATES


# --- Indicator derivations ------------------------------------------------------------

# Explicit, hand-maintained map of which supported, user-facing template consumes each
# executable indicator end-to-end. It is NOT auto-derived: RSI is consumed by
# rsi_mean_reversion's rsi-only `indicator` parameter, and SMA by moving_average_crossover
# (hardcoded in backtesting/signals.py). test_reachability_map_is_internally_consistent
# ties the RSI entry back to the rsi_mean_reversion parameter so the map cannot silently
# drift from the strategy definition. EMA/MACD/Bollinger compute but no named template
# consumes them (they remain usable inside a generic signal_strategy rule), so they stay
# draft — not executable — until a dedicated template exposes them.
INDICATOR_TEMPLATE_REACHABILITY: dict[str, str] = {
    "rsi": "rsi_mean_reversion",
    "sma": "moving_average_crossover",
}

# Indicators the engine can compute (have an execution spec).
EXECUTABLE_INDICATOR_KEYS: frozenset[str] = frozenset(EXECUTABLE_INDICATORS)
# Indicators reachable end-to-end via a named supported template.
REACHABLE_INDICATOR_KEYS: frozenset[str] = frozenset(INDICATOR_TEMPLATE_REACHABILITY)


def indicator_computes(key: str) -> bool:
    """True when the engine has an execution spec that computes this indicator."""
    return key in EXECUTABLE_INDICATORS


def indicator_template(key: str) -> str | None:
    """The named supported template that consumes this indicator, if any."""
    return INDICATOR_TEMPLATE_REACHABILITY.get(key)


def indicator_status(key: str) -> CapabilityStatus:
    """Typed 3-state capability status for an indicator.

    executable -> reachable via a named supported template (RSI, SMA)
    draft      -> computes but no named template consumes it (EMA, MACD, Bollinger)
    future     -> recognised in the catalog but not computable (ATR, VWAP, OBV, ...)
    """
    if indicator_template(key) is not None:
        return "executable"
    if indicator_computes(key):
        return "draft"
    return "future"
