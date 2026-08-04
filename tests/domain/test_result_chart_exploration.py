from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from argus.domain.backtesting import charts


def _build_chart(
    monkeypatch: pytest.MonkeyPatch,
    *,
    template: str = "buy_and_hold",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = pd.date_range("2025-01-01", periods=6, freq="D")
    bars = pd.DataFrame(
        {"close": [100.0, 101.0, 99.0, 102.0, 103.0, 104.0]}, index=index
    )
    entries = pd.Series([True, False, False, False, False, False], index=index)
    exits = pd.Series([False] * 6, index=index)

    return charts.build_result_chart(
        {
            "template": template,
            "symbols": ["AAPL"],
            "asset_class": "equity",
            "start_date": "2025-01-01",
            "end_date": "2025-01-06",
            "timeframe": "1D",
            "starting_capital": 10000.0,
            "parameters": parameters or {},
            "benchmark": "SPY",
        },
        fetch_ohlcv_func=lambda **_: bars,
        build_signals_func=lambda *_: (entries, exits),
    )


def test_result_chart_persists_resolved_exploration_policy(monkeypatch):
    chart = _build_chart(
        monkeypatch,
        template="dca_accumulation",
        parameters={"dca_cadence": "monthly"},
    )
    assert chart["exploration_policy"] == {
        "minimum_visible_observations": 6,
        "minimum_meaningful_duration": "P2M",
    }


def test_result_chart_uses_observation_only_policy_for_unknown_template(monkeypatch):
    chart = _build_chart(monkeypatch, template="future_strategy")
    assert chart["exploration_policy"] == {"minimum_visible_observations": 6}


def test_result_chart_records_exact_marker_cap_evidence(monkeypatch):
    all_markers = [
        {
            "time": f"2025-01-{(index % 28) + 1:02d}T{index % 24:02d}:00:00",
            "type": "entry" if index % 2 == 0 else "exit",
            "label": "ignored backend display copy",
            "symbols": ["AAPL"],
        }
        for index in range(124)
    ]
    monkeypatch.setattr(charts, "_chart_markers_from_events", lambda _: all_markers)
    chart = _build_chart(monkeypatch)
    assert len(chart["markers"]) == 80
    assert chart["marker_summary"] == {
        "total_groups": 124,
        "included_groups": 80,
        "sampled": True,
    }


def test_uncapped_chart_reports_complete_supplied_marker_set(monkeypatch):
    all_markers = [
        {
            "time": "2025-01-02",
            "type": "entry",
            "label": "Buy AAPL",
            "symbols": ["AAPL"],
        }
    ]
    monkeypatch.setattr(charts, "_chart_markers_from_events", lambda _: all_markers)
    chart = _build_chart(monkeypatch)
    assert chart["marker_summary"] == {
        "total_groups": 1,
        "included_groups": 1,
        "sampled": False,
    }


def test_chart_series_and_value_summary_are_unchanged_by_exploration_metadata(
    monkeypatch,
):
    chart = _build_chart(monkeypatch)
    assert chart["kind"] == "portfolio_equity"
    assert [point["value"] for point in chart["series"]] == [
        10000.0,
        10100.0,
        9900.0,
        10200.0,
        10300.0,
        10400.0,
    ]
    assert chart["base_value"] == 10000.0
    assert chart["value_summary"] == {
        "peak_value": 10400.0,
        "lowest_value": 9900.0,
        "currency": "USD",
        "source": "strategy_portfolio_equity_close",
    }
