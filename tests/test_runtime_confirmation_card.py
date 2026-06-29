from __future__ import annotations

import pytest
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.domain.engine_launch.display import format_timeframe_data_label


def _confirmation_result_with_draft_costs() -> dict[str, object]:
    return {
        "stage_outcome": "await_approval",
        "confirmation_payload": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold Apple with requested costs.",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": {"start": "2025-01-01", "end": "2025-01-07"},
                "extra_parameters": {
                    "fee_rate": 0.001,
                    "slippage": 0.0005,
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
                "symbol": "AAPL",
                "symbols": ["AAPL"],
                "timeframe": "1D",
                "date_range": {"start": "2025-01-01", "end": "2025-01-07"},
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


def test_runtime_confirmation_card_flag_off_never_advertises_modeled_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Flag off, the engine ignores draft fee/slippage values, so the card must
    # keep the idealized truth even when an edit stored costs on the draft.
    monkeypatch.delenv("ARGUS_ENABLE_EXECUTION_REALISM", raising=False)

    card = runtime_confirmation_card(_confirmation_result_with_draft_costs())

    assert card is not None
    assert card["display_facts"] == {
        "benchmark_symbol": "SPY",
        "fees": 0.0,
        "slippage": 0.0,
        "timeframe": "1D",
    }
    assert "No fees" in card["assumptions"]
    assert "No slippage" in card["assumptions"]
    assert not any("Modeled costs" in item for item in card["assumptions"])


def test_runtime_confirmation_card_flag_on_shows_draft_costs_without_launch_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")

    card = runtime_confirmation_card(_confirmation_result_with_draft_costs())

    assert card is not None
    assert card["display_facts"]["fees"] == 0.001
    assert card["display_facts"]["slippage"] == 0.0005
    assert "Modeled costs: 10 bps fee + 5 bps slippage" in card["assumptions"]


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
    assert card["strategy_type"] == "dca_accumulation"
    assert card["display_facts"] == {
        "benchmark_symbol": "BTC",
        "fees": 0.0,
        "slippage": 0.0,
        "timeframe": "1D",
    }
    assert any(
        row["key"] == "cadence"
        and row["labelKey"] == "chat.confirmation.rows.cadence"
        and row["value"] == "Monthly"
        for row in card["rows"]
    )
    assert any(
        row["key"] == "contribution"
        and row["labelKey"] == "chat.confirmation.rows.contribution"
        and row["value"] == "$500"
        for row in card["rows"]
    )
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
    assert any(
        row["key"] == "starting_capital"
        and row["labelKey"] == "chat.confirmation.rows.starting_capital"
        and row["value"] == "$100,000"
        for row in card["rows"]
    )
    assert "$100,000 starting capital" in card["assumptions"]
    assert "$10,000 starting capital" not in card["assumptions"]


def test_runtime_confirmation_card_promotes_default_starting_capital() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2025-06-13", "end": "2026-06-12"},
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
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2025-06-13", "end": "2026-06-12"},
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
    assert any(
        row["key"] == "starting_capital"
        and row["labelKey"] == "chat.confirmation.rows.starting_capital"
        and row["value"] == "$1,000"
        for row in card["rows"]
    )
    assert "$1,000 starting capital" not in card["assumptions"]
    assert "Benchmark: SPY" in card["assumptions"]


def test_runtime_confirmation_card_shows_execution_realism_values() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple with modeled costs.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2025-01-01", "end": "2025-01-07"},
                    "extra_parameters": {
                        "fee_rate": 0.001,
                        "slippage": 0.0005,
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
                    "symbol": "AAPL",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "date_range": {"start": "2025-01-01", "end": "2025-01-07"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 1000,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "SPY",
                    "_execution_realism": {
                        "enabled": True,
                        "fee_bps": 10.0,
                        "slippage_bps": 5.0,
                    },
                },
                "validation": {"executable": True},
            },
        }
    )

    assert card is not None
    assert card["display_facts"] == {
        "benchmark_symbol": "SPY",
        "fees": 0.001,
        "slippage": 0.0005,
        "timeframe": "1D",
    }
    assert "Modeled costs: 10 bps fee + 5 bps slippage" in card["assumptions"]
    assert "No fees" not in card["assumptions"]
    assert "No slippage" not in card["assumptions"]


def test_runtime_confirmation_card_localizes_spanish_confirmation_artifact() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Compra y mantén ETH.",
                    "asset_universe": ["ETH"],
                    "asset_class": "crypto",
                    "capital_amount": 100000.0,
                    "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
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
                    "symbol": "ETH",
                    "symbols": ["ETH"],
                    "timeframe": "1D",
                    "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
                    "sizing_mode": "capital_amount",
                    "capital_amount": 100000,
                    "position_size": None,
                    "parameters": {},
                    "risk_rules": [],
                    "benchmark_symbol": "BTC",
                },
                "validation": {"executable": True},
            },
        },
        language="es-419",
    )

    assert card is not None
    assert card["title"] == "ETH: Comprar y mantener"
    assert card["statusLabel"] == "Listo para ejecutar"
    assert (
        card["summary"]
        == "Listo para probar comprar y mantener ETH del 1 de enero de 2024 al 31 de marzo de 2024."
    )
    assert any(
        row["key"] == "strategy" and row["value"] == "Comprar y mantener"
        for row in card["rows"]
    )
    assert any(
        row["key"] == "period"
        and row["value"] == "1 de enero de 2024 al 31 de marzo de 2024"
        for row in card["rows"]
    )
    assert "$100,000 capital inicial" in card["assumptions"]
    assert "Datos diarios" in card["assumptions"]
    assert "Sin comisiones" in card["assumptions"]
    assert "Sin deslizamiento" in card["assumptions"]
    assert "Referencia: BTC" in card["assumptions"]
    assert all("starting capital" not in value for value in card["assumptions"])
    assert all("Benchmark:" not in value for value in card["assumptions"])


def test_runtime_confirmation_card_localizes_spanish_indicator_rules() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "indicator_threshold",
                    "strategy_thesis": "Usar RSI en ETH.",
                    "asset_universe": ["ETH"],
                    "asset_class": "crypto",
                    "date_range": {"start": "2025-10-15", "end": "2026-06-14"},
                    "entry_logic": "Buy when RSI(14) drops to 30 or below",
                    "exit_logic": "Sell when RSI(14) rises to 70 or above",
                    "extra_parameters": {
                        "indicator": "rsi",
                        "indicator_parameters": {
                            "indicator": "rsi",
                            "indicator_period": 14,
                            "entry_threshold": 30,
                            "exit_threshold": 70,
                        },
                    },
                },
                "optional_parameters": {
                    "initial_capital": {
                        "label": "Initial capital",
                        "source": "user",
                        "value": 100000,
                    },
                    "timeframe": {
                        "label": "Timeframe",
                        "source": "default",
                        "value": "1D",
                    },
                },
            },
        },
        language="es-419",
    )

    assert card is not None
    buy_rule = next(row for row in card["rows"] if row["key"] == "buy_rule")
    exit_rule = next(row for row in card["rows"] if row["key"] == "exit_rule")
    assert buy_rule["value"] == "Comprar cuando RSI(14) cae a 30 o menos"
    assert exit_rule["value"] == "Vender cuando RSI(14) sube a 70 o más"
    assert "Buy when" not in buy_rule["value"]
    assert "Sell when" not in exit_rule["value"]


def test_runtime_confirmation_card_localizes_spanish_moving_average_rules() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "signal_strategy",
                    "strategy_thesis": "Cruce de medias para ETH.",
                    "asset_universe": ["ETH"],
                    "asset_class": "crypto",
                    "date_range": {"start": "2025-10-15", "end": "2026-06-14"},
                    "entry_logic": "50-day SMA crosses above 200-day SMA",
                    "exit_logic": "50-day SMA crosses below 200-day SMA",
                    "entry_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "slow_indicator": "sma",
                        "fast_period": 50,
                        "slow_period": 200,
                        "direction": "bullish",
                    },
                    "exit_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "slow_indicator": "sma",
                        "fast_period": 50,
                        "slow_period": 200,
                        "direction": "bearish",
                    },
                },
                "optional_parameters": {},
            },
        },
        language="es-419",
    )

    assert card is not None
    buy_rule = next(row for row in card["rows"] if row["key"] == "buy_rule")
    exit_rule = next(row for row in card["rows"] if row["key"] == "exit_rule")
    assert (
        buy_rule["value"]
        == "Comprar cuando SMA de 50 días cruza por encima de SMA de 200 días"
    )
    assert (
        exit_rule["value"]
        == "Vender cuando SMA de 50 días cruza por debajo de SMA de 200 días"
    )
    assert "crosses above" not in buy_rule["value"]
    assert "crosses below" not in exit_rule["value"]


def test_runtime_confirmation_card_preserves_english_moving_average_word_order() -> None:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "signal_strategy",
                    "strategy_thesis": "50/200 moving-average crossover.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2025-06-14", "end": "2026-06-14"},
                    "entry_logic": "50-day SMA crosses above 200-day SMA",
                    "exit_logic": "50-day SMA crosses below 200-day SMA",
                    "entry_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "slow_indicator": "sma",
                        "fast_period": 50,
                        "slow_period": 200,
                        "direction": "bullish",
                    },
                    "exit_rule": {
                        "type": "moving_average_crossover",
                        "fast_indicator": "sma",
                        "slow_indicator": "sma",
                        "fast_period": 50,
                        "slow_period": 200,
                        "direction": "bearish",
                    },
                },
                "optional_parameters": {},
            },
        },
        language="en",
    )

    assert card is not None
    buy_rule = next(row for row in card["rows"] if row["key"] == "buy_rule")
    exit_rule = next(row for row in card["rows"] if row["key"] == "exit_rule")
    assert buy_rule["value"] == "Buy when 50-day SMA crosses above 200-day SMA"
    assert exit_rule["value"] == "Sell when 50-day SMA crosses below 200-day SMA"


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
    assert card["status"] == "ready_to_run"
    assert card["statusLabel"] == "Ready to run"
    assert any(
        row["key"] == "period"
        and row["labelKey"] == "chat.confirmation.rows.period"
        and row["value"] == "January 1, 2026 - June 2, 2026"
        for row in card["rows"]
    )
    assert "Through Jun 2" in card["assumptions"]


def test_runtime_confirmation_card_ignores_stale_latest_complete_data_assumption() -> (
    None
):
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
                    "date_range": {"start": "2026-01-01", "end": "2026-06-01"},
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
                    "date_range": {"start": "2026-01-01", "end": "2026-06-01"},
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
    assert any(
        row["key"] == "period"
        and row["labelKey"] == "chat.confirmation.rows.period"
        and row["value"] == "January 1, 2026 - June 1, 2026"
        for row in card["rows"]
    )
    assert "Through Jun 2" not in card["assumptions"]


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
    assert card["status"] == "needs_change"
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
