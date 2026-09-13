"""Bounded, opt-in Luna readout measurement on immutable run fixtures.

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
TASKS = ("result_summary", "result_breakdown")
MAX_INPUT_BYTES = 60_000  # Original default; larger measured ceilings are explicit.
MAX_ATTEMPTS = 1  # One provider HTTP request per frame, with retries blocked.


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def checked_input_limit(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("positive_integer_input_ceiling_required")
    return value


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
    """The same three saved runs, both languages, one paired composition each."""
    return [
        {"case_id": case_id, "language": language, "variant": "candidate", "replicate": 1}
        for case_id in case_ids
        for language in LANGUAGES
    ]


def _positive_integer(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("positive_integer_bound_required")
    return value


def _rate(value: Any) -> float:
    if (
        not isinstance(value, (float, int))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("invalid_price")
    return float(value)


def task_reservation(
    configuration: dict[str, Any], rates: dict[str, Any], input_limit: int
) -> float:
    """Conservative estimate, conditional on the provider honoring its limits.

    Agent retrieval can fill the model context repeatedly. Reserve a full
    context for each loop step plus a final generation, not just initial bytes.
    The raw invoice remains authoritative, including an unpriced first model.
    """
    provider = configuration["provider"]
    rate = rates.get(provider, {})
    if rate.get("model") != configuration["model"]:
        raise ValueError("unpriced_model")
    input_rate = _rate(rate.get("input_per_million"))
    output_rate = _rate(rate.get("output_per_million"))
    output = _positive_integer(configuration["max_output_tokens"])
    if provider == "openrouter":
        return (input_limit * input_rate + output * output_rate) / 1_000_000
    if provider != "perplexity_agent":
        raise ValueError("unexpected_provider")
    limits = configuration["request_limits"]
    steps = _positive_integer(limits.get("max_steps")) + 1
    calls = _positive_integer(limits.get("max_tool_calls"))
    context = _positive_integer(rate.get("context_window_tokens"))
    tools = {tool["type"]: tool for tool in limits["tools"]}
    if set(tools) != {"web_search", "fetch_url"}:
        raise ValueError("unexpected_agent_tools")
    for tool, fields in (
        ("web_search", ("max_tokens", "max_tokens_per_page", "max_results")),
        ("fetch_url", ("max_urls", "total_budget_tokens")),
    ):
        for name in fields:
            _positive_integer(tools[tool].get(name))
    tool_price = max(_rate(rate["tool_per_call"].get(tool)) for tool in tools)
    return (
        steps * (context * input_rate + output * output_rate) / 1_000_000
        + calls * tool_price
    )


@dataclass
class CostGuard:
    """Reserve before dispatch; never treat unknown billed usage as zero."""

    budget_usd: float
    rates: dict[str, Any]
    tasks: dict[str, dict[str, Any]]
    max_input_bytes: int = MAX_INPUT_BYTES
    reserved_usd: float = 0
    attempts: int = 0
    by_task: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        checked_input_limit(self.max_input_bytes)

    def reserve(self, payload: dict[str, Any], *, task: str) -> float:
        if task not in TASKS or task not in self.tasks:
            raise ValueError("unexpected_provider_task")
        if self.by_task.get(task, 0) >= MAX_ATTEMPTS:
            raise ValueError("attempt_limit")
        if not math.isfinite(self.budget_usd) or self.budget_usd <= 0:
            raise ValueError("positive_finite_budget_required")
        configuration = self.tasks[task]
        if len(encoded(payload)) > self.max_input_bytes:
            raise ValueError("payload_too_large")
        if configuration["provider"] == "openrouter":
            if payload.get("model") != configuration["model"]:
                raise ValueError("unexpected_primary_model")
            if payload.get("max_tokens") != configuration["max_output_tokens"]:
                raise ValueError("output_limit")
            if payload.get("tools") or payload.get("plugins"):
                raise ValueError("quick_take_search_forbidden")
        else:
            if payload.get("models") != [configuration["model"]]:
                raise ValueError("unexpected_primary_model")
            if any(
                payload.get(key) != value
                for key, value in configuration["request_limits"].items()
            ):
                raise ValueError("agent_request_limits_changed")
            if any(
                key in payload
                for key in ("preset", "background", "previous_response_id", "skills")
            ):
                raise ValueError("unexpected_agent_work")
        reservation = task_reservation(configuration, self.rates, self.max_input_bytes)
        if self.reserved_usd + reservation > self.budget_usd + 1e-12:
            raise ValueError("budget_exceeded")
        self.reserved_usd += reservation
        self.attempts += 1
        self.by_task[task] = self.by_task.get(task, 0) + 1
        return reservation


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


def measurement_can_continue(probe: dict[str, Any]) -> bool:
    """Unknown actual cost is allowed only when every attempt was fully reserved."""
    return (
        probe.get("all_attempts_reserved") is True
        and not probe.get("guard_failures")
        and not probe.get("stop_requested")
    )


def invoke_probe(
    *,
    python: str,
    checkout: Path,
    case: dict[str, Any],
    language: str,
    live: bool,
    budget_usd: float,
    rates: dict[str, Any],
    preflight: dict[str, Any] | None = None,
    max_input_bytes: int | None = None,
) -> dict[str, Any]:
    preflight_configuration = (preflight or {}).get("configuration", {})
    preflight_limit = preflight_configuration.get("max_input_bytes", MAX_INPUT_BYTES)
    input_limit = checked_input_limit(
        preflight_limit if max_input_bytes is None else max_input_bytes
    )
    if live and input_limit != preflight_limit:
        raise ValueError("input_ceiling_changed_after_preflight")
    timeout_seconds = 180.0
    visit_reservation = 0.0
    if live:
        if preflight is None:
            raise ValueError("live_probe_requires_preflight")
        visit_reservation = estimate_ceiling([preflight], rates)
        if visit_reservation > budget_usd:
            raise ValueError("budget_exceeded")
        # Include every configured attempt, then allow the production outer
        # deadline and receipt settlement to finish before this process stops.
        timeouts = [
            task["timeout_seconds"]
            for task in preflight["configuration"]["tasks"].values()
        ]
        if any(not math.isfinite(value) or value <= 0 for value in timeouts):
            raise ValueError("invalid_task_timeout")
        timeout_seconds = sum(timeouts) + 60

    def lost_receipts(reason: str) -> dict[str, Any]:
        if not live:
            raise ValueError(reason)
        # The visit was bounded before launch. If the isolated process cannot
        # deliver its ledger, retain that entire ceiling and stop without retry.
        return {
            "guard_failures": [reason],
            "stop_requested": True,
            "attempt_receipts_complete": False,
            "all_attempts_reserved": False,
            "reserved_usd": visit_reservation,
            "reservation_basis": "preflight maximum for this visit; attempt receipts unavailable",
            "observed_cost_usd": 0,
            "unknown_cost_attempts": None,
            "unknown_cost_reserved_usd": visit_reservation,
            "accounted_upper_bound_usd": visit_reservation,
            "http_attempts": None,
            "cost_complete": False,
        }

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
        "max_input_bytes": input_limit,
        "preflight_configuration": preflight_configuration,
    }
    try:
        child = subprocess.run(
            [python, str(Path(__file__).with_name("result_readout_probe.py"))],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            cwd=checkout,
            env=environment,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return lost_receipts("probe_subprocess_timeout")
    if child.returncode:
        # Child output can include third-party configuration logs. Do not echo it.
        return lost_receipts(f"probe_subprocess_failed:exit_{child.returncode}")
    try:
        result = json.loads(child.stdout)
    except ValueError:
        return lost_receipts("probe_subprocess_invalid_output")
    if result.get("error"):
        return lost_receipts("probe_refused")
    return result


def estimate_ceiling(probes: list[dict[str, Any]], rates: dict[str, Any]) -> float:
    return sum(
        task_reservation(
            task,
            rates,
            checked_input_limit(
                probe["configuration"].get("max_input_bytes", MAX_INPUT_BYTES)
            ),
        )
        for probe in probes
        for task in probe["configuration"]["tasks"].values()
    )


def estimate_payload_and_tools(
    probes: list[dict[str, Any]], rates: dict[str, Any]
) -> float:
    """Planning estimate only; remote internal context can exceed these inputs."""
    total = 0.0
    for probe in probes:
        for payload in probe["preflight_payloads"]:
            task = probe["configuration"]["tasks"][payload["task"]]
            rate = rates[task["provider"]]
            initial = payload["bytes_with_prior_quick_take_allowance"]
            output = task["max_output_tokens"]
            if task["provider"] == "openrouter":
                total += (
                    initial * rate["input_per_million"]
                    + output * rate["output_per_million"]
                ) / 1_000_000
                continue
            limits = task["request_limits"]
            steps = limits["max_steps"] + 1
            calls = limits["max_tool_calls"]
            tool_budget = max(
                tool["max_tokens"]
                if tool["type"] == "web_search"
                else tool["total_budget_tokens"]
                for tool in limits["tools"]
            )
            # Charge all allowed retrieved text and previous generated output
            # as input on every step, including a separate final generation.
            input_per_step = initial + calls * tool_budget + (steps - 1) * output
            total += steps * (
                input_per_step * rate["input_per_million"]
                + output * rate["output_per_million"]
            ) / 1_000_000 + calls * max(rate["tool_per_call"].values())
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--max-input-bytes", type=int, default=MAX_INPUT_BYTES)
    parser.add_argument(
        "--live", action="store_true", help="Paid; fresh founder approval required"
    )
    args = parser.parse_args()
    checked_input_limit(args.max_input_bytes)
    root = args.candidate.resolve()
    fixtures = load_fixture_set(args.fixtures.resolve(), live=args.live)
    provenance = checkout_provenance(root, require_clean=True)
    if args.output.resolve().is_relative_to(root):
        raise ValueError("output_must_be_outside_checkout")
    if args.output.exists():
        raise ValueError("output_already_exists")
    rates = {}
    pricing = None
    if args.pricing:
        pricing = json.loads(args.pricing.read_text())
        if not pricing.get("verified_at") or not pricing.get("source"):
            raise ValueError("pricing_source_and_date_required")
        rates = pricing["providers"]
    schedule = build_schedule([case["id"] for case in fixtures["cases"]])
    cases = {case["id"]: case for case in fixtures["cases"]}
    probes = [
        invoke_probe(
            python=args.python,
            checkout=root,
            case=cases[row["case_id"]],
            language=row["language"],
            live=False,
            budget_usd=0,
            rates=rates,
            max_input_bytes=args.max_input_bytes,
        )
        for row in schedule
    ]
    ceiling = estimate_ceiling(probes, rates) if rates else None
    prerequisites = []
    if any(case["source"].get("kind") != "recorded_run" for case in fixtures["cases"]):
        prerequisites.append("Three genuine source-verified saved runs required.")
    if not rates:
        prerequisites.append("Verified estimate-only prices for both providers required.")
    if any(not probe["configuration"]["credential_present"] for probe in probes):
        prerequisites.append(
            "Both provider credentials required in subprocess environment."
        )
    if any(
        row["bytes_with_prior_quick_take_allowance"] > args.max_input_bytes
        for probe in probes
        for row in probe["preflight_payloads"]
    ):
        prerequisites.append("Full request plus prior Quick take exceeds input ceiling.")
    if args.live and (prerequisites or ceiling is None or ceiling > args.budget_usd):
        raise ValueError("live_prerequisites_or_approved_budget_unsatisfied")
    report = {
        "schema_version": "targeted_readout_scorecard/v1",
        "scope": "Luna Quick take via OpenRouter and Breakdown via Perplexity Agent; generator-only proof",
        "comparison_mode": "luna",
        "replicates_per_variant": 1,
        "scheduled_task_completions": len(schedule) * len(TASKS),
        "fingerprint_authority": {
            "eligible": False,
            "reason": "No full live eval or fingerprint update authorized.",
        },
        "evaluation_mode": "live_targeted" if args.live else "preflight_no_calls",
        "remaining_prerequisites": prerequisites,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": fixtures["fixture_sha256"],
        "fixture_sources": {case["id"]: case["source"] for case in fixtures["cases"]},
        "checkouts": {"candidate": provenance},
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "probe_sha256": sha256(
            Path(__file__).with_name("result_readout_probe.py").read_bytes()
        ),
        "pricing": pricing,
        "budget": {
            "approved_usd": args.budget_usd,
            "worst_case_usd": ceiling,
            "payload_and_tools_estimate_usd": estimate_payload_and_tools(probes, rates)
            if rates
            else None,
            "max_input_bytes": args.max_input_bytes,
            "max_attempts_per_task": MAX_ATTEMPTS,
            "estimate_assumptions": "Agent envelope reserves a full model context per max_steps plus one final generation, output cap each, and max_tool_calls at the highest enabled tool rate. Conditional on provider enforcement; not billed-rate evidence. Unknown invoices retain the reservation; an invoice exceeding it stops later requests.",
            "payload_and_tools_assumptions": "Planning estimate uses measured full request bytes as input tokens, including prior Quick take headroom, plus every allowed tool result and prior output on each Agent step and final generation. Uses the same conservative price envelope. Provider internal context is unknown, so this estimate is not a spending cap.",
        },
        "totals": {
            "passed": 0,
            "failed": 0,
            "pending_review": len(schedule) * len(TASKS),
        },
        "quality_review": "Review every outcome for language, supported historical story, source citations/dates, numeric and relationship truth, complementary frames, no forecast/advice/em dashes.",
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    reserved = 0.0
    for row, dry_probe in zip(schedule, probes, strict=False):
        probe = dry_probe
        if args.live:
            if checkout_provenance(root, require_clean=True) != provenance:
                raise ValueError("checkout_changed_during_measurement")
            probe = invoke_probe(
                python=args.python,
                checkout=root,
                case=cases[row["case_id"]],
                language=row["language"],
                live=True,
                budget_usd=args.budget_usd - reserved,
                rates=rates,
                preflight=dry_probe,
            )
            reserved += probe["reserved_usd"]
        report["results"].append(
            {
                **row,
                **probe,
                "display_evidence_role": "Actual composer outcome; browser rendering is separate provider-free proof. Raw rejected drafts are diagnostics, not accepted text.",
            }
        )
        report["budget"]["reserved_usd"] = reserved
        for key in (
            "observed_cost_usd",
            "unknown_cost_reserved_usd",
            "accounted_upper_bound_usd",
        ):
            report["budget"][key] = sum(item[key] for item in report["results"])
        counts = [item["unknown_cost_attempts"] for item in report["results"]]
        report["budget"]["unknown_cost_attempts"] = (
            None if None in counts else sum(counts)
        )
        report["budget"]["cost_complete"] = all(
            item["cost_complete"] for item in report["results"]
        )
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if args.live and not measurement_can_continue(probe):
            raise ValueError("measurement_stopped_preserved_partial_evidence")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "live": args.live,
                "worst_case_usd": ceiling,
                "scheduled_task_completions": len(schedule) * len(TASKS),
                "remaining_prerequisites": prerequisites,
            }
        )
    )


if __name__ == "__main__":
    main()
