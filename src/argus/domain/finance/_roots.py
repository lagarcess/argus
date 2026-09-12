"""One root finder for every rate the math solves numerically."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

_DEFAULT_GRID: tuple[float, ...] = (
    -0.95,
    -0.5,
    -0.2,
    -0.1,
    -0.05,
    -0.01,
    0.0,
    0.01,
    0.05,
    0.1,
    0.2,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
)


def bracketed_root(
    function: Callable[[float], float],
    grid: Sequence[float] = _DEFAULT_GRID,
    *,
    tolerance: float = 1e-12,
    iterations: int = 300,
) -> float | None:
    """The first root between consecutive grid points where the sign changes."""
    previous_x: float | None = None
    previous_y: float | None = None
    for x in grid:
        try:
            y = function(x)
        except (OverflowError, ValueError, ZeroDivisionError):
            previous_x, previous_y = None, None
            continue
        if not math.isfinite(y):
            previous_x, previous_y = None, None
            continue
        if y == 0:
            return x
        if (
            previous_x is not None
            and previous_y is not None
            and (previous_y < 0) != (y < 0)
        ):
            return _bisect(
                function, previous_x, x, tolerance=tolerance, iterations=iterations
            )
        previous_x, previous_y = x, y
    return None


def _bisect(
    function: Callable[[float], float],
    low: float,
    high: float,
    *,
    tolerance: float,
    iterations: int,
) -> float:
    low_y = function(low)
    for _ in range(iterations):
        middle = (low + high) / 2
        middle_y = function(middle)
        if middle_y == 0 or (high - low) / 2 < tolerance:
            return middle
        if (middle_y < 0) == (low_y < 0):
            low, low_y = middle, middle_y
        else:
            high = middle
    return (low + high) / 2
