from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from server.argus_core.calculations import get_calculation_declarations
from server.argus_core.calculations._shared import no_solution
from server.argus_core.finance.outcomes import NoSolution
from server.argus_core.tool_contracts import ToolCall, ToolResultCard
from server.argus_core.tool_declaration import ToolCatalog, ToolInvocationError

CALCULATION_CASES = {
    "time_value": (
        {
            "currency": "USD",
            "direction": "borrow",
            "present_value": 200_000,
            "payment": None,
            "future_value": 0,
            "annual_rate_pct": 6,
            "periods": 360,
        },
        1_199.10,
    ),
    "growth_projection": (
        {
            "currency": "USD",
            "start_value": 1_000,
            "contribution": 100,
            "end_value": None,
            "annual_rate_pct": 7,
            "periods": 120,
            "inflation_rate_pct": 3,
        },
        19_318.14,
    ),
    "bond_value": (
        {
            "currency": "USD",
            "face_value": 1_000,
            "coupon_rate_pct": 5,
            "years": 10,
            "coupons_per_year": 2,
            "price": None,
            "yield_to_maturity_pct": 6,
        },
        925.61,
    ),
    "discounted_cash_flow": (
        {
            "currency": "USD",
            "cash_flow": 100,
            "discount_rate_pct": 10,
            "years": 5,
            "terminal_growth_rate_pct": 2,
            "growth_rate_pct": 5,
            "value": None,
        },
        1_446.21,
    ),
    "price_multiple": (
        {
            "currency": "USD",
            "symbol": "AAPL",
            "price": 150,
            "per_share": 6,
            "multiple": None,
        },
        25.0,
    ),
    "income_yield": (
        {
            "currency": "USD",
            "annual_income": 4,
            "price": 100,
            "yield_pct": None,
        },
        4.0,
    ),
    "effective_rate": (
        {
            "currency": "USD",
            "nominal_rate_pct": 12,
            "compounding_per_year": 12,
        },
        12.68,
    ),
    "debt_to_income": (
        {
            "currency": "USD",
            "monthly_debt_payments": 1_500,
            "monthly_income": 5_000,
            "ratio_pct": None,
        },
        30.0,
    ),
    "expense_ratio": (
        {
            "currency": "USD",
            "assets": 10_000,
            "annual_fee": None,
            "ratio_pct": 0.5,
            "years": 30,
            "growth_rate_pct": 7,
        },
        50.0,
    ),
    "ranked_comparison": (
        {
            "currency": "DOP",
            "key_label": "Annual rate",
            "key_kind": "percent",
            "prefer": "lower",
            "items": [
                {"label": "Card A", "value": 24.9},
                {"label": "Card B", "value": 18.5},
            ],
        },
        18.5,
    ),
    "valuation_scenarios": (
        {
            "currency": "USD",
            "symbol": "AAPL",
            "price": 150,
            "per_share": 6,
            "growth_low_pct": 3,
            "growth_base_pct": 8,
            "growth_high_pct": 12,
            "multiple_low": 18,
            "multiple_base": 22,
            "multiple_high": 28,
            "horizon_years": 5,
        },
        5.27,
    ),
}


def _card(name: str, arguments: dict[str, object]) -> ToolResultCard:
    declaration = ToolCatalog(get_calculation_declarations()).get(name)
    assert declaration is not None
    call = ToolCall(tool_name=name, call_id=f"call-{name}", arguments=arguments)
    outcome = declaration.invoke_sync(call.arguments)
    return declaration.result_card(
        call=call,
        outcome=outcome,
        artifact_id=f"artifact-{name}",
    )


@pytest.mark.parametrize("name", CALCULATION_CASES)
def test_every_reused_declaration_runs_its_production_math(name: str) -> None:
    arguments, expected = CALCULATION_CASES[name]
    card = _card(name, arguments)

    assert card.outcome.status == "succeeded"
    assert card.presentation.answer is not None
    assert card.presentation.answer.value == pytest.approx(expected, abs=0.01)
    assert card.presentation.sources == []


def test_catalog_is_the_single_complete_local_calculation_registry() -> None:
    catalog = ToolCatalog(get_calculation_declarations())

    assert {item.name for item in catalog.declarations} == set(CALCULATION_CASES)
    assert all(item.policy.execution == "local" for item in catalog.declarations)
    assert all(item.policy.external_calls == 0 for item in catalog.declarations)
    assert all(item.policy.confirmation == "never" for item in catalog.declarations)
    assert "time_value" in catalog.capability_text()


def test_recompute_preserves_the_selected_unknown_and_updates_provenance() -> None:
    declaration = ToolCatalog(get_calculation_declarations()).get("time_value")
    assert declaration is not None
    original = CALCULATION_CASES["time_value"][0]

    revised = declaration.recompute_arguments(original, {"annual_rate_pct": 7})

    assert revised.payment is None
    assert revised.annual_rate_pct == 7
    assert revised.sources["annual_rate_pct"].kind == "user"
    with pytest.raises(ValueError, match="retain the selected unknown"):
        declaration.recompute_arguments(original, {"payment": 1_200})


@pytest.mark.parametrize(("currency", "expected"), [("JPY", 33.0), ("KWD", 33.333)])
def test_money_presentation_uses_clara_currency_precision(
    currency: str, expected: float
) -> None:
    card = _card(
        "income_yield",
        {
            "currency": currency,
            "annual_income": 1,
            "price": None,
            "yield_pct": 3,
        },
    )

    assert card.outcome.result is not None
    assert card.outcome.result["price"] == pytest.approx(100 / 3)
    assert card.presentation.answer is not None
    assert card.presentation.answer.value == expected


@pytest.mark.parametrize(
    ("currency", "annual_income", "yield_pct", "expected"),
    [
        ("JPY", 1.0, 40.0, 3.0),
        ("KWD", 0.12345, 10.0, 1.235),
    ],
)
def test_half_unit_rounding_is_shared_by_answer_and_scenario_presenters(
    currency: str,
    annual_income: float,
    yield_pct: float,
    expected: float,
) -> None:
    answer_card = _card(
        "income_yield",
        {
            "currency": currency,
            "annual_income": annual_income,
            "price": None,
            "yield_pct": yield_pct,
        },
    )
    scenario_card = _card(
        "valuation_scenarios",
        {
            "currency": currency,
            "symbol": "TEST",
            "price": 1.0,
            "per_share": 1.0,
            "growth_low_pct": 0.0,
            "growth_base_pct": 0.0,
            "growth_high_pct": 0.0,
            "multiple_low": annual_income / (yield_pct / 100.0),
            "multiple_base": annual_income / (yield_pct / 100.0),
            "multiple_high": annual_income / (yield_pct / 100.0),
            "horizon_years": 1,
        },
    )

    assert answer_card.presentation.answer is not None
    assert answer_card.presentation.answer.value == expected
    scenario_prices = [
        row.value
        for row in scenario_card.presentation.rows
        if row.name.startswith("price_at_horizon_")
    ]
    assert scenario_prices == [expected, expected, expected]


@pytest.mark.parametrize(
    ("currency", "positive", "negative", "rounded_positive", "rounded_negative"),
    [
        ("JPY", 2.5, -2.5, 3.0, -3.0),
        ("KWD", 1.2345, -1.2345, 1.235, -1.235),
    ],
)
def test_ranked_money_presenter_rounds_half_units_away_from_zero(
    currency: str,
    positive: float,
    negative: float,
    rounded_positive: float,
    rounded_negative: float,
) -> None:
    card = _card(
        "ranked_comparison",
        {
            "currency": currency,
            "key_label": "Value",
            "key_kind": "money",
            "prefer": "higher",
            "items": [
                {"label": "Positive", "value": positive},
                {"label": "Negative", "value": negative},
            ],
        },
    )

    ranked_values = [
        fact.value
        for fact in [card.presentation.answer, *card.presentation.rows]
        if fact is not None and fact.name.startswith("rank_")
    ]
    assert ranked_values == [rounded_positive, rounded_negative]


@pytest.mark.parametrize(
    ("currency", "repair", "expected"),
    [
        (
            "JPY",
            {"payment": -2.5, "future_value": 2.5},
            {"payment": -3.0, "future_value": 3.0},
        ),
        (
            "KWD",
            {"payment": -1.2345, "future_value": 1.2345},
            {"payment": -1.235, "future_value": 1.235},
        ),
    ],
)
def test_money_repair_presenter_uses_half_up_currency_rounding(
    currency: str,
    repair: dict[str, float],
    expected: dict[str, float],
) -> None:
    error = no_solution(
        NoSolution(field="payment", code="repair_test", repair=repair),
        currency=currency,
    )

    assert isinstance(error, ToolInvocationError)
    failure = error.outcome.failure
    assert failure is not None
    assert failure.repair is not None
    assert failure.repair.changes == expected


def test_account_and_record_provenance_is_dated_referenced_and_single_currency() -> None:
    arguments = {
        "currency": "USD",
        "annual_income": 4,
        "price": 100,
        "yield_pct": None,
        "sources": {
            "annual_income": {
                "kind": "record",
                "date": "2026-09-20",
                "ref": "dividend-record-1",
                "currency": "USD",
            },
            "price": {
                "kind": "account",
                "date": "2026-09-20",
                "ref": "investment-account-1",
                "currency": "USD",
            },
            "yield_pct": {"kind": "not_found"},
        },
    }

    card = _card("income_yield", arguments)
    restored = ToolResultCard.model_validate_json(card.model_dump_json())
    facts = {item.name: item for item in restored.presentation.inputs}

    assert facts["annual_income"].source.kind == "record"
    assert facts["annual_income"].source.ref == "dividend-record-1"
    assert facts["price"].source.kind == "account"
    assert facts["price"].source.currency == "USD"
    assert facts["yield_pct"].source.kind == "computed"

    invalid = _card(
        "income_yield",
        {
            **arguments,
            "sources": {
                **arguments["sources"],
                "price": {
                    "kind": "account",
                    "date": "2026-09-20",
                    "ref": "euro-account",
                    "currency": "EUR",
                },
            },
        },
    )
    assert invalid.outcome.status == "invalid"
    assert invalid.outcome.failure is not None
    assert invalid.outcome.failure.code == "invalid_arguments"


def test_reused_core_imports_without_secrets_or_network() -> None:
    money_view = Path(__file__).resolve().parents[1]
    code = """
import importlib
import pkgutil
import socket
def blocked(*args, **kwargs):
    raise AssertionError('network access during import')
socket.socket.connect = blocked
import server.argus_core
for module in pkgutil.walk_packages(
    server.argus_core.__path__, prefix='server.argus_core.'
):
    importlib.import_module(module.name)
from server.argus_core.tool_declaration import ToolCatalog
from server.argus_core.calculations import get_calculation_declarations
assert len(ToolCatalog(get_calculation_declarations()).declarations) == 11
"""
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(money_view),
    }

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=money_view,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr


def test_reused_core_never_imports_the_production_argus_runtime() -> None:
    core = Path(__file__).resolve().parents[1] / "server" / "argus_core"
    imported = [
        path
        for path in core.rglob("*.py")
        if "argus.domain" in path.read_text(encoding="utf-8")
    ]
    assert imported == []
    assert socket.getdefaulttimeout() is None


def test_vendored_core_is_reproducible_and_detects_hand_edits(tmp_path: Path) -> None:
    money_view = Path(__file__).resolve().parents[1]
    script = money_view / "scripts" / "sync_argus_core.py"
    generated = tmp_path / "argus_core"

    written = subprocess.run(
        [sys.executable, str(script), "--write", "--output", str(generated)],
        cwd=money_view,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert written.returncode == 0, written.stderr

    checked = subprocess.run(
        [sys.executable, str(script), "--check", "--output", str(generated)],
        cwd=money_view,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert checked.returncode == 0, checked.stderr

    rogue = generated / "rogue_finance.py"
    rogue.write_text("VALUE = 'stale module'\n", encoding="utf-8")
    unexpected = subprocess.run(
        [sys.executable, str(script), "--check", "--output", str(generated)],
        cwd=money_view,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert unexpected.returncode == 1
    assert "unexpected:rogue_finance.py" in unexpected.stderr
    rogue.unlink()

    declaration = generated / "tool_declaration.py"
    declaration.write_text(
        declaration.read_text(encoding="utf-8") + "\n# hand edit\n",
        encoding="utf-8",
    )
    drifted = subprocess.run(
        [sys.executable, str(script), "--check", "--output", str(generated)],
        cwd=money_view,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert drifted.returncode == 1
    assert "tool_declaration.py" in drifted.stderr


def test_committed_vendored_core_matches_the_pinned_source() -> None:
    money_view = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/sync_argus_core.py", "--check"],
        cwd=money_view,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
