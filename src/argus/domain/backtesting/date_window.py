from __future__ import annotations

from datetime import date


def validate_backtest_date_window(
    *,
    start: date,
    end: date,
    today: date | None = None,
) -> None:
    """Validate execution date windows with specific protocol failure codes."""

    if start >= end:
        raise ValueError("invalid_chronological_date_range")
    if end > (today or date.today()):
        raise ValueError("future_end_date")

