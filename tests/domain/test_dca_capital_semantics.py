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
from typing import Any

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


def test_every_request_refusal_reaches_the_card_under_its_own_name() -> None:
    """A wrapped ValueError keeps its code; no refusal degrades to a generic one.

    The confirm stage used to recognise five hard-coded codes and call
    everything else ``missing_rule_group``, so each new rule silently lost its
    name on the way to the user. This asserts the general behaviour over every
    refusal the request model can raise, including ones added later.
    """
    from argus.agent_runtime.stages.confirm import _validation_error_code
    from argus.domain.engine_launch.models import LaunchBacktestRequest
    from pydantic import ValidationError

    base = {
        "strategy_type": "dca_accumulation",
        "symbol": "AAPL",
        "timeframe": "1D",
        "date_range": {"start": "2024-01-02", "end": "2024-12-31"},
        "sizing_mode": "capital_amount",
        "capital_amount": 200.0,
        "cadence": "monthly",
        "parameters": {},
        "risk_rules": [],
        "benchmark_symbol": "SPY",
    }
    refusals = {
        "contribution_period_exceeds_window": {
            "date_range": {"start": "2024-01-02", "end": "2024-01-22"}
        },
        "dca_capital_role_conflict": {"recurring_contribution": 999.0},
        "future_end_date": {
            "date_range": {"start": "2024-01-02", "end": "2999-12-31"}
        },
        "invalid_chronological_date_range": {
            "date_range": {"start": "2024-12-31", "end": "2024-01-02"}
        },
        "cadence_not_applicable": {"strategy_type": "buy_and_hold"},
        "starting_capital_not_applicable": {
            "strategy_type": "buy_and_hold",
            "cadence": None,
            "starting_capital": 1_000.0,
        },
    }

    for expected, override in refusals.items():
        try:
            LaunchBacktestRequest(**{**base, **override})
        except ValidationError as exc:
            assert _validation_error_code(exc) == expected, expected
        else:  # pragma: no cover - a refusal that stopped refusing
            raise AssertionError(f"{expected} no longer refuses")


@pytest.mark.parametrize(
    ("period", "requested_end", "fits"),
    [
        # A window that is exactly one period long stays runnable after the
        # provider moves its boundary to the nearest session.
        ("monthly", "2024-01-31", True),
        ("weekly", "2024-01-08", True),
        ("quarterly", "2024-03-31", True),
        # A window genuinely shorter than its period is still refused.
        ("monthly", "2024-01-22", False),
        ("quarterly", "2024-02-28", False),
    ],
)
def test_a_period_is_measured_against_the_window_the_user_asked_for(
    period: str,
    requested_end: str,
    fits: bool,
) -> None:
    """Coverage narrows the dates; the rule still answers the user's question.

    Provider alignment can move a boundary onto the next session, so measuring
    against the served window would refuse "January, monthly" for being one day
    short of the month it literally is.
    """
    from argus.agent_runtime.stages.confirm import _validation_error_code
    from argus.domain.engine_launch.models import LaunchBacktestRequest
    from pydantic import ValidationError

    request = {
        "strategy_type": "dca_accumulation",
        "symbol": "AAPL",
        "timeframe": "1D",
        # What coverage served: the first session on or after the request.
        "date_range": {"start": "2024-01-02", "end": requested_end},
        # What the user asked for.
        "requested_date_range": {"start": "2024-01-01", "end": requested_end},
        "sizing_mode": "capital_amount",
        "capital_amount": 200.0,
        "cadence": period,
        "parameters": {},
        "risk_rules": [],
        "benchmark_symbol": "SPY",
    }
    try:
        LaunchBacktestRequest(**request)
    except ValidationError as exc:
        assert not fits, f"{period} to {requested_end} should have been accepted"
        assert _validation_error_code(exc) == "contribution_period_exceeds_window"
    else:
        assert fits, f"{period} to {requested_end} should have been refused"


def test_an_unsupported_period_is_refused_rather_than_reported_as_applied() -> None:
    """The applier drops a period it cannot use, so the resolver must refuse it.

    An operation marked applied and then silently discarded is the shape the
    edit contract exists to prevent: the card comes back unchanged while the
    response says the change landed.
    """
    from argus.agent_runtime.artifact_edit_planner import (
        EditOperation,
        apply_edit_operations,
    )

    for value in ("fortnightly", "every other tuesday", "yearly"):
        resolved = apply_edit_operations(
            [EditOperation(op="set", target="cadence", value=value)]
        )
        assert resolved.cadence is None, value
        assert "set.cadence" in resolved.unsupported, value
        assert "set.cadence" not in resolved.applied, value

    for value in CONTRIBUTION_PERIOD_VALUES:
        resolved = apply_edit_operations(
            [EditOperation(op="set", target="cadence", value=value)]
        )
        assert resolved.cadence == value
        assert resolved.unsupported == []


def test_no_card_producer_lets_the_two_roles_collapse() -> None:
    """One invariant over every path that can mint a recurring card.

    The AST guard catches a cross-role read inside one expression. It cannot
    catch a field whose *meaning* changed while some writer kept filling it the
    old way, which is how retest came to fund a plan twice. This drives each
    producer with a seed and a contribution that are deliberately different and
    asserts neither ever shows up as the other.
    """
    from argus.agent_runtime.confirmation_direct_edit import (
        direct_edit_confirmation_preparation,
    )
    from argus.agent_runtime.retest_confirmation import retest_confirmation_payload
    from argus.api.chat.confirmation import runtime_confirmation_card
    from argus.domain.retest_setup import RetestSetup

    SEED, CONTRIBUTION = 7_500.0, 200.0
    window = {"start": "2024-01-02", "end": "2024-12-31"}
    strategy = {
        "strategy_type": "dca_accumulation",
        "asset_universe": ["AAPL"],
        "asset_class": "equity",
        "cadence": "monthly",
        "capital_amount": CONTRIBUTION,
        "date_range": dict(window),
        "extra_parameters": {"field_provenance": {"cadence": "explicit_user"}},
    }

    produced: dict[str, dict[str, Any]] = {}

    # 1. The conversational path, through the card builder every turn uses.
    produced["conversational"] = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "confirmation_id": "confirmation-roles",
                "strategy": strategy,
                "optional_parameters": {
                    "initial_capital": {"value": SEED, "source": "user"},
                },
                "launch_payload": {"sizing_mode": "capital_amount"},
            },
        }
    )["display_facts"]

    # 2. The typed no-turn edit path.
    prepared = direct_edit_confirmation_preparation(
        {
            "strategy": strategy,
            "launch_payload": {"sizing_mode": "capital_amount"},
            "optional_parameters": {},
        },
        capital=None,
        date_window=None,
        starting_capital=SEED,
        recurring_contribution=CONTRIBUTION,
    )
    assert prepared.confirmation_payload is not None, prepared.error_code
    launch = prepared.confirmation_payload["launch_payload"]
    produced["direct_edit"] = {
        "starting_capital": launch["starting_capital"],
        "recurring_contribution": launch["recurring_contribution"],
    }

    # 3. The retest path, rebuilt from a stored run.
    retest = retest_confirmation_payload(
        RetestSetup(
            source_run_id="run-roles",
            strategy_type="dca_accumulation",
            symbols=("AAPL",),
            asset_class="equity",
            timeframe="1D",
            original_start=date(2024, 1, 2),
            original_end=date(2024, 6, 28),
            start=date(2024, 1, 2),
            end=date(2024, 12, 31),
            sizing_mode="capital_amount",
            benchmark_symbol="SPY",
            capital_amount=CONTRIBUTION,
            cadence="monthly",
            recurring_contribution=CONTRIBUTION,
            starting_capital=SEED,
        ),
        language="en",
    )
    produced["retest"] = {
        "starting_capital": retest["launch_payload"]["starting_capital"],
        "recurring_contribution": retest["launch_payload"]["recurring_contribution"],
    }

    for producer, facts in produced.items():
        assert facts["starting_capital"] == SEED, producer
        assert facts["recurring_contribution"] == CONTRIBUTION, producer


def _preflight(*, reason: str, effective: dict[str, str], requested: dict[str, str]):
    return {
        "schema_version": "market_data_coverage_v1",
        "outcome": "adjusted_coverage",
        "requested_date_range": requested,
        "effective_date_range": effective,
        "adjustment_reason": reason,
        "preflight_id": "preflight-455",
        "observations_by_symbol": {"AAPL": 15},
    }


_YEAR = {"start": "2024-01-01", "end": "2024-12-31"}
_JANUARY_ASKED = {"start": "2024-01-01", "end": "2024-01-31"}
_JANUARY_SERVED = {"start": "2024-01-02", "end": "2024-01-31"}
_THREE_WEEKS = {"start": "2024-12-10", "end": "2024-12-31"}


@pytest.mark.parametrize(
    ("label", "date_range", "requested", "reason", "fits"),
    [
        # Nudging a boundary to the nearest session leaves a month a month.
        ("calendar alignment", _JANUARY_SERVED, _JANUARY_ASKED, "calendar_alignment", True),
        # Truncating a year to three weeks does not, so the served window rules.
        ("provider truncation", _THREE_WEEKS, _YEAR, "provider_coverage_adjustment", False),
        # A truncation that still leaves room stays runnable.
        ("truncation with room", _YEAR, _YEAR, "provider_coverage_adjustment", True),
        # With no coverage at all the request's own window is the only truth.
        ("no coverage, short ask", _THREE_WEEKS, None, None, False),
    ],
)
def test_the_window_a_period_must_fit_follows_why_coverage_moved_it(
    label: str,
    date_range: dict[str, str],
    requested: dict[str, str] | None,
    reason: str | None,
    fits: bool,
) -> None:
    """Coverage owns the distinction, so the rule reads it rather than guessing.

    Measuring only the requested span would let a year-long monthly plan mint
    against three weeks of data; measuring only the served span would refuse a
    plain "January, monthly" for being one session short of the month it is.
    """
    from argus.agent_runtime.stages.confirm import _validation_error_code
    from argus.domain.engine_launch.models import LaunchBacktestRequest
    from pydantic import ValidationError

    payload: dict[str, Any] = {
        "strategy_type": "dca_accumulation",
        "symbol": "AAPL",
        "timeframe": "1D",
        "date_range": date_range,
        "sizing_mode": "capital_amount",
        "capital_amount": 200.0,
        "cadence": "monthly",
        "parameters": {},
        "risk_rules": [],
        "benchmark_symbol": "SPY",
    }
    if requested is not None:
        payload["requested_date_range"] = requested
    if reason is not None and requested is not None:
        payload["coverage_preflight"] = _preflight(
            reason=reason,
            effective=date_range,
            requested=requested,
        )

    try:
        LaunchBacktestRequest(**payload)
    except ValidationError as exc:
        assert not fits, f"{label} should have been accepted"
        assert _validation_error_code(exc) == "contribution_period_exceeds_window"
    else:
        assert fits, f"{label} should have been refused"


@pytest.mark.parametrize(
    ("reason", "effective"),
    [
        ("provider_coverage_adjustment", {"start": "2024-12-10", "end": "2024-12-31"}),
        ("calendar_alignment", {"start": "2024-01-02", "end": "2024-12-31"}),
        ("provider_coverage_adjustment", {"start": "2024-06-01", "end": "2024-12-31"}),
        ("none", {"start": "2024-01-01", "end": "2024-12-31"}),
    ],
)
def test_a_card_never_offers_a_period_the_request_model_refuses(
    reason: str,
    effective: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The advertised set and the accepted set are the same set.

    The card promises which periods it will take and the request model refuses
    the ones it will not. Picking the measuring window separately let a card
    offer `monthly` against three weeks of data, so both now read one owner and
    this asserts they cannot disagree for any coverage outcome.
    """
    from argus.api.chat.confirmation import runtime_confirmation_card
    from argus.domain.engine_launch.models import LaunchBacktestRequest
    from pydantic import ValidationError

    # A card only advertises edit constraints while the in-place surface is on,
    # so this pins the flag rather than inheriting whatever ran before it.
    monkeypatch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")

    requested = {"start": "2024-01-01", "end": "2024-12-31"}
    coverage = {
        "schema_version": "market_data_coverage_v1",
        "outcome": "adjusted_coverage",
        "adjustment_reason": reason,
        "requested_date_range": requested,
        "effective_date_range": effective,
        "preflight_id": "preflight-455",
        "observations_by_symbol": {"AAPL": 20},
    }
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "confirmation_id": "confirmation-agreement",
                "strategy": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "cadence": "monthly",
                    "capital_amount": 200.0,
                    "date_range": dict(requested),
                },
                "optional_parameters": {},
                "launch_payload": {
                    "sizing_mode": "capital_amount",
                    "coverage_preflight": coverage,
                },
            },
        }
    )
    offered = set(card["capabilities"]["edit_constraints"]["contribution"]["periods"])

    accepted = set()
    for period in CONTRIBUTION_PERIOD_VALUES:
        try:
            LaunchBacktestRequest(
                strategy_type="dca_accumulation",
                symbol="AAPL",
                timeframe="1D",
                date_range=effective,
                requested_date_range=requested,
                coverage_preflight=coverage,
                sizing_mode="capital_amount",
                capital_amount=200.0,
                cadence=period,
                parameters={},
                risk_rules=[],
                benchmark_symbol="SPY",
            )
        except ValidationError:
            continue
        accepted.add(period)

    assert offered == accepted, f"{reason}: card offers {offered}, engine takes {accepted}"
