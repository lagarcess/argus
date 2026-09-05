"""Shared comparisons for route facts and delivered payloads."""

from __future__ import annotations

from datetime import date
from typing import Any


def _compare(name: str, expected: Any, actual: Any, failures: list[str]) -> None:
    if expected is None:
        return
    if actual != expected:
        failures.append(f"{name}: expected {expected!r}, got {actual!r}")


def _compare_subset(
    name: str,
    expected: Any,
    actual: Any,
    failures: list[str],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append(
                f"{name}: expected mapping subset {expected!r}, got {actual!r}"
            )
            return
        for key, expected_value in expected.items():
            _compare_subset(f"{name}.{key}", expected_value, actual.get(key), failures)
        return
    _compare(name, expected, actual, failures)


def _compare_date_range(
    name: str,
    expected: Any,
    actual: Any,
    failures: list[str],
) -> None:
    expected_window = _date_range_window(expected)
    actual_window = _date_range_window(actual)
    if expected_window is not None and actual_window is not None:
        if actual_window != expected_window:
            failures.append(f"{name}: expected {expected!r}, got {actual!r}")
        return
    _compare(name, expected, actual, failures)


def _date_range_window(value: Any) -> tuple[date, date] | None:
    if isinstance(value, dict):
        start = _date_boundary(value.get("start"))
        end = _date_boundary(value.get("end"))
        if start is None or end is None:
            return None
        return (start, end)
    if isinstance(value, str):
        parts = value.split("/")
        if len(parts) != 2:
            return None
        start = _date_boundary(parts[0])
        end = _date_boundary(parts[1])
        if start is None or end is None:
            return None
        return (start, end)
    return None


def _date_boundary(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
