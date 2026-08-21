"""Comparison of a promotion candidate against the deployed build.

A promotion asks whether the candidate is worse than what users have now.
Lives here rather than in the release-docs test so that test stays about
documents.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_PRODUCT_PATHS = ("src/", "web/app", "web/components", "web/lib", "web/public",
                  "render.yaml", "supabase/")


def _same_product_tree(left: str, right: str, *, repository_root: Path) -> bool:
    """True when two commits ship identical product code."""

    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--quiet", left, right, "--", *_PRODUCT_PATHS],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def measured_source_files(repository_root: Path) -> frozenset[str]:
    """Every repo file the live eval can reach, derived from its own imports.

    Enumerating this by hand would be a guess that goes stale the moment an
    import changes. Importing the harness and reading what loaded is the same
    question the eval answers when it runs.
    """

    script = (
        "import sys, pathlib, json;"
        "root = pathlib.Path('.').resolve();"
        "sys.path.insert(0, str(root));"
        "import tests.evals.measurement_eval_harness;"
        "out = set();"
        "[out.add(pathlib.Path(m.__file__).resolve().relative_to(root).as_posix())"
        " for n, m in list(sys.modules.items())"
        " if n.startswith('argus') and getattr(m, '__file__', None)"
        " and str(pathlib.Path(m.__file__).resolve()).startswith(str(root))];"
        "print(json.dumps(sorted(out)))"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=repository_root,
        capture_output=True,
        check=True,
        text=True,
    )
    return frozenset(json.loads(result.stdout.strip().splitlines()[-1]))


def eval_measured_code_unchanged(
    left: str, right: str, *, repository_root: Path
) -> tuple[bool, list[str]]:
    """True when no file the eval can reach differs between two commits.

    A change that cannot reach the measured code cannot regress it, which is a
    stronger statement than a scorecard whose noise floor is several cases.
    """

    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--name-only", left, right],
        cwd=repository_root,
        capture_output=True,
        check=True,
        text=True,
    )
    changed = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    touched = sorted(changed & measured_source_files(repository_root))
    return (not touched), touched


def assert_main_promotion_baseline_comparison(
    manifest: str,
    manifest_path: Path,
    *,
    candidate_results: list[dict[str, object]],
    repository_root: Path,
) -> None:
    baseline_match = re.search(
        r"^- Baseline eval scorecard: `([^`]+\.json)`",
        manifest,
        re.M,
    )
    assert baseline_match is not None, (
        f"{manifest_path.name}: a failing candidate run requires a baseline "
        "scorecard at the deployed production SHA"
    )
    rollback_match = re.search(r"^- Rollback target: `([0-9a-f]{40})`", manifest, re.M)
    assert rollback_match is not None, (
        f"{manifest_path.name}: missing the deployed SHA the baseline must run at"
    )
    baseline_path = (repository_root / baseline_match.group(1)).resolve()
    assert baseline_path.is_file(), (
        f"{manifest_path.name}: baseline eval scorecard does not exist"
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    # A deployed build predating the provenance harness emits schema v1 and
    # cannot self-identify; bind provenance as soon as it can.
    if baseline.get("schema_version", 1) >= 2:
        baseline_provenance = baseline.get("provenance", {})
        baseline_sha = str(baseline_provenance.get("candidate_sha") or "")
        deployed_sha = rollback_match.group(1)
        # What must hold is that the baseline measured the deployed PRODUCT
        # code. Merging to main mints a new SHA, so string equality would fail
        # every promotion; identical product trees is the real invariant.
        assert baseline_sha == deployed_sha or _same_product_tree(
            baseline_sha, deployed_sha, repository_root=repository_root
        ), f"{manifest_path.name}: baseline did not measure the deployed build"
        assert baseline_provenance.get("evaluation_mode") == "live"
    else:
        assert rollback_match.group(1)[:8] in baseline_path.name, (
            f"{manifest_path.name}: a pre-provenance baseline must carry the "
            "deployed SHA in its filename"
        )

    baseline_failed = {
        result["id"]
        for result in baseline.get("results", [])
        if result.get("status") == "failed"
    }
    candidate_failed = {
        result["id"]
        for result in candidate_results
        if result.get("status") == "failed"
    }
    candidate_match = re.search(
        r"^- (?:Runtime )?Candidate SHA:\s*`([0-9a-f]{40})`", manifest, re.M
    )
    assert candidate_match is not None
    # A change that cannot reach the measured code cannot regress it. The suite
    # flips several cases per run on identical input, so counts are noise at
    # this resolution and this proof is the stronger one. Derived from the
    # harness's own imports, never a hand-written path list.
    untouched, _ = eval_measured_code_unchanged(
        rollback_match.group(1),
        candidate_match.group(1),
        repository_root=repository_root,
    )
    if untouched:
        return

    # Totals fluctuate on identical code and can both invent a regression and
    # hide one behind an offsetting flip. Case identity is the gate: every case
    # that passes deployed and fails here must be named and dispositioned.
    for case_id in sorted(candidate_failed - baseline_failed):
        assert case_id in manifest, (
            f"{manifest_path.name}: {case_id} passes on the deployed build and "
            "fails on the candidate. Name it in the manifest with its "
            "disposition, or do not promote."
        )
