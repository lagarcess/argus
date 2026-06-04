from __future__ import annotations

from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)


def test_benchmark_comparison_exposes_lagged_magnitude_without_signed_user_copy() -> None:
    comparison = benchmark_comparison_from_delta(-8.1)

    assert comparison.claim == "lagged_benchmark"
    assert comparison.signed_delta_percent == "-8.1%"
    assert comparison.magnitude_points == "8.1 percentage points"
    assert comparison.user_phrase == "Lagged by 8.1 percentage points"


def test_benchmark_comparison_exposes_beat_magnitude_without_signed_user_copy() -> None:
    comparison = benchmark_comparison_from_delta(27.9)

    assert comparison.claim == "beat_benchmark"
    assert comparison.signed_delta_percent == "+27.9%"
    assert comparison.magnitude_points == "27.9 percentage points"
    assert comparison.user_phrase == "Beat by 27.9 percentage points"


def test_benchmark_comparison_treats_near_zero_as_inline() -> None:
    comparison = benchmark_comparison_from_delta(0.02)

    assert comparison.claim == "matched_benchmark"
    assert comparison.signed_delta_percent == "+0.0%"
    assert comparison.magnitude_points == "0.0 percentage points"
    assert comparison.user_phrase == "In line with benchmark"
