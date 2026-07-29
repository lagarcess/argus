"""Card-time price-coverage grounding for a resolved benchmark (issue #301).

A catalog-resolved benchmark with no usable bars in the requested window
reconciles to the class default before the card promises it; the cleared
leg keeps provenance so the card discloses the swap. Probe failures other
than a provider no-data answer keep the benchmark untouched.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest
from argus.agent_runtime.stages.interpret_internal.benchmark_coverage import (
    strategy_with_benchmark_price_coverage,
)
from argus.agent_runtime.state.models import ResolutionProvenance, StrategySummary


def _bars(rows: int) -> pd.DataFrame:
    index = pd.date_range("2023-01-03", periods=max(rows, 1), freq="1D", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
        },
        index=index,
    )
    return frame.iloc[:rows]


def _strategy(**overrides: Any) -> StrategySummary:
    fields: dict[str, Any] = {
        "strategy_type": "buy_and_hold",
        "asset_universe": ["AAPL"],
        "asset_class": "equity",
        "date_range": {"start": "2023-01-03", "end": "2023-12-29"},
        "comparison_baseline": "NTDOY",
        "resolution_provenance": [
            ResolutionProvenance(
                field="comparison_baseline",
                raw_text="NINTENDO",
                source="llm_extraction",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol="NTDOY",
                asset_class="equity",
            )
        ],
    }
    fields.update(overrides)
    return StrategySummary(**fields)


def test_benchmark_without_bars_reconciles_and_keeps_disclosure_provenance() -> None:
    calls: list[dict[str, Any]] = []

    def fetch(**kwargs: Any) -> pd.DataFrame:
        calls.append(kwargs)
        return _bars(0)

    updated, reason_codes = strategy_with_benchmark_price_coverage(
        _strategy(),
        fetch_ohlcv_func=fetch,
    )

    assert updated.comparison_baseline is None
    assert reason_codes == ["benchmark_without_price_coverage_cleared"]
    assert calls[0]["symbol"] == "NTDOY"
    assert calls[0]["start_date"] == date(2023, 1, 3)
    assert calls[0]["end_date"] == date(2023, 12, 29)
    entries = [
        item
        for item in updated.resolution_provenance
        if item.field == "comparison_baseline"
    ]
    assert len(entries) == 1
    assert entries[0].resolution_status == "unavailable_for_requested_run"
    assert entries[0].raw_text == "NINTENDO"
    assert entries[0].canonical_symbol == "NTDOY"
    assert entries[0].validated_by == "price_coverage_probe"


def test_provider_zero_bars_answer_counts_as_missing_coverage() -> None:
    def fetch(**kwargs: Any) -> pd.DataFrame:
        raise ValueError("market_data_empty")

    updated, reason_codes = strategy_with_benchmark_price_coverage(
        _strategy(),
        fetch_ohlcv_func=fetch,
    )

    assert updated.comparison_baseline is None
    assert reason_codes == ["benchmark_without_price_coverage_cleared"]


def test_transport_failure_keeps_the_benchmark() -> None:
    def fetch(**kwargs: Any) -> pd.DataFrame:
        raise ValueError("market_data_unavailable")

    strategy = _strategy()
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        strategy,
        fetch_ohlcv_func=fetch,
    )

    assert updated is strategy
    assert reason_codes == []


def test_unexpected_probe_failure_keeps_the_benchmark() -> None:
    def fetch(**kwargs: Any) -> pd.DataFrame:
        raise RuntimeError("boom")

    strategy = _strategy()
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        strategy,
        fetch_ohlcv_func=fetch,
    )

    assert updated is strategy
    assert reason_codes == []


def test_covered_benchmark_is_untouched() -> None:
    strategy = _strategy()
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        strategy,
        fetch_ohlcv_func=lambda **kwargs: _bars(5),
    )

    assert updated is strategy
    assert reason_codes == []


def test_class_default_benchmark_is_never_probed() -> None:
    def fetch(**kwargs: Any) -> pd.DataFrame:
        raise AssertionError("the class default must not be probed")

    strategy = _strategy(comparison_baseline="SPY", resolution_provenance=[])
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        strategy,
        fetch_ohlcv_func=fetch,
    )

    assert updated is strategy
    assert reason_codes == []


def test_missing_class_default_leaves_the_leg_for_the_run_corridor() -> None:
    strategy = _strategy(asset_class="collectibles")
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        strategy,
        fetch_ohlcv_func=lambda **kwargs: _bars(0),
    )

    assert updated is strategy
    assert reason_codes == []


@pytest.mark.parametrize("timeframe", [None, "daily bars", "weekly"])
def test_unrecognized_timeframe_probes_daily(timeframe: str | None) -> None:
    calls: list[dict[str, Any]] = []

    def fetch(**kwargs: Any) -> pd.DataFrame:
        calls.append(kwargs)
        return _bars(5)

    strategy_with_benchmark_price_coverage(
        _strategy(timeframe=timeframe),
        fetch_ohlcv_func=fetch,
    )

    assert calls[0]["timeframe"] == "1D"


def test_probe_without_prior_provenance_discloses_the_symbol_itself() -> None:
    updated, reason_codes = strategy_with_benchmark_price_coverage(
        _strategy(resolution_provenance=[]),
        fetch_ohlcv_func=lambda **kwargs: _bars(0),
    )

    assert reason_codes == ["benchmark_without_price_coverage_cleared"]
    entries = [
        item
        for item in updated.resolution_provenance
        if item.field == "comparison_baseline"
    ]
    assert len(entries) == 1
    assert entries[0].raw_text == "NTDOY"
    assert entries[0].resolution_status == "unavailable_for_requested_run"


def test_serialization_keeps_the_probe_status_over_the_resolved_entry() -> None:
    """The dedupe key is (field, raw_text, source, kind); the probe must
    replace the resolved entry so the disclosure survives serialization."""
    updated, _ = strategy_with_benchmark_price_coverage(
        _strategy(),
        fetch_ohlcv_func=lambda **kwargs: _bars(0),
    )

    dumped = updated.model_dump(mode="python")
    statuses = [
        item["resolution_status"]
        for item in dumped["resolution_provenance"]
        if item["field"] == "comparison_baseline"
    ]
    assert statuses == ["unavailable_for_requested_run"]
