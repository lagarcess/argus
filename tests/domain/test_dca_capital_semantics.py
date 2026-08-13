"""The two DCA money roles can never substitute for each other (#455).

Two invariants, not a list of cases. The first says no source line anywhere in
``src`` may derive one role from the other. The second drives the whole shape
space of (seed, contribution) pairs through the real surfaces and asserts every
one of them reports the value it was given, so a defect that swapped the roles
would have to swap them consistently everywhere to survive.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import date

import pandas as pd
import pytest
from argus.domain.backtesting.execution import _dca_equity_curve
from argus.domain.dca_capital import (
    CONTRIBUTION_PERIOD_VALUES,
    DcaCapitalError,
    build_dca_capital_plan,
    contribution_periods_for_window,
    dca_capital_config_fields,
    dca_capital_plan_from_config,
)

_SOURCE_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "argus"

# The two role names as every layer spells them. A source-level fallback
# between any seed spelling and any contribution spelling is the defect.
_SEED_NAMES = frozenset(
    {"starting_capital", "starting_principal", "initial_capital", "seed"}
)
_CONTRIBUTION_NAMES = frozenset(
    {"recurring_contribution", "contribution", "recurring_amount", "contribution_amount"}
)


def _referenced_names(node: ast.AST) -> set[str]:
    """Every identifier and string literal a expression could name a field by."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            names.add(child.value)
    return names


def _role_of(operand: ast.AST) -> str | None:
    """The role an operand would yield, or None if it yields a boolean.

    Asking whether either role arrived is legitimate; taking one role's value
    when the other is missing is the defect. Only value-shaped operands can do
    the second, so predicates are not offenders.
    """
    if isinstance(operand, ast.Compare | ast.BoolOp | ast.UnaryOp | ast.Constant):
        return None
    names = _referenced_names(operand)
    seeds = names & _SEED_NAMES
    contributions = names & _CONTRIBUTION_NAMES
    if seeds and not contributions:
        return "seed"
    if contributions and not seeds:
        return "contribution"
    return None


def _python_sources() -> list[pathlib.Path]:
    return sorted(_SOURCE_ROOT.rglob("*.py"))


def test_no_source_line_derives_one_capital_role_from_the_other() -> None:
    """``a or b`` and ``a if a else b`` across the roles are both the defect.

    This is the structural half of the invariant: the shape that produced #455
    cannot exist in the tree at all, so a future edit cannot reintroduce it in
    a file this lane never touched.
    """
    offenders: list[str] = []
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            operand_groups: list[ast.AST] = []
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                operand_groups = list(node.values)
            elif isinstance(node, ast.IfExp):
                operand_groups = [node.body, node.orelse]
            if len(operand_groups) < 2:
                continue
            roles = {_role_of(operand) for operand in operand_groups}
            if {"seed", "contribution"} <= roles:
                offenders.append(
                    f"{path.relative_to(_SOURCE_ROOT.parents[1])}:{node.lineno}"
                )
    assert offenders == []


def _launch_config(
    *,
    starting_capital: float,
    contribution: float,
    period: str,
) -> dict[str, object]:
    plan = build_dca_capital_plan(
        starting_capital=starting_capital,
        contribution=contribution,
        period=period,
    )
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "side": "long",
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": period},
        **dca_capital_config_fields(plan),
    }


# Distinct values in every position, so a swap can never coincide with a match.
_SEED_VALUES = (0.0, 1.0, 7_500.0)
_CONTRIBUTION_VALUES = (0.01, 200.0, 33_333.0)


@pytest.mark.parametrize("seed", _SEED_VALUES)
@pytest.mark.parametrize("contribution", _CONTRIBUTION_VALUES)
@pytest.mark.parametrize("period", CONTRIBUTION_PERIOD_VALUES)
def test_each_capital_role_round_trips_as_itself(
    seed: float,
    contribution: float,
    period: str,
) -> None:
    """Whatever went into a role comes back out of that role, never the other."""
    config = _launch_config(
        starting_capital=seed,
        contribution=contribution,
        period=period,
    )
    plan = dca_capital_plan_from_config(config)

    assert plan.starting_capital == seed
    assert plan.contribution == contribution
    assert plan.period == period
    # A recurring config carries no shared bankroll slot for either role to be
    # read out of, which is what makes the swap unrepresentable rather than
    # merely untested.
    assert "starting_capital" not in config
    assert "recurring_contribution" not in config
    assert "starting_principal" not in config


@pytest.mark.parametrize("symbol_count", [1, 3, 5])
def test_splitting_a_plan_across_symbols_scales_both_roles_alike(
    symbol_count: int,
) -> None:
    plan = build_dca_capital_plan(
        starting_capital=6_000.0,
        contribution=300.0,
        period="monthly",
    )
    split = plan.per_symbol(symbol_count)

    assert split.starting_capital == 6_000.0 / symbol_count
    assert split.contribution == 300.0 / symbol_count
    assert split.period == plan.period


def test_total_invested_counts_the_seed_once_and_the_contribution_per_buy() -> None:
    plan = build_dca_capital_plan(
        starting_capital=1_000.0,
        contribution=250.0,
        period="monthly",
    )

    assert plan.total_invested(0) == 1_000.0
    assert plan.total_invested(12) == 1_000.0 + 250.0 * 12


@pytest.mark.parametrize(
    ("starting_capital", "contribution", "code"),
    [
        (0.0, 0.0, "dca_requires_starting_capital_or_contribution"),
        (None, None, "dca_requires_starting_capital_or_contribution"),
        (5_000.0, 0.0, "dca_contribution_zero_is_buy_and_hold"),
        (-1.0, 200.0, "invalid_starting_capital"),
        (0.0, -200.0, "invalid_recurring_contribution"),
        (0.0, 100_000_001.0, "invalid_recurring_contribution"),
        (100_000_001.0, 200.0, "invalid_starting_capital"),
    ],
)
def test_an_unfundable_plan_names_its_own_rule(
    starting_capital: float | None,
    contribution: float | None,
    code: str,
) -> None:
    with pytest.raises(DcaCapitalError) as excinfo:
        build_dca_capital_plan(
            starting_capital=starting_capital,
            contribution=contribution,
            period="monthly",
        )

    assert excinfo.value.code == code


def test_a_seed_alone_is_never_silently_reinterpreted_as_a_contribution() -> None:
    """The founder's split: $0 contribution beside a seed is buy and hold."""
    with pytest.raises(DcaCapitalError) as excinfo:
        build_dca_capital_plan(
            starting_capital=10_000.0,
            contribution=0.0,
            period="monthly",
        )

    assert excinfo.value.code == "dca_contribution_zero_is_buy_and_hold"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # A three week window does not offer monthly, per the founder decision.
        (date(2025, 1, 1), date(2025, 1, 21), ("daily", "weekly", "biweekly")),
        (date(2025, 1, 1), date(2025, 1, 1), ("daily",)),
        (date(2025, 1, 1), date(2025, 1, 7), ("daily", "weekly")),
        (date(2025, 1, 1), date(2025, 1, 31), ("daily", "weekly", "biweekly", "monthly")),
        (
            date(2025, 1, 1),
            date(2025, 3, 31),
            ("daily", "weekly", "biweekly", "monthly", "quarterly"),
        ),
    ],
)
def test_only_periods_that_fit_the_window_are_offered(
    start: date,
    end: date,
    expected: tuple[str, ...],
) -> None:
    assert contribution_periods_for_window(start=start, end=end) == expected


@pytest.mark.parametrize("seed", [0.0, 1_000.0])
def test_the_seed_buys_on_day_one_and_contributions_follow(seed: float) -> None:
    """Both roles are invested on their own dates, in fractional shares.

    Prices double after the first bar, so the seed's shares are worth twice
    what they cost and each later contribution is worth exactly what it cost.
    Nothing is left as cash, which is what makes the return denominator the
    plain sum of the two roles.
    """
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    close = pd.Series([10.0, 20.0, 20.0, 20.0], index=index, dtype=float)
    entries = pd.Series([True, True, False, False], index=index, dtype=bool)

    equity, invested = _dca_equity_curve(
        close=close,
        entries=entries,
        contribution=200.0,
        starting_capital=seed,
    )

    # Day one buys the seed and the first contribution at $10 a share.
    assert equity.iloc[0] == pytest.approx(seed + 200.0)
    # The second contribution buys at $20; everything bought at $10 doubled.
    assert equity.iloc[1] == pytest.approx((seed + 200.0) * 2.0 + 200.0)
    assert invested == pytest.approx(seed + 400.0)


def test_changing_only_the_seed_changes_only_the_seed_s_contribution_to_equity() -> None:
    """The roles are independent: moving one never moves the other's effect."""
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    close = pd.Series([10.0, 10.0, 10.0], index=index, dtype=float)
    entries = pd.Series([True, True, True], index=index, dtype=bool)

    without_seed, invested_without = _dca_equity_curve(
        close=close, entries=entries, contribution=200.0, starting_capital=0.0
    )
    with_seed, invested_with = _dca_equity_curve(
        close=close, entries=entries, contribution=200.0, starting_capital=5_000.0
    )

    assert (with_seed - without_seed).round(6).eq(5_000.0).all()
    assert invested_with - invested_without == pytest.approx(5_000.0)


def test_narrowing_a_window_narrows_the_offered_periods() -> None:
    wide = contribution_periods_for_window(
        start=date(2025, 1, 1),
        end=date(2025, 12, 31),
    )
    narrow = contribution_periods_for_window(
        start=date(2025, 1, 1),
        end=date(2025, 1, 10),
    )

    assert set(narrow) < set(wide)
    assert "monthly" not in narrow
