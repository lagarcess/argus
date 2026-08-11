"""Fail-closed Perplexity Agent API research pricing validation.

Agent responses report the exact multi-step bill. Argus validates that bill
against explicit served-model and tool rates before writing it to the cost
ledger. Unknown served models fail closed so a fallback can never turn
unpriced spend into a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

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
    _validate_tier_mix(
        total_input_tokens=input_tokens,
        short_tier_max_input_tokens=tiers[0].max_input_tokens,
        input_components=(
            (
                uncached_input_tokens,
                provider_input_cost_usd,
                tuple(tier.input_usd_per_million for tier in candidate_tiers),
            ),
            (
                cache_creation_input_tokens,
                provider_cache_creation_cost_usd,
                tuple(
                    tier.cache_creation_input_usd_per_million for tier in candidate_tiers
                ),
            ),
            (
                cache_read_input_tokens,
                provider_cache_read_cost_usd,
                tuple(tier.cache_read_input_usd_per_million for tier in candidate_tiers),
            ),
        ),
        output_component=(
            output_tokens,
            provider_output_cost_usd,
            tuple(tier.output_usd_per_million for tier in candidate_tiers),
        ),
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


def _validate_tier_mix(
    *,
    total_input_tokens: int,
    short_tier_max_input_tokens: int | None,
    input_components: tuple[tuple[int, Decimal, tuple[Decimal, ...]], ...],
    output_component: tuple[int, Decimal, tuple[Decimal, ...]],
) -> None:
    """Require the aggregate bill to admit a valid per-call tier allocation.

    A long-context call contributes more than the short-tier threshold across
    all input buckets. Component rounding leaves a range of possible long-tier
    token counts; their combined range must describe all-short calls or at
    least one real long-context call, with a compatible output tier.
    """
    rate_counts = {len(rates) for _, _, rates in (*input_components, output_component)}
    if rate_counts == {1}:
        return
    if rate_counts != {2} or short_tier_max_input_tokens is None:
        raise AssertionError("input tier validation supports one threshold")
    if total_input_tokens <= short_tier_max_input_tokens:
        raise AssertionError("long-context candidates below their threshold")

    possible_high_token_ranges = tuple(
        _possible_high_tier_token_range(
            tokens=tokens,
            reported_cost=reported_cost,
            short_rate=rates[0],
            long_rate=rates[1],
        )
        for tokens, reported_cost, rates in input_components
    )
    all_short_input_possible = all(
        minimum == 0 for minimum, _ in possible_high_token_ranges
    )
    long_input_possible = (
        sum(maximum for _, maximum in possible_high_token_ranges)
        > short_tier_max_input_tokens
    )
    output_tokens, output_cost, output_rates = output_component
    minimum_long_output_tokens, maximum_long_output_tokens = (
        _possible_high_tier_token_range(
            tokens=output_tokens,
            reported_cost=output_cost,
            short_rate=output_rates[0],
            long_rate=output_rates[1],
        )
    )
    all_short_calls_possible = (
        all_short_input_possible and minimum_long_output_tokens == 0
    )
    at_least_one_long_call_possible = long_input_possible and (
        output_tokens == 0 or maximum_long_output_tokens > 0
    )
    if not all_short_calls_possible and not at_least_one_long_call_possible:
        _malformed("usage.cost components imply an impossible tier mix")


def _possible_high_tier_token_range(
    *,
    tokens: int,
    reported_cost: Decimal,
    short_rate: Decimal,
    long_rate: Decimal,
) -> tuple[int, int]:
    if long_rate < short_rate:
        raise AssertionError("long-context rate is below the short-context rate")
    if long_rate == short_rate:
        return (0, tokens)

    rounded_reported = reported_cost.quantize(
        _PROVIDER_COST_PRECISION_USD, rounding=ROUND_HALF_UP
    )
    half_quantum = _PROVIDER_COST_PRECISION_USD / 2
    short_cost = Decimal(tokens) * short_rate / _MILLION
    increment_per_high_token = (long_rate - short_rate) / _MILLION
    lower_inclusive = rounded_reported - half_quantum
    upper_exclusive = rounded_reported + half_quantum
    minimum = int(
        ((lower_inclusive - short_cost) / increment_per_high_token).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    maximum = (
        int(
            ((upper_exclusive - short_cost) / increment_per_high_token).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        - 1
    )
    minimum = max(0, minimum)
    maximum = min(tokens, maximum)
    if minimum > maximum:
        _malformed("usage.cost token component has no valid tier allocation")
    return minimum, maximum


def _rounded_token_cost(tokens: int, rate: Decimal) -> Decimal:
    return (Decimal(tokens) * rate / _MILLION).quantize(
        _PROVIDER_COST_PRECISION_USD, rounding=ROUND_HALF_UP
    )


def _require_cost_match(*, path: str, reported: Decimal, expected: Decimal) -> None:
    if abs(reported - expected) > _PROVIDER_COST_TOLERANCE_USD:
        _malformed(f"{path} does not match response usage")


def _malformed(detail: str) -> None:
    raise ResearchUnavailableError("malformed_response", detail)
