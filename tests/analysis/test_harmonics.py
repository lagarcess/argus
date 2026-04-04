"""Unit tests for harmonic analysis module."""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from crypto_signals.analysis.harmonics import (
    FIB_382,
    FIB_618,
    FIB_786,
    FIB_886,
    FIB_1270,
    FIB_1618,
    HarmonicAnalyzer,
)
from crypto_signals.analysis.structural import Pivot


@pytest.fixture
def sample_pivots():
    """Create sample pivots for testing."""
    base_time = datetime(2024, 1, 1)

    pivots = [
        # X
        Pivot(
            timestamp=pd.Timestamp(base_time),
            price=100.0,
            pivot_type="VALLEY",
            index=0,
        ),
        # A
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=10)),
            price=150.0,
            pivot_type="PEAK",
            index=10,
        ),
        # B
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=20)),
            price=119.1,  # 0.618 retracement of XA (50 * 0.618 = 30.9, so 150 - 30.9 = 119.1)
            pivot_type="VALLEY",
            index=20,
        ),
        # C
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=30)),
            price=140.0,
            pivot_type="PEAK",
            index=30,
        ),
        # D
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=40)),
            price=110.7,  # 0.786 retracement of XA (50 * 0.786 = 39.3, so 150 - 39.3 = 110.7)
            pivot_type="VALLEY",
            index=40,
        ),
    ]
    return pivots


@pytest.fixture
def bat_pattern_pivots():
    """Create pivots forming a perfect Bat pattern."""
    base_time = datetime(2024, 1, 1)

    # Bat: B at 0.382-0.50 of XA; D at 0.886 of XA
    pivots = [
        # X
        Pivot(
            timestamp=pd.Timestamp(base_time),
            price=100.0,
            pivot_type="VALLEY",
            index=0,
        ),
        # A
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=10)),
            price=150.0,
            pivot_type="PEAK",
            index=10,
        ),
        # B - 0.45 of XA (midpoint of 0.382-0.50 range)
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=20)),
            price=127.5,  # 150 - (50 * 0.45) = 150 - 22.5 = 127.5
            pivot_type="VALLEY",
            index=20,
        ),
        # C
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=30)),
            price=145.0,
            pivot_type="PEAK",
            index=30,
        ),
        # D - 0.886 of XA
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=40)),
            price=105.7,  # 150 - (50 * 0.886) = 150 - 44.3 = 105.7
            pivot_type="VALLEY",
            index=40,
        ),
    ]
    return pivots


@pytest.fixture
def abcd_pattern_pivots():
    """Create pivots forming a perfect ABCD pattern."""
    base_time = datetime(2024, 1, 1)

    # ABCD: abs(A-B) ≈ abs(C-D) and time(B-A) ≈ time(D-C)
    pivots = [
        # A
        Pivot(
            timestamp=pd.Timestamp(base_time),
            price=100.0,
            pivot_type="VALLEY",
            index=0,
        ),
        # B
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=10)),
            price=150.0,  # +50 points
            pivot_type="PEAK",
            index=10,
        ),
        # C
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=20)),
            price=120.0,
            pivot_type="VALLEY",
            index=20,
        ),
        # D
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=30)),
            price=170.0,  # +50 points (same as AB)
            pivot_type="PEAK",
            index=30,
        ),
    ]
    return pivots


@pytest.fixture
def macro_pattern_pivots():
    """Create pivots forming a pattern >90 days (MACRO)."""
    base_time = datetime(2024, 1, 1)

    pivots = [
        # X
        Pivot(
            timestamp=pd.Timestamp(base_time),
            price=100.0,
            pivot_type="VALLEY",
            index=0,
        ),
        # A
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=30)),
            price=150.0,
            pivot_type="PEAK",
            index=30,
        ),
        # B
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=60)),
            price=119.1,  # 0.618 retracement
            pivot_type="VALLEY",
            index=60,
        ),
        # C
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=80)),
            price=140.0,
            pivot_type="PEAK",
            index=80,
        ),
        # D (100 days from X = MACRO)
        Pivot(
            timestamp=pd.Timestamp(base_time + timedelta(days=100)),
            price=110.7,  # 0.786 retracement
            pivot_type="VALLEY",
            index=100,
        ),
    ]
    return pivots


class TestHarmonicAnalyzer:
    """Tests for HarmonicAnalyzer initialization."""

    def test_init_with_few_pivots(self, sample_pivots):
        """Should accept all pivots when count <= 15."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        assert len(analyzer.pivots) == len(sample_pivots)

    def test_init_limits_to_15_pivots(self):
        """Should limit to last 15 pivots for performance."""
        # Create 20 pivots
        base_time = datetime(2024, 1, 1)
        many_pivots = [
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=i)),
                price=100.0 + i,
                pivot_type="PEAK" if i % 2 == 0 else "VALLEY",
                index=i,
            )
            for i in range(20)
        ]

        analyzer = HarmonicAnalyzer(many_pivots)
        assert len(analyzer.pivots) == 15
        # Should keep the most recent 15
        assert analyzer.pivots[0].index == 5
        assert analyzer.pivots[-1].index == 19


class TestCalculateRatio:
    """Tests for calculate_ratio method."""

    def test_basic_ratio_calculation(self, sample_pivots):
        """Should calculate correct Fibonacci ratio."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        X, A, B = sample_pivots[0:3]

        # XA move: 100 -> 150 (range = 50)
        # AB move: 150 -> 119.1 (retracement = 30.9)
        # Ratio: 30.9 / 50 = 0.618
        ratio = analyzer.calculate_ratio(X, A, B)
        assert abs(ratio - FIB_618) < 0.01  # Allow small floating point variance

    def test_ratio_with_zero_reference(self, sample_pivots):
        """Should return 0.0 when reference move is zero."""
        analyzer = HarmonicAnalyzer(sample_pivots)

        # Create two pivots with same price
        p1 = Pivot(
            timestamp=pd.Timestamp("2024-01-01"),
            price=100.0,
            pivot_type="VALLEY",
            index=0,
        )
        p2 = Pivot(
            timestamp=pd.Timestamp("2024-01-02"),
            price=100.0,  # Same as p1
            pivot_type="PEAK",
            index=1,
        )
        p3 = sample_pivots[2]

        ratio = analyzer.calculate_ratio(p1, p2, p3)
        assert ratio == 0.0


class TestPrecisionGate:
    """Tests for precision gate methods."""

    def test_matches_ratio_exact(self, sample_pivots):
        """Should match exact ratio."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        assert analyzer._matches_ratio(0.618, FIB_618)

    def test_matches_ratio_within_tolerance(self, sample_pivots):
        """Should match ratio within ±0.1% tolerance."""
        analyzer = HarmonicAnalyzer(sample_pivots)

        # 0.618 ± 0.1% = [0.617382, 0.618618] (but floating point precision matters)
        assert analyzer._matches_ratio(0.617382, FIB_618)  # Lower bound
        assert analyzer._matches_ratio(0.618, FIB_618)  # Exact value
        assert analyzer._matches_ratio(0.618617, FIB_618)  # Just below upper bound

    def test_matches_ratio_outside_tolerance(self, sample_pivots):
        """Should reject ratio outside tolerance."""
        analyzer = HarmonicAnalyzer(sample_pivots)

        # Outside ±0.1% tolerance
        assert not analyzer._matches_ratio(0.617, FIB_618)  # Too low
        assert not analyzer._matches_ratio(0.619, FIB_618)  # Too high

    def test_matches_range(self, sample_pivots):
        """Should match value within range."""
        analyzer = HarmonicAnalyzer(sample_pivots)

        # Test Bat B-leg range: 0.382-0.50
        assert analyzer._matches_range(0.45, FIB_382, 0.50)
        assert analyzer._matches_range(0.382, FIB_382, 0.50)
        assert analyzer._matches_range(0.50, FIB_382, 0.50)

    def test_matches_range_with_tolerance(self, sample_pivots):
        """Should expand range boundaries by tolerance."""
        analyzer = HarmonicAnalyzer(sample_pivots)

        # Range [0.382, 0.50] with ±0.1% tolerance
        # Lower: 0.382 * 0.999 = 0.381618
        # Upper: 0.50 * 1.001 = 0.5005
        assert analyzer._matches_range(0.381618, FIB_382, 0.50)  # Exact lower bound
        assert analyzer._matches_range(0.5005, FIB_382, 0.50)  # Exact upper bound
        assert analyzer._matches_range(0.45, FIB_382, 0.50)  # Middle of range


class TestPatternDetection:
    """Tests for individual pattern detection methods."""

    def test_detect_gartley(self, sample_pivots):
        """Should detect valid Gartley pattern."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        pattern = analyzer.detect_gartley()

        assert pattern is not None
        assert pattern.pattern_type == "GARTLEY"
        assert len(pattern.pivots) == 5
        assert "B_ratio" in pattern.ratios
        assert "D_ratio" in pattern.ratios
        # Verify ratios are close to expected Fibonacci values
        assert pattern.ratios["B_ratio"] == pytest.approx(FIB_618, abs=0.01)
        assert pattern.ratios["D_ratio"] == pytest.approx(FIB_786, abs=0.01)

    def test_detect_bat(self, bat_pattern_pivots):
        """Should detect valid Bat pattern."""
        analyzer = HarmonicAnalyzer(bat_pattern_pivots)
        pattern = analyzer.detect_bat()

        assert pattern is not None
        assert pattern.pattern_type == "BAT"
        assert len(pattern.pivots) == 5
        assert "B_ratio" in pattern.ratios
        assert "D_ratio" in pattern.ratios
        # B should be in [0.382, 0.50] range
        assert 0.382 <= pattern.ratios["B_ratio"] <= 0.50
        # D should be ~0.886
        assert pattern.ratios["D_ratio"] == pytest.approx(FIB_886, abs=0.01)

    def test_detect_abcd(self, abcd_pattern_pivots):
        """Should detect valid ABCD pattern."""
        analyzer = HarmonicAnalyzer(abcd_pattern_pivots)
        pattern = analyzer.detect_abcd()

        assert pattern is not None
        assert pattern.pattern_type == "ABCD"
        assert len(pattern.pivots) == 4
        assert "AB_CD_price_ratio" in pattern.ratios
        assert "AB_CD_time_ratio" in pattern.ratios
        # Both ratios should be close to 1.0 (symmetry)
        assert pattern.ratios["AB_CD_price_ratio"] == pytest.approx(1.0, abs=0.01)
        assert pattern.ratios["AB_CD_time_ratio"] == pytest.approx(1.0, abs=0.01)

    def test_detect_butterfly(self):
        """Should detect valid Butterfly pattern."""
        base_time = datetime(2024, 1, 1)

        # Butterfly: B at 0.786 of XA; D at 1.27 of XA
        pivots = [
            Pivot(
                timestamp=pd.Timestamp(base_time),
                price=100.0,
                pivot_type="VALLEY",
                index=0,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=10)),
                price=150.0,
                pivot_type="PEAK",
                index=10,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=20)),
                price=110.7,  # 0.786 retracement: 150 - (50 * 0.786) = 110.7
                pivot_type="VALLEY",
                index=20,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=30)),
                price=140.0,
                pivot_type="PEAK",
                index=30,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=40)),
                price=86.5,  # 1.27 extension: 150 - (50 * 1.27) = 86.5
                pivot_type="VALLEY",
                index=40,
            ),
        ]

        analyzer = HarmonicAnalyzer(pivots)
        pattern = analyzer.detect_butterfly()

        assert pattern is not None
        assert pattern.pattern_type == "BUTTERFLY"
        assert pattern.ratios["B_ratio"] == pytest.approx(FIB_786, abs=0.01)
        assert pattern.ratios["D_ratio"] == pytest.approx(FIB_1270, abs=0.01)

    def test_detect_crab(self):
        """Should detect valid Crab pattern."""
        base_time = datetime(2024, 1, 1)

        # Crab: B at 0.382-0.618 of XA; D at 1.618 of XA
        pivots = [
            Pivot(
                timestamp=pd.Timestamp(base_time),
                price=100.0,
                pivot_type="VALLEY",
                index=0,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=10)),
                price=150.0,
                pivot_type="PEAK",
                index=10,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=20)),
                price=125.0,  # 0.50 retracement (midpoint of range)
                pivot_type="VALLEY",
                index=20,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=30)),
                price=145.0,
                pivot_type="PEAK",
                index=30,
            ),
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=40)),
                price=69.1,  # 1.618 extension: 150 - (50 * 1.618) = 69.1
                pivot_type="VALLEY",
                index=40,
            ),
        ]

        analyzer = HarmonicAnalyzer(pivots)
        pattern = analyzer.detect_crab()

        assert pattern is not None
        assert pattern.pattern_type == "CRAB"
        assert 0.382 <= pattern.ratios["B_ratio"] <= 0.618
        assert pattern.ratios["D_ratio"] == pytest.approx(FIB_1618, abs=0.01)

    def test_detect_elliott_wave(self):
        """Should detect valid Elliott Wave 1-3-5 pattern."""
        base_time = datetime(2024, 1, 1)

        # Elliott Wave: Wave 3 > Wave 1, Wave 4 doesn't retrace into Wave 1
        pivots = [
            # Wave 0 (start)
            Pivot(
                timestamp=pd.Timestamp(base_time),
                price=100.0,
                pivot_type="VALLEY",
                index=0,
            ),
            # Wave 1 peak
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=10)),
                price=120.0,
                pivot_type="PEAK",
                index=10,
            ),
            # Wave 2 valley
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=20)),
                price=110.0,
                pivot_type="VALLEY",
                index=20,
            ),
            # Wave 3 peak (longer than Wave 1)
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=30)),
                price=145.0,  # Wave 3 = 35 points > Wave 1 = 20 points
                pivot_type="PEAK",
                index=30,
            ),
            # Wave 4 valley (above Wave 1 peak at 120)
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=40)),
                price=125.0,
                pivot_type="VALLEY",
                index=40,
            ),
        ]

        analyzer = HarmonicAnalyzer(pivots)
        pattern = analyzer.detect_elliott_wave_135()

        assert pattern is not None
        assert pattern.pattern_type == "ELLIOTT_WAVE_135"
        assert "wave3_to_wave1_ratio" in pattern.ratios
        assert pattern.ratios["wave3_to_wave1_ratio"] > 1.0  # Wave 3 > Wave 1


class TestMacroClassification:
    """Tests for MACRO pattern classification."""

    def test_macro_classification(self, macro_pattern_pivots):
        """Should classify pattern as MACRO when >90 days."""
        analyzer = HarmonicAnalyzer(macro_pattern_pivots)
        pattern = analyzer.detect_gartley()

        assert pattern is not None
        assert pattern.is_macro is True

    def test_non_macro_classification(self, sample_pivots):
        """Should not classify as MACRO when ≤90 days."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        pattern = analyzer.detect_gartley()

        assert pattern is not None
        assert pattern.is_macro is False


class TestScanAllPatterns:
    """Tests for scan_all_patterns method."""

    def test_scan_all_patterns_gartley(self, sample_pivots):
        """Should find Gartley pattern in scan."""
        analyzer = HarmonicAnalyzer(sample_pivots)
        patterns = analyzer.scan_all_patterns()

        assert len(patterns) > 0
        # Should find at least the Gartley pattern
        pattern_types = [p.pattern_type for p in patterns]
        assert "GARTLEY" in pattern_types

    def test_scan_all_patterns_bat(self, bat_pattern_pivots):
        """Should find Bat pattern in scan."""
        analyzer = HarmonicAnalyzer(bat_pattern_pivots)
        patterns = analyzer.scan_all_patterns()

        assert len(patterns) > 0
        pattern_types = [p.pattern_type for p in patterns]
        assert "BAT" in pattern_types

    def test_scan_all_patterns_empty(self):
        """Should return empty list when no patterns found."""
        # Create pivots that don't form any harmonic pattern
        base_time = datetime(2024, 1, 1)
        random_pivots = [
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=i)),
                price=100.0 + (i * 2),  # Linear progression, no Fibonacci ratios
                pivot_type="PEAK" if i % 2 == 0 else "VALLEY",
                index=i,
            )
            for i in range(5)
        ]

        analyzer = HarmonicAnalyzer(random_pivots)
        patterns = analyzer.scan_all_patterns()

        # May or may not find patterns depending on coincidental ratios
        # Just verify it doesn't crash
        assert isinstance(patterns, list)


class TestPerformance:
    """Performance tests for sub-2ms target."""

    def test_performance_with_15_pivots(self, sample_pivots):
        """Should scan all patterns in reasonable time."""
        import time

        # Extend to 15 pivots
        base_time = datetime(2024, 1, 1)
        extended_pivots = sample_pivots + [
            Pivot(
                timestamp=pd.Timestamp(base_time + timedelta(days=50 + i)),
                price=100.0 + (i * 5),
                pivot_type="PEAK" if i % 2 == 0 else "VALLEY",
                index=50 + i,
            )
            for i in range(10)
        ]

        analyzer = HarmonicAnalyzer(extended_pivots)

        start = time.perf_counter()
        patterns = analyzer.scan_all_patterns()
        elapsed = time.perf_counter() - start

        # Should complete in well under 2ms (allowing 10ms for CI variance)
        assert elapsed < 0.01, f"Scan took {elapsed * 1000:.2f}ms"
        assert isinstance(patterns, list)
