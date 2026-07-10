"""Provider-independent benchmark repairs for interpret stage drafts.

Behavior-preserving relocation from stages/interpret.py and
interpret_internal/asset_resolution.py; resolver-backed benchmark repairs
(owner grounding, provider validation) stay with the stage."""

from __future__ import annotations

from typing import cast, get_args

from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _normalized_symbol,
    _strategy_field_provenance,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.domain.backtesting.config import (
    AssetClass as BacktestAssetClass,
)
from argus.domain.backtesting.config import (
    default_benchmark as default_backtest_benchmark,
)

_BACKTEST_ASSET_CLASSES = frozenset(get_args(BacktestAssetClass))


def strategy_with_separate_benchmark_symbol(
    strategy: StrategySummary,
    *,
    prior_strategy: StrategySummary | None = None,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = benchmark
    assets = [_normalized_symbol(symbol) for symbol in updated.asset_universe]
    normalized_assets = [symbol for symbol in assets if symbol is not None]
    filtered_assets = [
        symbol
        for symbol in normalized_assets
        if symbol != benchmark
    ]
    if len(filtered_assets) == len(normalized_assets):
        return updated, []
    if not filtered_assets and _traded_asset_is_user_owned(
        strategy,
        benchmark,
        prior_strategy=prior_strategy,
    ):
        # The turn's own edit or the active draft already owns this symbol as
        # the traded asset (a BTC hold benchmarked to BTC); emptying the
        # universe is no repair.
        updated.asset_universe = list(dict.fromkeys(normalized_assets))
        return updated, []
    updated.asset_universe = list(dict.fromkeys(filtered_assets))
    return updated, ["benchmark_symbol_removed_from_asset_universe"]


def _traded_asset_is_user_owned(
    strategy: StrategySummary,
    benchmark: str,
    *,
    prior_strategy: StrategySummary | None,
) -> bool:
    """Typed evidence the benchmark symbol is genuinely the traded asset: a
    planned-edit provenance, or continuity with the active draft that already
    trades it. Resolver provenance alone is not user evidence — the
    canonicalization pass appends it to any echoed candidate, so a vague
    benchmark-only turn must keep its strip-and-clarify."""

    if _strategy_field_provenance(strategy, "asset_universe") == "explicit_user":
        return True
    if prior_strategy is None:
        return False
    return any(
        _normalized_symbol(symbol) == benchmark
        for symbol in prior_strategy.asset_universe
    )


def default_benchmark_for_asset_class(
    asset_class: str,
    *,
    symbols: list[str],
) -> str | None:
    if asset_class not in _BACKTEST_ASSET_CLASSES:
        return None
    return default_backtest_benchmark(
        cast(BacktestAssetClass, asset_class),
        symbols,
    )


def strategy_with_default_benchmark(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    if _normalized_symbol(strategy.comparison_baseline):
        return strategy, []
    if not strategy.asset_class:
        return strategy, []
    benchmark = default_benchmark_for_asset_class(
        strategy.asset_class,
        symbols=strategy.asset_universe,
    )
    if benchmark is None:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = benchmark
    return updated, ["default_benchmark_applied"]


def strategy_with_unstated_benchmark_guard(
    *,
    strategy: StrategySummary,
    prior_strategy: StrategySummary | None,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(provenance, dict) and provenance.get("comparison_baseline") in {
        "explicit_user",
        "stated_run_field_fidelity_audit",
    }:
        return strategy, []
    prior_benchmark = (
        _normalized_symbol(prior_strategy.comparison_baseline)
        if prior_strategy is not None
        else None
    )
    if prior_benchmark == benchmark:
        return strategy, []
    if _strategy_uses_safe_default_benchmark(strategy, benchmark):
        return strategy, []
    updated = strategy.model_copy(deep=True)
    if prior_benchmark is not None:
        updated.comparison_baseline = prior_benchmark
        return updated, ["unstated_benchmark_symbol_reverted"]
    updated.comparison_baseline = None
    return updated, ["unstated_benchmark_symbol_cleared"]


def _strategy_uses_safe_default_benchmark(
    strategy: StrategySummary,
    benchmark: str,
) -> bool:
    if not strategy.asset_class or not strategy.asset_universe:
        return False
    default_benchmark_value = default_benchmark_for_asset_class(
        strategy.asset_class,
        symbols=strategy.asset_universe,
    )
    return default_benchmark_value == benchmark
