"""The card builder identifies the renderer for new pending artifacts."""

import pytest
from argus.api.chat.confirmation import runtime_confirmation_card


@pytest.mark.parametrize("strategy_type", ["buy_and_hold", "dca_accumulation"])
def test_new_confirmation_identifies_backtest_kind(strategy_type: str) -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": strategy_type,
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "capital_amount": 1000,
                    "extra_parameters": (
                        {"recurring_contribution": 100, "contribution_period": "monthly"}
                        if strategy_type == "dca_accumulation"
                        else {}
                    ),
                    "date_range": {"start": "2025-01-02", "end": "2025-06-30"},
                },
            },
        },
        confirmation_id="pending-artifact-card",
    )

    assert card is not None
    assert card["kind"] == "backtest"
