"""
Generate candlestick pattern visualizations for documentation.
Uses mplfinance to create professional-looking chart pattern images.
"""

from datetime import datetime, timedelta
from pathlib import Path

import mplfinance as mpf
import pandas as pd

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "images" / "patterns"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Custom dark style matching our docs
DARK_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#00ff88",  # Green for bullish
        down="#ff4444",  # Red for bearish
        edge={"up": "#00ff88", "down": "#ff4444"},
        wick={"up": "#00ff88", "down": "#ff4444"},
        volume={"up": "#00ff88", "down": "#ff4444"},
    ),
    facecolor="#0d1117",  # Dark background
    figcolor="#0d1117",
    gridcolor="#21262d",
    gridstyle="--",
    gridaxis="both",
)


def create_ohlc_data(patterns: list[tuple]) -> pd.DataFrame:
    """Create OHLC DataFrame from pattern tuples (open, high, low, close)."""
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(len(patterns))]
    data = {
        "Open": [p[0] for p in patterns],
        "High": [p[1] for p in patterns],
        "Low": [p[2] for p in patterns],
        "Close": [p[3] for p in patterns],
        "Volume": [1000000] * len(patterns),
    }
    df = pd.DataFrame(data, index=pd.DatetimeIndex(dates))
    df.index.name = "Date"
    return df


def save_pattern(df: pd.DataFrame, name: str, title: str = "") -> None:
    """Save pattern chart to file."""
    filepath = OUTPUT_DIR / f"{name}.png"
    mpf.plot(
        df,
        type="candle",
        style=DARK_STYLE,
        title=title,
        ylabel="",
        figsize=(4, 3),
        savefig=dict(fname=filepath, dpi=100, bbox_inches="tight", pad_inches=0.1),
        axisoff=True,
    )
    print(f"Saved: {filepath}")


# ============================================================================
# SINGLE CANDLE PATTERNS
# ============================================================================


def generate_hammer():
    """Hammer: small body at top, long lower wick."""
    # (open, high, low, close)
    data = [
        (100, 101, 95, 98),  # Context: bearish
        (98, 99, 92, 94),  # Context: bearish
        (94, 95, 85, 94.5),  # HAMMER: opens low area, long lower wick, closes near high
    ]
    save_pattern(create_ohlc_data(data), "hammer", "Hammer")


def generate_inverted_hammer():
    """Inverted Hammer: small body at bottom, long upper wick."""
    data = [
        (100, 101, 95, 96),  # Context: bearish
        (96, 97, 90, 91),  # Context: bearish
        (91, 99, 90, 92),  # INVERTED HAMMER: long upper wick, small body at bottom
    ]
    save_pattern(create_ohlc_data(data), "inverted_hammer", "Inverted Hammer")


def generate_dragonfly_doji():
    """Dragonfly Doji: open=close=high, long lower shadow."""
    data = [
        (100, 101, 95, 96),  # Context: bearish
        (96, 97, 90, 91),  # Context: bearish
        (95, 95.2, 85, 95),  # DRAGONFLY: open≈close≈high, long lower shadow
    ]
    save_pattern(create_ohlc_data(data), "dragonfly_doji", "Dragonfly Doji")


def generate_belt_hold():
    """Bullish Belt Hold: opens at low, large green body, no lower wick."""
    data = [
        (100, 101, 95, 96),  # Context: bearish
        (96, 97, 90, 91),  # Context: bearish
        (88, 98, 88, 97),  # BELT HOLD: opens at low, closes near high
    ]
    save_pattern(create_ohlc_data(data), "belt_hold", "Bullish Belt Hold")


def generate_marubozu():
    """Bullish Marubozu: full body, no wicks."""
    data = [
        (95, 96, 93, 94),  # Context
        (94, 95, 92, 93),  # Context
        (93, 103, 93, 103),  # MARUBOZU: open=low, close=high
    ]
    save_pattern(create_ohlc_data(data), "marubozu", "Bullish Marubozu")


# ============================================================================
# TWO CANDLE PATTERNS
# ============================================================================


def generate_bullish_engulfing():
    """Bullish Engulfing: green candle completely covers previous red."""
    data = [
        (100, 101, 95, 96),  # Context: bearish
        (96, 97, 92, 93),  # Small red candle
        (92, 100, 91, 99),  # ENGULFING: large green covers the red
    ]
    save_pattern(create_ohlc_data(data), "bullish_engulfing", "Bullish Engulfing")


def generate_bullish_harami():
    """Bullish Harami: small green inside large red."""
    data = [
        (100, 101, 95, 96),  # Context
        (98, 99, 88, 89),  # Large red candle
        (92, 94, 91, 93),  # HARAMI: small green inside the red body
    ]
    save_pattern(create_ohlc_data(data), "bullish_harami", "Bullish Harami")


def generate_bullish_kicker():
    """Bullish Kicker: gap up from red to green."""
    data = [
        (100, 101, 95, 96),  # Context
        (96, 97, 90, 91),  # Red candle
        (98, 108, 97, 107),  # KICKER: gap up, large green
    ]
    save_pattern(create_ohlc_data(data), "bullish_kicker", "Bullish Kicker")


def generate_piercing_line():
    """Piercing Line: green opens below, closes above midpoint of red."""
    data = [
        (100, 101, 95, 96),  # Context
        (98, 99, 88, 89),  # Large red: open 98, close 89, mid=93.5
        (87, 96, 86, 95),  # PIERCING: opens below 89, closes above 93.5
    ]
    save_pattern(create_ohlc_data(data), "piercing_line", "Piercing Line")


def generate_tweezer_bottoms():
    """Tweezer Bottoms: two candles with matching lows."""
    data = [
        (100, 101, 95, 96),  # Context
        (96, 97, 88, 89),  # First candle: low at 88
        (89, 95, 88, 94),  # TWEEZER: matching low at 88, bullish close
    ]
    save_pattern(create_ohlc_data(data), "tweezer_bottoms", "Tweezer Bottoms")


# ============================================================================
# THREE CANDLE PATTERNS
# ============================================================================


def generate_morning_star():
    """Morning Star: large red, small doji, large green."""
    data = [
        (100, 101, 90, 91),  # Large red candle
        (89, 90, 86, 87),  # Small star/doji (gap down)
        (89, 99, 88, 98),  # Large green candle (gap up from star)
    ]
    save_pattern(create_ohlc_data(data), "morning_star", "Morning Star")


def generate_three_white_soldiers():
    """Three White Soldiers: three ascending green candles."""
    data = [
        (90, 95, 89, 94),  # First soldier
        (93, 99, 92, 98),  # Second soldier (opens within previous body)
        (97, 104, 96, 103),  # Third soldier
    ]
    save_pattern(create_ohlc_data(data), "three_white_soldiers", "Three White Soldiers")


def generate_three_inside_up():
    """Three Inside Up: large red, small green harami, green confirmation."""
    data = [
        (100, 101, 88, 89),  # Large red
        (92, 95, 91, 94),  # Small green harami (inside red body)
        (94, 102, 93, 101),  # Green confirmation (closes above red open)
    ]
    save_pattern(create_ohlc_data(data), "three_inside_up", "Three Inside Up")


def generate_rising_three_methods():
    """Rising Three Methods: large green, 3 small reds inside, green breakout."""
    data = [
        (90, 100, 89, 99),  # Large green trend candle
        (98, 99, 94, 95),  # Small red 1 (inside range)
        (95, 96, 92, 93),  # Small red 2
        (93, 94, 91, 92),  # Small red 3
        (92, 105, 91, 104),  # Large green breakout (closes above first candle high)
    ]
    save_pattern(create_ohlc_data(data), "rising_three_methods", "Rising Three Methods")


# ============================================================================
# CHART PATTERNS (Multi-day)
# ============================================================================


def generate_double_bottom():
    """Double Bottom: W-shape pattern."""
    data = [
        (100, 101, 98, 99),  # Decline start
        (99, 100, 94, 95),  # Decline
        (95, 96, 88, 89),  # First bottom
        (89, 95, 88, 94),  # Rally to neckline
        (94, 97, 93, 96),  # Neckline area
        (96, 97, 89, 90),  # Decline to second bottom
        (90, 91, 87, 88),  # Second bottom (≈ first)
        (88, 96, 87, 95),  # Rally
        (95, 102, 94, 101),  # Breakout above neckline
    ]
    save_pattern(create_ohlc_data(data), "double_bottom", "Double Bottom")


def generate_cup_and_handle():
    """Cup and Handle: U-shape with small handle consolidation."""
    data = [
        (100, 101, 98, 99),  # Left rim
        (99, 100, 94, 95),  # Cup descent
        (95, 96, 88, 89),  # Cup bottom
        (89, 92, 88, 91),  # Cup bottom
        (91, 94, 90, 93),  # Cup ascent
        (93, 97, 92, 96),  # Approaching right rim
        (96, 100, 95, 99),  # Right rim (≈ left rim)
        (99, 100, 96, 97),  # Handle: slight pullback
        (97, 98, 95, 96),  # Handle consolidation
        (96, 105, 95, 104),  # Breakout
    ]
    save_pattern(create_ohlc_data(data), "cup_and_handle", "Cup and Handle")


def generate_ascending_triangle():
    """Ascending Triangle: flat resistance, rising support."""
    data = [
        (92, 100, 91, 99),  # Test resistance
        (99, 100, 94, 95),  # Pullback
        (95, 100, 94, 99),  # Test resistance again
        (99, 100, 96, 97),  # Higher low pullback
        (97, 100, 96, 99),  # Test resistance
        (99, 100, 97, 98),  # Higher low
        (98, 105, 97, 104),  # Breakout above resistance
    ]
    save_pattern(create_ohlc_data(data), "ascending_triangle", "Ascending Triangle")


def generate_falling_wedge():
    """Falling Wedge: converging downward trendlines with breakout."""
    data = [
        (100, 101, 95, 96),  # Start high
        (96, 98, 92, 97),  # Lower high, higher low (converging)
        (97, 98, 90, 91),  # Decline
        (91, 94, 88, 93),  # Lower high
        (93, 94, 87, 88),  # Decline
        (88, 91, 86, 90),  # Narrow range (wedge apex)
        (90, 98, 89, 97),  # Breakout above upper trendline
    ]
    save_pattern(create_ohlc_data(data), "falling_wedge", "Falling Wedge")


def generate_bull_flag():
    """Bull Flag: strong rally (flagpole) then slight consolidation (flag)."""
    data = [
        (80, 85, 79, 84),  # Flagpole start
        (84, 92, 83, 91),  # Flagpole rally
        (91, 100, 90, 99),  # Flagpole peak
        (99, 100, 96, 97),  # Flag: slight decline
        (97, 98, 95, 96),  # Flag consolidation
        (96, 97, 94, 95),  # Flag consolidation
        (95, 105, 94, 104),  # Breakout
    ]
    save_pattern(create_ohlc_data(data), "bull_flag", "Bull Flag")


def generate_inverse_head_shoulders():
    """Inverse Head and Shoulders: three troughs with middle lowest."""
    data = [
        (100, 101, 95, 96),  # Decline
        (96, 97, 88, 89),  # Left shoulder low
        (89, 95, 88, 94),  # Rally to neckline
        (94, 95, 90, 91),  # Decline toward head
        (91, 92, 82, 83),  # HEAD (lowest point)
        (83, 92, 82, 91),  # Rally to neckline
        (91, 95, 90, 94),  # Neckline area
        (94, 95, 87, 88),  # Right shoulder low (≈ left shoulder)
        (88, 96, 87, 95),  # Rally
        (95, 103, 94, 102),  # Breakout above neckline
    ]
    save_pattern(create_ohlc_data(data), "inverse_head_shoulders", "Inverse H&S")


# ============================================================================
# HARMONIC PATTERNS (Fibonacci-based)
# ============================================================================


def save_harmonic_pattern(
    df: pd.DataFrame,
    name: str,
    title: str,
    pivots: list[tuple[int, float, str]],
) -> None:
    """Save harmonic pattern chart with pivot annotations and connecting lines.

    Args:
        df: OHLC DataFrame
        name: Output filename
        title: Chart title
        pivots: List of (bar_index, price, label) tuples for pivot points
    """
    import matplotlib.pyplot as plt

    filepath = OUTPUT_DIR / f"{name}.png"

    # Create custom addplot for pivot lines
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=DARK_STYLE,
        title=title,
        ylabel="",
        figsize=(5, 3.5),
        returnfig=True,
        axisoff=True,
    )

    ax = axes[0]

    # Draw lines connecting pivots
    if len(pivots) >= 2:
        xs = [p[0] for p in pivots]
        ys = [p[1] for p in pivots]
        ax.plot(xs, ys, color="#00bfff", linewidth=1.5, linestyle="-", alpha=0.8)

    # Add labels for each pivot point
    for idx, price, label in pivots:
        ax.annotate(
            label,
            xy=(idx, price),
            xytext=(0, 8 if label in ["A", "C"] else -12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="bold",
            color="#ffffff",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#1e3a5f", edgecolor="none"),
        )
        ax.plot(idx, price, "o", color="#00bfff", markersize=6)

    fig.savefig(filepath, dpi=100, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"Saved: {filepath}")


def generate_abcd():
    """ABCD Pattern: price and time symmetry AB ≈ CD."""
    # Create data showing AB move followed by CD move of same magnitude
    data = [
        (90, 92, 89, 91),  # Context
        (91, 93, 90, 92),  # A - start of AB leg
        (92, 98, 91, 97),  # Rising
        (97, 103, 96, 102),  # B - peak of AB leg
        (102, 103, 97, 98),  # Decline - BC retracement
        (98, 99, 94, 95),  # C - start of CD leg
        (95, 101, 94, 100),  # Rising
        (100, 106, 99, 105),  # D - peak of CD leg (≈ AB)
    ]
    df = create_ohlc_data(data)
    pivots = [
        (1, 91, "A"),  # Valley
        (3, 102, "B"),  # Peak
        (5, 95, "C"),  # Valley
        (7, 105, "D"),  # Peak
    ]
    save_harmonic_pattern(df, "abcd", "ABCD Pattern", pivots)


def generate_gartley():
    """Gartley Pattern: B=0.618, D=0.786 of XA."""
    # X to A is a 50 point move, B retraces 61.8%, D ends at 78.6%
    data = [
        (50, 52, 49, 51),  # X valley
        (51, 65, 50, 64),  # Rising
        (64, 82, 63, 81),  # Rising
        (81, 101, 80, 100),  # A peak (X=50, A=100, range=50)
        (100, 101, 90, 91),  # Decline
        (91, 92, 68, 69),  # B valley (100 - 50*0.618 = 69.1)
        (69, 82, 68, 81),  # Rising
        (81, 92, 80, 91),  # C peak
        (91, 92, 75, 76),  # Decline
        (76, 77, 60, 61),  # D valley (100 - 50*0.786 = 60.7)
    ]
    df = create_ohlc_data(data)
    pivots = [
        (0, 50, "X"),  # Valley
        (3, 100, "A"),  # Peak
        (5, 69, "B"),  # Valley (0.618 retracement)
        (7, 91, "C"),  # Peak
        (9, 61, "D"),  # Valley (0.786 retracement)
    ]
    save_harmonic_pattern(df, "gartley", "Gartley Pattern", pivots)


def generate_bat():
    """Bat Pattern: B=0.382-0.50, D=0.886 of XA."""
    # X to A is a 50 point move, B retraces 45%, D ends at 88.6%
    data = [
        (50, 52, 49, 51),  # X valley
        (51, 68, 50, 67),  # Rising
        (67, 85, 66, 84),  # Rising
        (84, 101, 83, 100),  # A peak (X=50, A=100, range=50)
        (100, 101, 92, 93),  # Decline
        (93, 94, 76, 77.5),  # B valley (100 - 50*0.45 = 77.5)
        (77.5, 88, 76.5, 87),  # Rising
        (87, 96, 86, 95),  # C peak
        (95, 96, 80, 81),  # Decline
        (81, 82, 55, 56),  # D valley (100 - 50*0.886 = 55.7)
    ]
    df = create_ohlc_data(data)
    pivots = [
        (0, 50, "X"),  # Valley
        (3, 100, "A"),  # Peak
        (5, 77.5, "B"),  # Valley (0.45 retracement)
        (7, 95, "C"),  # Peak
        (9, 56, "D"),  # Valley (0.886 retracement)
    ]
    save_harmonic_pattern(df, "bat", "Bat Pattern", pivots)


def generate_butterfly():
    """Butterfly Pattern: B=0.786, D=1.27 extension of XA."""
    # X to A is a 40 point move, D extends 27% beyond X
    data = [
        (60, 62, 59, 61),  # X valley
        (61, 75, 60, 74),  # Rising
        (74, 90, 73, 89),  # Rising
        (89, 101, 88, 100),  # A peak (X=60, A=100, range=40)
        (100, 101, 85, 86),  # Decline
        (86, 87, 68, 69),  # B valley (100 - 40*0.786 = 68.6)
        (69, 80, 68, 79),  # Rising
        (79, 92, 78, 91),  # C peak
        (91, 92, 70, 71),  # Decline
        (71, 72, 48, 49),  # D valley (100 - 40*1.27 = 49.2) - below X!
    ]
    df = create_ohlc_data(data)
    pivots = [
        (0, 60, "X"),  # Valley
        (3, 100, "A"),  # Peak
        (5, 69, "B"),  # Valley (0.786 retracement)
        (7, 91, "C"),  # Peak
        (9, 49, "D"),  # Valley (1.27 extension - below X)
    ]
    save_harmonic_pattern(df, "butterfly", "Butterfly Pattern", pivots)


def generate_crab():
    """Crab Pattern: B=0.382-0.618, D=1.618 extension of XA."""
    # X to A is a 35 point move, D extends to 1.618
    data = [
        (65, 67, 64, 66),  # X valley
        (66, 78, 65, 77),  # Rising
        (77, 90, 76, 89),  # Rising
        (89, 101, 88, 100),  # A peak (X=65, A=100, range=35)
        (100, 101, 90, 91),  # Decline
        (91, 92, 81, 82),  # B valley (100 - 35*0.50 = 82.5)
        (82, 90, 81, 89),  # Rising
        (89, 96, 88, 95),  # C peak
        (95, 96, 75, 76),  # Decline
        (76, 77, 42, 43),  # D valley (100 - 35*1.618 = 43.4) - far below X!
    ]
    df = create_ohlc_data(data)
    pivots = [
        (0, 65, "X"),  # Valley
        (3, 100, "A"),  # Peak
        (5, 82, "B"),  # Valley (0.50 retracement)
        (7, 95, "C"),  # Peak
        (9, 43, "D"),  # Valley (1.618 extension)
    ]
    save_harmonic_pattern(df, "crab", "Crab Pattern", pivots)


def generate_elliott_wave():
    """Elliott Wave 1-3-5: Wave 3 > Wave 1, Wave 4 above Wave 1 peak."""
    # Classic 5-wave impulse structure
    data = [
        (50, 52, 49, 51),  # Wave 0 start
        (51, 60, 50, 59),  # Wave 1 rise
        (59, 68, 58, 67),  # Wave 1 peak
        (67, 68, 60, 61),  # Wave 2 correction
        (61, 75, 60, 74),  # Wave 3 start
        (74, 90, 73, 89),  # Wave 3 rise (longest)
        (89, 100, 88, 99),  # Wave 3 peak
        (99, 100, 80, 81),  # Wave 4 correction (stays above Wave 1 peak)
        (81, 95, 80, 94),  # Wave 5 rise
        (94, 110, 93, 109),  # Wave 5 peak (final)
    ]
    df = create_ohlc_data(data)
    pivots = [
        (0, 50, "0"),  # Start
        (2, 67, "1"),  # Wave 1 peak
        (3, 61, "2"),  # Wave 2 valley
        (6, 99, "3"),  # Wave 3 peak
        (7, 81, "4"),  # Wave 4 valley (above Wave 1 peak)
        (9, 109, "5"),  # Wave 5 peak
    ]
    save_harmonic_pattern(df, "elliott_wave", "Elliott Wave 1-3-5", pivots)


def main():
    """Generate all pattern visualizations."""
    print("Generating pattern visualizations...")

    # Single candle
    generate_hammer()
    generate_inverted_hammer()
    generate_dragonfly_doji()
    generate_belt_hold()
    generate_marubozu()

    # Two candle
    generate_bullish_engulfing()
    generate_bullish_harami()
    generate_bullish_kicker()
    generate_piercing_line()
    generate_tweezer_bottoms()

    # Three candle
    generate_morning_star()
    generate_three_white_soldiers()
    generate_three_inside_up()
    generate_rising_three_methods()

    # Chart patterns
    generate_double_bottom()
    generate_cup_and_handle()
    generate_ascending_triangle()
    generate_falling_wedge()
    generate_bull_flag()
    generate_inverse_head_shoulders()

    # Harmonic patterns
    generate_abcd()
    generate_gartley()
    generate_bat()
    generate_butterfly()
    generate_crab()
    generate_elliott_wave()

    print(f"\nAll patterns saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
