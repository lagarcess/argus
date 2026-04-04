"""Tests for compute_diversity_metrics() in signal_generator.py."""

from unittest.mock import MagicMock

import pytest
from crypto_signals.engine.signal_generator import SignalGenerator


@pytest.fixture
def generator():
    """Minimal SignalGenerator for static method access."""
    return SignalGenerator(
        market_provider=MagicMock(),
        indicators=MagicMock(),
        pattern_analyzer_cls=MagicMock(),
        signal_repo=MagicMock(),
    )


def _make_signal(pattern_name, structural_context=None, conviction_tier=None):
    """Create a minimal mock signal for diversity metrics."""
    sig = MagicMock()
    sig.pattern_name = pattern_name
    sig.structural_context = structural_context
    sig.conviction_tier = conviction_tier
    return sig


def test_diversity_metrics_single_pattern(generator):
    """A single repeated pattern should have Shannon entropy = 0."""
    signals = [_make_signal("BULL_FLAG") for _ in range(5)]
    metrics = SignalGenerator.compute_diversity_metrics(signals)

    assert (
        metrics["total_signals"] == 5
    ), f'Expected total_signals == 5, got {metrics["total_signals"]}'
    assert (
        metrics["pattern_distribution"]["BULL_FLAG"] == {"count": 5, "pct": 100.0}
    ), f'Expected BULL_FLAG distribution == {{"count": 5, "pct": 100.0}}, got {metrics["pattern_distribution"]["BULL_FLAG"]}'
    assert (
        metrics["shannon_entropy"] == 0.0
    ), f'Expected shannon_entropy == 0.0 for single repeated pattern, got {metrics["shannon_entropy"]}'


def test_diversity_metrics_uniform_distribution(generator):
    """Uniformly distributed patterns should have maximum entropy."""
    patterns = ["BULL_FLAG", "DOUBLE_BOTTOM", "CUP_AND_HANDLE", "BULLISH_ENGULFING"]
    signals = [_make_signal(p) for p in patterns]
    metrics = SignalGenerator.compute_diversity_metrics(signals)

    assert (
        metrics["total_signals"] == 4
    ), f'Expected total_signals == 4, got {metrics["total_signals"]}'
    assert (
        len(metrics["pattern_distribution"]) == 4
    ), f'Expected 4 pattern distributions, got {len(metrics["pattern_distribution"])}'
    for p in patterns:
        assert (
            metrics["pattern_distribution"][p] == {"count": 1, "pct": 25.0}
        ), f'Expected {p} distribution == {{"count": 1, "pct": 25.0}}, got {metrics["pattern_distribution"][p]}'

    # Shannon entropy of uniform distribution of 4 items = log2(4) = 2.0
    assert (
        abs(metrics["shannon_entropy"] - 2.0) < 0.01
    ), f'Expected shannon_entropy ≈ 2.0 for uniform distribution, got {metrics["shannon_entropy"]}'


def test_diversity_metrics_with_structural_context(generator):
    """Structural context distribution should count non-None values."""
    signals = [
        _make_signal("BULL_FLAG", structural_context="GARTLEY", conviction_tier="HIGH"),
        _make_signal("BULL_FLAG", structural_context="GARTLEY", conviction_tier="HIGH"),
        _make_signal("DOUBLE_BOTTOM", structural_context="ABCD", conviction_tier="HIGH"),
        _make_signal("CUP_AND_HANDLE"),  # No structural context
    ]
    metrics = SignalGenerator.compute_diversity_metrics(signals)

    assert (
        metrics["structural_context_distribution"]["GARTLEY"] == 2
    ), f'Expected GARTLEY count == 2, got {metrics["structural_context_distribution"]["GARTLEY"]}'
    assert (
        metrics["structural_context_distribution"]["ABCD"] == 1
    ), f'Expected ABCD count == 1, got {metrics["structural_context_distribution"]["ABCD"]}'
    assert (
        metrics["conviction_distribution"]["HIGH"] == 3
    ), f'Expected HIGH conviction count == 3, got {metrics["conviction_distribution"]["HIGH"]}'
    assert (
        metrics["conviction_distribution"].get(None, 0) == 1
    ), f'Expected None conviction count == 1, got {metrics["conviction_distribution"].get(None, 0)}'


def test_diversity_metrics_empty_signals(generator):
    """Empty list should return zero metrics gracefully."""
    metrics = SignalGenerator.compute_diversity_metrics([])

    assert (
        metrics["total_signals"] == 0
    ), f'Expected total_signals == 0, got {metrics["total_signals"]}'
    assert (
        metrics["pattern_distribution"] == {}
    ), f'Expected empty pattern_distribution, got {metrics["pattern_distribution"]}'
    assert (
        metrics["structural_context_distribution"] == {}
    ), f'Expected empty structural_context_distribution, got {metrics["structural_context_distribution"]}'
    assert (
        metrics["conviction_distribution"] == {}
    ), f'Expected empty conviction_distribution, got {metrics["conviction_distribution"]}'
    assert (
        metrics["shannon_entropy"] == 0.0
    ), f'Expected shannon_entropy == 0.0 for empty signals, got {metrics["shannon_entropy"]}'
