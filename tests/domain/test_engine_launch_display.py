from __future__ import annotations

import pytest
from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.engine_launch.display import (
    describe_timeframe,
    format_benchmark_comparison_phrase,
    format_recurring_entry_caveat,
    format_timeframe_data_caveat,
    format_timeframe_data_label,
    normalize_legacy_data_caveat,
)


@pytest.mark.parametrize(
    ("timeframe", "label"),
    [
        ("1D", "Daily data"),
        ("daily", "Daily data"),
        ("1h", "Hourly data"),
        ("2h", "2-hour data"),
        ("15m", "15-minute data"),
    ],
)
def test_timeframe_display_labels_are_user_facing(timeframe: str, label: str) -> None:
    assert format_timeframe_data_label(timeframe) == label
    assert describe_timeframe(timeframe).data_label == label


def test_timeframe_caveats_use_single_display_boundary() -> None:
    assert format_timeframe_data_caveat("1D") == "Daily data only."
    assert format_timeframe_data_caveat("2h") == "2-hour data only."
    assert (
        format_recurring_entry_caveat("1D")
        == "Recurring entries use the first available daily price in each cadence window."
    )
    assert (
        format_recurring_entry_caveat("15m")
        == "Recurring entries use the first available 15-minute price in each cadence window."
    )


def test_legacy_data_caveat_cleanup_is_centralized_compatibility() -> None:
    assert normalize_legacy_data_caveat("1D bars only.") == "Daily data only."
    assert normalize_legacy_data_caveat("2h bars only.") == "2-hour data only."
    assert (
        normalize_legacy_data_caveat(
            "Recurring entries use the first available bar in each cadence window."
        )
        == "Recurring entries use the first available daily price in each cadence window."
    )


@pytest.mark.parametrize("delta", [None, 0.02, 9.3, -9.3])
def test_benchmark_comparison_copy_is_exhaustive_and_language_aware(
    delta: float | None,
) -> None:
    comparison = benchmark_comparison_from_delta(delta)

    english = format_benchmark_comparison_phrase(
        comparison.claim,
        comparison.magnitude_points,
        language="en",
    )
    spanish = format_benchmark_comparison_phrase(
        comparison.claim,
        comparison.magnitude_points,
        language="es-419",
    )

    assert english != spanish
    if comparison.claim in {"beat_benchmark", "lagged_benchmark"}:
        assert delta is not None
        expected_magnitude = f"{abs(float(delta)):.1f}"
        assert expected_magnitude in english
        assert expected_magnitude in spanish
