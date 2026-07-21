from __future__ import annotations

from argus.api.chat.confirmation import runtime_confirmation_card


def test_confirmation_card_carries_provider_neutral_effective_window_adjustment() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-03", "end": "2024-01-05"},
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "asset_class": "equity",
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-03", "end": "2024-01-05"},
                    "requested_date_range": {
                        "start": "2024-01-01",
                        "end": "2024-01-05",
                    },
                    "coverage_preflight": {
                        "outcome": "adjusted_coverage",
                        "requested_date_range": {
                            "start": "2024-01-01",
                            "end": "2024-01-05",
                        },
                        "effective_date_range": {
                            "start": "2024-01-03",
                            "end": "2024-01-05",
                        },
                        "preflight_id": "coverage-fixture",
                    },
                    "sizing_mode": "capital_amount",
                    "capital_amount": 10_000,
                    "benchmark_symbol": "SPY",
                },
            },
        },
        language="en",
    )

    assert card is not None
    assert card["date_range"] == {
        "start": "2024-01-03",
        "end": "2024-01-05",
        "display": "January 3, 2024 - January 5, 2024",
    }
    assert card["period_adjustment"] == {
        "code": "effective_window_adjusted",
        "requested_date_range": {"start": "2024-01-01", "end": "2024-01-05"},
        "effective_date_range": {"start": "2024-01-03", "end": "2024-01-05"},
    }


def test_full_coverage_confirmation_does_not_emit_adjustment() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-01", "end": "2024-01-05"},
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "asset_class": "equity",
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-01-05"},
                    "requested_date_range": {
                        "start": "2024-01-01",
                        "end": "2024-01-05",
                    },
                    "coverage_preflight": {
                        "outcome": "full_coverage",
                        "requested_date_range": {
                            "start": "2024-01-01",
                            "end": "2024-01-05",
                        },
                        "effective_date_range": {
                            "start": "2024-01-01",
                            "end": "2024-01-05",
                        },
                        "preflight_id": "coverage-fixture",
                    },
                    "sizing_mode": "capital_amount",
                    "capital_amount": 10_000,
                    "benchmark_symbol": "SPY",
                },
            },
        }
    )

    assert card is not None
    assert "period_adjustment" not in card
