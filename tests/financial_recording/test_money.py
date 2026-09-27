from fractions import Fraction

import pytest

from tests.financial_recording import scenarios
from tests.financial_recording.money import (
    InvalidInput,
    exponent,
    parse_minor,
    round_half_up,
)


@pytest.mark.parametrize(
    ("text", "currency", "minor"),
    [
        ("250000.00", "DOP", 25_000_000),
        ("-21500.00", "DOP", -2_150_000),
        ("0.5", "DOP", 50),
        ("7", "USD", 700),
        ("1500", "JPY", 1500),
        ("1.234", "KWD", 1234),
    ],
)
def test_parse_minor_is_exact_in_the_currency_exponent(text, currency, minor):
    assert parse_minor(text, currency) == minor


@pytest.mark.parametrize(
    ("text", "currency", "code"),
    [
        ("1500.5", "JPY", "amount_precision"),
        ("10.001", "DOP", "amount_precision"),
        ("1.234,56", "DOP", "amount_invalid"),
        ("1e3", "DOP", "amount_invalid"),
        ("12.", "DOP", "amount_invalid"),
        ("", "DOP", "amount_invalid"),
        ("١٢", "DOP", "amount_invalid"),
        ("10", "ZZZ", "currency_unsupported"),
        ("10", "$", "currency_unsupported"),
    ],
)
def test_parse_minor_refuses_instead_of_rounding_or_guessing(text, currency, code):
    with pytest.raises(InvalidInput) as refused:
        parse_minor(text, currency)
    assert refused.value.code == code


def test_exponent_comes_from_the_currency_authority():
    assert [exponent(code) for code in ("JPY", "DOP", "KWD")] == [0, 2, 3]


def test_unknown_code_is_refused_not_defaulted_to_two_digits():
    with pytest.raises(InvalidInput) as refused:
        exponent("ZZZ")
    assert refused.value.code == "currency_unsupported"


@pytest.mark.parametrize(
    ("value", "rounded"),
    [
        (Fraction(1, 2), 1),
        (Fraction(-1, 2), -1),
        (Fraction(49, 100), 0),
        (Fraction(3, 2), 2),
        (Fraction(-5, 2), -3),
        (Fraction(25_000_000, 1), 25_000_000),
    ],
)
def test_round_half_up_rounds_ties_away_from_zero(value, rounded):
    assert round_half_up(value) == rounded


def test_multiple_precisions_scenario():
    assert scenarios.multiple_precisions() == {
        "yen_balance": 1500,
        "dinar_balance": 1234,
        "yen_fraction_issues": {"amount_precision": "blocking"},
        "yen_fraction_opening": "InvalidInput:amount_precision",
        "unknown_currency": "InvalidInput:currency_unsupported",
        "positions": {"DOP": 1000, "JPY": 1500, "KWD": 1234},
    }
