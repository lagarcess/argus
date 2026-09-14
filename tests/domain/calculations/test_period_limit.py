"""A solved period count stays within the periods a plan's arguments accept."""

from __future__ import annotations

import pytest
from argus.domain.calculations._shared import MAX_PERIODS
from argus.domain.calculations.effective_rate import EffectiveRateArguments
from argus.domain.calculations.growth_projection import GrowthArguments
from argus.domain.calculations.time_value import TimeValueArguments

from tests.domain.calculations.support import run_calculation


def test_the_limit_is_the_periods_fields_own_bound() -> None:
    for arguments in (TimeValueArguments, GrowthArguments, EffectiveRateArguments):
        bound = next(
            item.le
            for item in arguments.model_fields["periods"].metadata
            if hasattr(item, "le")
        )
        assert bound == MAX_PERIODS, arguments.__name__


@pytest.mark.parametrize(
    ("kind", "arguments", "field"),
    [
        (
            "time_value",
            {
                "direction": "borrow",
                "present_value": 100_000,
                "payment": 50,
                "future_value": 0,
                "annual_rate_pct": 0,
                "periods": None,
            },
            "payment",
        ),
        (
            "growth_projection",
            {
                "start_value": 100,
                "contribution": 0,
                "end_value": 1_000_000,
                "annual_rate_pct": 0.1,
                "periods": None,
            },
            "annual_rate_pct",
        ),
        (
            "growth_projection",
            {
                "start_value": 0,
                "contribution": 1,
                "end_value": 1_000_000,
                "annual_rate_pct": 0,
                "periods": None,
            },
            "contribution",
        ),
    ],
)
def test_a_plan_past_the_period_limit_names_what_to_change(
    kind, arguments, field
) -> None:
    card = run_calculation(kind, {"currency": "USD", **arguments})
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "periods_beyond_limit"
    assert card.outcome.failure.fields == [field]
