"""Comparison of a promotion candidate against the deployed build.

A promotion asks whether the candidate is worse than what users have now.
Lives here rather than in the release-docs test so that test stays about
documents.
"""

from __future__ import annotations

import json
import re
import subprocess
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
    assert len(candidate_failed) <= len(baseline_failed), (
        f"{manifest_path.name}: the candidate fails more cases "
        f"({len(candidate_failed)}) than the deployed build "
        f"({len(baseline_failed)}). That is a regression."
    )

    # A favourable total can hide a regression behind an offsetting flip, so
    # every case that passes deployed and fails here is named, not absorbed.
    for case_id in sorted(candidate_failed - baseline_failed):
        assert case_id in manifest, (
            f"{manifest_path.name}: {case_id} passes on the deployed build and "
            "fails on the candidate. Name it in the manifest with its "
            "disposition, or do not promote."
        )
