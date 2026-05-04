import pandas as pd
from argus.domain.engine import _build_signals, build_result_card, compute_alpha_metrics


def test_dca_accumulation_signals_weekly():
    # Create 14 days of data (2 weeks)
    index = pd.date_range("2024-01-01", periods=14, freq="D")
    data = pd.DataFrame({"close": [100] * 14}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "weekly"}
    }

    entries, exits = _build_signals(config, data)

    # Should have entries at start of each week
    # 2024-01-01 is a Monday (start of week 1)
    # 2024-01-08 is the next Monday (start of week 2)
    assert entries.sum() == 2
    assert bool(entries.iloc[0])
    assert bool(entries.iloc[7])
    assert exits.sum() == 0


def test_dca_metrics_account_for_each_recurring_contribution(monkeypatch):
    index = pd.date_range("2024-01-01", periods=60, freq="D")
    prices = [100.0] * 31 + [200.0] * 29
    bars = pd.DataFrame(
        {
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1_000_000] * 60,
        },
        index=index,
    )

    monkeypatch.setattr("argus.domain.engine.fetch_ohlcv", lambda **_kwargs: bars)
    monkeypatch.setattr(
        "argus.domain.engine.fetch_price_series",
        lambda **_kwargs: bars["close"],
    )

    metrics = compute_alpha_metrics(
        {
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
            "timeframe": "1D",
            "starting_capital": 500.0,
            "allocation_method": "equal_weight",
            "benchmark_symbol": "AAPL",
            "parameters": {"dca_cadence": "monthly"},
        }
    )

    performance = metrics["aggregate"]["performance"]
    assert performance["profit"] == 500.0
    assert performance["total_return_pct"] == 50.0
    assert metrics["aggregate"]["efficiency"]["total_trades"] == 2

    card = build_result_card(
        {
            "template": "dca_accumulation",
            "symbols": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-29",
            "starting_capital": 500.0,
            "benchmark_symbol": "AAPL",
        },
        metrics,
    )
    cash_row = next(row for row in card["rows"] if row["key"] == "cash_value")
    assert cash_row["label"] == "Final Value ($)"
    assert cash_row["value"] == "$1.0k -> $1.5k"
    assert "Recurring contribution: $500." in card["assumptions"]

def test_dca_accumulation_signals_monthly():
    # Create 60 days of data (approx 2 months)
    index = pd.date_range("2024-01-01", periods=60, freq="D")
    data = pd.DataFrame({"close": [100] * 60}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "monthly"}
    }

    entries, exits = _build_signals(config, data)

    # 2024-01-01 and 2024-02-01
    assert entries.sum() == 2
    assert bool(entries.iloc[0])
    assert bool(entries.iloc[31]) # Feb 1st
    assert exits.sum() == 0

def test_dca_accumulation_signals_daily():
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    data = pd.DataFrame({"close": [100] * 5}, index=index)
    config = {
        "template": "dca_accumulation",
        "parameters": {"dca_cadence": "daily"}
    }

    entries, exits = _build_signals(config, data)
    assert entries.sum() == 5
    assert entries.all()


def test_buy_and_hold_signals():
    """buy_and_hold: single entry on bar 0, no exits, hold through entire period."""
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    data = pd.DataFrame({"close": range(100, 130)}, index=index)
    config = {"template": "buy_and_hold", "parameters": {}}

    entries, exits = _build_signals(config, data)

    # Exactly one entry on bar 0
    assert entries.sum() == 1
    assert bool(entries.iloc[0])
    # No entries on any other bar
    assert not entries.iloc[1:].any()
    # Zero exits — hold through end_date
    assert exits.sum() == 0
