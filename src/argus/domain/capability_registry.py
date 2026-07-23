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

from typing import Annotated

from pydantic import AfterValidator, WithJsonSchema

from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

# --- Strategy derivations -------------------------------------------------------------

# Every named strategy Argus recognizes, including draft-only templates. This is a
# derived view of STRATEGY_CAPABILITIES, not a second capability registry.
REGISTERED_STRATEGY_TEMPLATES: frozenset[str] = frozenset(STRATEGY_CAPABILITIES)


def _ensure_registered_strategy_template(value: str) -> str:
    if value not in REGISTERED_STRATEGY_TEMPLATES:
        raise ValueError(f"unrecognized strategy template: {value!r}")
    return value


RegisteredStrategyTemplate = Annotated[
    str,
    AfterValidator(_ensure_registered_strategy_template),
    WithJsonSchema(
        {
            "type": "string",
            "enum": sorted(REGISTERED_STRATEGY_TEMPLATES),
            "title": "RegisteredStrategyTemplate",
        }
    ),
]


def requested_strategy_template_capability_clause() -> str:
    """LLM contract generated from the canonical strategy capability registry."""

    capability_rows = ", ".join(
        f"{template}={STRATEGY_CAPABILITIES[template].status}"
        for template in sorted(REGISTERED_STRATEGY_TEMPLATES)
    )
    return (
        "Named strategy capability identity is separate from execution routing. "
        "When the user names or clearly requests a registered strategy template, "
        "set candidate_strategy_draft.requested_strategy_template to its canonical "
        f"registry key. Registered template statuses are: {capability_rows}. "
        "Preserve a draft template's identity even though it is not runnable: do "
        "not relabel it as buy_and_hold, do not create a rule_spec, and do not ask "
        "the user to define custom logic as though Argus could then run it. For a "
        "draft template, classify the turn as unsupported_or_out_of_scope with "
        "semantic_turn_act=unsupported_request, preserve the user's asset, amount, "
        "and dates, explain that Argus cannot run that named strategy yet, and offer "
        "only genuinely executable alternatives. For an executable template, set "
        "requested_strategy_template too and use its normal execution family.\n\n"
    )


# User-facing templates that are reachable end-to-end (status == executable).
EXECUTABLE_TEMPLATES: frozenset[str] = frozenset(
    template
    for template, capability in STRATEGY_CAPABILITIES.items()
    if capability.status == "executable"
)

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


def indicator_template(key: str) -> str | None:
    """The named supported template that consumes this indicator, if any (else None)."""
    return INDICATOR_TEMPLATE_REACHABILITY.get(key)
