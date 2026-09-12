"""Valuation scenarios from typed inputs, as labeled low-to-high ranges."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.finance.outcomes import NoSolution


@dataclass(frozen=True)
class Scenario:
    label: str
    growth: float
    multiple: float
    per_share_at_horizon: float
    price_at_horizon: float
    annual_return: float


def scenario_price(
    per_share: float, growth: float, multiple: float, horizon: float
) -> float:
    return per_share * (1.0 + growth) ** horizon * multiple


def implied_annual_return(
    price: float, future_price: float, horizon: float
) -> float | NoSolution:
    if horizon <= 0:
        return NoSolution(field="horizon_years", code="no_periods")
    if price <= 0 or future_price <= 0:
        return NoSolution(field="price", code="growth_needs_positive_values")
    return (future_price / price) ** (1.0 / horizon) - 1.0


def valuation_scenarios(
    *,
    price: float,
    per_share: float,
    growth: tuple[float, float, float],
    multiples: tuple[float, float, float],
    horizon: float,
) -> list[Scenario] | NoSolution:
    """Low, base and high cases from paired growth and multiple assumptions."""
    if horizon <= 0:
        return NoSolution(field="horizon_years", code="no_periods")
    if price <= 0:
        return NoSolution(field="price", code="growth_needs_positive_values")
    if per_share <= 0:
        return NoSolution(field="per_share", code="growth_needs_positive_values")
    scenarios: list[Scenario] = []
    for label, growth_rate, multiple in zip(
        ("low", "base", "high"), growth, multiples, strict=False
    ):
        if multiple <= 0 or growth_rate <= -1:
            return NoSolution(
                field=f"multiple_{label}", code="growth_needs_positive_values"
            )
        future_per_share = per_share * (1.0 + growth_rate) ** horizon
        future_price = future_per_share * multiple
        annual = implied_annual_return(price, future_price, horizon)
        if isinstance(annual, NoSolution):
            return annual
        scenarios.append(
            Scenario(
                label=label,
                growth=growth_rate,
                multiple=multiple,
                per_share_at_horizon=future_per_share,
                price_at_horizon=future_price,
                annual_return=annual,
            )
        )
    return scenarios
