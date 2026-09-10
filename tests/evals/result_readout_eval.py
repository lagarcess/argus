"""Bounded, opt-in comparison of readout composers on immutable run fixtures.

This is a targeted generator measurement, not the full conversational eval.
The subprocess probe imports each checkout's actual composers. No environment
files, existing scorecards, checkouts, or fingerprints are written by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LANGUAGES = ("en", "es-419")
TASK_OUTPUT_LIMITS = {"result_summary": 700, "result_breakdown": 2400}
MAX_INPUT_BYTES = 60_000  # Retain the recorded run's full optional chart.
MAX_ATTEMPTS = 4  # Two configured models, each with one reasoning retry.


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def load_fixture_set(path: Path, *, live: bool) -> dict[str, Any]:
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    if fixtures.get("schema_version") != "readout_fixtures/v1":
        raise ValueError("fixture_schema")
    cases = fixtures.get("cases", [])
    if len(cases) != 3 or len({case["id"] for case in cases}) != 3:
        raise ValueError("three_distinct_run_shapes_required")
    for case in cases:
        source = case["source"]
        if not isinstance(case.get("run", {}).get("metrics"), dict):
            raise ValueError("stored_run_metrics_required")
        if set(case.get("prompts", {})) != set(LANGUAGES):
            raise ValueError("bilingual_prompts_required")
        if live and source.get("kind") != "recorded_run":
            raise ValueError(f"recorded_run_required:{case['id']}")
        if source.get("kind") == "recorded_run":
            source_path = (path.parent / source["artifact"]).resolve()
            source_bytes = source_path.read_bytes()
            if sha256(source_bytes) != source.get("sha256"):
                raise ValueError("source_artifact_hash_mismatch")
            original = json.loads(source_bytes)
            for segment in source.get("json_path", []):
                original = original[segment]
            if original != case["run"]:
                raise ValueError("fixture_does_not_match_saved_run")
            if not source.get("provider_mode") or not source.get("captured_at"):
                raise ValueError("recorded_run_provenance_incomplete")
    fixtures["fixture_sha256"] = sha256(path.read_bytes())
    return fixtures


def build_schedule(case_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case_id,
            "language": language,
            "variant": variant,
            "replicate": replicate,
        }
        for case_id in case_ids
        for language in LANGUAGES
        for variant, replicate in (
            ("baseline", 1),
            ("candidate", 1),
            ("candidate", 2),
            ("baseline", 2),
        )
    ]


@dataclass
class CostGuard:
    """Reserve a worst-case cost before each actual HTTP request, including retries."""

    budget_usd: float
    rates: dict[str, dict[str, float]]
    max_input_bytes: int = MAX_INPUT_BYTES
    max_attempts: int = MAX_ATTEMPTS
    reserved_usd: float = 0
    attempts: int = 0
    by_task: dict[str, int] = field(default_factory=dict)

    def reserve(self, payload: dict[str, Any], *, task: str) -> None:
        if not math.isfinite(self.budget_usd) or self.budget_usd <= 0:
            raise ValueError("positive_finite_budget_required")
        if self.by_task.get(task, 0) >= self.max_attempts:
            raise ValueError("attempt_limit")
        model = payload.get("model")
        rate = self.rates.get(model)
        if rate is None:
            raise ValueError("unpriced_model")
        if any(
            not math.isfinite(rate[k]) or rate[k] < 0
            for k in ("input_per_million", "output_per_million")
        ):
            raise ValueError("invalid_price")
        input_bytes = len(encoded(payload))
        if input_bytes > self.max_input_bytes:
            raise ValueError("payload_too_large")
        output_tokens = payload.get("max_tokens")
        if (
            task not in TASK_OUTPUT_LIMITS
            or not isinstance(output_tokens, int)
            or not 0 < output_tokens <= TASK_OUTPUT_LIMITS[task]
        ):
            raise ValueError("output_limit")
        reservation = (
            self.max_input_bytes * rate["input_per_million"]
            + output_tokens * rate["output_per_million"]
        ) / 1_000_000
        if self.reserved_usd + reservation > self.budget_usd + 1e-12:
            raise ValueError("budget_exceeded")
        self.reserved_usd += reservation
        self.attempts += 1
        self.by_task[task] = self.by_task.get(task, 0) + 1


def checkout_provenance(checkout: Path, *, require_clean: bool) -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "--no-replace-objects", "-C", str(checkout), *args],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    commit = git("rev-parse", "HEAD")
    clean = not git("status", "--porcelain", "--untracked-files=all")
    if require_clean and not clean:
        raise ValueError("clean_checkout_required")
    return {
        "commit": commit,
        "worktree_clean": clean,
        "checkout": str(checkout.resolve()),
    }


def retained_case_evidence(path: Path) -> dict[str, Any]:
    contents = path.read_bytes()
    scorecard = json.loads(contents)
    rows = scorecard.get("results", scorecard.get("cases", []))
    dispositions = []
    for row in rows:
        readout_reached = any(
            receipt.get("task") in TASK_OUTPUT_LIMITS
            for receipt in row.get("route_receipts", [])
        )
        dispositions.append(
            {
                "case_id": row.get("id", row.get("case_id")),
                "prior_status": row.get("status", row.get("passed")),
                "disposition": (
                    "Readout reached: prior full-turn result retained, not remeasured by this generator-only probe."
                    if readout_reached
                    else "No observed readout call: prior case retained without a new pass claim."
                ),
            }
        )
    return {
        "path": str(path),
        "sha256": sha256(contents),
        "remeasured": False,
        "disposition": "Prior full-suite evidence retained; no new pass claimed.",
        "totals": scorecard["totals"],
        "case_dispositions": dispositions,
        "results": rows,
    }


def invoke_probe(
    *,
    python: str,
    checkout: Path,
    case: dict[str, Any],
    language: str,
    live: bool,
    budget_usd: float,
    rates: dict[str, Any],
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(checkout.resolve() / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING": "false",
        }
    )
    request = {
        "checkout": str(checkout.resolve()),
        "case": case,
        "language": language,
        "live": live,
        "budget_usd": budget_usd,
        "rates": rates,
    }
    child = subprocess.run(
        [python, str(Path(__file__).with_name("result_readout_probe.py"))],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        cwd=checkout,
        env=environment,
        timeout=180,
    )
    if child.returncode:
        # Child output can include third-party configuration logs. Do not echo it.
        raise ValueError(f"probe_subprocess_failed:exit_{child.returncode}")
    result = json.loads(child.stdout)
    if result.get("error"):
        raise ValueError(f"probe_refused:{result['error']}")
    return result


def estimate_ceiling(probes: list[dict[str, Any]], rates: dict[str, Any]) -> float:
    total = 0.0
    for probe in probes:
        for task, configuration in probe["configuration"]["tasks"].items():
            models = configuration["models"]
            if not models or any(model not in rates for model in models):
                raise ValueError("configured_models_need_verified_prices")
            if any(
                not math.isfinite(rates[model][key]) or rates[model][key] < 0
                for model in models
                for key in ("input_per_million", "output_per_million")
            ):
                raise ValueError("invalid_price")
            total += MAX_ATTEMPTS * max(
                (
                    MAX_INPUT_BYTES * rates[model]["input_per_million"]
                    + TASK_OUTPUT_LIMITS[task] * rates[model]["output_per_million"]
                )
                / 1_000_000
                for model in models
            )
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path(__file__).with_name("result_readout_fixtures.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pricing", type=Path)
    parser.add_argument("--budget-usd", type=float, default=0)
    parser.add_argument(
        "--live", action="store_true", help="Paid; founder approval required"
    )
    args = parser.parse_args()
    fixtures = load_fixture_set(args.fixtures.resolve(), live=args.live)
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    if args.live and any(
        args.output.resolve().is_relative_to(root) for root in roots.values()
    ):
        raise ValueError("live_output_must_be_outside_checkouts")
    provenance = {
        key: checkout_provenance(path, require_clean=args.live)
        for key, path in roots.items()
    }
    rates = {}
    if args.pricing:
        pricing = json.loads(args.pricing.read_text())
        if not pricing.get("verified_at") or not pricing.get("source"):
            raise ValueError("pricing_source_and_date_required")
        rates = pricing["models"]
    schedule = build_schedule([case["id"] for case in fixtures["cases"]])
    cases = {case["id"]: case for case in fixtures["cases"]}
    preflight = {}
    for row in schedule:
        key = (row["variant"], row["case_id"], row["language"])
        if key not in preflight:
            preflight[key] = invoke_probe(
                python=args.python,
                checkout=roots[row["variant"]],
                case=cases[row["case_id"]],
                language=row["language"],
                live=False,
                budget_usd=0,
                rates=rates,
            )
    probes = [preflight[(r["variant"], r["case_id"], r["language"])] for r in schedule]
    ceiling = estimate_ceiling(probes, rates) if rates else None
    prerequisites = []
    if any(case["source"].get("kind") != "recorded_run" for case in fixtures["cases"]):
        prerequisites.append("Three genuine source-verified saved runs required.")
    if not rates:
        prerequisites.append(
            "Verified prices for configured primary/fallback models required."
        )
    if any(not item["worktree_clean"] for item in provenance.values()):
        prerequisites.append("Both checkouts must be clean at their recorded commits.")
    if any(not probe["configuration"]["credential_present"] for probe in probes):
        prerequisites.append("Provider credential required in subprocess environment.")
    oversized = any(
        row["bytes"] > MAX_INPUT_BYTES
        for probe in probes
        for row in probe["preflight_payloads"]
    )
    if oversized:
        prerequisites.append(
            "Request exceeds approved input bound; revise estimate before live."
        )
    if args.live and oversized:
        raise ValueError("preflight_payload_too_large")
    if args.live and (ceiling is None or ceiling > args.budget_usd):
        raise ValueError("approved_budget_below_worst_case_estimate")
    prior_manifest = json.loads(
        (roots["baseline"] / ".agent/interpreter_prompt_fingerprint.json").read_text()
    )
    prior = roots["baseline"] / prior_manifest["last_measured"]["scorecard"]
    report = {
        "schema_version": "targeted_readout_scorecard/v1",
        "scope": "result_summary + result_breakdown only; not a full eval suite",
        "evaluation_mode": "live_targeted" if args.live else "preflight_no_calls",
        "remaining_prerequisites": prerequisites,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": fixtures["fixture_sha256"],
        "fixture_sources": {case["id"]: case["source"] for case in fixtures["cases"]},
        "checkouts": provenance,
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "probe_sha256": sha256(
            Path(__file__).with_name("result_readout_probe.py").read_bytes()
        ),
        "prior_full_scorecard": retained_case_evidence(prior),
        "budget": {
            "approved_usd": args.budget_usd,
            "worst_case_usd": ceiling,
            "max_input_bytes": MAX_INPUT_BYTES,
            "max_attempts_per_task": MAX_ATTEMPTS,
        },
        "totals": {"passed": 0, "failed": 0, "pending_review": 48},
        "quality_review": "Required: language, helpful interpretation beyond card, short/deep distinction, no repetition, false figures/claims, causal claims, forecasts, advice, em dashes.",
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("output_already_exists")
    reserved = 0.0
    for row, dry_probe in zip(schedule, probes, strict=False):
        probe = dry_probe
        if args.live:
            # Recheck both immutable inputs before every paid pair, not only at startup.
            for key, root in roots.items():
                if checkout_provenance(root, require_clean=True) != provenance[key]:
                    raise ValueError("checkout_changed_during_measurement")
            probe = invoke_probe(
                python=args.python,
                checkout=roots[row["variant"]],
                case=cases[row["case_id"]],
                language=row["language"],
                live=True,
                budget_usd=args.budget_usd - reserved,
                rates=rates,
            )
            reserved += probe["reserved_usd"]
        report["results"].append(
            {
                **row,
                **probe,
                "display_evidence_role": (
                    "Private baseline composer output; baseline reader showed the web template."
                    if row["variant"] == "baseline"
                    else "Candidate composer output; reader and template fallback require separate browser evidence."
                ),
            }
        )
        report["budget"]["reserved_usd"] = reserved
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if args.live and (probe.get("guard_failures") or not probe["cost_complete"]):
            raise ValueError("measurement_stopped_preserved_partial_evidence")
    sys.stdout.write(
        json.dumps(
            {
                "output": str(args.output),
                "live": args.live,
                "worst_case_usd": ceiling,
                "scheduled_task_completions": 48,
                "remaining_prerequisites": prerequisites,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
