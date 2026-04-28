import pandas as pd
from argus.domain.engine import _build_signals


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
