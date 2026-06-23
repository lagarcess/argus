from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

AssetUniverseOperation = Literal["replace", "append", "add"]


def apply_asset_universe_edit(
    base_symbols: list[str],
    patch_symbols: list[str],
    operation: AssetUniverseOperation | None,
) -> list[str]:
    normalized_patch = _symbols(patch_symbols)
    if normalized_asset_universe_operation(operation) == "append":
        return _dedupe([*base_symbols, *normalized_patch])
    return normalized_patch


def normalized_asset_symbols(values: Any) -> list[str]:
    if not isinstance(values, list | tuple | set):
        return []
    return _symbols(values)


def same_asset_universe(left: Any, right: Any) -> bool:
    left_symbols = normalized_asset_symbols(left)
    right_symbols = normalized_asset_symbols(right)
    return bool(left_symbols or right_symbols) and set(left_symbols) == set(
        right_symbols
    )


def normalized_asset_universe_operation(
    operation: Any,
) -> Literal["replace", "append"] | None:
    normalized = str(operation or "").strip().casefold()
    if normalized in {"append", "add"}:
        return "append"
    if normalized == "replace":
        return "replace"
    return None


def _symbols(values: Iterable[Any]) -> list[str]:
    return _dedupe(
        symbol
        for value in values
        if (symbol := _symbol(value)) is not None
    )


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace("-", "/")
    return symbol or None
