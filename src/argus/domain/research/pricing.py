"""Deterministic Perplexity Agent API research pricing.

Rates are explicit because provider responses report usage, while Argus owns
the derived amount written to its cost ledger. Unknown served models fail
closed so a model fallback can never turn unpriced spend into a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from argus.domain.research.contracts import ResearchUnavailableError

_MILLION = Decimal(1_000_000)
_COST_PRECISION_USD = Decimal("0.000001")


@dataclass(frozen=True)
class ModelTokenRate:
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    max_input_tokens: int | None = None


# Perplexity Agent API rates verified 2026-08-10. GPT-5.6 Sol uses its
# published long-context tier above 272k input tokens.
MODEL_RATE_TABLE_USD_PER_MILLION: dict[str, tuple[ModelTokenRate, ...]] = {
    "openai/gpt-5.6-sol": (
        ModelTokenRate(
            input_usd_per_million=Decimal("5"),
            output_usd_per_million=Decimal("30"),
            max_input_tokens=272_000,
        ),
        ModelTokenRate(
            input_usd_per_million=Decimal("10"),
            output_usd_per_million=Decimal("45"),
        ),
    ),
    "anthropic/claude-opus-4-7": (
        ModelTokenRate(
            input_usd_per_million=Decimal("5"),
            output_usd_per_million=Decimal("25"),
        ),
    ),
}

TOOL_RATE_TABLE_USD_PER_INVOCATION: dict[str, Decimal] = {
    "finance_search": Decimal("0.005"),
    "web_search": Decimal("0.0025"),
    "fetch_url": Decimal("0.00025"),
}


def derive_research_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    finance_search_invocations: int,
    web_search_invocations: int,
    fetch_url_invocations: int,
) -> float:
    """Price one completed Agent API response from its actual usage."""
    rate = _token_rate_for(model=model, input_tokens=input_tokens)
    total = (
        Decimal(input_tokens) * rate.input_usd_per_million / _MILLION
        + Decimal(output_tokens) * rate.output_usd_per_million / _MILLION
    )
    tool_counts = {
        "finance_search": finance_search_invocations,
        "web_search": web_search_invocations,
        "fetch_url": fetch_url_invocations,
    }
    for tool, count in tool_counts.items():
        total += Decimal(count) * TOOL_RATE_TABLE_USD_PER_INVOCATION[tool]
    return float(total.quantize(_COST_PRECISION_USD, rounding=ROUND_HALF_UP))


def _token_rate_for(*, model: str, input_tokens: int) -> ModelTokenRate:
    tiers = MODEL_RATE_TABLE_USD_PER_MILLION.get(model)
    if tiers is None:
        raise ResearchUnavailableError("unknown_model_rate", model)
    for tier in tiers:
        if tier.max_input_tokens is None or input_tokens <= tier.max_input_tokens:
            return tier
    raise AssertionError(f"model rate table has no terminal tier: {model}")
