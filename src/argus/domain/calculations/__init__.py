"""Answer calculations: declarations, compute functions, tests and presenters.

This registry owns the catalog. Free local calculations also become editable
decision kernels; provider-backed calculations preserve their provider policy
and do not fetch again automatically when a decision is opened.
"""

from __future__ import annotations

from argus.domain.tool_declaration import ToolDeclaration


def get_calculation_declarations() -> tuple[ToolDeclaration, ...]:
    from argus.domain.calculations.bond_value import get_bond_value_declaration
    from argus.domain.calculations.debt_to_income import get_debt_to_income_declaration
    from argus.domain.calculations.discounted_cash_flow import (
        get_discounted_cash_flow_declaration,
    )
    from argus.domain.calculations.effective_rate import get_effective_rate_declaration
    from argus.domain.calculations.expense_ratio import get_expense_ratio_declaration
    from argus.domain.calculations.growth_projection import (
        get_growth_projection_declaration,
    )
    from argus.domain.calculations.historical_drawdown import (
        get_historical_drawdown_declaration,
    )
    from argus.domain.calculations.income_yield import get_income_yield_declaration
    from argus.domain.calculations.price_multiple import get_price_multiple_declaration
    from argus.domain.calculations.ranked_comparison import (
        get_ranked_comparison_declaration,
    )
    from argus.domain.calculations.scaled_amount import get_scaled_amount_declaration
    from argus.domain.calculations.time_value import get_time_value_declaration
    from argus.domain.calculations.valuation_scenarios import (
        get_valuation_scenarios_declaration,
    )

    return (
        get_time_value_declaration(),
        get_scaled_amount_declaration(),
        get_growth_projection_declaration(),
        get_bond_value_declaration(),
        get_discounted_cash_flow_declaration(),
        get_price_multiple_declaration(),
        get_income_yield_declaration(),
        get_effective_rate_declaration(),
        get_debt_to_income_declaration(),
        get_expense_ratio_declaration(),
        get_ranked_comparison_declaration(),
        get_valuation_scenarios_declaration(),
        get_historical_drawdown_declaration(),
    )


def is_free_calculation(declaration: ToolDeclaration) -> bool:
    """Whether a declaration can be recomputed instantly without provider calls."""
    policy = declaration.policy
    return (
        policy.execution == "local"
        and policy.confirmation == "never"
        and policy.external_calls == 0
        and bool(policy.editable_fields)
    )


def is_calculation(declaration: ToolDeclaration) -> bool:
    """The calculation registry owns answer admission, history and markers."""
    return is_free_calculation(declaration) or any(
        item.name == declaration.name for item in get_calculation_declarations()
    )
