"""A solved annual rate stays within the rates a plan's arguments accept."""

from __future__ import annotations

import pytest
from argus.domain.calculations._shared import MIN_ANNUAL_RATE_PCT
from argus.domain.calculations.growth_projection import GrowthArguments
from argus.domain.calculations.time_value import TimeValueArguments

from tests.domain.calculations.support import run_calculation


def test_the_floor_is_the_rate_fields_own_bound() -> None:
    for arguments in (TimeValueArguments, GrowthArguments):
        bound = next(
            item.gt
            for item in arguments.model_fields["annual_rate_pct"].metadata
            if hasattr(item, "gt")
        )
        assert bound == MIN_ANNUAL_RATE_PCT, arguments.__name__


@pytest.mark.parametrize(
    ("kind", "arguments"),
    [
        (
            "growth_projection",
            {
                "start_value": 100,
                "contribution": 0,
                "end_value": 10,
                "annual_rate_pct": None,
                "periods": 1,
            },
        ),
        (
            "time_value",
            {
                "direction": "save",
                "present_value": 100,
                "payment": 0,
                "future_value": 10,
                "annual_rate_pct": None,
                "periods": 1,
            },
        ),
    ],
)
def test_a_solved_rate_past_the_floor_is_out_of_range(kind, arguments) -> None:
    card = run_calculation(kind, {"currency": "USD", **arguments})
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "rate_out_of_range"
    assert card.outcome.failure.fields == ["annual_rate_pct"]
