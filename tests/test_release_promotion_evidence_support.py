"""Focused tests for production-promotion baseline comparison."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.release_promotion_evidence_support import (
    assert_main_promotion_baseline_comparison,
)

ROOT = Path(__file__).resolve().parents[1]


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repository_root: Path, message: str) -> str:
    _git(repository_root, "add", ".")
    _git(repository_root, "commit", "-m", message)
    return _git(repository_root, "rev-parse", "HEAD")


def _comparison_repository(repository_root: Path) -> tuple[str, str]:
    _git(repository_root, "init")
    _git(repository_root, "config", "user.email", "release-test@example.com")
    _git(repository_root, "config", "user.name", "Release Test")

    for package in ("tests", "tests/evals", "argus"):
        package_path = repository_root / package
        package_path.mkdir(parents=True, exist_ok=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")
    (repository_root / "tests/evals/measurement_eval_harness.py").write_text(
        "import argus.measured\n",
        encoding="utf-8",
    )
    measured_path = repository_root / "argus/measured.py"
    measured_path.write_text("VALUE = 'baseline'\n", encoding="utf-8")
    baseline_sha = _commit(repository_root, "baseline")

    measured_path.write_text("VALUE = 'candidate'\n", encoding="utf-8")
    candidate_sha = _commit(repository_root, "candidate")
    return baseline_sha, candidate_sha


def test_documented_candidate_only_failure_is_not_blocked_by_total_count(
    tmp_path: Path,
) -> None:
    baseline_sha, candidate_sha = _comparison_repository(tmp_path)
    baseline_relative_path = (
        f"docs/reports/evidence/promotion/baseline-{baseline_sha[:8]}.json"
    )
    baseline_path = tmp_path / baseline_relative_path
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_text(
        json.dumps(
            {
                "results": [
                    {"id": "shared-failure", "status": "failed"},
                    {"id": "candidate-only", "status": "passed"},
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "2026-08-21-main-production-promotion.md"
    manifest = (
        f"- Candidate SHA: `{candidate_sha}`\n"
        f"- Rollback target: `{baseline_sha}`\n"
        f"- Baseline eval scorecard: `{baseline_relative_path}`\n"
        "- `candidate-only`: model variance confirmed by an interleaved A/B.\n"
    )

    assert_main_promotion_baseline_comparison(
        manifest,
        manifest_path,
        candidate_results=[
            {"id": "shared-failure", "status": "failed"},
            {"id": "candidate-only", "status": "failed"},
        ],
        repository_root=tmp_path,
    )


def test_runbook_makes_founder_browser_acceptance_the_stronger_gate() -> None:
    runbook = " ".join(
        (ROOT / "docs/PRIVATE_LAUNCH_RUNBOOK.md").read_text(encoding="utf-8").split()
    )

    assert "This eval gate is weak evidence" in runbook
    assert "Founder-overseen production browser acceptance is the stronger gate" in (
        runbook
    )
    assert "post-deploy checklist decides whether the promotion succeeded" in runbook
