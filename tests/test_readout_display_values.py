"""Readout figures use the card's precision before the model writes prose."""

from copy import deepcopy

import pytest
from argus.domain.display_figure import display_figure
from argus.domain.result_readout_display_values import readout_display_value


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("value", [42.12, 42.25, 42.35, -42.25, -42.35])
def test_percent_reuses_canonical_card_rounding(language, value):
    expected = display_figure(value)
    assert readout_display_value(
        {"value": value, "unit": "percent"}, language=language
    ) == {
        "value": expected,
        "text": f"{expected:.1f}%",
    }


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_drawdown_display_uses_magnitude_without_mutating_fact(language):
    row = {
        "value": -42.12,
        "unit": "percent",
        "presentation": ["absolute_magnitude"],
        "meaning": "Stored drawdown",
    }
    before = deepcopy(row)
    assert readout_display_value(row, language=language) == {
        "value": 42.1,
        "text": "42.1%",
    }
    assert row == before


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    "value,rounded,text",
    [
        (6644.07, 6644, "$6,644"),
        (6644.49, 6644, "$6,644"),
        (6644.5, 6645, "$6,645"),
        (6645.5, 6646, "$6,646"),
        (-6644.5, -6645, "-$6,645"),
        (-0.1, -0.0, "-$0"),
    ],
)
def test_money_matches_card_zero_decimals_and_half_expand(language, value, rounded, text):
    row = {"value": value, "unit": "currency", "currency": "USD"}
    before = deepcopy(row)
    assert readout_display_value(row, language=language) == {
        "value": rounded,
        "text": text,
    }
    assert row == before


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    "row,expected",
    [
        ({"value": 13, "unit": "count"}, {"value": 13, "text": "13"}),
        (
            {"value": -8.29, "unit": "percentage_points"},
            {"value": -8.3, "text": "-8.3 pp"},
        ),
        ({"value": 5, "unit": "basis_points"}, {"value": 5, "text": "5 bps"}),
        ({"value": 30, "unit": "indicator_points"}, {"value": 30, "text": "30"}),
        ({"value": 1.456, "unit": "ratio"}, {"value": 1.46, "text": "1.46"}),
        (
            {"value": 0.5712, "unit": "ratio", "presentation": ["fraction_as_percent"]},
            {"value": 57.1, "text": "57.1%"},
        ),
    ],
)
def test_existing_numeric_fact_units_have_plain_display_values(language, row, expected):
    assert readout_display_value(row, language=language) == expected


@pytest.mark.parametrize(
    "language,text",
    [("en", "September 1, 2023"), ("es-419", "1 de septiembre de 2023")],
)
def test_date_localizes_display_and_keeps_iso_reference(language, text):
    assert readout_display_value(
        {"value": "2023-09-01", "unit": "date"}, language=language
    ) == {"value": "2023-09-01", "text": text}


@pytest.mark.parametrize("value", [None, True, "unknown", float("nan"), float("inf")])
def test_unavailable_numeric_value_has_no_display(value):
    assert (
        readout_display_value({"value": value, "unit": "percent"}, language="en") is None
    )


def test_unknown_unit_or_language_does_not_invent_a_display():
    assert readout_display_value({"value": 13, "unit": "unknown"}, language="en") is None
    assert readout_display_value({"value": 13, "unit": "count"}, language="fr") is None
