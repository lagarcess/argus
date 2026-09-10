"""Shared benchmark provider validation, reconciliation, and defaults."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast, get_args

from argus.agent_runtime.interpreter import provider_context_assets
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.run_field_contract import (
    _contains_ordered_token_span,
    field_fidelity_tokens,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _normalized_symbol,
    _strategy_field_provenance,
)
from argus.agent_runtime.state.models import (
    ResolutionProvenance,
    StrategySummary,
    dedupe_resolution_provenance_items,
)
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
    filtered_assets = [symbol for symbol in normalized_assets if symbol != benchmark]
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


# Statuses whose comparison_baseline provenance the confirmation card
# renders as a reconciliation disclosure.
BENCHMARK_DISCLOSURE_STATUSES = frozenset(
    {"unsupported", "ambiguous", "unavailable_for_requested_run"}
)


def provenance_without_benchmark_disclosures(
    provenance: list["ResolutionProvenance"],
) -> list["ResolutionProvenance"]:
    return [
        item
        for item in provenance
        if not (
            item.field == "comparison_baseline"
            and item.resolution_status in BENCHMARK_DISCLOSURE_STATUSES
        )
    ]


@dataclass(frozen=True)
class BenchmarkResolution:
    """One provider outcome bound to its requested reference and class hint.

    An explicit failed outcome is reusable too. This is a private preparation
    value, never model-authored arguments or persisted provider evidence.
    """

    query: str | None
    asset_class_hint: str | None
    outcome: AssetResolution | None


def resolve_benchmark_symbol(
    strategy: StrategySummary,
    *,
    resolve_candidate: Callable[..., AssetResolution],
    previous: BenchmarkResolution | None = None,
) -> BenchmarkResolution:
    query = _normalized_symbol(strategy.comparison_baseline)
    if previous is not None and (
        previous.query == query and previous.asset_class_hint == strategy.asset_class
    ):
        return previous
    outcome = None
    if query is not None:
        try:
            outcome = provider_context_assets.resolution_from_strategy_context(
                strategy, query, field="comparison_baseline"
            ) or resolve_candidate(
                query,
                field="comparison_baseline",
                source="llm_extraction",
                asset_class_hint=strategy.asset_class,
            )
        except ValueError:
            pass
    return BenchmarkResolution(query, strategy.asset_class, outcome)


def strategy_with_validated_benchmark_symbol(
    strategy: StrategySummary,
    *,
    resolution: BenchmarkResolution,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    scrub_reason_codes: list[str] = []
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if (
        isinstance(field_provenance, dict)
        and field_provenance.get("comparison_baseline") == "explicit_user"
    ):
        # A benchmark the user names this turn retires any earlier
        # reconciliation disclosure; a fresh clearing re-adds its own.
        scrubbed = provenance_without_benchmark_disclosures(
            strategy.resolution_provenance
        )
        if len(scrubbed) != len(strategy.resolution_provenance):
            strategy = strategy.model_copy(deep=True)
            strategy.resolution_provenance = scrubbed
            scrub_reason_codes = ["stale_benchmark_disclosure_retired"]
    outcome = resolution.outcome
    if outcome is not None and outcome.status == "resolved" and outcome.asset is not None:
        benchmark_asset_class = outcome.asset.asset_class
        if strategy.asset_class and benchmark_asset_class != strategy.asset_class:
            updated = strategy.model_copy(deep=True)
            updated.comparison_baseline = None
            return updated, [*scrub_reason_codes, "invalid_benchmark_symbol_cleared"]
        canonical = outcome.asset.canonical_symbol.strip().upper()
        if canonical == benchmark:
            return strategy, scrub_reason_codes
        updated = strategy.model_copy(deep=True)
        updated.comparison_baseline = canonical
        # The stated name rides along so a later coverage clearing can
        # disclose the user's words rather than the canonical symbol.
        updated.resolution_provenance = dedupe_resolution_provenance_items(
            [*updated.resolution_provenance, outcome.provenance]
        )
        return updated, [*scrub_reason_codes, "benchmark_symbol_provider_validated"]
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = None
    if outcome is not None and outcome.status in {"unsupported", "ambiguous"}:
        # The user named this leg and no clarification will run for it; keep
        # its provenance so the card discloses exactly this reconciliation.
        updated.resolution_provenance = dedupe_resolution_provenance_items(
            [
                *provenance_without_benchmark_disclosures(updated.resolution_provenance),
                outcome.provenance,
            ]
        )
    return updated, [*scrub_reason_codes, "invalid_benchmark_symbol_cleared"]


def benchmark_repair_disposition(
    *,
    before: StrategySummary,
    after: StrategySummary,
    resolutions: tuple[BenchmarkResolution, BenchmarkResolution],
    source: str,
) -> Literal["provider_equivalent", "disclosed_reconciliation"] | None:
    """A provider identity can agree; a bounded refusal can be disclosed.

    Fallback equality never establishes asset equivalence. A reconciliation
    retains both reads' source binding, the actual provider refusal, and the
    supplied effective benchmark. Other requested facts keep their own guards.
    """
    old_resolution, new_resolution = resolutions
    old_outcome, new_outcome = old_resolution.outcome, new_resolution.outcome
    if old_outcome is None or old_outcome.status != "resolved" or new_outcome is None:
        return None
    old_strategy, _ = strategy_with_validated_benchmark_symbol(
        before, resolution=old_resolution
    )
    new_strategy, _ = strategy_with_validated_benchmark_symbol(
        after, resolution=new_resolution
    )
    if old_strategy.comparison_baseline is None:
        return None
    if new_outcome.status == "resolved":
        return (
            "provider_equivalent"
            if _normalized_symbol(new_strategy.comparison_baseline)
            == _normalized_symbol(old_strategy.comparison_baseline)
            and old_outcome.asset is not None
            and new_outcome.asset is not None
            and new_outcome.asset.asset_class == old_outcome.asset.asset_class
            else None
        )
    if (
        new_outcome.status not in {"unsupported", "ambiguous"}
        or new_outcome.provenance not in new_strategy.resolution_provenance
        or not _benchmark_reference_is_source_bound(
            before=before, after=after, source=source
        )
    ):
        return None
    reconciled, _ = strategy_with_default_benchmark(new_strategy)
    return (
        "disclosed_reconciliation"
        if _normalized_symbol(reconciled.comparison_baseline)
        == _normalized_symbol(old_strategy.comparison_baseline)
        else None
    )


def _benchmark_reference_is_source_bound(
    *,
    before: StrategySummary,
    after: StrategySummary,
    source: str,
) -> bool:
    reference_tokens = field_fidelity_tokens(
        str(after.comparison_baseline or "").strip().casefold()
    )
    if not reference_tokens:
        return False
    for strategy in (before, after):
        evidence = strategy.extra_parameters.get("evidence_spans")
        span = evidence.get("comparison_baseline") if isinstance(evidence, dict) else None
        if not isinstance(span, str) or not span.strip() or span.strip() not in source:
            return False
        if not _contains_ordered_token_span(
            field_fidelity_tokens(span.casefold()), reference_tokens
        ):
            return False
    return True
