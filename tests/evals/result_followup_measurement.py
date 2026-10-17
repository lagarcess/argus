"""Opt-in #606 paired measurement. Default execution is entirely offline.

The baseline is the candidate archive with only the result-conversation module
restored from integration. Its manifest says so; it is not an integration run.
The shared spend ledger bounds all twelve turns and the native suite together.
No path writes the prompt fingerprint or treats authored answers as a quality pass.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("result_followup_measurement_fixtures.json")
PROBE = Path(__file__).with_name("result_followup_measurement_probe.py")
PROMPT_MODULE = "src/argus/agent_runtime/result_conversation.py"
LANGUAGES = ("en", "es-419")
BASELINE_SHA = "538aec3a9947caf8eb290a1f87551a2212496d44"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(
        ["git", "--no-replace-objects", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


def assert_exact_head(root: Path, expected: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("full_candidate_sha_required")
    if git("rev-parse", "HEAD", root=root) != expected:
        raise ValueError("candidate_head_changed")
    if git("status", "--porcelain", "--untracked-files=all", root=root):
        raise ValueError("clean_candidate_required")


def load_fixtures(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if document.get("schema_version") != "result_followup_measurement/v1":
        raise ValueError("fixture_schema")
    cases = document.get("cases", [])
    if {c["shape"] for c in cases} != {
        "dca_accumulation",
        "buy_and_hold",
        "moving_average_crossover",
    } or len(cases) != 3:
        raise ValueError("three_strategy_shapes_required")
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("unique_case_ids_required")
    for case in cases:
        run = case["run"]
        if (
            run["status"] != "completed"
            or case["source"]["kind"] != "authored_completed_result"
        ):
            raise ValueError("authored_completed_run_required")
        if set(case["prompts"]) != set(LANGUAGES):
            raise ValueError("bilingual_prompts_required")
        if case["research"] != (case["shape"] != "buy_and_hold"):
            raise ValueError("research_path_mismatch")
        if case["shape"] == "dca_accumulation":
            risk = run["metrics"]["aggregate"]["risk"]
            if not all(
                risk.get(f"max_drawdown_{edge}_date") for edge in ("peak", "trough")
            ):
                raise ValueError("dca_drop_dates_required")
    return {**document, "fixture_sha256": digest(path.read_bytes())}


def build_schedule(fixtures: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"case_id": case["id"], "language": language, "variant": variant}
        for case in fixtures["cases"]
        for language in LANGUAGES
        for variant in ("baseline", "candidate")
    ]


def compare_pair(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for answer in (baseline, candidate):
        if not answer.get("accepted_text"):
            failures.append("missing_accepted_text")
        if not answer.get("sidecars", {}).get("next_steps", {}).get("items"):
            failures.append("missing_next_steps")
        if "\u2014" in json.dumps(
            [answer.get("accepted_text"), answer.get("sidecars")], ensure_ascii=False
        ):
            failures.append("visible_em_dash")
    if baseline.get("release_configuration") != candidate.get("release_configuration"):
        failures.append("release_configuration_changed")
    return {
        "failed_checks": sorted(set(failures)),
        "semantic_review": "pending_manual_review",
        "manual_checks": [
            "no repeated suggestions between prose and controls",
            "figures and dates preserved",
            "correct language",
            "test payloads and question order",
            "baseline versus candidate",
        ],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--live", action="store_true")
    result.add_argument("--expected-head")
    result.add_argument("--baseline-sha", default=BASELINE_SHA)
    result.add_argument("--env-file", type=Path)
    result.add_argument("--rates", type=Path)
    result.add_argument("--fixtures", type=Path, default=FIXTURES)
    result.add_argument(
        "--output", type=Path, default=ROOT / "temp/issue-606-measurement"
    )
    return result


def validate_live_arguments(args: argparse.Namespace) -> None:
    if args.live and not all((args.expected_head, args.env_file, args.rates)):
        raise ValueError("live_inputs_required: --expected-head --env-file --rates")
    if args.live and args.baseline_sha != BASELINE_SHA:
        raise ValueError("approved_integration_baseline_required")
    if args.live and args.fixtures.resolve() != FIXTURES.resolve():
        raise ValueError("committed_measurement_fixtures_required")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def baseline_archive(
    directory: Path, candidate_sha: str, baseline_sha: str
) -> dict[str, Any]:
    """Extract candidate source, swapping just the baseline model-facing module."""
    raw = subprocess.run(
        ["git", "archive", candidate_sha],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        # A committed archive can contain symlinks; refuse external destinations.
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                continue
            destination = (directory / member.name).resolve()
            if directory.resolve() not in destination.parents:
                raise ValueError("unsafe_archive_path")
            archive.extract(member, directory)
    original = subprocess.run(
        ["git", "show", f"{baseline_sha}:{PROMPT_MODULE}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    candidate = (directory / PROMPT_MODULE).read_bytes()
    if original == candidate:
        raise ValueError("baseline_has_no_prompt_difference")
    (directory / PROMPT_MODULE).write_bytes(original)
    return {
        "kind": "candidate_archive_with_integration_prompt_module",
        "candidate_tree_sha": candidate_sha,
        "integration_prompt_sha": baseline_sha,
        "swapped_path": PROMPT_MODULE,
        "candidate_module_sha256": digest(candidate),
        "baseline_module_sha256": digest(original),
    }


def child(
    payload: dict[str, Any], *, source_root: Path, output: Path, deadline: float | None
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(source_root / "src"), str(ROOT)))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if not payload["live"]:
        env["PYTHON_DOTENV_DISABLED"] = "1"
        env["ARGUS_RUN_LIVE_EVALS"] = "0"
    timeout = max(0.1, deadline - time.time()) if deadline else 60
    with output.with_suffix(".log").open("w") as log:
        result = subprocess.run(
            [sys.executable, str(PROBE)],
            input=json.dumps(payload),
            text=True,
            cwd=source_root,
            env=env,
            stdout=log,
            stderr=log,
            timeout=timeout,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"probe_failed:{output.name}:see_local_log")
    return json.loads(output.read_text())


def run(args: argparse.Namespace) -> dict[str, Any]:
    validate_live_arguments(args)
    fixtures = load_fixtures(args.fixtures)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "evidence_kind": "live_model_on_authored_results"
        if args.live
        else "offline_request_shape_only",
        "fixture_sha256": fixtures["fixture_sha256"],
        "schedule": build_schedule(fixtures),
        "pairs": [],
        "semantic_review": "pending_manual_review" if args.live else "not_measured",
        "refreeze": "not_performed",
        "status": "incomplete",
    }
    if not args.live:
        previews = []
        for case in fixtures["cases"]:
            for language in LANGUAGES:
                path = args.output / f"dry-{case['id']}-{language}.json"
                previews.append(
                    child(
                        {
                            "live": False,
                            "case": case,
                            "language": language,
                            "output": str(path),
                        },
                        source_root=ROOT,
                        output=path,
                        deadline=None,
                    )
                )
        report.update(
            status="offline_validation_complete", previews=previews, provider_calls=0
        )
        report["native_budget_note"] = (
            "The full native suite reserves dynamically before every paid dispatch. "
            "A research model's full context or fallback ceiling can exceed the "
            "combined $12.50 cap; that stops the run without a full scorecard."
        )
        if args.rates:
            from tests.evals.measurement_spend_guard import request_reservation

            rates = json.loads(args.rates.read_text())
            report["request_reservations"] = [
                {
                    "case_id": preview["case_id"],
                    "language": preview["language"],
                    "provider": request["provider"],
                    "maximum_usd": request_reservation(
                        request["provider"], request["payload"], rates
                    ),
                }
                for preview in previews
                for request in preview["requests"]
            ]
        write_json(args.output / "report.json", report)
        return report

    assert_exact_head(ROOT, args.expected_head)
    # Keep imports that resolve Argus configuration in the env-loaded child.
    from tests.evals.measurement_eval_scorecard import assert_eval_env_file_untracked
    from tests.evals.measurement_spend_guard import initialize_budget, read_budget

    assert_eval_env_file_untracked(args.env_file.resolve())
    rates = json.loads(args.rates.read_text())
    ledger = args.output / "spend-ledger.json"
    common = {
        "live": True,
        "env_file": str(args.env_file.resolve()),
        "rates": rates,
        "ledger": str(ledger),
        "expected_head": args.expected_head,
        "repository_root": str(ROOT),
        "fixture_sha256": fixtures["fixture_sha256"],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="argus-606-baseline-") as temporary:
            baseline = Path(temporary)
            report["baseline"] = baseline_archive(
                baseline, args.expected_head, args.baseline_sha
            )
            budget = initialize_budget(ledger, rates)
            for case in fixtures["cases"]:
                for language in LANGUAGES:
                    pair = {}
                    for variant, source in (("baseline", baseline), ("candidate", ROOT)):
                        assert_exact_head(ROOT, args.expected_head)
                        path = args.output / f"{case['id']}-{language}-{variant}.json"
                        scope = f"{case['id']}:{language}:{variant}"
                        pair[variant] = child(
                            {
                                **common,
                                "case": case,
                                "language": language,
                                "scope": scope,
                                "variant": variant,
                                "baseline": report["baseline"],
                                "output": str(path),
                            },
                            source_root=source,
                            output=path,
                            deadline=budget["deadline_epoch"],
                        )
                        if read_budget(ledger)["stopped"]:
                            raise RuntimeError("spend_guard_stopped")
                    comparison = compare_pair(pair["baseline"], pair["candidate"])
                    report["pairs"].append(
                        {
                            "case_id": case["id"],
                            "language": language,
                            "outputs": pair,
                            **comparison,
                        }
                    )
                    write_json(args.output / "report.json", report)
                    if comparison["failed_checks"]:
                        raise RuntimeError("pair_failed")
            path = args.output / "native-suite.json"
            report["native_suite"] = child(
                {**common, "native": True, "scope": "native_suite", "output": str(path)},
                source_root=ROOT,
                output=path,
                deadline=budget["deadline_epoch"],
            )
            assert_exact_head(ROOT, args.expected_head)
            if read_budget(ledger)["stopped"] or report["native_suite"]["failed_checks"]:
                raise RuntimeError("native_suite_failed")
            report["status"] = "measurement_captured_manual_review_pending"
    except Exception as exc:
        report["stop_reason"] = str(exc)
        raise
    finally:
        if ledger.exists():
            report["budget"] = read_budget(ledger)
        write_json(args.output / "report.json", report)
    return report


if __name__ == "__main__":
    result = run(parser().parse_args())
    print(
        json.dumps(
            {
                "status": result["status"],
                "semantic_review": result["semantic_review"],
                "refreeze": result["refreeze"],
            }
        )
    )
