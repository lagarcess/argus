"""Formatted Wallet amounts: read only when one value is possible, never guessed."""

import pytest
from argus.domain.ingestion.shortcuts.amounts import parse_amount


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("RD$1,250.00", "1250.00", "DOP"),
        ("RD$ 1 250,00", "1250.00", "DOP"),
        ("US$ 12.50", "12.50", "USD"),
        ("1.250,00 €", "1250.00", "EUR"),
        ("12,50 €", "12.50", "EUR"),
        ("£3.20", "3.20", "GBP"),
        ("USD 3", "3", "USD"),
        ("DOP 1.250,75", "1250.75", "DOP"),
        ("1,250,000.50 USD", "1250000.50", "USD"),
        ("RD$ 1 250,00", "1250.00", "DOP"),
    ],
)
def test_unambiguous_amounts_parse_deterministically(text, amount, currency):
    parsed = parse_amount(text)
    assert (parsed.amount, parsed.currency, parsed.uncertain) == (
        amount,
        currency,
        frozenset(),
    )


@pytest.mark.parametrize("text", ["$12.50", "$ 1,250.00", "¥1.000,5", "C$4.00"])
def test_ambiguous_symbol_keeps_currency_open_and_uncertain(text):
    parsed = parse_amount(text)
    assert parsed.amount is not None
    assert parsed.currency is None
    assert parsed.uncertain == frozenset({"currency"})


def test_explicit_iso_code_settles_an_ambiguous_symbol():
    assert parse_amount("$12.50", currency_code="usd").currency == "USD"
    assert parse_amount("$12.50", currency_code="DOP").currency == "DOP"
    assert parse_amount("12.50", currency_code="DOP").uncertain == frozenset()


def test_explicit_code_never_overrides_a_marker_that_disagrees():
    parsed = parse_amount("RD$5.00", currency_code="USD")
    assert parsed.currency is None and parsed.uncertain == frozenset({"currency"})


@pytest.mark.parametrize(
    "text",
    ["1,250", "1.250", "$1.250", "1,25,000", "$.99", "12.", "abc", "1-250", "١٢٣"],
)
def test_amounts_with_more_than_one_reading_stay_unresolved(text):
    parsed = parse_amount(text)
    assert parsed.amount is None
    assert "amount" in parsed.uncertain


def test_no_marker_is_missing_currency_not_a_guess():
    parsed = parse_amount("12.50")
    assert (parsed.amount, parsed.currency, parsed.uncertain) == (
        "12.50",
        None,
        frozenset(),
    )


def test_unlisted_three_letter_word_is_not_a_currency():
    parsed = parse_amount("ABC 3")
    assert parsed.currency is None and parsed.uncertain == frozenset({"currency"})


def test_sign_is_dropped_from_the_magnitude():
    # Direction is never inferred from a sign; the raw text stays as excerpt.
    assert parse_amount("-$4.00").amount == "4.00"


def test_missing_and_oversized_amounts():
    assert parse_amount(None).amount is None and parse_amount("").uncertain == set()
    assert parse_amount("9" * 65).uncertain == frozenset({"amount", "currency"})
