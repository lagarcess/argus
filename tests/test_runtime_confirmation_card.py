from __future__ import annotations

from argus.api.chat.confirmation import runtime_confirmation_card
from argus.domain.engine_launch.display import format_timeframe_data_label


def test_runtime_confirmation_card_uses_recurring_contribution_for_dca() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "dca_accumulation",
                    "strategy_thesis": "Invest $500 in Bitcoin every month.",
                    "asset_universe": ["BTC"],
                    "asset_class": "crypto",
                    "cadence": "monthly",
                    "capital_amount": 500.0,
                    "date_range": {"start": "2024-05-03", "end": "2026-05-03"},
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "default",
                        "value": 1000.0,
                    },
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                    "fees": {"label": "Fees", "source": "default", "value": 0.0},
                    "slippage": {
                        "label": "Slippage",
                        "source": "default",
                        "value": 0.0,
                    },
                },
            },
        }
    )

    assert card is not None
    assert {"label": "Cadence", "value": "Monthly"} in card["rows"]
    assert {"label": "Contribution", "value": "$500"} in card["rows"]
    assert "$500 recurring contribution" in card["assumptions"]
    assert "Daily data" in card["assumptions"]
    assert "1D bars" not in card["assumptions"]
    assert "$10,000 starting capital" not in card["assumptions"]


def test_runtime_confirmation_card_uses_shared_timeframe_display() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "capital_amount": 1000.0,
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                },
                "optional_parameters": {
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "user",
                        "value": "2h",
                    },
                },
            },
        }
    )

    assert card is not None
    assert format_timeframe_data_label("2h") in card["assumptions"]
    assert all("bars" not in assumption.lower() for assumption in card["assumptions"])


def test_runtime_confirmation_card_uses_starting_capital_for_buy_and_hold() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold SBUX and CMG.",
                    "asset_universe": ["SBUX", "CMG"],
                    "asset_class": "equity",
                    "capital_amount": 100000.0,
                    "date_range": "year_to_date",
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "default",
                        "value": 1000.0,
                    },
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                },
            },
        }
    )

    assert card is not None
    assert {"label": "Starting capital", "value": "$100,000"} in card["rows"]
    assert "$100,000 starting capital" in card["assumptions"]
    assert "$10,000 starting capital" not in card["assumptions"]


def test_runtime_confirmation_card_uses_explicit_benchmark_assumption() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Compare Apple with QQQ.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "comparison_baseline": "QQQ",
                    "capital_amount": 1000.0,
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "default",
                        "value": 1000.0,
                    },
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 1000,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "QQQ",
                },
                "validation": {"executable": True},
            },
        }
    )

    assert card is not None
    assert "Benchmark: QQQ" in card["assumptions"]
    assert "Benchmark: SPY" not in card["assumptions"]


def test_runtime_confirmation_card_displays_latest_complete_data_assumption() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold NU this year so far.",
                    "asset_universe": ["NU"],
                    "asset_class": "equity",
                    "capital_amount": 500.0,
                    "date_range": {"start": "2026-01-01", "end": "2026-06-02"},
                    "extra_parameters": {
                        "data_availability_adjustment": {
                            "kind": "latest_complete_daily_data",
                            "original_end": "2026-06-03",
                            "through": "2026-06-02",
                        },
                    },
                },
                "optional_parameters": {
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                    "fees": {"label": "Fees", "source": "default", "value": 0.0},
                    "slippage": {
                        "label": "Slippage",
                        "source": "default",
                        "value": 0.0,
                    },
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "NU",
                    "symbols": ["NU"],
                    "timeframe": "1D",
                    "date_range": {"start": "2026-01-01", "end": "2026-06-02"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 500,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True, "date_adjusted": True},
            },
        }
    )

    assert card is not None
    assert card["statusLabel"] == "Adjusted"
    assert {"label": "Period", "value": "January 1, 2026 - June 2, 2026"} in card[
        "rows"
    ]
    assert "Through Jun 2" in card["assumptions"]


def test_runtime_confirmation_card_uses_visible_benchmark_when_payload_is_stale() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Compare Apple with QQQ.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "comparison_baseline": "QQQ",
                    "capital_amount": 1000.0,
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "default",
                        "value": 1000.0,
                    },
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 1000,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True},
            },
        }
    )

    assert card is not None
    assert card["statusLabel"] == "Needs change"
    assert "Benchmark: QQQ" in card["assumptions"]
    assert "Benchmark: SPY" not in card["assumptions"]
    assert all(action["type"] != "run_backtest" for action in card["actions"])


def test_runtime_confirmation_card_carries_active_confirmation_identity() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "default",
                        "value": 1000.0,
                    },
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2025-05-14", "end": "2026-05-14"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 1000,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True},
            },
        },
        confirmation_id="confirm-1",
    )

    assert card is not None
    assert card["confirmation_id"] == "confirm-1"
    assert card["confirmation_state"] == "active"
    run_action = next(
        action for action in card["actions"] if action["type"] == "run_backtest"
    )
    assert run_action["payload"]["confirmation_id"] == "confirm-1"
