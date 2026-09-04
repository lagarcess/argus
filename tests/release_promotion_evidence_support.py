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

# Ten paired rounds is what settled the 2026-08-21 and 2026-09-03 disputes.
_PROSE_AB_MINIMUM_ATTEMPTS = 10

# Shipped before this rule existed, and their trees are no longer deployed, so
# the measurement can never be taken. 2026-08-27 settled its prose failure with
# a judge-only replay: 13 of 13 passes on the recorded text. That establishes
# the grader was stable on that input, which is a different question from
# whether the candidate voiced it more often than production. The replay is why
# this rule exists, not evidence that satisfies it.
_MANIFESTS_PREDATING_PROSE_AB_RULE = frozenset(
    {
        "2026-08-27-main-production-promotion.md",
    }
)

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
    prose_failures = {
        result["id"]
        for result in candidate_results
        if result.get("status") == "failed"
        and isinstance(judge := result.get("prose_judge"), dict)
        and judge.get("pass") is False
    }
    for case_id in sorted(candidate_failed - baseline_failed):
        assert case_id in manifest, (
            f"{manifest_path.name}: {case_id} passes on the deployed build and "
            "fails on the candidate. Name it in the manifest with its "
            "disposition, or do not promote."
        )
        if (
            case_id in prose_failures
            and manifest_path.name not in _MANIFESTS_PREDATING_PROSE_AB_RULE
        ):
            assert_prose_failure_measured_on_both_sides(
                manifest,
                manifest_path,
                case_id=case_id,
                deployed_sha=rollback_match.group(1),
                candidate_sha=candidate_match.group(1),
                repository_root=repository_root,
            )


def assert_prose_failure_measured_on_both_sides(
    manifest: str,
    manifest_path: Path,
    *,
    case_id: str,
    deployed_sha: str,
    candidate_sha: str,
    repository_root: Path,
) -> None:
    """A prose regression is a rate on two sides, never one run's verdict.

    Voiced prose is stochastic, so a single suite run can hand back a
    candidate-only prose failure that no user would ever meet twice. Prose
    cannot be dispositioned by argument here: the manifest must carry a
    targeted interleaved A/B that measured the same case on the deployed build
    and on the candidate. Ten paired rounds cost about $0.20 against $1.33 and
    half an hour for a suite that still could not answer the question.

    Evidence is matched by content, never by filename: a side-labelled document
    naming this case, whose provenance measured the right tree.
    """

    sides: dict[str, dict[str, object]] = {}
    for relative in re.findall(r"`([^`]+\.json)`", manifest):
        path = (repository_root / relative).resolve()
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(document, dict) or document.get("case_id") != case_id:
            continue
        side = document.get("side")
        if side in {"baseline", "candidate"}:
            sides[str(side)] = document

    missing = {"baseline", "candidate"} - sides.keys()
    assert not missing, (
        f"{manifest_path.name}: {case_id} is a candidate-only PROSE failure, so "
        f"naming it is not a disposition. Missing the {', '.join(sorted(missing))} "
        "side of a targeted interleaved A/B. Measure the same case on both the "
        "deployed build and the candidate, reference both documents here, and "
        "record the two rates. Roughly ten minutes and $0.20."
    )

    expected_sha = {"baseline": deployed_sha, "candidate": candidate_sha}
    for side, document in sorted(sides.items()):
        measured_sha = str((document.get("provenance") or {}).get("candidate_sha") or "")
        assert measured_sha == expected_sha[side] or _same_product_tree(
            measured_sha, expected_sha[side], repository_root=repository_root
        ), (
            f"{manifest_path.name}: the {side} A/B for {case_id} measured "
            f"{measured_sha or '<unrecorded>'}, which is not the "
            f"{'deployed build' if side == 'baseline' else 'candidate'}."
        )

        measurement = document.get("measurement")
        assert isinstance(measurement, dict), (
            f"{manifest_path.name}: the {side} A/B for {case_id} records no "
            "measurement."
        )
        attempts = measurement.get("attempts")
        assert isinstance(attempts, int) and attempts >= _PROSE_AB_MINIMUM_ATTEMPTS, (
            f"{manifest_path.name}: the {side} A/B for {case_id} ran "
            f"{attempts!r} attempts. Fewer than {_PROSE_AB_MINIMUM_ATTEMPTS} "
            "cannot separate a regression from voicing noise."
        )
        counts = [
            value
            for key, value in measurement.items()
            if key.endswith("_count") and isinstance(value, int)
        ]
        assert counts, (
            f"{manifest_path.name}: the {side} A/B for {case_id} reports no "
            "occurrence count, so the two sides cannot be compared."
        )
