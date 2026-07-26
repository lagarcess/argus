from __future__ import annotations

from collections.abc import Callable
from typing import Any


def fetch_all_rows(
    query_factory: Callable[[int, int], Any],
    *,
    batch_size: int = 500,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        response = query_factory(start, start + batch_size - 1).execute()
        data = response.data or []
        rows.extend(data)
        if len(data) < batch_size:
            break
        start += batch_size
    return rows
