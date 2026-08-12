from __future__ import annotations

from dataclasses import fields

from argus.domain.benchmark_comparison import (
    BenchmarkComparison,
    benchmark_comparison_from_delta,
)


def test_benchmark_comparison_carries_only_typed_facts() -> None:
    assert {field.name for field in fields(BenchmarkComparison)} == {
        "claim",
        "signed_delta_percent",
        "magnitude_points",
    }


def test_benchmark_comparison_exposes_lagged_magnitude() -> None:
    comparison = benchmark_comparison_from_delta(-8.1)

    assert comparison.claim == "lagged_benchmark"
    assert comparison.signed_delta_percent == "-8.1%"
    assert comparison.magnitude_points == "8.1 percentage points"


def test_benchmark_comparison_exposes_beat_magnitude() -> None:
    comparison = benchmark_comparison_from_delta(27.9)

    assert comparison.claim == "beat_benchmark"
    assert comparison.signed_delta_percent == "+27.9%"
    assert comparison.magnitude_points == "27.9 percentage points"


def test_benchmark_comparison_treats_near_zero_as_inline() -> None:
    comparison = benchmark_comparison_from_delta(0.02)

    assert comparison.claim == "matched_benchmark"
    assert comparison.signed_delta_percent == "+0.0%"
    assert comparison.magnitude_points == "0.0 percentage points"
