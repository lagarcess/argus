"""Harmonic Analysis Module for Fibonacci-based Pattern Detection.

This module implements high-performance harmonic pattern recognition using
strict Fibonacci ratios with precision gates. Designed for sub-2ms scans
on recent pivot data.

Key Patterns:
- ABCD Measured Move: Price symmetry pattern
- Gartley: 0.618/0.786 harmonic pattern
- Bat: 0.382-0.50/0.886 harmonic pattern
- Butterfly: 0.786/1.27 harmonic pattern
- Crab: 0.382-0.618/1.618 harmonic pattern
- Elliott Wave (1-3-5): Impulse wave structure

Classification:
- MACRO_HARMONIC: Patterns exceeding 90 days from X to D
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from crypto_signals.analysis.structural import Pivot

# Fibonacci ratios used in harmonic patterns
FIB_382 = 0.382
FIB_500 = 0.500
FIB_618 = 0.618
FIB_786 = 0.786
FIB_886 = 0.886
FIB_1270 = 1.270
FIB_1618 = 1.618

# Precision gate: ±0.1% tolerance for ratio matching
PRECISION_TOLERANCE = 0.001  # 0.1% = 0.001

# Classification threshold
MACRO_THRESHOLD_DAYS = 90


@dataclass
class HarmonicPattern:
    """Represents a detected harmonic pattern.

    Attributes:
        pattern_type: Type of harmonic pattern detected
        pivots: List of 5 pivots (X, A, B, C, D) forming the pattern
        ratios: Dictionary of calculated Fibonacci ratios
        is_macro: Whether pattern exceeds 90-day threshold
    """

    pattern_type: Literal[
        "ABCD",
        "GARTLEY",
        "BAT",
        "BUTTERFLY",
        "CRAB",
        "ELLIOTT_WAVE_135",
    ]
    pivots: List[Pivot]
    ratios: Dict[str, float]
    is_macro: bool


class HarmonicAnalyzer:
    """Analyzes pivots for harmonic patterns using Fibonacci ratios.

    Optimized for performance: processes only recent pivots (last 10-15)
    to achieve sub-2ms scan times.
    """

    def __init__(self, pivots: List[Pivot]):
        """Initialize analyzer with pivot data.

        Args:
            pivots: List of Pivot objects from structural analysis.
                    Only the most recent 10-15 pivots will be processed.
        """
        # Performance optimization: keep only recent pivots
        self.pivots = pivots[-15:] if len(pivots) > 15 else pivots

    def calculate_ratio(self, p1: Pivot, p2: Pivot, p3: Pivot) -> float:
        """Calculate Fibonacci retracement/extension ratio.

        Computes the ratio of the move from p2 to p3 relative to the move
        from p1 to p2.

        Args:
            p1: First pivot (start of reference move)
            p2: Second pivot (end of reference move)
            p3: Third pivot (measured against reference)

        Returns:
            float: The retracement/extension ratio

        Example:
            >>> # XA move: 100 -> 150 (range = 50)
            >>> # AB move: 150 -> 120 (retracement = 30)
            >>> # Ratio: 30/50 = 0.618 (61.8% retracement)
        """
        reference_move = abs(p2.price - p1.price)
        if reference_move == 0:
            return 0.0

        measured_move = abs(p3.price - p2.price)
        return measured_move / reference_move

    def _matches_ratio(
        self, actual: float, target: float, tolerance: float = PRECISION_TOLERANCE
    ) -> bool:
        """Check if actual ratio matches target within tolerance.

        Args:
            actual: Calculated ratio
            target: Target Fibonacci ratio
            tolerance: Allowed variance (default ±0.1%)

        Returns:
            bool: True if ratio matches within tolerance
        """
        lower_bound = target * (1 - tolerance)
        upper_bound = target * (1 + tolerance)
        return lower_bound <= actual <= upper_bound

    def _matches_range(
        self,
        actual: float,
        min_ratio: float,
        max_ratio: float,
        tolerance: float = PRECISION_TOLERANCE,
    ) -> bool:
        """Check if actual ratio falls within a range with tolerance.

        Args:
            actual: Calculated ratio
            min_ratio: Minimum acceptable ratio
            max_ratio: Maximum acceptable ratio
            tolerance: Allowed variance on boundaries

        Returns:
            bool: True if ratio falls within range
        """
        # Expand range by tolerance on both ends
        lower_bound = min_ratio * (1 - tolerance)
        upper_bound = max_ratio * (1 + tolerance)
        return lower_bound <= actual <= upper_bound

    def _calculate_time_span_days(self, p_start: Pivot, p_end: Pivot) -> int:
        """Calculate time span in days between two pivots.

        Args:
            p_start: Starting pivot
            p_end: Ending pivot

        Returns:
            int: Number of days between pivots
        """
        delta = p_end.timestamp - p_start.timestamp
        return int(delta.days)

    def detect_abcd(self) -> Optional[HarmonicPattern]:
        """Detect ABCD measured move pattern.

        Pattern: abs(A-B) ≈ abs(C-D) and (Index_B-Index_A) ≈ (Index_D-Index_C)

        Returns:
            HarmonicPattern if detected, None otherwise
        """
        if len(self.pivots) < 4:
            return None

        # Scan recent pivots for ABCD pattern (4 consecutive pivots)
        for i in range(len(self.pivots) - 3):
            A, B, C, D = self.pivots[i : i + 4]

            # Price symmetry check
            ab_move = abs(B.price - A.price)
            cd_move = abs(D.price - C.price)
            price_ratio = cd_move / ab_move if ab_move > 0 else 0

            # Time symmetry check
            ab_time = B.index - A.index
            cd_time = D.index - C.index
            time_ratio = cd_time / ab_time if ab_time > 0 else 0

            # Both must match 1.0 within tolerance (±0.1%)
            if self._matches_ratio(price_ratio, 1.0) and self._matches_ratio(
                time_ratio, 1.0
            ):
                time_span = self._calculate_time_span_days(A, D)
                is_macro = time_span > MACRO_THRESHOLD_DAYS

                return HarmonicPattern(
                    pattern_type="ABCD",
                    pivots=[A, B, C, D],
                    ratios={
                        "AB_CD_price_ratio": price_ratio,
                        "AB_CD_time_ratio": time_ratio,
                    },
                    is_macro=is_macro,
                )

        return None

    def detect_gartley(self) -> Optional[HarmonicPattern]:
        """Detect Gartley pattern.

        Pattern: B at 0.618 of XA; D at 0.786 of XA

        Returns:
            HarmonicPattern if detected, None otherwise
        """
        if len(self.pivots) < 5:
            return None

        # Scan recent pivots for Gartley (5 consecutive pivots: X, A, B, C, D)
        for i in range(len(self.pivots) - 4):
            X, A, B, C, D = self.pivots[i : i + 5]

            # Calculate ratios
            b_ratio = self.calculate_ratio(X, A, B)
            d_ratio = self.calculate_ratio(X, A, D)

            # Gartley: B=0.618, D=0.786
            if self._matches_ratio(b_ratio, FIB_618) and self._matches_ratio(
                d_ratio, FIB_786
            ):
                time_span = self._calculate_time_span_days(X, D)
                is_macro = time_span > MACRO_THRESHOLD_DAYS

                return HarmonicPattern(
                    pattern_type="GARTLEY",
                    pivots=[X, A, B, C, D],
                    ratios={
                        "B_ratio": b_ratio,
                        "D_ratio": d_ratio,
                    },
                    is_macro=is_macro,
                )

        return None

    def detect_bat(self) -> Optional[HarmonicPattern]:
        """Detect Bat pattern.

        Pattern: B at 0.382-0.50 of XA; D at 0.886 of XA

        Returns:
            HarmonicPattern if detected, None otherwise
        """
        if len(self.pivots) < 5:
            return None

        # Scan recent pivots for Bat (5 consecutive pivots)
        for i in range(len(self.pivots) - 4):
            X, A, B, C, D = self.pivots[i : i + 5]

            # Calculate ratios
            b_ratio = self.calculate_ratio(X, A, B)
            d_ratio = self.calculate_ratio(X, A, D)

            # Bat: B in [0.382, 0.50], D=0.886
            if self._matches_range(b_ratio, FIB_382, FIB_500) and self._matches_ratio(
                d_ratio, FIB_886
            ):
                time_span = self._calculate_time_span_days(X, D)
                is_macro = time_span > MACRO_THRESHOLD_DAYS

                return HarmonicPattern(
                    pattern_type="BAT",
                    pivots=[X, A, B, C, D],
                    ratios={
                        "B_ratio": b_ratio,
                        "D_ratio": d_ratio,
                    },
                    is_macro=is_macro,
                )

        return None

    def detect_butterfly(self) -> Optional[HarmonicPattern]:
        """Detect Butterfly pattern.

        Pattern: B at 0.786 of XA; D at 1.27 of XA

        Returns:
            HarmonicPattern if detected, None otherwise
        """
        if len(self.pivots) < 5:
            return None

        # Scan recent pivots for Butterfly (5 consecutive pivots)
        for i in range(len(self.pivots) - 4):
            X, A, B, C, D = self.pivots[i : i + 5]

            # Calculate ratios
            b_ratio = self.calculate_ratio(X, A, B)
            d_ratio = self.calculate_ratio(X, A, D)

            # Butterfly: B=0.786, D=1.27
            if self._matches_ratio(b_ratio, FIB_786) and self._matches_ratio(
                d_ratio, FIB_1270
            ):
                time_span = self._calculate_time_span_days(X, D)
                is_macro = time_span > MACRO_THRESHOLD_DAYS

                return HarmonicPattern(
                    pattern_type="BUTTERFLY",
                    pivots=[X, A, B, C, D],
                    ratios={
                        "B_ratio": b_ratio,
                        "D_ratio": d_ratio,
                    },
                    is_macro=is_macro,
                )

        return None

    def detect_crab(self) -> Optional[HarmonicPattern]:
        """Detect Crab pattern.

        Pattern: B at 0.382-0.618 of XA; D at 1.618 of XA

        Returns:
            HarmonicPattern if detected, None otherwise
        """
        if len(self.pivots) < 5:
            return None

        # Scan recent pivots for Crab (5 consecutive pivots)
        for i in range(len(self.pivots) - 4):
            X, A, B, C, D = self.pivots[i : i + 5]

            # Calculate ratios
            b_ratio = self.calculate_ratio(X, A, B)
            d_ratio = self.calculate_ratio(X, A, D)

            # Crab: B in [0.382, 0.618], D=1.618
            if self._matches_range(b_ratio, FIB_382, FIB_618) and self._matches_ratio(
                d_ratio, FIB_1618
            ):
                time_span = self._calculate_time_span_days(X, D)
                is_macro = time_span > MACRO_THRESHOLD_DAYS

                return HarmonicPattern(
                    pattern_type="CRAB",
                    pivots=[X, A, B, C, D],
                    ratios={
                        "B_ratio": b_ratio,
                        "D_ratio": d_ratio,
                    },
                    is_macro=is_macro,
                )

        return None

    def detect_elliott_wave_135(self) -> Optional[HarmonicPattern]:
        """Detect Elliott Wave impulse pattern (waves 1-3-5).

        Strict implementation with Fibonacci requirements:
        - Wave 2 must not retrace > 100% of Wave 1
        - Wave 3 must be at least 1.618x Wave 1 (high conviction)
        - Wave 4 must retrace at least 23.6% of Wave 3
        - Wave 4 must not retrace into Wave 1 territory

        Returns:
            HarmonicPattern if detected, None otherwise.
            Returns the most recent pattern in the lookback window.
        """
        if len(self.pivots) < 5:
            return None

        detected_pattern = None

        # Scan for Elliott Wave (5 consecutive pivots)
        # Expected structure: Valley(0), Peak(1), Valley(2), Peak(3), Valley(4)
        # or Peak(0), Valley(1), Peak(2), Valley(3), Peak(4)
        for i in range(len(self.pivots) - 4):
            p0, p1, p2, p3, p4 = self.pivots[i : i + 5]

            # Check alternating pattern
            if not (
                p0.pivot_type != p1.pivot_type
                and p1.pivot_type != p2.pivot_type
                and p2.pivot_type != p3.pivot_type
                and p3.pivot_type != p4.pivot_type
            ):
                continue

            # For bullish impulse: p0=valley, p1=peak, p2=valley, p3=peak, p4=valley
            if p0.pivot_type == "VALLEY":
                # Rule 1: Wave 2 must not retrace > 100% of Wave 1
                if p2.price <= p0.price:
                    continue

                wave1_len = p1.price - p0.price
                wave3_len = p3.price - p2.price
                wave4_retrace_len = p3.price - p4.price

                # Rule 2: Wave 3 must be at least 1.618x Wave 1 (Tightened from 1.0x)
                if wave3_len < (1.618 * wave1_len):
                    continue

                # Rule 3: Wave 4 must retrace at least 23.6% of Wave 3
                if wave4_retrace_len < (0.236 * wave3_len):
                    continue

                # Rule 4: Wave 4 (p4) must not retrace into Wave 1 territory
                if p4.price <= p1.price:
                    continue

            # For bearish impulse: p0=peak, p1=valley, p2=peak, p3=valley, p4=peak
            elif p0.pivot_type == "PEAK":
                # Rule 1: Wave 2 must not retrace > 100% of Wave 1
                if p2.price >= p0.price:
                    continue

                wave1_len = p0.price - p1.price
                wave3_len = p2.price - p3.price
                wave4_retrace_len = p4.price - p3.price

                # Rule 2: Wave 3 must be at least 1.618x Wave 1
                if wave3_len < (1.618 * wave1_len):
                    continue

                # Rule 3: Wave 4 must retrace at least 23.6% of Wave 3
                if wave4_retrace_len < (0.236 * wave3_len):
                    continue

                # Rule 4: Wave 4 (p4) must not retrace into Wave 1 territory
                if p4.price >= p1.price:
                    continue

            else:
                continue

            # Pattern detected
            time_span = self._calculate_time_span_days(p0, p4)
            is_macro = time_span > MACRO_THRESHOLD_DAYS

            wave3_to_wave1_ratio = wave3_len / wave1_len if wave1_len > 0 else 0

            # Update detected_pattern (loop continues to find the most recent one)
            detected_pattern = HarmonicPattern(
                pattern_type="ELLIOTT_WAVE_135",
                pivots=[p0, p1, p2, p3, p4],
                ratios={
                    "wave3_to_wave1_ratio": round(wave3_to_wave1_ratio, 3),
                    "wave4_retrace_ratio": round(
                        wave4_retrace_len / wave3_len if wave3_len > 0 else 0, 3
                    ),
                },
                is_macro=is_macro,
            )

        return detected_pattern

    def scan_all_patterns(self) -> List[HarmonicPattern]:
        """Scan for all harmonic patterns.

        Returns:
            List of detected HarmonicPattern objects
        """
        patterns = []

        # Try each pattern detector
        detectors = [
            self.detect_abcd,
            self.detect_gartley,
            self.detect_bat,
            self.detect_butterfly,
            self.detect_crab,
            self.detect_elliott_wave_135,
        ]

        for detector in detectors:
            pattern = detector()
            if pattern:
                patterns.append(pattern)

        return patterns
