from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from server.calculator import (
    CalculationError,
    calculate,
    confirmation_assumptions,
    present_result,
    validate_comparison_inputs,
)
from server.fixtures import FixtureProvider, get_examples
from server.models import (
    DepositRate,
    InflationRate,
    PlacementInputs,
    RateDataset,
    dataset_content_id,
)

NOW = datetime(2026, 9, 20, 15, 30, tzinfo=timezone.utc)


def _do_inputs(**changes: object) -> PlacementInputs:
    values: dict[str, object] = {
        "amount": "250000",
        "currency": "DOP",
        "horizon_days": 180,
        "country": "DO",
        "current_annual_rate_pct": "5.25",
    }
    values.update(changes)
    return PlacementInputs.model_validate(values)


def _replace_rate(rate: DepositRate, **changes: object) -> DepositRate:
    values = rate.model_dump(mode="python")
    values.update(changes)
    return DepositRate.model_validate(values)


def _replace_inflation(
    inflation: InflationRate,
    **changes: object,
) -> InflationRate:
    values = inflation.model_dump(mode="python")
    values.update(changes)
    return InflationRate.model_validate(values)


def _replace_dataset(dataset: RateDataset, **changes: object) -> RateDataset:
    values = dataset.model_dump(mode="python")
    values.update(changes)
    values["id"] = "pending-content-hash"
    candidate = RateDataset.model_validate(values)
    return candidate.model_copy(update={"id": dataset_content_id(candidate)})


def test_do_example_exposes_the_founder_selected_amount_and_horizon() -> None:
    example = get_examples()[0]

    assert example["id"] == "do-180-day-placement"
    assert example["inputs"] == {
        "amount": "250000",
        "currency": "DOP",
        "horizon_days": 180,
        "country": "DO",
        "current_annual_rate_pct": "5.25",
    }
    assert example["messages"]["es-419"] == (
        "Quiero comparar RD$250,000 durante 180 días."
    )


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"amount": "0"}, "amount"),
        ({"amount": "NaN"}, "amount"),
        ({"amount": "1000000000000.01"}, "amount"),
        ({"horizon_days": 0}, "horizon_days"),
        ({"horizon_days": True}, "horizon_days"),
        ({"country": "DOM"}, "country"),
        ({"currency": "PESO"}, "currency"),
    ],
)
def test_placement_inputs_reject_invalid_boundary_values(
    changes: dict[str, object],
    field: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        _do_inputs(**changes)

    assert field in str(error.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "0.0009"},
        {"amount": "1e-999999"},
        {"current_annual_rate_pct": "1000.000001"},
        {"current_annual_rate_pct": "1e20"},
        {"current_annual_rate_pct": "1e999999"},
    ],
)
def test_placement_inputs_reject_values_outside_calculation_envelope(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _do_inputs(**changes)


def test_external_rate_fee_and_inflation_values_use_bounded_precision() -> None:
    dataset = FixtureProvider().fetch("DO")

    with pytest.raises(ValidationError):
        _replace_rate(dataset.rates[0], annual_rate_pct="1000.000001")
    with pytest.raises(ValidationError):
        _replace_rate(dataset.rates[1], annual_fee="1000000000000.001")
    with pytest.raises(ValidationError):
        _replace_inflation(dataset.inflation[0], annual_rate_pct="1000.000001")


def test_boundary_models_are_closed_and_immutable() -> None:
    inputs = _do_inputs()

    with pytest.raises(ValidationError, match="extra_forbidden"):
        PlacementInputs.model_validate(inputs.model_dump() | {"advice": True})
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.amount = Decimal("1")  # type: ignore[misc]


def test_calculation_uses_simple_act_365_and_prorates_only_sourced_fee() -> None:
    dataset = FixtureProvider().fetch("DO")

    result = calculate(
        _do_inputs(),
        dataset,
        comparison_id="comparison-1",
        created_at=NOW,
    )
    presented = present_result(result)

    assert result.winner_ids == ["deposit:do-certificate-180"]
    assert presented["rows"][0]["end_value"] == "256472.60"
    assert presented["rows"][1]["interest"] == "7643.84"
    assert presented["rows"][1]["fees"] == "0.00"
    assert presented["rows"][2]["interest"] == "9616.44"
    assert presented["rows"][2]["fees"] == "295.89"
    assert presented["rows"][2]["end_value"] == "259320.55"
    assert presented["rows"][2]["fee_source"]["id"] == (
        "fixture-do-baseline-certificate"
    )
    assert result.rows[2].real_value < result.rows[2].end_value


def test_verified_zero_fee_keeps_its_source_receipt() -> None:
    original = FixtureProvider().fetch("DO")
    rates = [
        _replace_rate(rate, annual_fee=Decimal("0"))
        if rate.id == "do-certificate-180"
        else rate
        for rate in original.rates
    ]
    dataset = _replace_dataset(original, rates=rates)

    result = calculate(
        _do_inputs(),
        dataset,
        comparison_id="verified-zero-fee",
        created_at=NOW,
    )

    certificate = next(row for row in result.rows if row.product_type == "certificate")
    assert certificate.fees == Decimal("0")
    assert certificate.fee_source is not None
    assert certificate.fee_source.id == "fixture-do-baseline-certificate"


def test_supported_maximum_values_present_without_decimal_context_failure() -> None:
    inputs = _do_inputs(
        amount="1000000000000",
        horizon_days=3650,
        current_annual_rate_pct="1000",
    )

    result = calculate(
        inputs,
        FixtureProvider().fetch("DO"),
        comparison_id="supported-maximum",
        created_at=NOW,
    )
    presented = present_result(result)

    assert presented["rows"][0]["end_value"] == "101000000000000.00"


def test_minimum_amount_and_maximum_fee_fail_with_typed_calculation_error() -> None:
    original = FixtureProvider().fetch("DO")
    rates = [
        _replace_rate(rate, annual_fee=Decimal("1000000000000"))
        if rate.id == "do-certificate-180"
        else rate
        for rate in original.rates
    ]
    dataset = _replace_dataset(original, rates=rates)

    with pytest.raises(CalculationError) as error:
        calculate(
            _do_inputs(amount="0.001"),
            dataset,
            comparison_id="bounded-extremes",
            created_at=NOW,
        )

    assert error.value.code == "nonpositive_end_value"


def test_certificate_requires_exact_horizon_while_savings_remains_eligible() -> None:
    dataset = FixtureProvider().fetch("DO")
    inputs = _do_inputs(horizon_days=181)

    result = calculate(inputs, dataset, comparison_id="comparison-2", created_at=NOW)

    assert [row.product_type for row in result.rows] == ["cash", "savings"]
    assert result.winner_ids == ["deposit:do-savings"]


def test_complete_tie_set_includes_cash_and_each_deposit() -> None:
    dataset = FixtureProvider().fetch("DO")
    tied_rates = [
        _replace_rate(
            rate,
            annual_rate_pct=Decimal("5.25"),
            annual_fee=None,
            fee_source=None,
        )
        for rate in dataset.rates
    ]
    tied_dataset = _replace_dataset(dataset, rates=tied_rates)

    result = calculate(
        _do_inputs(),
        tied_dataset,
        comparison_id="comparison-tie",
        created_at=NOW,
    )

    assert result.winner_ids == [
        "cash",
        "deposit:do-savings",
        "deposit:do-certificate-180",
    ]


def test_missing_current_rate_is_an_explicit_zero_cash_assumption() -> None:
    dataset = FixtureProvider().fetch("DO")
    inputs = _do_inputs(current_annual_rate_pct=None)

    result = calculate(
        inputs,
        dataset,
        comparison_id="comparison-assumption",
        created_at=NOW,
    )

    assert result.rows[0].annual_rate_pct == Decimal("0")
    assert result.rows[0].source.model_dump(mode="json") == {
        "kind": "assumption",
        "recorded_on": "2026-09-20T15:30:00Z",
    }
    assert confirmation_assumptions(inputs)[-1] == (
        "zero_interest_cash_baseline_confirmed"
    )
    assert result.assumptions == confirmation_assumptions(inputs)


@pytest.mark.parametrize(
    ("currency", "expected_amount", "expected_fee"),
    [("JPY", "250000", "296"), ("KWD", "250000.000", "295.890")],
)
def test_presenter_rounds_money_once_using_currency_minor_digits(
    currency: str,
    expected_amount: str,
    expected_fee: str,
) -> None:
    original = FixtureProvider().fetch("DO")
    rates = [_replace_rate(rate, currency=currency) for rate in original.rates]
    inflation = [_replace_inflation(original.inflation[0], currency=currency)]
    dataset = _replace_dataset(original, rates=rates, inflation=inflation)

    result = calculate(
        _do_inputs(currency=currency),
        dataset,
        comparison_id=f"comparison-{currency}",
        created_at=NOW,
    )
    presented = present_result(result)

    assert presented["inputs"]["amount"] == expected_amount
    assert presented["rows"][2]["fees"] == expected_fee
    assert result.rows[2].fees == Decimal(
        "295.89041095890410958904109589041095890410958904109"
    )


def test_calculation_rejects_tampered_dataset_identity() -> None:
    dataset = FixtureProvider().fetch("DO").model_copy(update={"id": "not-the-hash"})

    with pytest.raises(CalculationError) as error:
        validate_comparison_inputs(_do_inputs(), dataset)

    assert error.value.code == "invalid_dataset_identity"


def test_dataset_identity_ignores_normalized_row_order() -> None:
    dataset = FixtureProvider().fetch("DO")
    reversed_dataset = dataset.model_copy(update={"rates": list(reversed(dataset.rates))})

    assert dataset_content_id(reversed_dataset) == dataset.id


def test_dataset_rejects_missing_or_mismatched_inflation_basket() -> None:
    dataset = FixtureProvider().fetch("DO")

    with pytest.raises(ValidationError, match="inflation basket"):
        RateDataset.model_validate(
            dataset.model_dump(mode="python")
            | {
                "inflation": [
                    _replace_inflation(dataset.inflation[0], currency="USD")
                ]
            }
        )


def test_repeating_calculation_with_same_identity_is_deterministic() -> None:
    inputs = _do_inputs()
    dataset = FixtureProvider().fetch("DO")

    first = calculate(inputs, dataset, comparison_id="same", created_at=NOW)
    second = calculate(inputs, dataset, comparison_id="same", created_at=NOW)

    assert first == second
