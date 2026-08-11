from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BenchmarkComparisonClaim = Literal[
    "beat_benchmark",
    "lagged_benchmark",
    "matched_benchmark",
    "unknown",
]


@dataclass(frozen=True)
class BenchmarkComparison:
    claim: BenchmarkComparisonClaim
    signed_delta_percent: str
    magnitude_points: str


def benchmark_comparison_from_delta(
    delta_percent: float | int | None,
    *,
    tolerance: float = 0.05,
) -> BenchmarkComparison:
    if delta_percent is None:
        return BenchmarkComparison(
            claim="unknown",
            signed_delta_percent="unknown",
            magnitude_points="unknown",
        )

    delta = float(delta_percent)
    signed_delta = _format_signed_percent(delta)
    magnitude = _format_percentage_points(abs(delta))
    if abs(delta) < tolerance:
        return BenchmarkComparison(
            claim="matched_benchmark",
            signed_delta_percent=signed_delta,
            magnitude_points=magnitude,
        )
    if delta > 0:
        return BenchmarkComparison(
            claim="beat_benchmark",
            signed_delta_percent=signed_delta,
            magnitude_points=magnitude,
        )
    return BenchmarkComparison(
        claim="lagged_benchmark",
        signed_delta_percent=signed_delta,
        magnitude_points=magnitude,
    )


def _format_signed_percent(value: float) -> str:
    prefix = "+" if value >= 0 else ""
    return f"{prefix}{value:.1f}%"


def _format_percentage_points(value: float) -> str:
    return f"{value:.1f} percentage points"
