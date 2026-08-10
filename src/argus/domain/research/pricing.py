"""Fail-closed Perplexity Agent API research pricing validation.

Agent responses report the exact multi-step bill. Argus validates that bill
against explicit served-model and tool rates before writing it to the cost
ledger. Unknown served models fail closed so a fallback can never turn
unpriced spend into a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from argus.domain.research.contracts import ResearchUnavailableError

_MILLION = Decimal(1_000_000)
_COST_PRECISION_USD = Decimal("0.000001")
_PROVIDER_COST_PRECISION_USD = Decimal("0.00001")
_PROVIDER_COST_TOLERANCE_USD = Decimal("0.00001")


@dataclass(frozen=True)
class ModelTokenRate:
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    cache_creation_input_usd_per_million: Decimal
    cache_read_input_usd_per_million: Decimal
    max_input_tokens: int | None = None


# Perplexity Agent API rates verified 2026-08-10. GPT-5.6 Sol uses its
# published long-context tier above 272k input tokens.
MODEL_RATE_TABLE_USD_PER_MILLION: dict[str, tuple[ModelTokenRate, ...]] = {
    "openai/gpt-5.6-sol": (
        ModelTokenRate(
            input_usd_per_million=Decimal("5"),
            output_usd_per_million=Decimal("30"),
            cache_creation_input_usd_per_million=Decimal("6.25"),
            cache_read_input_usd_per_million=Decimal("0.5"),
            max_input_tokens=272_000,
        ),
        ModelTokenRate(
            input_usd_per_million=Decimal("10"),
            output_usd_per_million=Decimal("45"),
            cache_creation_input_usd_per_million=Decimal("12.5"),
            cache_read_input_usd_per_million=Decimal("1"),
        ),
    ),
    "anthropic/claude-opus-4-7": (
        ModelTokenRate(
            input_usd_per_million=Decimal("5"),
            output_usd_per_million=Decimal("25"),
            cache_creation_input_usd_per_million=Decimal("6.25"),
            cache_read_input_usd_per_million=Decimal("0.5"),
        ),
    ),
}

TOOL_RATE_TABLE_USD_PER_INVOCATION: dict[str, Decimal] = {
    "finance_search": Decimal("0.005"),
    "web_search": Decimal("0.0025"),
    "fetch_url": Decimal("0.00025"),
}


def validated_research_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int,
    cache_read_input_tokens: int,
    finance_search_invocations: int,
    web_search_invocations: int,
    fetch_url_invocations: int,
    provider_input_cost_usd: Decimal,
    provider_output_cost_usd: Decimal,
    provider_cache_creation_cost_usd: Decimal,
    provider_cache_read_cost_usd: Decimal,
    provider_tool_calls_cost_usd: Decimal,
    provider_tool_costs_usd: dict[str, Decimal],
    provider_total_cost_usd: Decimal,
) -> float:
    """Validate and return the Agent API's exact multi-step billed cost.

    Agent usage aggregates several internal model calls. The provider cost
    components retain the per-call cache and long-context billing that cannot
    be reconstructed from aggregate token counts alone. The rate table remains
    the fail-closed validation boundary for the served model and every tool.
    """
    tiers = _token_rates_for(model)
    if cache_creation_input_tokens + cache_read_input_tokens > input_tokens:
        _malformed("usage.input_tokens_details exceeds usage.input_tokens")
    uncached_input_tokens = (
        input_tokens - cache_creation_input_tokens - cache_read_input_tokens
    )
    candidate_tiers = _candidate_tiers(tiers=tiers, input_tokens=input_tokens)
    _validate_token_component(
        path="usage.cost.input_cost",
        tokens=uncached_input_tokens,
        reported_cost=provider_input_cost_usd,
        rates=tuple(tier.input_usd_per_million for tier in candidate_tiers),
    )
    _validate_token_component(
        path="usage.cost.output_cost",
        tokens=output_tokens,
        reported_cost=provider_output_cost_usd,
        rates=tuple(tier.output_usd_per_million for tier in candidate_tiers),
    )
    _validate_token_component(
        path="usage.cost.cache_creation_cost",
        tokens=cache_creation_input_tokens,
        reported_cost=provider_cache_creation_cost_usd,
        rates=tuple(
            tier.cache_creation_input_usd_per_million for tier in candidate_tiers
        ),
    )
    _validate_token_component(
        path="usage.cost.cache_read_cost",
        tokens=cache_read_input_tokens,
        reported_cost=provider_cache_read_cost_usd,
        rates=tuple(tier.cache_read_input_usd_per_million for tier in candidate_tiers),
    )
    tool_counts = {
        "finance_search": finance_search_invocations,
        "web_search": web_search_invocations,
        "fetch_url": fetch_url_invocations,
    }
    expected_tool_costs = {
        tool: Decimal(count) * TOOL_RATE_TABLE_USD_PER_INVOCATION[tool]
        for tool, count in tool_counts.items()
    }
    expected_tool_total = sum(expected_tool_costs.values(), start=Decimal(0))
    _require_cost_match(
        path="usage.cost.tool_calls_cost",
        reported=provider_tool_calls_cost_usd,
        expected=expected_tool_total,
    )
    for tool, reported in provider_tool_costs_usd.items():
        _require_cost_match(
            path=f"usage.cost.tool_calls_cost_details.{tool}",
            reported=reported,
            expected=expected_tool_costs[tool],
        )
    if provider_tool_costs_usd:
        detailed_total = sum(provider_tool_costs_usd.values(), start=Decimal(0))
        _require_cost_match(
            path="usage.cost.tool_calls_cost_details",
            reported=detailed_total,
            expected=provider_tool_calls_cost_usd,
        )
    component_total = sum(
        (
            provider_input_cost_usd,
            provider_output_cost_usd,
            provider_cache_creation_cost_usd,
            provider_cache_read_cost_usd,
            provider_tool_calls_cost_usd,
        ),
        start=Decimal(0),
    )
    _require_cost_match(
        path="usage.cost.total_cost",
        reported=provider_total_cost_usd,
        expected=component_total,
    )
    return float(
        provider_total_cost_usd.quantize(_COST_PRECISION_USD, rounding=ROUND_HALF_UP)
    )


def _token_rates_for(model: str) -> tuple[ModelTokenRate, ...]:
    tiers = MODEL_RATE_TABLE_USD_PER_MILLION.get(model)
    if tiers is None:
        raise ResearchUnavailableError("unknown_model_rate", model)
    return tiers


def _candidate_tiers(
    *, tiers: tuple[ModelTokenRate, ...], input_tokens: int
) -> tuple[ModelTokenRate, ...]:
    first = tiers[0]
    if first.max_input_tokens is None or input_tokens <= first.max_input_tokens:
        return (first,)
    # Agent usage is the sum of multiple internal calls. Above the first
    # threshold, only the provider knows which individual calls crossed it.
    return tiers


def _validate_token_component(
    *, path: str, tokens: int, reported_cost: Decimal, rates: tuple[Decimal, ...]
) -> None:
    possible_costs = tuple(_rounded_token_cost(tokens, rate) for rate in rates)
    lower = min(possible_costs)
    upper = max(possible_costs)
    if (
        reported_cost < lower - _PROVIDER_COST_TOLERANCE_USD
        or reported_cost > upper + _PROVIDER_COST_TOLERANCE_USD
    ):
        _malformed(f"{path} is outside the served-model rate table")


def _rounded_token_cost(tokens: int, rate: Decimal) -> Decimal:
    return (Decimal(tokens) * rate / _MILLION).quantize(
        _PROVIDER_COST_PRECISION_USD, rounding=ROUND_HALF_UP
    )


def _require_cost_match(*, path: str, reported: Decimal, expected: Decimal) -> None:
    if abs(reported - expected) > _PROVIDER_COST_TOLERANCE_USD:
        _malformed(f"{path} does not match response usage")


def _malformed(detail: str) -> None:
    raise ResearchUnavailableError("malformed_response", detail)
