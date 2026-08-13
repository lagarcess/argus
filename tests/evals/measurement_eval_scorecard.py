from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

FIXTURE_DIR = Path(__file__).with_name("measurement_cases")
SCORECARD_DIR = Path("temp/argus_eval_scorecards")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_LIVE_PROBE_SYMBOL = "SPY"
_LIVE_PROBE_REQUESTED_DATE_RANGE = {
    "start": "2024-01-01",
    "end": "2024-01-10",
}
_LIVE_PROBE_EFFECTIVE_DATE_RANGE = {
    "start": "2024-01-02",
    "end": "2024-01-10",
}
_FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LiveMarketDataProbe:
    symbol: str
    requested_date_range: dict[str, str]
    effective_date_range: dict[str, str]
    adjustment_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "requested_date_range": dict(self.requested_date_range),
            "effective_date_range": dict(self.effective_date_range),
            "adjustment_reason": self.adjustment_reason,
        }


@dataclass(frozen=True)
class EvalScorecardProvenance:
    evaluation_mode: str
    market_data_provider_mode: str
    asset_provider_mode: str
    candidate_sha: str
    python_version: str
    fixture_sha256: str
    worktree_clean: bool
    live_market_data_probe: LiveMarketDataProbe | None = None


def measurement_fixture_paths(path: Path = FIXTURE_DIR) -> tuple[Path, ...]:
    fixture_paths = tuple(sorted(path.glob("*.yaml")))
    if not fixture_paths:
        raise ValueError("scorecard_provenance:fixture_set_empty")
    return fixture_paths


def measurement_fixture_sha256(path: Path = FIXTURE_DIR) -> str:
    digest = hashlib.sha256()
    for fixture_path in measurement_fixture_paths(path):
        relative_name = fixture_path.relative_to(path).as_posix().encode("utf-8")
        contents = fixture_path.read_bytes()
        digest.update(len(relative_name).to_bytes(8, "big"))
        digest.update(relative_name)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def build_scorecard_provenance(
    *,
    evaluation_mode: str,
    fixture_dir: Path = FIXTURE_DIR,
    repository_root: Path = REPOSITORY_ROOT,
) -> EvalScorecardProvenance:
    if evaluation_mode not in {"live", "mocked"}:
        raise ValueError("scorecard_provenance:evaluation_mode")
    market_data_provider_mode = _resolved_provider_mode(
        "ARGUS_MARKET_DATA_PROVIDER_MODE"
    )
    asset_provider_mode = _resolved_provider_mode("ARGUS_ASSET_PROVIDER_MODE")
    candidate_sha = _candidate_sha(repository_root)
    python_version = platform.python_version()
    fixture_sha256 = measurement_fixture_sha256(fixture_dir)
    worktree_clean = _worktree_is_clean(repository_root)
    if not worktree_clean:
        raise ValueError("scorecard_provenance:worktree_clean")
    live_probe = None
    if evaluation_mode == "live":
        if os.getenv("ARGUS_RUN_LIVE_EVALS") != "1":
            raise RuntimeError("live_eval_requires_ARGUS_RUN_LIVE_EVALS")
        live_probe = verify_live_market_data_environment()
    provenance = EvalScorecardProvenance(
        evaluation_mode=evaluation_mode,
        market_data_provider_mode=market_data_provider_mode,
        asset_provider_mode=asset_provider_mode,
        candidate_sha=candidate_sha,
        python_version=python_version,
        fixture_sha256=fixture_sha256,
        worktree_clean=worktree_clean,
        live_market_data_probe=live_probe,
    )
    validated_provenance_payload(provenance)
    return provenance


def verify_live_market_data_environment(
    *,
    prepare_market_data_func: Callable[[dict[str, Any]], Any] | None = None,
) -> LiveMarketDataProbe:
    provider_mode = _resolved_provider_mode("ARGUS_MARKET_DATA_PROVIDER_MODE")
    if provider_mode != "live_provider":
        raise RuntimeError(
            "live_eval_requires_explicit_live_provider:"
            f"ARGUS_MARKET_DATA_PROVIDER_MODE={provider_mode}"
        )
    if prepare_market_data_func is None:
        from argus.domain.backtesting.coverage import prepare_market_data

        prepare_market_data_func = prepare_market_data

    config = {
        "asset_class": "equity",
        "symbols": [_LIVE_PROBE_SYMBOL],
        "timeframe": "1D",
        "start_date": _LIVE_PROBE_REQUESTED_DATE_RANGE["start"],
        "end_date": _LIVE_PROBE_REQUESTED_DATE_RANGE["end"],
        "requested_date_range": dict(_LIVE_PROBE_REQUESTED_DATE_RANGE),
        "benchmark_symbol": _LIVE_PROBE_SYMBOL,
    }
    try:
        prepared = prepare_market_data_func(config)
        effective_date_range = prepared.effective_date_range.model_dump()
        adjustment_reason = prepared.adjustment_reason
    except Exception as exc:
        raise RuntimeError("live_eval_market_data_probe_failed:provider_error") from exc

    probe = LiveMarketDataProbe(
        symbol=_LIVE_PROBE_SYMBOL,
        requested_date_range=dict(_LIVE_PROBE_REQUESTED_DATE_RANGE),
        effective_date_range={
            "start": str(effective_date_range.get("start") or ""),
            "end": str(effective_date_range.get("end") or ""),
        },
        adjustment_reason=(
            str(adjustment_reason) if adjustment_reason is not None else None
        ),
    )
    if (
        probe.effective_date_range != _LIVE_PROBE_EFFECTIVE_DATE_RANGE
        or probe.adjustment_reason != "calendar_alignment"
    ):
        raise RuntimeError(
            "live_eval_market_data_probe_failed:"
            "expected_2024-01-02_calendar_alignment"
        )
    return probe


def scorecard_for_results(
    results: list[dict[str, Any]],
    *,
    provenance: EvalScorecardProvenance,
) -> dict[str, Any]:
    by_category: dict[str, dict[str, int | float]] = {}
    for result in results:
        category = str(result["category"])
        bucket = by_category.setdefault(
            category,
            {
                "passed": 0,
                "failed": 0,
                "expected_failed": 0,
                "unexpected_pass": 0,
                "skipped": 0,
                "pass_rate": 0.0,
            },
        )
        status = str(result["status"])
        if status not in bucket:
            status = "failed"
        bucket[status] = int(bucket[status]) + 1

    for bucket in by_category.values():
        denominator = sum(
            int(bucket[status])
            for status in ("passed", "failed", "expected_failed", "unexpected_pass")
        )
        bucket["pass_rate"] = (
            0.0 if denominator == 0 else round(int(bucket["passed"]) / denominator, 4)
        )

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": validated_provenance_payload(provenance),
        "provider_usage": _provider_usage(results),
        "category_pass_rates": by_category,
        "totals": {
            status: sum(int(item[status]) for item in by_category.values())
            for status in (
                "passed",
                "failed",
                "expected_failed",
                "unexpected_pass",
                "skipped",
            )
        },
        "results": results,
    }


def write_scorecard(
    results: list[dict[str, Any]],
    *,
    provenance: EvalScorecardProvenance,
    output_dir: Path = SCORECARD_DIR,
) -> Path:
    assert_provenance_matches_current_run(provenance)
    scorecard = scorecard_for_results(results, provenance=provenance)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"argus-eval-scorecard-{stamp}.json"
    path.write_text(json.dumps(scorecard, indent=2, sort_keys=True), encoding="utf-8")
    return path


def validated_provenance_payload(
    provenance: EvalScorecardProvenance,
) -> dict[str, Any]:
    if provenance.evaluation_mode not in {"live", "mocked"}:
        raise ValueError("scorecard_provenance:evaluation_mode")
    for field_name in (
        "market_data_provider_mode",
        "asset_provider_mode",
        "python_version",
    ):
        if not str(getattr(provenance, field_name) or "").strip():
            raise ValueError(f"scorecard_provenance:{field_name}")
    if not _FULL_SHA_PATTERN.fullmatch(provenance.candidate_sha):
        raise ValueError("scorecard_provenance:candidate_sha")
    if not _SHA256_PATTERN.fullmatch(provenance.fixture_sha256):
        raise ValueError("scorecard_provenance:fixture_sha256")
    if provenance.worktree_clean is not True:
        raise ValueError("scorecard_provenance:worktree_clean")

    live_probe_payload = None
    if provenance.live_market_data_probe is not None:
        live_probe_payload = provenance.live_market_data_probe.as_dict()
    if provenance.evaluation_mode == "live":
        if provenance.market_data_provider_mode != "live_provider":
            raise ValueError(
                "scorecard_provenance:live_market_data_provider_mode"
            )
        if (
            live_probe_payload is None
            or live_probe_payload["symbol"] != _LIVE_PROBE_SYMBOL
            or live_probe_payload["requested_date_range"]
            != _LIVE_PROBE_REQUESTED_DATE_RANGE
            or live_probe_payload["effective_date_range"]
            != _LIVE_PROBE_EFFECTIVE_DATE_RANGE
            or live_probe_payload["adjustment_reason"] != "calendar_alignment"
        ):
            raise ValueError("scorecard_provenance:live_market_data_probe")

    return {
        "evaluation_mode": provenance.evaluation_mode,
        "market_data_provider_mode": provenance.market_data_provider_mode,
        "asset_provider_mode": provenance.asset_provider_mode,
        "candidate_sha": provenance.candidate_sha,
        "python_version": provenance.python_version,
        "fixture_sha256": provenance.fixture_sha256,
        "worktree_clean": provenance.worktree_clean,
        "live_market_data_probe": live_probe_payload,
    }


def assert_provenance_matches_current_run(
    provenance: EvalScorecardProvenance,
) -> None:
    validated_provenance_payload(provenance)
    expected_values = {
        "market_data_provider_mode": _resolved_provider_mode(
            "ARGUS_MARKET_DATA_PROVIDER_MODE"
        ),
        "asset_provider_mode": _resolved_provider_mode("ARGUS_ASSET_PROVIDER_MODE"),
        "candidate_sha": _candidate_sha(REPOSITORY_ROOT),
        "python_version": platform.python_version(),
        "fixture_sha256": measurement_fixture_sha256(FIXTURE_DIR),
        "worktree_clean": _worktree_is_clean(REPOSITORY_ROOT),
    }
    for field_name, expected in expected_values.items():
        if getattr(provenance, field_name) != expected:
            raise ValueError(f"scorecard_provenance:{field_name}_mismatch")


def _resolved_provider_mode(env_name: str) -> str:
    mode = (os.getenv(env_name) or "").strip().lower()
    if not mode:
        raise RuntimeError(f"scorecard_provenance:{env_name.lower()}_missing")
    return mode


def _candidate_sha(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("scorecard_provenance:candidate_sha_unavailable") from exc
    candidate_sha = completed.stdout.strip().lower()
    if not _FULL_SHA_PATTERN.fullmatch(candidate_sha):
        raise RuntimeError("scorecard_provenance:candidate_sha_unavailable")
    return candidate_sha


def _worktree_is_clean(repository_root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("scorecard_provenance:worktree_status_unavailable") from exc
    return not completed.stdout.strip()


def _provider_usage(results: list[dict[str, Any]]) -> dict[str, Any]:
    route_receipts: list[Any] = []
    for result in results:
        receipts = result.get("route_receipts")
        if isinstance(receipts, list):
            route_receipts.extend(receipts)
    reported_costs: list[Decimal] = []
    unreported_cost_receipt_count = 0
    for receipt in route_receipts:
        raw_cost = receipt.get("usage_cost_usd") if isinstance(receipt, dict) else None
        if raw_cost is None:
            unreported_cost_receipt_count += 1
            continue
        try:
            reported_costs.append(Decimal(str(raw_cost)))
        except (InvalidOperation, ValueError):
            unreported_cost_receipt_count += 1
    return {
        "route_receipt_count": len(route_receipts),
        "reported_cost_receipt_count": len(reported_costs),
        "unreported_cost_receipt_count": unreported_cost_receipt_count,
        "reported_cost_usd": float(sum(reported_costs, Decimal("0"))),
    }
